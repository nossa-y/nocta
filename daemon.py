#!/usr/bin/env python3
"""
Nocta Daemon — Context API server + background screen activity analyzer.

Single process, two threads:
  1. HTTP server on port 7676 (GET /context, GET /health, GET /status)
  2. Context updater loop (queries screen recorder DB every 30s, writes cache)

Zero heavy dependencies — only Python stdlib + sqlite3.
"""
import http.server
import json
import os
import re
import signal
import sqlite3
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# ============================================================
# Configuration
# ============================================================

PORT = int(os.environ.get("NOCTA_PORT", "7676"))
UPDATE_INTERVAL = int(os.environ.get("NOCTA_UPDATE_INTERVAL", "30"))
WINDOW_MINUTES = int(os.environ.get("NOCTA_WINDOW_MINUTES", "15"))
RECORDER_DB = os.path.expanduser(os.environ.get("NOCTA_RECORDER_DB", "~/.screenpipe/db.sqlite"))
CACHE_PATH = os.path.expanduser("~/.nocta/cache/context.json")
PID_PATH = os.path.expanduser("~/.nocta/cache/daemon.pid")
VERSION = "0.1.0"

Path(CACHE_PATH).parent.mkdir(parents=True, exist_ok=True)


# ============================================================
# Screen Activity Analyzer
# ============================================================

def query_recorder(minutes=15):
    """Pull recent activity from the screen recorder database."""
    if not os.path.exists(RECORDER_DB):
        return {"frames": [], "ui_events": [], "audio": []}

    try:
        db = sqlite3.connect(RECORDER_DB, timeout=5)
        db.row_factory = sqlite3.Row
        cutoff = f"-{minutes} minutes"

        frames = db.execute("""
            SELECT app_name, window_name, timestamp
            FROM frames
            WHERE timestamp > datetime('now', ?)
            AND app_name != ''
            ORDER BY timestamp ASC
        """, (cutoff,)).fetchall()

        ui_events = db.execute("""
            SELECT event_type, app_name, window_title as window_name, timestamp
            FROM ui_events
            WHERE timestamp > datetime('now', ?)
            ORDER BY timestamp ASC
        """, (cutoff,)).fetchall()

        audio = db.execute("""
            SELECT timestamp, transcription, device
            FROM audio_transcriptions
            WHERE timestamp > datetime('now', ?)
            AND length(transcription) > 10
            ORDER BY timestamp DESC
            LIMIT 10
        """, (cutoff,)).fetchall()

        db.close()
        return {
            "frames": [dict(f) for f in frames],
            "ui_events": [dict(e) for e in ui_events],
            "audio": [dict(a) for a in audio],
        }
    except Exception as e:
        return {"frames": [], "ui_events": [], "audio": [], "error": str(e)}


def _safe(frame, key):
    """Safely get a string value from a frame dict."""
    return frame.get(key) or ""


def build_time_on_task(frames):
    """Track how long user spent on each app/file/url."""
    if not frames:
        return {"apps": {}, "windows": {}, "current": None, "segments": 0}

    segments = []
    current_seg = None

    for frame in frames:
        app = _safe(frame, "app_name")
        window = _safe(frame, "window_name")
        key = f"{app}|{window}"

        if current_seg and current_seg["key"] == key:
            current_seg["end"] = frame["timestamp"]
            current_seg["frame_count"] += 1
        else:
            if current_seg:
                segments.append(current_seg)
            current_seg = {
                "key": key, "app": app, "window": window,
                "start": frame["timestamp"], "end": frame["timestamp"],
                "frame_count": 1,
            }
    if current_seg:
        segments.append(current_seg)

    app_time = defaultdict(float)
    window_time = defaultdict(float)
    for seg in segments:
        duration_sec = seg["frame_count"]
        app_time[seg["app"]] += duration_sec
        window_time[seg["window"][:100]] += duration_sec

    apps = dict(sorted(app_time.items(), key=lambda x: -x[1]))
    windows = dict(sorted(window_time.items(), key=lambda x: -x[1])[:10])
    current = segments[-1] if segments else None

    return {
        "apps": {k: round(v / 60, 1) for k, v in apps.items()},
        "windows": {k: round(v / 60, 1) for k, v in windows.items()},
        "current": {
            "app": current["app"],
            "window": current["window"][:100],
            "minutes_on_current": round(current["frame_count"] / 60, 1),
        } if current else None,
        "segments": len(segments),
    }


