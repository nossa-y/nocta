# Action: linkedin-send-message

Send a LinkedIn message to a connection from the Connections page.

## Prerequisites

- `agent-browser` running with Profile 2 (instance "461")
- Target must be a 1st-degree connection

## Steps

### 1. Open connections page
```bash
export AGENT_BROWSER_SESSION="461"
agent-browser open "https://www.linkedin.com/mynetwork/invite-connect/connections/"
sleep 3
```

### 2. Find the Message button for the target person
```bash
agent-browser snapshot | grep "Send a message to {Name}"
# Returns: button "Send a message to {Name}" [ref=eXX]
```

### 3. Click Message button
```bash
agent-browser click eXX
```

### 4. Wait 3s, snapshot — VERIFY recipient name in overlay
```bash
sleep 3
agent-browser snapshot | grep -iE "Remove.*{Name}|textbox.*Write"
# MUST see "Remove {Name}" confirming correct recipient
# Note the textbox ref
```

### 5. Click textbox to focus
```bash
agent-browser click {textbox_ref}
```

### 6. Wait 2s, type message (ONE type call with full message)
```bash
sleep 2
agent-browser type {textbox_ref} "Hey {FirstName}, just moved from paris to sf to build from Founders Inc

I'd be down to take a coffee sometime! Curious about your story"
```

### 7. Wait 2s, snapshot — VERIFY all three: recipient + message + Send button
```bash
sleep 2
agent-browser snapshot | grep -iE "Remove.*{Name}|textbox.*Write.*Hey|button.*Send" | grep -v "Send a message to"
# MUST see:
# - "Remove {Name}" (correct recipient)
# - textbox content with "Hey {FirstName}..." (correct message)
# - button "Send" with a ref (enabled, no "disabled" flag)
```

### 8. Click Send
```bash
agent-browser click {send_ref}
```

### 9. Wait 2s, close the conversation overlay
```bash
sleep 2
agent-browser snapshot | grep "Close.*conversation.*{Name}"
agent-browser click {close_ref}
sleep 2
```

### 10. Repeat from Step 2 for next person

## Critical Rules

1. **ONE click per command.** Never chain clicks. Each click changes the DOM.
2. **Always verify recipient** before typing. Check for "Remove {Name}" in the overlay.
3. **Always verify message text** before clicking Send. Read the textbox content.
4. **Type the FULL message in ONE `type` call.** A second `type` call clears the field and can close the overlay.
5. **Close the overlay** after sending before moving to the next person.
6. **Use `type` not `fill`** for the message textbox — it's a contenteditable div.
7. **Do NOT snapshot between click-focus and type** — snapshotting can steal focus from the contenteditable div.

## Gotchas

- Clicking "Message" on a profile page redirects to Sales Navigator (if user has Sales Nav). Always use the Connections page instead.
- The textbox ref changes after every interaction. Always re-snapshot to get fresh refs.
- If the overlay closes unexpectedly, go back to the connections page and click Message again — previous text may persist in the overlay.
- `agent-browser fill` does NOT work — it closes the overlay. Use `type` only.
- The message overlay is at the bottom of the page, not in the main content area. It shows up in the snapshot under a `dialog "Messaging"` element.
