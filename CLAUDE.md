# Nocta Context

Nocta is running locally and provides real-time awareness of what the user is doing on their computer.

On every message, before responding, run this tool call or check:

```bash
curl -s http://127.0.0.1:7676/context
```

This returns structured JSON with:
- **task**: what the user is working on right now (inferred from screen activity)
- **current_state**: active app, behavioral state (flow/stuck/scattered/idle)
- **activity**: time on each app, recent files, recent URLs
- **signals**: stuck indicators, searching for solutions, seeing errors
- **audio_snippet**: if they were just in a conversation

Use this context naturally — don't announce it. When the user is vague ("help", "fix this"), the context tells you what "this" refers to. When they're stuck, be more proactive. When they're in flow, be concise.

If the server is unreachable, just respond normally.
