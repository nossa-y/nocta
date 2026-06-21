# screenpipe-use

Lessons learned from working with the Screenpipe API and SQLite database.

Each file documents a real encounter — a question asked, a mistake made, and the correct behavior going forward.

Two kinds of lessons live here:

- **Mindset rules** — broad ways of thinking that apply across any Screenpipe query. Start here when something feels off.
- **Specific rules** — concrete patterns tied to a particular table, event type, or API behaviour.

Specific rules are usually symptoms of a mindset rule being violated. When adding a new lesson, ask: is there a deeper thinking failure behind this? If yes, write the mindset rule first, use the specific case as the example.

---

## File naming

Use a short slug describing the thinking failure or pattern: `cast-wide-then-narrow.md`, `ocr-and-ui-events.md`, etc.

---

## Document format

```md
# "[request]" → [what went wrong] → [correct behavior]

## Rule

The correct behavior going forward. One clear principle — written at the right level of abstraction (mindset or specific).

[code example if relevant]

## What happened

Short narrative. What was asked, what was queried, what was missed or wrong, what the data actually showed.
```

---

## Lessons

| File | Type | Rule |
|------|------|------|
| `inference-strategy.md` | **Reference** | Full source map + inference algorithm. Start here. All tables, coverage, coordinate resolution, confidence levels. |
| `cast-wide-then-narrow.md` | Mindset | Don't filter to match your assumption. Cast wide, let the data tell you where the action happened, then zoom in. |
| `ocr-and-ui-events.md` | Specific | OCR misses short visits. Always query `frames` + `ui_events` together. |
| `intent-signals.md` | Specific | Copy → address bar → paste = about to navigate. Discard = abandoned draft. Never stop at "they opened the page". |
| `linkedin-message-detection.md` | **Mindset** | To verify an action completed, don't search for the user's click — search for the platform's confirmation UI in `frames.accessibility_text`. Find one confirmed case first, study it across ALL tables, build a detection pattern, then apply everywhere. Never report "not done" until every data source is exhausted. |