def detect_behavioral_patterns(frames, ui_events):
    """Detect stuck, flow, transition patterns."""
    patterns = {
        "state": "unknown",
        "signals": [],
        "app_switches_per_min": 0,
        "unique_windows_last_5min": 0,
        "revisit_count": 0,
    }

    if not frames:
        patterns["state"] = "idle"
        return patterns

    # Count app switches
    switches = 0
    prev_app = None
    for frame in frames:
        app = _safe(frame, "app_name")
        if prev_app and app != prev_app:
            switches += 1
        prev_app = app

    total_minutes = max(1, len(frames) / 60)
    patterns["app_switches_per_min"] = round(switches / total_minutes, 1)

    # Recent 5 min window diversity
    recent = frames[-300:] if len(frames) > 300 else frames
    unique_windows = len(set(_safe(f, "window_name") for f in recent))
    patterns["unique_windows_last_5min"] = unique_windows

    # Revisit detection
    window_sequence = []
    prev_window = None
    for f in recent:
        w = _safe(f, "window_name")
        if w != prev_window:
            window_sequence.append(w)
            prev_window = w

    revisits = 0
    seen = set()
    for w in window_sequence:
        if w in seen:
            revisits += 1
        seen.add(w)
    patterns["revisit_count"] = revisits

    # Determine state
    if patterns["app_switches_per_min"] > 4 and revisits > 3:
        patterns["state"] = "stuck"
        patterns["signals"].append("rapid switching between same windows")
    elif patterns["app_switches_per_min"] > 3:
        patterns["state"] = "scattered"
        patterns["signals"].append("high app switching rate")
    elif patterns["app_switches_per_min"] < 1 and unique_windows <= 3:
        patterns["state"] = "flow"
        patterns["signals"].append("deep focus on few windows")
    else:
        patterns["state"] = "active"

    # Specific signals
    apps_used = set(_safe(f, "app_name") for f in recent)
    windows_text = " ".join(_safe(f, "window_name").lower() for f in recent[-50:])

    if "Google Chrome" in apps_used and any(
        term in windows_text for term in ["stackoverflow", "github.com/issues", "google.com/search"]
    ):
        patterns["signals"].append("searching_for_solutions")

    if any(term in windows_text for term in ["error", "traceback", "failed", "exception"]):
        patterns["signals"].append("seeing_errors")

    return patterns


def extract_urls_and_files(frames):
    """Extract URLs from browsers and files from editors."""
    urls, files = [], []
    seen_urls, seen_files = set(), set()

    for frame in frames:
        window = _safe(frame, "window_name")
        app = _safe(frame, "app_name")

        if any(b in app for b in ("Chrome", "Firefox", "Safari", "Arc", "Brave")):
            title = re.sub(r'\s*-\s*(Google Chrome|Firefox|Safari|Arc|Brave).*$', '', window)
            # Strip high memory warnings
            title = re.sub(r'\s*-\s*High memory usage.*$', '', title)
            if title and title not in seen_urls and len(title) > 3:
                seen_urls.add(title)
                urls.append(title)

        if app in ("Cursor", "Visual Studio Code", "Code", "Sublime Text", "vim", "nvim", "Zed"):
            match = re.match(r'^([^\u2014\u2013\-]+)', window)
            if match:
                fname = match.group(1).strip()
                if fname and fname not in seen_files and len(fname) < 100:
                    seen_files.add(fname)
                    files.append(fname)

    return urls[:15], files[:10]


