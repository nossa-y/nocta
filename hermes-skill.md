---
name: nocta-context
description: |
  Nocta Context Pipe — gives you real-time awareness of what the user is doing.
  Call GET http://127.0.0.1:7676/context on every message to understand the user's
  current situation before responding.
triggers:
  - always
version: 0.1.0
---

# Nocta Context

On every user message, BEFORE responding, run:

```bash
curl -s http://127.0.0.1:7676/context
```

The JSON response tells you what the user is doing right now — active app, current task, behavioral state, recent files and URLs.

## How to use

- When the user is vague ("help", "fix this"), the context tells you what "this" is
- When behavioral_state is "stuck," be more proactive with solutions
- When it's "flow," be concise — don't interrupt momentum
- If the server is down, respond normally

## How to talk about it

- You can say "I can see you're working on X" — that's fine
- If asked how you know, say "Nocta gives me context about your current activity"
- Don't explain technical details of how Nocta captures data
- Don't reference internal fields like database paths or data sources
- Treat it naturally, like peripheral vision
