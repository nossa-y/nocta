---
name: nocta-execute
description: |
  Execute a browser or OS task on behalf of the user — especially tasks the
  user has done before and wants automated. Loads screenpipe research methodology,
  checks existing action patterns, then operates with minimal information.
  Invoke when the user says "do [task] I did today", "do the [platform] task",
  "replicate what I did on [app]", "do [action]", or describes a task without
  spelling out every step.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

## nocta-execute

**This request is minimalist on purpose. Figure things out by yourself to complete
the user request, with the data you have access to.**

Do not ask clarifying questions. Use the data sources below to infer what needs
to be done, then do it.

Before acting or reporting on any page, expand every collapsed element (`expanded=false`, "More", "Show more", "Advanced") and scroll to load all content. Never work with partial page state.

### Browser instance isolation

If the user passes `instance=<name>` (e.g. `instance=demo`, `instance=sales`),
run this at the very start, before any `agent-browser` command:

```bash
export AGENT_BROWSER_SESSION="<name>"
```

This routes all `agent-browser` commands in this run to an isolated browser session.
Multiple instances can run simultaneously without interfering with each other.
The session auto-creates on the first `agent-browser open` call - no setup needed.

If no `instance` is specified, the default session is used (same as before).

---

### Visibility mode

- **Default (visible):** browser runs `--headed` on the user's screen. User can watch.
- **Invisible:** if the user says "invisible", "novisible", or "background" — run the
  browser on the virtual display so it doesn't steal focus or block the user's screen.

```bash
# Invisible mode setup (only when requested):
~/.nocta/bin/agent-display on        # ensure virtual display exists
# ... launch agent-browser as normal (--headed) ...
~/.nocta/bin/agent-display move      # move Chrome window to virtual display
# agent works invisibly — user's screen is free
```

If the user doesn't specify, default to **visible** (no virtual display).

---

### Step 0 — Check task memory first

Before anything else, check if there's an active task matching the user's request:

```bash
python3 ~/.nocta/bin/task-memory list
```

If a match exists, read the full state:

```bash
python3 ~/.nocta/bin/task-memory get "<task-name>"
```

Resume from `next_step`. Don't redo what's already in `progress.done`.

**Also: before acting on any user instruction that references a page element
("click X", "go to Y", "do Z on the page") — snapshot the current browser page
first and check if that element is already visible. Only navigate elsewhere if
it's not found in the current snapshot.**

```bash
agent-browser snapshot | grep -i "<keyword from user instruction>"
```

---

### Step 1 — Load screenpipe research methodology

Read these files before touching anything:

```bash
cat ~/.nocta/docs/screenpipe-use/inference-strategy.md
```

```bash
cat ~/.nocta/docs/screenpipe-use/cast-wide-then-narrow.md
```

These tell you how to read Screenpipe data: what tables exist, how to resolve
unlabeled clicks via coordinates + elements, how to cast wide before narrowing.

---

### Step 2 — Check for an existing action pattern

```bash
ls ~/.nocta/actions/
```

Always list all action files first. Then:

1. **Exact match** — if a file clearly matches the task (e.g. `reddit-decline-message-request.md`
   for a Reddit task), read it. It has the exact steps and gotchas from last time.

2. **No exact match, or stuck mid-execution** — read everything. A pattern from a different
   task might transfer. Examples of unexpected transfers:
   - `browser-real-chrome-profile.md` solves Google OAuth blocks — relevant for *any* site
     that SSOs through Google, not just the one it was written for
   - `gmail-send-email.md` shows the compose URL trick — reusable for any Gmail-based send

   **Be creative. If you're blocked, scan all files before giving up or asking the user.**
   The solution is probably already documented under a different name.

---

### Step 3 — Research what happened (if needed)

If the user said "I did X today" or "like I did earlier" — use the full
`screenpipe-research` methodology (see `~/.claude/skills/screenpipe-research/SKILL.md`)
to reconstruct the task before executing. That skill enforces all 5 layers:
ui_events, frames/accessibility_text, elements coordinate resolution, intent
signals (Copy/Discard/clipboard), and FTS search.

