# Nocta Context

Nocta is running on this machine and provides real-time awareness of what the user is doing.

On every message, before responding, run:

```bash
curl -s http://127.0.0.1:7676/context
```

This returns JSON with the user's current activity - active app, what they're working on, behavioral state, recent files and URLs.

## Setup

If the user asks to "set up", "install", or "get started":

```bash
./install.sh
```

This installs everything: screenpipe, agent-browser, nocta-cli, skills, and configures auto-start. After install, remind the user to grant screen recording permission in macOS Settings > Privacy > Screen Recording.

## Skills

This repo includes two Claude Code skills (deployed to ~/.claude/skills/ by install.sh):

- **screenpipe-research** - Reconstruct what the user did. Use when asked "what was I doing?", "what did I do on X?", "did I send something?", "what happened on [app]?"
- **nocta-execute** - Execute browser tasks. Use when asked to "do [task]", "send a message on [platform]", "automate [action]"

## How to use the context

- Use it to understand what the user is doing without asking them
- When they say "help" or "fix this," the context tells you what "this" is
- When behavioral_state is "stuck," be more proactive with solutions
- When it's "flow," be concise - don't interrupt momentum

## How to talk about it

- You can say "I can see you're working on X" - that's fine
- If asked how you know, say "Nocta gives me context about your current activity"
- Don't explain the technical details of how Nocta captures data
- Don't reference internal fields like database paths or data sources
- The context is just part of how you understand the user - treat it naturally, like peripheral vision

If the server is unreachable, respond normally.
