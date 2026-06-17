# Nocta

**Your AI agents get eyes.**

Nocta watches your screen activity and provides structured context to any AI agent — Claude Code, Hermes, Cursor, or your own tools. One API call, 6ms, and the agent knows what you're doing before you type a word.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/nossa-y/nocta/main/install.sh | bash
```

That's it. One command. It installs everything, sets up auto-start, and configures your AI agents.

## What it does

You open Claude Code. Before you type anything, it already knows:

```json
{
  "task": "Debugging — errors in auth.py",
  "current_state": {
    "app": "Cursor",
    "behavioral_state": "stuck"
  },
  "activity": {
    "recent_files": ["auth.py", "test_auth.py"],
    "recent_urls": ["jwt.io/introduction", "stackoverflow.com/q/jwt-rs256"]
  },
  "signals": ["searching_for_solutions", "seeing_errors"]
}
```

You type "help" — and the agent understands what "help" means.

## How it works

1. **Screenpipe** records your screen activity (OCR, window titles, audio)
2. **Nocta** analyzes that data every 30 seconds — infers your current task, detects if you're stuck or in flow, tracks what you're researching
3. **Any agent** calls `GET http://localhost:7676/context` and gets structured context in 6ms

## Commands

```
nocta start       Start the service
nocta stop        Stop the service
nocta status      Show what Nocta sees right now
nocta context     View the full context JSON
nocta logs        View service logs
nocta install     Set up auto-start on login
nocta uninstall   Remove auto-start
```

## API

```
GET  /context    → Structured context JSON (6ms)
GET  /health     → Service health check
GET  /status     → Detailed status
POST /context    → Same as GET, plus additionalContext for Claude Code hooks
```

## Requirements

- macOS (Linux coming soon)
- Python 3.9+
- Screen recording permission (the installer walks you through it)

## Privacy

Everything runs locally. Your screen data never leaves your machine. No cloud, no accounts, no telemetry.
