---
name: screenpipe-research
description: |
  Deep research into what the user did using Screenpipe data.
  Use when asked "what was I doing?", "what did I do on X?", "did I send something?",
  "was I about to do something?", "what happened on [app]?", or any reconstruction
  of past user activity. Also use proactively when another skill (nocta-execute,
  brain-dump, etc.) needs to understand recent user context before acting.
allowed-tools:
  - Bash
  - Read
---

## screenpipe-research

Reconstruct what the user did - completely. Not just what was on screen. What they
**clicked**, **typed**, **copied**, **pasted**, and were **about to do**.

Detect **workflows** - sequences of actions driven by a single intent - and infer
**why** the user was doing each one. The goal is not a flat event log. The goal
is: "you were doing X because Y, and you didn't finish Z."

**Never conclude from one data source. Never conclude from absence in one source.**

---

### CRITICAL RULES (non-negotiable)

#### Rule 1 - App identification

`ui_events.app_name` LIES. Screenpipe has a stale-app bug: when the user switches
apps, `ui_events` often keeps reporting the PREVIOUS app because no `app_switch`
event is emitted. This has caused wrong conclusions repeatedly.

**Mandatory verification - do this EVERY time:**

```sql
-- Step 1: What do ui_events CLAIM the app was?
SELECT DISTINCT app_name, window_title FROM ui_events
WHERE timestamp BETWEEN '<start>' AND '<end>';

-- Step 2: What do FRAMES (ground truth) say was focused?
SELECT app_name, window_name, focused, browser_url FROM frames
WHERE timestamp BETWEEN '<start>' AND '<end>' AND focused = 1
ORDER BY timestamp ASC;
```

**If they disagree: frames win. Period.** Do not rationalize the disagreement.
The frames are literal screenshots of what was on screen. The ui_events app
field is an OS-level label that goes stale. There is no scenario where
ui_events.app_name is right and frames.app_name is wrong.

When they disagree: use frames to determine WHICH APP, use ui_events to
determine WHAT ACTIONS within that app.

#### Rule 2 - Browser tab awareness

For browser apps (Chrome, Safari, Firefox, Arc, Edge), treat each **domain** as
a separate "app" for workflow grouping. Two Chrome tabs on different domains are
functionally different apps. Use `browser_url` from frames to distinguish them.

```
linkedin.com in Chrome tab 1  = "LinkedIn"
calendar.google.com in tab 2  = "Google Calendar"
github.com in tab 3           = "GitHub"
```

All three are "Google Chrome" in `app_name`. That tells you nothing.
The domain tells you everything.

#### Rule 3 - Cast wide, then narrow

Never pre-filter by app or URL. The action is often in a window whose title
doesn't match the keyword you'd expect. Query by time window first, let the
data show you where the action happened.

---

### Question routing

| User asks | Route |
|-----------|-------|
| "What was I doing?" / "What did I work on?" | Phase 1 → 2 → 3 |
| "Find my workflows" / "What patterns?" | Phase 1 → 2 → 3 |
| "Did I send X?" / "Did I complete X?" | Phase 1 → 4 (skip workflow detection) |
| "Summarize my meeting" | API: `/search?content_type=audio` |
| "How long on X?" / "Which apps?" | API: `/activity-summary` |
| "Was I about to do something?" | Phase 1 → 2 → 3 (check incomplete workflows) |

---

### Phase 1 - Activity skeleton

Build the full picture of what happened, fast. Two steps.

#### Step 0 - API quick check (if available)

```bash
curl -s -H "Authorization: Bearer $SCREENPIPE_LOCAL_API_KEY" \
  "http://localhost:3030/activity-summary?start_time=<range>&end_time=now" \
  -o /tmp/sp_summary.json && wc -c /tmp/sp_summary.json
```

If API is down (connection refused on 3030), skip straight to Step 1.

**Context window protection:** Always write API responses to file first, check
size with `wc -c`, read only first 50-100 lines if over 5KB. Extract with `jq`.

#### Step 1 - Build the transition graph (this is the key step)

