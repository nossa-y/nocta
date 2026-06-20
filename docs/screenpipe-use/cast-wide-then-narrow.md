# "What did I send on Reddit?" → filtered by URL, missed the message → cast wide first, let the data tell you where the action happened

## Rule

**Don't filter the search to match your assumption about where the data is. Cast wide, then narrow.**

When you already have a mental model of what something looks like — a Reddit message lives on a Reddit URL, a LinkedIn reply lives on a LinkedIn window — you design the query to confirm that model. That's what misses the data.

Start with the broadest possible query (time window only). Let the data tell you which app, which window, which URL the action happened on. Then zoom in.

Concretely: when searching for what a user typed, never pre-filter by app or URL. Filter by time, read everything, find the action.

```sql
-- wrong: assumes the message was typed while on a Reddit window
SELECT * FROM ui_events
WHERE event_type = 'text'
  AND lower(window_title) LIKE '%reddit%'

-- right: cast wide, let the data show you where it happened
SELECT timestamp, event_type, text_content, window_title
FROM ui_events
WHERE event_type IN ('text', 'key')
  AND timestamp BETWEEN '2026-05-11T04:10:00' AND '2026-05-11T04:20:00'
ORDER BY timestamp
```

## What happened

Asked to find a Reddit message the user had sent. Searched `ui_events` filtered by Reddit window titles — found nothing relevant. Concluded the data wasn't there.

User said "keep looking." Second pass: queried all `text` events in a 10-minute time window with no app or URL filter. The message appeared immediately — typed in a window titled *"Found a satisfying way to preserve my dad's art : r/SideProject"*, which didn't contain the word "reddit" and didn't match the original filter.

The full message, reconstructed from fragments: **"sorry, i'm not interested"** — a comment reply to someone pitching their product on a r/SideProject post.

The data was always there. The assumption about where it would be is what hid it.