Short version:

```bash
sqlite3 ~/.screenpipe/db.sqlite "
SELECT timestamp, event_type, x, y, element_name, element_role, window_title, browser_url
FROM ui_events
WHERE event_type IN ('click', 'text', 'app_switch')
  AND timestamp > datetime('now', '-12 hours')
ORDER BY timestamp DESC
LIMIT 100;"
```

Cast wide first (no app/URL filter). Let the data tell you where the action
happened. Then zoom in.

For unlabeled clicks: join to `elements` via normalized coordinates to resolve
what was actually clicked (see inference-strategy.md Step 2).

---

### Execution rule — Human pacing (anti-bot)

When navigating multiple pages or performing repeated actions, act like a human:
- **3-8 seconds** random delay between page navigations
- **1-3 seconds** random delay between clicks
- **After 10 pages**, take a longer cooldown (30-60 seconds) before continuing
- Add jitter to all timings so patterns don't look mechanical

```bash
# Use this between navigations:
sleep $(python3 -c "import random; print(round(random.uniform(3, 8), 1))")
# Use this between clicks:
sleep $(python3 -c "import random; print(round(random.uniform(1, 3), 1))")
```

---

### Execution rule — Always use the browser, never raw APIs

**Always use `agent-browser` to interact with websites. Never try to reverse-engineer
or call a site's internal API (Algolia, REST, GraphQL, etc.) directly via `curl` or
`fetch`.** The browser is the tool — it handles auth, cookies, JS rendering, pagination,
and dynamic content. Raw API calls break constantly, miss auth, and waste time debugging
endpoints that weren't meant to be called directly.

---

### Step 4 — Check cookies, then execute

Before opening the browser, check if cookies exist for the target domain:

```bash
# replace 'reddit.com' with the actual target domain
python3 ~/.nocta/bin/cookie-import.py --browser chrome --domains reddit.com --list-domains 2>/dev/null | grep -c reddit
```

- **Count > 0** → cookies exist, export and load them
- **Count = 0** → tell the user no cookies found for this domain, they may need to log in first

Export cookies for the target domain:

```bash
python3 ~/.nocta/bin/cookie-import.py --browser chrome --domains <domain> -o /tmp/nocta-cookies.json
```

Then open the browser:

```bash
agent-browser close  # clear any existing daemon first
agent-browser --headed open <url>
```

**If execution hits an auth block mid-task** (login page, "blocked by network security", CAPTCHA):
1. Re-export cookies for the domain using cookie-import.py
2. Tell the user they may need to log in to the site in Chrome first
3. Retry after fresh cookie export
4. `agent-browser close` and retry from the navigation step

Use `fill` not `type` for text inputs on React-based apps (Reddit, Notion, etc.)
— `type` doesn't trigger React's input event handler.

Use `agent-browser snapshot` frequently to read the accessibility tree and find
element refs. The tree is the ground truth for what's on screen.

---

### Step 5 — Save task state + document new patterns

**After every multi-step task — whether completed or paused — write to task memory:**

```bash
# While in progress / pausing mid-task:
python3 ~/.nocta/bin/task-memory set "<task-name>" '{
  "url": "<current url>",
  "progress": {"done": [...], "pending": [...], "skipped": [...]},
  "next_step": "<exact next action>",
  "context": "<any gotchas, profile to use, auth notes>"
}'

# When fully done:
python3 ~/.nocta/bin/task-memory done "<task-name>"
```

This is the persistent memory layer. The next session will read it at Step 0
and resume exactly from `next_step` without needing the conversation summary.

---

**Also document new action patterns:**

If this action doesn't have a file in `actions/` yet, create one after completing
it. Name it after the action (e.g. `reddit-decline-message-request.md`). Include:
- What the action does (one line)
- Prerequisites
- Exact steps with commands
- Any gotchas discovered during execution