One query that gives you the full workflow skeleton:

```sql
SELECT timestamp, app_name, browser_url, window_name
FROM frames
WHERE focused = 1
  AND timestamp BETWEEN '<start_utc>' AND '<end_utc>'
ORDER BY timestamp ASC;
```

**DB path:** `~/.screenpipe/db.sqlite`
**Timestamps are UTC** - adjust for user's timezone (PDT = UTC-7).

Write results to file, then extract the transition sequence:
- Group consecutive frames on the same domain (for browsers) or app (for native apps)
- Note the duration on each domain/app
- Note the order of transitions

This gives you the skeleton: `Event site → Calendar → LinkedIn → [43 min gap] → Google search → Landing page → ...`

**Do NOT drill into individual events yet.** Get the shape first.

#### Step 1b - Extract search terms from URLs

Search queries are the highest-signal workflow labels. Extract them:

```sql
SELECT timestamp, browser_url,
  SUBSTR(browser_url, INSTR(browser_url, 'q=') + 2,
    CASE
      WHEN INSTR(SUBSTR(browser_url, INSTR(browser_url, 'q=') + 2), '&') > 0
        THEN INSTR(SUBSTR(browser_url, INSTR(browser_url, 'q=') + 2), '&') - 1
      ELSE LENGTH(browser_url)
    END
  ) as search_term
FROM frames
WHERE focused = 1
  AND browser_url LIKE '%?q=%' OR browser_url LIKE '%&q=%'
  AND timestamp BETWEEN '<start_utc>' AND '<end_utc>'
ORDER BY timestamp;
```

URL-decode the result (replace `+` with space, `%20` with space, etc.).
These search terms become workflow names: "researching [search term]".

**Prefer URL params over raw keystrokes.** URL params are clean, structured,
and not affected by AZERTY keyboard layout. Raw `ui_events.text_content` from
AZERTY keyboards requires decoding (q->a, z->w, ;->m, etc.) and is error-prone.

---

### Phase 2 - Workflow detection

Split the transition graph from Phase 1 into distinct workflows.

#### Step 1 - Boundary detection

Apply these rules in order:

**Boundaries (these SPLIT workflows):**
- Temporal gap > 5 min with app/domain change = new workflow
- Navigation to a feed page (LinkedIn feed, Twitter feed, email inbox) = boundary
- Opening a new tab (`chrome://newtab`, blank page) = boundary
- Explicit app switch to an unrelated app after > 2 min = boundary

**Connectors (these DO NOT split workflows):**
- Search engine return (Google, Bing, DuckDuckGo) = transit point, NOT a boundary.
  Going back to Google to search the next thing is continuing a research session.
- Cross-domain navigation within 60s without hitting a feed/new-tab = same workflow.
  Example: cerebralvalley.ai → lu.ma → calendar.google.com = one workflow.
- Same domain, sequential pages = same workflow (URL progression)
- App A → App B → App A return within 10 min = B was a sub-task of A
- Two apps alternating 3+ times in 5 min = one dual-window workflow

**Ambiguous (use content to decide):**
- 1-5 min gap with domain change: check if content is related (same topic in
  window titles or search terms). If related, same workflow. If not, new workflow.

#### Step 2 - Background check detection

Some domains appear repeatedly across workflows but aren't workflows themselves.
Detect them:

- Same domain appears 3+ times across different workflow segments
- Each visit is < 30 seconds
- No meaningful actions (no text typed, no forms filled)

Label these as **background checks**, not workflows. Common examples:
LinkedIn Grow page, email inbox glances, Slack quick-checks.

#### Step 3 - Group and label

For each workflow segment, assign a preliminary label from:
- The search term that started it ("researching [term]")
- The anchor domain ("browsing [domain]")
- The action type ("composing email", "editing document")

---

### Phase 3 - Intent inference

For each workflow detected in Phase 2, figure out WHY the user was doing it.

#### Step 1 - Extract signals per workflow

For each workflow, gather:

