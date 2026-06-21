# Action: reddit-decline-message-request

Decline an unsolicited Reddit chat request with a short reply (e.g. "sorry, i'm not interested").

## Prerequisites

- gstack browser installed (`~/.claude/skills/gstack/browse/dist/browse`)
- `agent-browser` installed
- Reddit session imported into gstack Chromium profile

## Steps

### 1. Import Reddit cookies (if not already done)

```bash
B=~/.claude/skills/gstack/browse/dist/browse
$B cookie-import-browser chrome
# picker opens at http://127.0.0.1:<port>/cookie-picker
# select reddit.com, close the tab
```

### 2. Close any existing agent-browser daemon and relaunch headed

```bash
agent-browser close
agent-browser --profile ~/.gstack/chromium-profile --headed open https://www.reddit.com/message/messages/
```

Must be `--headed` — Reddit blocks headless even with real cookies.

### 3. Open chat

```bash
agent-browser snapshot  # find the "Open chat" button ref
agent-browser click "<ref>"
```

Look for: `button "Open chat"` in the navbar (top right, badge showing unread count).

### 4. Navigate to requests

```bash
agent-browser snapshot  # find "View chat requests N unread"
agent-browser click "<ref>"
# then find "Additional requests" button if present
agent-browser click "<ref>"
```

### 5. View the target request

```bash
agent-browser snapshot  # lists pending requests with sender + timestamp
agent-browser click "<View Request ref>"  # opens the message thread
```

Read the message content from the snapshot to confirm it's the right one.

### 6. Accept the request

```bash
agent-browser snapshot  # find "Accept" and "Ignore" buttons
agent-browser click "<Accept ref>"
```

Must accept before replying — the send button stays disabled until accepted.

### 7. Fill and send the reply

```bash
agent-browser fill "<Write message ref>" "sorry, i'm not interested"
agent-browser snapshot  # confirm Send button is now enabled (not disabled)
agent-browser click "<Send message ref>"
```

**Use `fill`, not `type`** — `type` does not trigger Reddit's input event handler and leaves the Send button disabled.

### 8. Confirm delivery

```bash
agent-browser snapshot  # look for "You: sorry, i'm not interested" in the thread
```

## Notes

- `fill` vs `type`: Reddit's chat input requires `fill` to register the value. `type` keystroke-by-keystroke doesn't trigger the React state update, so the Send button stays disabled.
- The chat panel is a nested iframe. agent-browser resolves refs across iframes automatically — no special handling needed.
- If the daemon was already running without `--headed`, requests will be blocked by Reddit's network check. Always `agent-browser close` before reopening with the profile flag.
- "Additional requests" is a separate button from the main requests list — contains older or lower-priority requests.
