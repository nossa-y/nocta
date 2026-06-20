# Action: browser-real-chrome-profile

Use the user's real Chrome profile directly for browser automation — bypasses Google's OAuth bot detection and inherits any existing logged-in session (Vercel, Notion, etc.) without cookie import.

## Why this exists

The gstack Chromium profile works for most sites, but **Google blocks OAuth flows** from it with "Ce navigateur ou cette application ne sont peut-être pas sécurisés" — it detects Playwright's automation fingerprint (`navigator.webdriver = true`).

The fix: skip gstack entirely and connect to the user's **real Chrome profiles** using `--profile "<Profile Name>"` + `--args "--disable-blink-features=AutomationControlled"`. Chrome already has the sessions. No cookie import needed.

## Prerequisites

- `agent-browser` installed
- Chrome installed with at least one profile that has an active session on the target site

## Steps

### 1. List available Chrome profiles

```bash
agent-browser profiles
```

Output example:
```
Chrome profiles (/Users/nossa/Library/Application Support/Google/Chrome):

  Default  (odecloud.com)
  Profile 2  (nels)
  Profile 3  (Work)           ← nossa.iyamu1@gmail.com — Vercel, Gmail, etc.
  Profile 4  (nels82434@gmail.com)
  Profile 7  (apify-profile-2)
```

Profile 3 = Work = `nossa.iyamu1@gmail.com`. Use this for anything tied to that Google account (Vercel, Google Workspace, etc.).

### 2. Close existing daemon and open with real Chrome profile

```bash
agent-browser close
agent-browser --profile "Profile 3" --headed --args "--disable-blink-features=AutomationControlled" open "<url>"
```

The `--disable-blink-features=AutomationControlled` flag removes the automation fingerprint Chrome normally exposes. Google's OAuth flow won't block it.

### 3. Proceed as normal

```bash
agent-browser snapshot   # read the accessibility tree
agent-browser click "<ref>"
agent-browser fill "<ref>" "text"
```

No cookie picker, no import step — the real session is already there.

## Example — Vercel dashboard

```bash
agent-browser close
agent-browser --profile "Profile 3" --headed --args "--disable-blink-features=AutomationControlled" \
  open "https://vercel.com/mes-projects-f3d5d41e/hp-auto-deploy/logs"
# → lands directly on the logs page, no login required
```

## When to use this vs gstack

| Situation | Use |
|-----------|-----|
| Google OAuth blocks the flow ("unsecure browser") | Real Chrome profile |
| Site works fine with gstack cookies | gstack profile (avoids touching user's real browser) |
| Session already active in Chrome and cookie export is painful | Real Chrome profile |
| Need fresh isolated session | gstack profile |

## Notes

- The `--profile` value is the profile **folder name** (e.g. `"Profile 3"`), not the display name. Use `agent-browser profiles` to see folder names.
- `--headed` is still required — headless Chrome behaves differently and some sites (Reddit, Vercel) detect it.
- This opens a Chrome window in the user's existing Chrome instance. The user may see a new window appear.
- `--disable-blink-features=AutomationControlled` hides `navigator.webdriver` — the main signal Google uses to block automated OAuth flows.