```sql
-- A) Page topics from window titles
SELECT DISTINCT window_name FROM frames
WHERE focused = 1 AND timestamp BETWEEN '<wf_start>' AND '<wf_end>'
AND app_name = '<browser_app>';

-- B) Behavioral trails from ui_events
SELECT timestamp, event_type, element_name, SUBSTR(text_content, 1, 100),
       window_title
FROM ui_events
WHERE timestamp BETWEEN '<wf_start>' AND '<wf_end>'
  AND event_type IN ('text', 'click', 'clipboard', 'key')
ORDER BY timestamp;

-- C) Accessibility text sample (what was ON the page)
SELECT timestamp, SUBSTR(accessibility_text, 1, 500)
FROM frames
WHERE focused = 1 AND timestamp BETWEEN '<wf_start>' AND '<wf_end>'
ORDER BY timestamp ASC LIMIT 1;  -- start of workflow

SELECT timestamp, SUBSTR(accessibility_text, 1, 500)
FROM frames
WHERE focused = 1 AND timestamp BETWEEN '<wf_start>' AND '<wf_end>'
ORDER BY timestamp DESC LIMIT 1;  -- end of workflow
```

#### Step 2 - Classify intent

Use the combined signals to classify:

| Pattern | Intent |
|---------|--------|
| Search + multiple landing pages (different domains) | Competitive research / comparison |
| Event page + profiles + calendar | Networking prep for event |
| Single site, long duration (> 5 min), minimal clicks | Deep reading / learning |
| Compose + send confirmation in accessibility_text | Communication (completed) |
| Compose + no send, or compose + Discard click | Abandoned draft - **latent task** |
| Profile visits + Connect/Message buttons in a11y | Outreach |
| GitHub repo + docs/blog pages | Technical research |
| Calendar + search + calendar (A→B→A) | Planning logistics |
| Code editor + browser docs (alternating) | Development / debugging |
| Own profile + own posts + notifications | Checking engagement |
| Product page + pricing page | Evaluating a tool/service |
| Feed scrolling, no searches, no specific clicks | Passive browsing (not a workflow) |

**When no pattern matches:** label as "browsing / context switching."
Honest labeling beats hallucinated intent.

#### Step 3 - Check workflow completion

For each workflow, determine status:

- **Completed**: natural end reached (page closed, moved to next task, confirmation toast)
- **In progress**: user is still mid-workflow (session ongoing)
- **Abandoned**: user switched away mid-action (compose without send, form half-filled,
  search without clicking results)
- **Interrupted**: external interruption (notification click, phone call, app switch
  to unrelated app mid-task)

Abandoned and interrupted workflows are **latent tasks** - flag them.

For uncertain completion, use behavioral inference:
- Heavy compose + no Discard + navigate to next target = **likely completed**
- Text typed + Discard button clicked = **deliberately abandoned**
- Text typed + window switch, no submit = **abandoned mid-compose**

---

### Phase 4 - Deep verification (use only when needed)

This phase contains the battle-tested forensic techniques. Use it when:
- Verifying if a specific action completed ("did I send that message?")
- Workflow completion status is uncertain
- User explicitly asks about a specific action

**Do NOT run these queries by default for every workflow.** They are expensive
and most workflows don't need forensic verification.

#### Platform confirmation patterns

Search `frames.accessibility_text` for the platform's own confirmation UI:

```sql
SELECT f.id, f.timestamp, f.window_name,
       SUBSTR(f.accessibility_text,
              INSTR(f.accessibility_text, '<confirmation text>'), 200)
FROM frames f
WHERE f.accessibility_text LIKE '%<confirmation text>%'
ORDER BY f.timestamp ASC;
```

**Ground truth first methodology:** Find ONE confirmed case of the action
completing. Study what it looks like across ALL tables. Build a detection
pattern from that. Then apply to uncertain cases.

Known confirmation patterns:
- LinkedIn: `"invitation to connect was sent"`, `"1 Message"` count, `"Options for the message from Nossa"`
- Gmail: `"Message envoye"` / `"Message sent"` toast
- WhatsApp: `"Sent to [Name], Delivered"` label

