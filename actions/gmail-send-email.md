# Action: gmail-send-email

Send an email via Gmail using the authenticated Google session.

## Prerequisites

- Google/Gmail cookies in gstack Chromium profile (check: `sqlite3 ~/.gstack/chromium-profile/Default/Cookies "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%google.com%';"`)
- `agent-browser` installed

## Steps

### 1. Check cookies

```bash
sqlite3 ~/.gstack/chromium-profile/Default/Cookies \
  "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%google.com%';"
```

If 0, run the gstack cookie picker and select google.com / mail.google.com.

### 2. Open Gmail compose with pre-filled recipient

```bash
agent-browser close
agent-browser --profile ~/.gstack/chromium-profile --headed open \
  "https://mail.google.com/mail/u/0/?view=cm&to=RECIPIENT@example.com&su=SUBJECT&body="
```

The `?view=cm&to=...` query string opens directly into compose mode with the recipient pre-filled. No need to navigate to inbox first.

### 3. Fill body and send

```bash
# Gmail UI may be in French (Corps du message = message body, Envoyer = Send)
agent-browser snapshot  # find textbox "Corps du message" or "Message Body" ref
agent-browser fill "<body ref>" "your message here"

agent-browser snapshot  # find "Envoyer" or "Send" button ref
agent-browser click "<send ref>"
```

### 4. Confirm

```bash
agent-browser snapshot  # look for "Message envoyé" or "Message sent" toast
```

## Notes

- Gmail UI language follows the account's language setting — may be French, English, etc. Button/field names change but refs still work.
- Use `fill` not `type` — Gmail body is a contenteditable div, `type` doesn't populate it reliably.
- The compose URL parameter `fs=1&tf=cm` opens compose in full-screen mode if needed.
- Subject can be pre-filled via `&su=Your+Subject` in the URL.
