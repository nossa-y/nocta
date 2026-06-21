# Screenpipe inference strategy — all sources, how to combine them

## The core problem

Many ui_events clicks come in unlabeled: `element_role = AXGroup`, `element_name = ''`. Naively this looks like missing data. It isn't. Every click can be fully resolved by combining the available signals. This document describes every signal, its coverage, and the exact join strategy.

---

## All data sources

### 1. `ui_events` — what the user did (10k+ rows, complete coverage)

The most reliable table. Every click, keystroke, paste, and app switch is here.

| event_type | key fields |
|------------|-----------|
| `click` | `x`, `y` (absolute pixels), `element_role`, `element_name`, `browser_url`, `window_title` |
| `text` | `text_content` (what was typed), `window_title` |
| `key` | `key_code`, `modifiers` |
| `clipboard` | `text_content` (what was pasted) |
| `app_switch` | `app_name`, `window_title` |

**Limitation:** `element_name` is empty on ~98% of AXGroup clicks and ~57% of AXImage clicks. Raw mouse-hook events (no `element_role`) appear as a duplicate of every click — ignore rows where `element_role = ''`.

---

### 2. `frames` — screen state at capture time (1928 rows)

Each row is a snapshot of what was on screen. Key fields:

| Field | What it gives you |
|-------|------------------|
| `timestamp` | When the frame was captured |
| `app_name`, `window_name`, `browser_url` | Context |
| `capture_trigger` | **Why** the frame was captured (see below) |
| `accessibility_text` | Full readable text of the screen, newline-separated — fast to scan |
| `accessibility_tree_json` | Full JSON tree with role, text, depth, normalized bounds, properties |
| `elements_ref_frame_id` | Points to which frame's elements to use (see frame pair pattern) |
| `snapshot_path` | Actual screenshot image — last resort, or for visual confirmation |
| `simhash` | Near-duplicate detection (1824 frames, 1312 unique screen states) |

**Capture triggers:**

| Trigger | Count | When |
|---------|-------|------|
| `visual_change` | 879 | Screen content changed |
| `click` | 643 | User clicked something |
| `idle` | 257 | User was idle |
| `app_switch` | 147 | Switched app/window |

Click-triggered frames are the richest: they were captured specifically because a user action happened.

**Frame pair pattern:**
Screenpipe captures in pairs. Odd frame = primary snapshot with elements. Even frame = diff frame pointing back via `elements_ref_frame_id`. When resolving a click:
- Use `elements_ref_frame_id` if present, else use the frame's own id.

---

### 3. `elements` — full accessibility tree (189k rows, ~99% labeled)

This is the unlock for unlabeled clicks. For every captured frame, the full macOS accessibility tree is stored as rows — one row per element. 187,579 of 189,989 rows have text.

| Field | What it gives you |
|-------|------------------|
| `frame_id` | Links to `frames.id` (or `frames.elements_ref_frame_id`) |
| `role` | AXButton, AXLink, AXStaticText, AXTextArea, etc. |
| `text` | The element's label — "Open chat", "Submit", "u/Ambitious-Age-5676" |
| `left_bound`, `top_bound`, `width_bound`, `height_bound` | Normalized 0–1 relative to screen size |
| `properties` | JSON: `is_enabled`, `is_focused`, `is_selected`, `is_expanded`, `role_description` |
| `depth`, `parent_id` | Tree structure — allows walking up to find a labeled ancestor |

**This resolves any unlabeled click.** If you have (x, y) and the frame's elements_ref, you can find exactly which element was clicked by matching bounds.

Top roles by count:
- `AXStaticText` 69k — visible text labels
- `block` 58k — Screenpipe-internal content blocks
- `AXButton` 25k — buttons (almost always labeled)
- `AXRadioButton` 15k, `AXLink` 11k

---

### 4. `ocr_text` — pixel-level OCR (399 rows, ~20% of frames)

Sparse — only present when `text_source = 'ocr'` or `'hybrid'`. Most frames now use `text_source = 'accessibility'`, making this table largely redundant. 

**When it's useful:** For apps that don't expose accessibility trees (games, some Electron apps, PDFs). Contains word-level bounding boxes in `text_json`.

For most purposes, prefer `frames.accessibility_text` over OCR — it's present on 1529 frames vs 399.

---

### 5. `memories` — semantic blocks (0 rows currently, was active)

Auto-extracted high-level summaries. When populated: `content`, `source_context`, `importance` score (0–1), `tags`. Fast for finding what *happened* (high-level) rather than exact mechanics. Currently empty — Screenpipe populates this asynchronously and may reset.

---

### 6. `audio_transcriptions` — microphone (2 rows, disabled)

Disabled via `--disable-audio`. When active: Whisper transcription, speaker diarization (`speaker_id`), device type (`is_input_device`). Not useful for current setup.

---

### 7. `meetings`, `vision_tags`, `tags` — future (0 rows each)