def infer_current_task(time_data, patterns, urls, files, audio):
    """Infer what the user is currently working on."""
    task = {"description": "unknown", "confidence": 0.0, "evidence": []}

    if not time_data.get("current"):
        return task

    current_app = time_data["current"]["app"]

    # LinkedIn outreach
    linkedin_signals = [u for u in urls if "linkedin" in u.lower()]
    if len(linkedin_signals) >= 3:
        task["description"] = "LinkedIn outreach — browsing profiles"
        task["confidence"] = 0.8
        task["evidence"] = linkedin_signals[:3]
        return task

    # Coding
    if current_app in ("Cursor", "Visual Studio Code", "Code", "Zed"):
        if files:
            task["description"] = f"Coding — working on {files[0]}"
            task["confidence"] = 0.6
            task["evidence"] = files[:3]

            if "searching_for_solutions" in patterns.get("signals", []):
                task["description"] = f"Debugging — stuck on {files[0]}"
                task["confidence"] = 0.75
                task["evidence"].append("searching for solutions online")

            if "seeing_errors" in patterns.get("signals", []):
                task["description"] = f"Debugging — errors in {files[0]}"
                task["confidence"] = 0.8
                task["evidence"].append("error messages visible")

            return task

    # Research
    if any(b in current_app for b in ("Chrome", "Firefox", "Safari", "Arc", "Brave")):
        if urls:
            task["description"] = f"Researching — reading {urls[0][:60]}"
            task["confidence"] = 0.5
            task["evidence"] = urls[:3]
            return task

    # Communication
    if current_app in ("WhatsApp", "Telegram", "Slack", "Discord", "Messages", "Mail"):
        task["description"] = f"Messaging on {current_app}"
        task["confidence"] = 0.7
        task["evidence"] = [f"active in {current_app}"]
        return task

    # On a call
    if audio:
        text = audio[0].get("transcription", "")[:100]
        if len(text) > 20:
            task["description"] = "In a conversation"
            task["confidence"] = 0.6
            task["evidence"] = [f"audio detected"]
            return task

    # Fallback
    task["description"] = f"Using {current_app}"
    task["confidence"] = 0.3
    task["evidence"] = [time_data["current"]["window"][:60]]
    return task


def build_context():
    """Build full structured context. Called every UPDATE_INTERVAL seconds."""
    raw = query_recorder(minutes=WINDOW_MINUTES)

    if raw.get("error"):
        return {"error": raw["error"], "timestamp": datetime.utcnow().isoformat() + "Z"}

    time_data = build_time_on_task(raw["frames"])
    patterns = detect_behavioral_patterns(raw["frames"], raw["ui_events"])
    urls, files = extract_urls_and_files(raw["frames"])
    task = infer_current_task(time_data, patterns, urls, files, raw["audio"])

    audio_snippet = None
    if raw["audio"]:
        audio_snippet = raw["audio"][0].get("transcription", "")[:200]

    context = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": VERSION,
        "current_state": {
            "app": time_data["current"]["app"] if time_data.get("current") else None,
            "window": time_data["current"]["window"] if time_data.get("current") else None,
            "minutes_on_current": time_data["current"]["minutes_on_current"] if time_data.get("current") else 0,
            "behavioral_state": patterns["state"],
        },
        "task": task,
        "activity": {
            "apps_by_time": time_data["apps"],
            "recent_urls": urls[:5],
            "recent_files": files[:5],
            "app_switches_per_min": patterns["app_switches_per_min"],
        },
        "signals": patterns["signals"],
        "audio_snippet": audio_snippet,
        "meta": {
            "frames_analyzed": len(raw["frames"]),
            "window_minutes": WINDOW_MINUTES,
        }
    }

    # Write cache
    Path(CACHE_PATH).parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(context, f)
    except Exception as e:
        print(f"Cache write error: {e}", flush=True)

    return context


def read_cache():
    """Read pre-computed context. <5ms."""
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return build_context()


# ============================================================
# HTTP Server
# ============================================================

class NoctaHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for the Nocta context API."""

    def log_message(self, format, *args):
        """Suppress default request logging."""
        pass

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/context":
            self._respond(200, read_cache())

        elif path == "/health":
            self._respond(200, {
                "status": "ok",
                "version": VERSION,
                "uptime_seconds": round(time.time() - START_TIME, 1),
                "recorder_db_exists": os.path.exists(RECORDER_DB),
            })

        elif path == "/status":
            ctx = read_cache()
            recorder_running = False
            try:
                import subprocess
                result = subprocess.run(["pgrep", "-f", "screenpipe"], capture_output=True)
                recorder_running = result.returncode == 0
            except Exception:
                pass

            self._respond(200, {
                "version": VERSION,
                "daemon": "running",
                "recorder": "running" if recorder_running else "stopped",
                "last_update": ctx.get("timestamp"),
                "current_task": ctx.get("task", {}).get("description"),
                "behavioral_state": ctx.get("current_state", {}).get("behavioral_state"),
                "uptime_seconds": round(time.time() - START_TIME, 1),
            })

        elif path == "/":
            self._respond(200, {
                "name": "nocta",
                "version": VERSION,
                "endpoints": ["/context", "/health", "/status"],
                "docs": "https://nocta.dev/docs",
            })

        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/context":
            # POST also works for /context (for Claude Code hooks)
            ctx = read_cache()
            # Return in hook-compatible format
            self._respond(200, {
                "additionalContext": format_context_for_agent(ctx),
                "context": ctx,
            })
        else:
            self._respond(404, {"error": "not found"})

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def format_context_for_agent(ctx):
    """Format context as a concise text block for injection into agent prompts."""
    if not ctx or ctx.get("error"):
        return ""

    lines = ["[Nocta Context — what the user is doing right now]"]

    state = ctx.get("current_state", {})
    task = ctx.get("task", {})
    activity = ctx.get("activity", {})
    signals = ctx.get("signals", [])

    if task.get("description") and task.get("confidence", 0) > 0.3:
        lines.append(f"Current task: {task['description']} (confidence: {task['confidence']:.0%})")

    if state.get("app"):
        lines.append(f"Active app: {state['app']}")
        if state.get("minutes_on_current", 0) > 1:
            lines.append(f"Time on current: {state['minutes_on_current']} min")

    if state.get("behavioral_state") and state["behavioral_state"] != "unknown":
        lines.append(f"State: {state['behavioral_state']}")

    files = activity.get("recent_files", [])
    if files:
        lines.append(f"Recent files: {', '.join(files[:3])}")

    urls = activity.get("recent_urls", [])
    if urls:
        lines.append(f"Recent pages: {', '.join(u[:50] for u in urls[:3])}")

    if signals:
        lines.append(f"Signals: {', '.join(signals)}")

    audio = ctx.get("audio_snippet")
    if audio and len(audio) > 20:
        lines.append(f"Recent audio: \"{audio[:100]}...\"")

    apps = activity.get("apps_by_time", {})
    if apps:
        top3 = list(apps.items())[:3]
        lines.append(f"Time today: {', '.join(f'{k} ({v}min)' for k, v in top3)}")

    lines.append("[End Nocta Context]")
    return "\n".join(lines)


# ============================================================
# Background Updater
# ============================================================

def updater_loop():
    """Background thread that updates context cache every N seconds."""
    while True:
        try:
            ctx = build_context()
            state = ctx.get("current_state", {}).get("behavioral_state", "?")
            task = ctx.get("task", {}).get("description", "?")[:50]
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] {state:10s} | {task}", flush=True)
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Updater error: {e}", flush=True)
        time.sleep(UPDATE_INTERVAL)


# ============================================================
# Main
# ============================================================

START_TIME = time.time()


def main():
    # Ensure directories exist
    Path(CACHE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(PID_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(os.path.expanduser("~/.nocta/logs")).mkdir(parents=True, exist_ok=True)

    # Write PID file
    with open(PID_PATH, "w") as f:
        f.write(str(os.getpid()))

    # Handle graceful shutdown
    def shutdown(sig, frame):
        print("\nShutting down...", flush=True)
        try:
            os.remove(PID_PATH)
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Start background updater thread
    updater = threading.Thread(target=updater_loop, daemon=True)
    updater.start()

    # Build initial context
    build_context()

    # Start HTTP server
    server = http.server.HTTPServer(("127.0.0.1", PORT), NoctaHandler)
    print(f"Nocta v{VERSION} running on http://127.0.0.1:{PORT}", flush=True)
    print(f"  Context API: GET http://127.0.0.1:{PORT}/context", flush=True)
    print(f"  Recorder DB: {RECORDER_DB}", flush=True)
    print(f"  Update interval: {UPDATE_INTERVAL}s", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        shutdown(None, None)


if __name__ == "__main__":
    main()
