# Nocta

**Your AI agents get eyes.**

Nocta watches your screen activity and provides structured context to any AI agent - Claude Code, Hermes, Cursor, or your own tools. One API call, 6ms, and the agent knows what you're doing before you type a word.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/nossa-y/nocta/main/install.sh | bash
```

One command. Installs everything: screenpipe, agent-browser, skills, auto-start, agent config.

After install, grant **screen recording permission** when prompted (macOS Settings > Privacy > Screen Recording).

## What's included

| Component | What it does |
|-----------|-------------|
| **nocta context** | Real-time screen activity API (localhost:7676) |
| **screenpipe-research** | Claude Code skill - reconstructs what you did, detects workflows |
| **nocta-execute** | Claude Code skill - automates browser tasks using your real cookies |
| **cookie-import** | Decrypts Chrome/Arc/Brave/Edge cookies for browser automation |

## Quick start

After install, open Claude Code in any project:

```
You: "what was I doing this afternoon?"
  → screenpipe-research reconstructs your workflows

You: "send a LinkedIn connection request to [person]"
  → nocta-execute automates it in your browser

You: "help" (while stuck on a bug)
  → nocta context tells the agent what you're working on
```

## Cookie import

Export cookies from your browser for automation tasks:

```bash
# List Chrome profiles
python3 ~/.nocta/bin/cookie-import.py --browser chrome --list-profiles

# Export GitHub cookies
python3 ~/.nocta/bin/cookie-import.py --browser chrome --domains github.com -o /tmp/cookies.json

# List all domains with cookie counts
python3 ~/.nocta/bin/cookie-import.py --browser chrome --list-domains
```

Supports: Chrome, Arc, Brave, Edge, Chromium.

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
GET  /context    Structured context JSON (6ms)
GET  /health     Service health check
GET  /status     Detailed status
POST /context    Same as GET, plus additionalContext for Claude Code hooks
```

## Requirements

- **macOS 14 (Sonoma) or later** (recommended)
- macOS 13.7.8+ (Ventura, known issues - see [TROUBLESHOOTING.md](TROUBLESHOOTING.md))
- Python 3.9+ (ships with macOS)
- Node.js (for screenpipe and agent-browser)
- 8GB RAM recommended

## Privacy

Everything runs locally. Your screen data never leaves your machine. No cloud, no accounts, no telemetry.
