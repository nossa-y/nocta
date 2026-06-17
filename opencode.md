# Nocta Context

Nocta is running locally and provides real-time awareness of what the user is doing on their computer.

On every message, before responding, run:

```bash
curl -s http://127.0.0.1:7676/context
```

This returns structured JSON with:
- **task**: what the user is working on right now (inferred from screen activity)
- **current_state**: active app, behavioral state (flow/stuck/scattered/idle)
- **activity**: time on each app, recent files, recent URLs
- **signals**: stuck indicators, searching for solutions, seeing errors

Use this context naturally — don't announce it. When the user is vague ("help", "fix this"), the context tells you what "this" refers to.

If the server is unreachable, just respond normally.
