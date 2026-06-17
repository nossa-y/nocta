# Nocta Setup Troubleshooting

## Screen Recording Not Working (0 Frames Captured)

If `nocta status` shows `frames_analyzed: 0` and no screen recording is happening, this is typically caused by one of two issues.

### Check Current State

```bash
# 1. Is Nocta running?
curl http://127.0.0.1:7676/context

# 2. Is screenpipe running?
ps aux | grep screenpipe

# 3. Any frames captured?
sqlite3 ~/.screenpipe/db.sqlite "SELECT COUNT(*) FROM frames;"

# 4. Check logs
ls -lt ~/.screenpipe/screenpipe.*.log
cat ~/.screenpipe/screenpipe.$(date +%Y-%m-%d).*.log
```

---

### Issue 1: macOS 13 Ventura SCKit Bug (Apple Bug)

**Symptoms:**
- `SCShareableContent.current` hangs indefinitely
- screenpipe log shows: `Using sck-rs for screen capture (macOS 12.3+)` then nothing
- Even a minimal Swift test hangs:

```bash
cat << 'EOF' | swift -
import ScreenCaptureKit
import Foundation
let semaphore = DispatchSemaphore(value: 0)
SCShareableContent.current { content, error in
    if let error = error { print("ERROR: \(error)") }
    else if let content = content { print("OK: \(content.displays.count) displays") }
    else { print("ERROR: no content and no error") }
    semaphore.signal()
}
_ = semaphore.wait(timeout: .now() + 10)
EOF
```

If this **hangs** (doesn't print "OK" within 10 seconds), you have the Apple bug.

**Root Cause:** Apple introduced a regression in ScreenCaptureKit on macOS Ventura 13.7.0–13.7.7. `SCShareableContent.current` never returns.

**Fix:** Update macOS to **13.7.8 or later**.

```bash
# Check your version
sw_vers
# ProductVersion: 13.7.8 (or later)

# Update via System Settings → Software Update
# Or command line:
sudo softwareupdate --install --all
```

---

### Issue 2: Pre-Built screenpipe Binary SDK Mismatch

**Symptoms:**
- macOS is on 13.7.8 (SCKit Swift test passes)
- screenpipe log shows `Using sck-rs for screen capture (macOS 12.3+)` and hangs
- `curl http://127.0.0.1:7676/context` shows `frames_analyzed: 0`

**Root Cause:** screenpipe is distributed as a **pre-compiled binary** via npm. It is compiled against the **macOS 15.5 SDK** on the publisher's CI. When this binary runs on macOS 13 Ventura, it calls ScreenCaptureKit APIs in ways that expect macOS 15+ behavior, causing it to hang.

You can check:

```bash
codesign -dvvv $(find /opt/homebrew -name screenpipe -type f 2>/dev/null | head -1) 2>&1 | grep "Runtime Version"
# → Runtime Version=15.5.0 (means compiled against macOS 15.5 SDK)
```

**Why Swift test works but screenpipe doesn't:** `swift` compiles code on your machine using your local SDK (13.7.8), producing a compatible binary. The pre-built screenpipe binary was compiled on a macOS 15.5 machine — it has macOS 15.5 API expectations baked in.

**Fixes (choose one):**

| Option | How | Time |
|---|---|---|
| **Upgrade macOS to Sonoma+** | System Settings → Software Update | 30–60 min |
| **Build screenpipe from source** | `cargo build --release` (uses your local SDK) | 20–30 min |
| **Use screenpipe desktop app** | Download .dmg from https://screenpi.pe | 5 min |

---

### Issue 3: Permission Dialog Hidden

**Symptoms:** screenpipe hangs on first launch with no log output.

**Fix:** The macOS permission dialog often appears **behind all open windows**. Check behind every window — it may be lurking. Click "Allow" and screenpipe will proceed.

---

### Issue 4: Permissions Not Granted

```bash
# Reset all screen recording permissions
tccutil reset ScreenCapture

# Re-launch screenpipe — System Settings should prompt for permission
screenpipe --use-all-monitors
```

---

## macOS Version Guide

| macOS Version | SCKit Status | screenpipe Binary | Recommendation |
|---|---|---|---|
| Ventura 13.0–13.7.7 | **Bug**: SCKit hangs | Doesn't work | Update to 13.7.8 |
| Ventura 13.7.8 | Works (Swift) | May hang (SDK mismatch) | Upgrade to 14+ or build from source |
| Sonoma 14.x | Works | Likely works | Good |
| Sequoia 15.5+ | Works | Works | Best |

---

## Full Log Reference

| Log Message | What It Means |
|---|---|
| `Using sck-rs for screen capture (macOS 12.3+)` | screenpipe is initializing — if no further output, SCKit is stuck |
| `VisionManager: no monitors matched the allowed list (0 enumerated, 0 started)` | SCKit returned no displays — likely the Ventura bug |
| `screen recording: ok` | Screen Recording permission IS granted (this just checks TCC) |
| `frames_analyzed: 0` | No frames were ever captured by screenpipe |
| `Runtime Version=15.5.0` (in codesign) | Binary compiled against macOS 15.5 SDK — may not run on older OS |
