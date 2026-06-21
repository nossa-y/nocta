# Action: linkedin-withdraw-invitations

Bulk withdraw pending LinkedIn connection requests from the Sent tab.

## Prerequisites

- `agent-browser` installed
- LinkedIn session active in Chrome Profile 2 (nels / samuel.iyamu2@gmail.com)

## Steps

### 1. Open sent invitations page with real Chrome profile

```bash
agent-browser close
agent-browser --profile "Profile 2" --headed --args "--disable-blink-features=AutomationControlled" \
  open "https://www.linkedin.com/mynetwork/invitation-manager/sent/"
```

### 2. Scroll to bottom to load all invitations

```bash
agent-browser scroll down 20
```

Repeat until the full list is loaded. Check count with:
```bash
agent-browser snapshot 2>&1 | grep -E "People \("
```

### 3. Withdraw in a loop (bottom-up)

```bash
while true; do
    SNAPSHOT=$(agent-browser snapshot 2>&1)
    LAST_LINE=$(echo "$SNAPSHOT" | grep -E 'Withdraw invitation sent to' | tail -1)
    
    # Stop condition — change "Vikram C." to your target
    if echo "$LAST_LINE" | grep -q "STOP_NAME"; then
        echo "Done."
        break
    fi
    
    REF=$(echo "$LAST_LINE" | sed 's/.*ref=\(e[0-9]*\).*/\1/')
    NAME=$(echo "$LAST_LINE" | sed 's/.*sent to //' | sed 's/".*//')
    
    agent-browser click "$REF" 2>&1 > /dev/null
    sleep 1
    
    # Snapshot to find the ACTUAL confirm button ref (it's always "Withdraw invitation sent to X")
    CONFIRM_REF=$(agent-browser snapshot 2>&1 | grep -E 'button "Withdraw invitation sent to' | sed 's/.*ref=\(e[0-9]*\).*/\1/')
    agent-browser click "$CONFIRM_REF" 2>&1 > /dev/null
    sleep 1
done
```

## Gotchas

- **macOS grep doesn't support `-P`** — use `sed` for regex extraction, not `grep -oP`
- **Confirm dialog button ref changes** — do NOT hardcode `e4`. Snapshot after clicking "Withdraw" and dynamically find the confirm button ref from the dialog
- **Scrolling loads more items** — LinkedIn lazy-loads. Scroll down first to load the full list before starting the loop
- **First script attempt failed** because it hardcoded `e4` and didn't re-snapshot between the withdraw click and the confirm click. The fix: snapshot → find confirm ref → click
- **3-week cooldown** — LinkedIn warns "you won't be able to resend for up to 3 weeks" after withdrawing