#### Coordinate resolution for unlabeled clicks

~98% of `AXGroup` clicks have no `element_name`. Resolve via coordinate bounds:

```sql
-- Find frame closest to click time
SELECT id, elements_ref_frame_id FROM frames
WHERE timestamp BETWEEN datetime('<T>', '-1 second') AND datetime('<T>', '+1 second')
ORDER BY ABS(julianday(timestamp) - julianday('<T>')) LIMIT 1;

-- Find element at (x, y) - normalize: x_norm = x/screen_width, y_norm = y/screen_height
SELECT role, text, left_bound, top_bound, width_bound, height_bound
FROM elements
WHERE frame_id = <ref_frame_id>
  AND left_bound <= <x_norm> AND (left_bound + width_bound) >= <x_norm>
  AND top_bound <= <y_norm> AND (top_bound + height_bound) >= <y_norm>
  AND text IS NOT NULL AND text != ''
ORDER BY (width_bound * height_bound) ASC LIMIT 5;
```

#### Intent signals around a moment

```sql
SELECT timestamp, event_type, text_content, element_name, window_title
FROM ui_events
WHERE timestamp BETWEEN datetime('<T>', '-10 seconds') AND datetime('<T>', '+10 seconds')
  AND event_type IN ('text', 'key', 'clipboard')
ORDER BY timestamp;
```

| Signal sequence | Intent |
|----------------|--------|
| `text` then `AXButton: Submit/Send/Post` | Sent |
| `text` then `AXButton: Discard/Cancel` | Abandoned - **latent task** |
| `text` then no submit, window switch | Abandoned mid-compose - **latent task** |
| Heavy compose then no Discard then navigate to next target | **Likely completed** |
| `AXButton: Copy` then app switch then `clipboard` | Copied to use elsewhere |
| `app_switch` mid-task | Interrupted - note what was interrupted |

#### State change tracking

Compare the same page at different timestamps to detect transitions:

```sql
SELECT f.timestamp, f.window_name,
       CASE
         WHEN f.accessibility_text LIKE '%Connect%' THEN 'NOT_CONNECTED'
         WHEN f.accessibility_text LIKE '%Message [Name]%' THEN 'CONNECTED'
         WHEN f.accessibility_text LIKE '%1 Message%' THEN 'MSG_SENT'
       END as status
FROM frames f
WHERE f.window_name LIKE '%[target]%'
ORDER BY f.timestamp ASC;
```

#### FTS search (when timestamp is unknown)

```sql
SELECT f.id, f.timestamp, f.app_name, f.window_name
FROM frames f JOIN frames_fts fts ON fts.rowid = f.id
WHERE frames_fts MATCH '<keyword>' ORDER BY fts.rank;
```

Also available: `ui_events_fts`, `elements_fts` for searching across all tables.

---

### Investigation methodology - go deeper every time

1. **Don't conclude from one source.** API found nothing? Check SQLite. `ui_events`
   empty? Check `frames.accessibility_text`. Still nothing? Check `elements` via
   coordinates. Check `full_text` (OCR). Check FTS indexes.

2. **Ground truth first.** When verifying if action X happened, find ONE confirmed
   case. Study what it looks like across ALL data sources. Build detection templates.
   Apply to uncertain cases.

3. **Search for the platform's output, not the user's input.** The user's click may
   be unlabeled. The platform's confirmation toast/dialog is always captured in
   `frames.accessibility_text`.

4. **Track state over time.** Before/after frame comparison reveals transitions
   that single-point queries miss.

5. **Build inference chains when signals are missing.** Heavy compose + no Discard +
   navigate away = likely completed. Not definitive, but much better than "not found."

6. **Challenge every "not found" before reporting.** Checklist:
   - Did I check `frames.accessibility_text` for platform confirmations?
   - Did I check a wider time window? (action may have happened later)
   - Did I check for behavioral completion patterns?
   - Did I look for a confirmed case to calibrate against?
   - Did I try FTS search across frames, ui_events, and elements?

