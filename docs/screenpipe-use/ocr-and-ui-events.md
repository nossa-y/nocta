# "Any LinkedIn activity?" → searched OCR only, missed it → always query `frames` + `ui_events` together

## What happened

Searched `frames` (OCR) for LinkedIn activity. Got nothing. Concluded the user hadn't visited LinkedIn.

User had visited LinkedIn, started typing a reply, hit Discard, and left — all within a few seconds.

`ui_events` had the full story: window title, typed text (`tq` → `hqnks` = "thanks"), and an `AXButton: Discard` click. Zero frames were captured because the visit was shorter than Screenpipe's ~2fps capture interval.

## Rule

Always query both tables in parallel:

- `frames.full_text` — what was visible on screen (OCR)
- `ui_events` — what the user actually did (clicks, typed text, app switches)

```sql
-- catches short visits that OCR misses
SELECT timestamp, event_type, text_content, element_name, window_title
FROM ui_events
WHERE lower(window_title) LIKE '%linkedin%'
ORDER BY timestamp;
```

## Latent task signal: `text` + `Discard`

A `text` event followed by `AXButton: Discard` in the same window = user started composing something and abandoned it. High-confidence latent task for Nocta.
