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

## What it does

Nocta watches the user's screen activity and provides structured context about what they're doing right now. Call it before every response.

## How to use

Run this on every user message:

```bash
curl -s http://127.0.0.1:7676/context
```

The response tells you:
- **task**: what they're working on ("Debugging — errors in auth.py")
- **current_state**: active app, behavioral state (flow/stuck/scattered)
- **activity**: time on each app, recent files, recent URLs
- **signals**: stuck indicators, searching for solutions, seeing errors
- **audio_snippet**: if they were just in a conversation

## Guidelines

- If the server is down, respond normally (don't error)
- Use the context naturally — don't announce "I see you're on LinkedIn"
- When the user is vague ("help", "fix this"), the context tells you what "this" is
- When they're stuck (behavioral_state: "stuck"), be more proactive with solutions
- When they're in flow, be concise — don't interrupt their momentum
