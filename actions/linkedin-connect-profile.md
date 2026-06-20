# Action: linkedin-connect-profile

Send a LinkedIn connection request (no note) to a profile already open in a browser tab.

## Prerequisites

- `agent-browser` running with real Chrome profile (Profile 2 = samuel.iyamu2, Profile 3 = nossa.iyamu1)
- Target profile tab already open

## Steps

### 1. Switch to the tab and snapshot
```bash
agent-browser tab <tN>
sleep $(python3 -c "import random; print(round(random.uniform(2,4),1))")
agent-browser snapshot | grep -iE "connect|1st degree|pending|withdraw|more actions" | grep "button"
```

### 2. Skip conditions (do NOT connect)
- "1st degree connection" in snapshot → already connected
- "Pending / Withdraw invitation" button → already sent

### 3a. Direct Connect button visible (no note)
```bash
agent-browser click "<connect_ref>"
sleep 1
SNAP=$(agent-browser snapshot)
SEND_REF=$(echo "$SNAP" | grep -i "send without" | grep -o 'ref=e[0-9]*' | head -1 | sed 's/ref=//')
agent-browser click "$SEND_REF"
```

### 3a-note. Direct Connect button visible (with personalized note)
```bash
agent-browser click "<connect_ref>"
sleep 1
SNAP=$(agent-browser snapshot)
# Click "Add a note" button instead of "Send without a note"
NOTE_REF=$(echo "$SNAP" | grep -i "add a note" | grep -o 'ref=e[0-9]*' | head -1 | sed 's/ref=//')
agent-browser click "$NOTE_REF"
sleep 1
SNAP2=$(agent-browser snapshot)
# Fill the note textarea
MSG_REF=$(echo "$SNAP2" | grep -i "textarea\|message" | grep -o 'ref=e[0-9]*' | head -1 | sed 's/ref=//')
agent-browser fill "$MSG_REF" "Your message here"
sleep 1
SNAP3=$(agent-browser snapshot)
SEND_REF=$(echo "$SNAP3" | grep -i "send invitation\|send now" | grep -o 'ref=e[0-9]*' | head -1 | sed 's/ref=//')
agent-browser click "$SEND_REF"
```

### 3b. Connect hidden under More actions (common for high-follower profiles)
```bash
agent-browser click "<more_actions_ref>"
sleep 1
SNAP=$(agent-browser snapshot)
CONN_REF=$(echo "$SNAP" | grep -i "invite <FirstName>.*connect\|invite.*<LastName>.*connect" | grep -o 'ref=e[0-9]*' | head -1 | sed 's/ref=//')
agent-browser click "$CONN_REF"
sleep 1
SNAP2=$(agent-browser snapshot)
SEND_REF=$(echo "$SNAP2" | grep -i "send without" | grep -o 'ref=e[0-9]*' | head -1 | sed 's/ref=//')
agent-browser click "$SEND_REF"
```

### 4. Verify
```bash
agent-browser snapshot | grep -iE "pending|withdraw"
# Should show "Pending, click to withdraw invitation sent to X"
```

## Gotchas

- **"Message" button ≠ connected** — LinkedIn shows Message for non-connections too. Only trust "1st degree" or "Pending/Withdraw"
- **Connect is often hidden** — High-follower/influencer profiles hide Connect under "More actions". Always check More if no direct Connect button
- **Always re-snapshot after each click** — refs change after every action. Never reuse a ref across steps
- **Human pacing** — 3-8s between tabs, 1-2s between clicks
- **Tab may load wrong page** — if tab switched to wrong URL, use `agent-browser open <url>` to navigate directly
- **Browser profile matters** — LinkedIn is on Profile 2 (samuel.iyamu2 / "nels"). Start with `agent-browser --profile "Profile 2" --headed open "https://www.linkedin.com"`. The gstack chromium profile does NOT have LinkedIn cookies - always use `--profile "Profile 2"`.
- **Already connected check** — always check "1st degree connection" in the snapshot before attempting to connect. If already connected, skip.
