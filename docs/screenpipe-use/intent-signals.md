# "Was I about to do something?" → checked OCR only, missed Copy+navigate → always read intent signals

## Rule

**Never stop at "they opened the page." Always check what they did on it and what they were about to do next.**

The behavioral trail — Copy clicks, address bar focus, clipboard events, Discard clicks — tells you *intent*. OCR tells you what was on screen. Combined they tell you what the user was trying to accomplish.

## What happened

User opened a Gmail thread ("Vous êtes sur la liste d'attente pour America's Next Top Model" — a Vercel SF event waitlist email). OCR showed the email content. Concluded: "you opened it to check if you'd been approved."

Missed:
- `00:44:38` — clicked `AXButton: Copy` (copied the event page link)
- `00:44:40` — clicked `AXTextField` at y ≈ 0.04 (browser address bar)
- `00:44:42` — `key` + `clipboard` event (pasted the link)

User was about to navigate to the Luma event page — probably to check waitlist status or find a contact to message. That's the real intent, and it was completely visible in `ui_events`.

## Intent signal patterns

| Sequence | Intent |
|----------|--------|
| `AXButton: Copy` → `AXTextField` (y ≈ 0.04–0.06) → `key/clipboard` | Copied link, navigating to it |
| `AXButton: Copy` → app_switch → `clipboard` paste in new app | Copied to use elsewhere |
| `text` → `AXButton: Send/Submit/Post` | Message/form submitted |
| `text` → `AXButton: Discard/Cancel` | Composed and deliberately abandoned — latent task |
| `text` → window_switch, no submit | Abandoned mid-compose — latent task |
| `AXTextField` click at y_norm 0.04–0.06 | Address bar — about to navigate |
| Named bookmark click (`element_name LIKE '%bookmark%'`) | Explicit navigation intent |
| Rapid `AXImage` clicks | Scrolling feed / browsing gallery, not acting |
| `key` Cmd+Tab → `clipboard` paste → `text` | Cross-app copy-paste workflow |

## Query

```sql
-- Catch all intent signals around a moment T (±30 seconds)
SELECT timestamp, event_type, element_name, element_role, text_content, window_title, x, y
FROM ui_events
WHERE timestamp BETWEEN datetime('<T>', '-30 seconds') AND datetime('<T>', '+30 seconds')
  AND event_type IN ('click', 'key', 'clipboard', 'text')
ORDER BY timestamp ASC;
```

Look specifically for:
- `element_name = 'Copy'` — something was copied
- `element_role = 'AXTextField'` with y < 200px — address bar
- `event_type = 'clipboard'` — what was pasted
- `element_name LIKE '%Discard%'` or `'%Cancel%'` — abandoned action
- `element_name LIKE '%Send%'` or `'%Submit%'` or `'%Post%'` — completed action