---

### Output format

**Always produce workflow-structured output.** Not a flat timeline.

```
## Workflow 1: Networking prep for Agent Skills Hack Day
Intent: Discover upcoming event, check details, update calendar
Confidence: High (cross-domain chain within 60s: event site -> details -> calendar)

Steps:
  5:00 PM  Browsed Cerebral Valley events page
  5:00 PM  Clicked into "The Super Solo: Agent Skills Hack Day" on Luma
  5:00 PM  Switched to Google Calendar, viewed this week
  5:00 PM  Opened and edited a calendar event
  5:01 PM  Checked Stephane Paquet's LinkedIn profile
Status: Completed

## Workflow 2: Competitor research (lightfield, hotdata)
Intent: Evaluate competing products in the AI/data space
Confidence: High (search -> landing page pattern, two targets in sequence)

Steps:
  5:45 PM  Google search: "lightfield"
  5:45 PM  Read lightfield.app (AI-native CRM) for ~4 min
  5:46 PM  Quick Gmail inbox check (background)
  5:49 PM  Google search: "hotdata"
  5:49 PM  Read hotdata.dev for ~3 min
Status: Completed

## Background checks (not workflows):
  LinkedIn Grow page - appeared 4 times, <10s each visit
  Gmail inbox - 1 glance, 1 second

## Latent tasks:
  None detected
```

**Per-conclusion confidence:**

| Signals | Confidence |
|---------|-----------|
| Platform confirmation UI (toast/dialog) | High |
| elements hit + before/after state change | High |
| Cross-domain chain with temporal proximity | High |
| Behavioral inference (compose + no discard + navigate) | Medium |
| Zone heuristic + URL + window change | Medium |
| Raw (x,y) + window title only | Speculative |

---

### Anti-patterns (never do these)

- Do not query one source, find nothing, conclude "nothing happened"
- Do not filter by app/URL before casting wide
- Do not search for the user's "Send" click instead of the platform's confirmation
- Do not report "not sent" without checking `frames.accessibility_text`
- Do not ignore `clipboard` and `key` events
- Do not stop at "they opened the page" - always check what they did *on* the page
- Do not assume AZERTY = QWERTY - Screenpipe captures raw key positions: q->a, a->q, z->w, w->z, ;->m, m->,. Prefer URL params and window titles over raw keystrokes.
- Do not trust ui_events.app_name over frames - frames.app_name with focused=1 is ground truth
- Do not dump large API responses directly into context - write to file first
- Do not treat search engine returns as workflow boundaries - Google is a transit point, not a destination
- Do not treat Chrome as one app - use browser_url domain as the identifier
- Do not run forensic queries (Phase 4) before building the workflow skeleton (Phase 1-2)
- Do not query `/memories` endpoint - table has 0 rows, it's a dead end
- Do not produce flat timelines as output - always structure by workflow

---

### Reference

Lessons learned (read these if investigation stalls):
- `docs/screenpipe-use/linkedin-message-detection.md` - ground-truth-first methodology, go deeper every time
- `docs/screenpipe-use/cast-wide-then-narrow.md` - don't filter to match your assumption
- `docs/screenpipe-use/ocr-and-ui-events.md` - OCR misses short visits, always check ui_events too
- `docs/screenpipe-use/intent-signals.md` - Copy/Discard/Cancel are high-signal intent markers

Full data source map + SQL templates:
- `docs/screenpipe-use/inference-strategy.md`

Coordinate zone heuristics (fallback when element bounds miss):

| x_norm | y_norm | Zone |
|--------|--------|------|
| any | < 0.08 | OS menubar |
| any | 0.04-0.07 | Browser chrome (tabs, address bar) |
| any | 0.07-0.18 | App/page navbar |
| < 0.15 | any | Left sidebar |
| > 0.85 | any | Right sidebar |
| 0.15-0.85 | 0.18-0.9 | Main content area |
| any | > 0.9 | Footer/status bar |