Not yet populated. `meetings` would auto-detect Zoom/Meet sessions. `vision_tags` would add AI image labels.

---

## The inference algorithm

### For any unlabeled click at (x, y) at timestamp T:

**Step 1 — Get the frame**
```sql
-- Find the frame closest to the click, capture_trigger = 'click' preferred
SELECT id, timestamp, app_name, window_name, browser_url,
       accessibility_text, elements_ref_frame_id
FROM frames
WHERE timestamp BETWEEN datetime(T, '-1 second') AND datetime(T, '+1 second')
ORDER BY ABS(julianday(timestamp) - julianday(T))
LIMIT 1;
```

**Step 2 — Resolve the element by coordinates**
```sql
-- Normalize: x_norm = x / screen_width, y_norm = y / screen_height
-- Screen width/height: infer from the largest element bounds (usually close to 1.0)
-- Or assume 1920x1080, 2560x1440, etc. — adjust if bounds don't match

SELECT role, text, left_bound, top_bound, width_bound, height_bound, properties
FROM elements
WHERE frame_id = <elements_ref_frame_id or frame_id>
  AND left_bound <= <x_norm>
  AND (left_bound + width_bound) >= <x_norm>
  AND top_bound <= <y_norm>
  AND (top_bound + height_bound) >= <y_norm>
  AND text IS NOT NULL AND text != ''
ORDER BY (width_bound * height_bound) ASC  -- smallest = most specific hit
LIMIT 5;
```

**Step 3 — Before/after events for intent**
```sql
SELECT timestamp, event_type, element_name, window_title, text_content
FROM ui_events
WHERE timestamp BETWEEN datetime(T, '-3 seconds') AND datetime(T, '+5 seconds')
ORDER BY timestamp;
```

**Step 4 — Read the screen**
```sql
-- Full text of what was on screen at that moment
SELECT accessibility_text FROM frames WHERE id = <frame_id>;
```

---

## Coordinate zone heuristics (fallback when elements don't cover the click)

When elements bounds don't contain the click (can happen with custom renderers):

| x_norm | y_norm | Zone |
|--------|--------|------|
| any | < 0.08 | OS menubar |
| any | 0.04–0.07 | Browser chrome (tabs, address bar) |
| any | 0.07–0.18 | App/page navbar |
| < 0.15 | any | Left sidebar |
| > 0.85 | any | Right sidebar or overflow |
| 0.15–0.85 | 0.18–0.9 | Main content area |
| any | > 0.9 | Footer / status bar |

Combined with `browser_url` this is usually enough:
- Reddit + (x > 0.85, y ≈ 0.15) → navbar icon (chat, inbox, notifications)
- Gmail + (x < 0.25, y ≈ 0.3–0.7) → label/folder list
- Notion + (x < 0.20) → page sidebar

---

## Inference confidence levels

| Signals available | Confidence | Action |
|------------------|-----------|--------|
| elements hit + before/after event confirms | **High** | Use as fact |
| elements hit, no corroborating event | **Medium** | Use with note |
| Zone heuristic + URL + window change confirms | **Medium** | Use with note |
| Zone heuristic only | **Low** | Use as hypothesis |
| Only raw (x, y) + window title | **Speculative** | Flag for review |

---

## FTS tables — full-text search across all sources

Every major table has a paired FTS index:

```sql
-- Search all screen text for a keyword
SELECT rowid, rank FROM frames_fts WHERE frames_fts MATCH 'checkout' ORDER BY rank;

-- Search all ui_events for what was typed
SELECT rowid, rank FROM ui_events_fts WHERE ui_events_fts MATCH 'sorry' ORDER BY rank;

-- Search elements for any label
SELECT rowid, rank FROM elements_fts WHERE elements_fts MATCH '"Open chat"' ORDER BY rank;
```

Use FTS when you don't know the timestamp — search by content first, then get the timestamp from the matched row.

---

## Synthesis rules for Nocta

1. **Never conclude "nothing happened" from one table.** Always check at minimum: `frames` + `ui_events` + `elements`.

2. **Unlabeled click ≠ unknowable click.** Join to `elements` via coordinate bounds first. Fall back to zone heuristic. Use before/after events to confirm intent.

3. **Window title change after click = intent confirmed.** The outcome is often more reliable than the element label.

4. **Cast wide, then narrow.** Query a 10-minute time window with no app/URL filter. Let the data show you where the action happened. Then zoom in. (See `cast-wide-then-narrow.md`)

5. **Prefer `accessibility_text` over OCR.** 1529 frames have it vs 399 with OCR. It's also structured (newline-separated elements, not noisy pixel text).

6. **For latent task detection:** `text` event + no submit event = abandoned draft. `text` + `AXButton: Discard` = explicitly abandoned. Both are high-signal latent tasks.

7. **`capture_trigger = 'click'` frames are the richest.** Prioritize these when reconstructing a session — they were taken specifically because the user acted.
