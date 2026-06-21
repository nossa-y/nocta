#!/usr/bin/env python3
"""
Decrypt and export cookies from Chromium-based browsers on macOS.

Supports Chrome, Arc, Brave, Edge, Chromium. Reads the encrypted cookie
store, derives the AES key from macOS Keychain, decrypts, and outputs
JSON compatible with Playwright/CDP cookie loading.

Based on: nocta/scripts/extract_chrome_cookie.py (LinkedIn-only version)
Verified against: gstack cookie-import-browser.ts (626 lines)

Usage:
    python3 cookie-import.py --browser chrome --domains github.com -o /tmp/cookies.json
    python3 cookie-import.py --browser chrome --list-profiles
    python3 cookie-import.py --browser chrome --list-domains
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

# ── Browser registry ──
# Matches gstack's BROWSER_REGISTRY exactly (keychainService values verified)

BROWSERS = {
    "chrome":   {"data_dir": "Google/Chrome",              "keychain": "Chrome Safe Storage"},
    "arc":      {"data_dir": "Arc/User Data",              "keychain": "Arc Safe Storage"},
    "brave":    {"data_dir": "BraveSoftware/Brave-Browser", "keychain": "Brave Safe Storage"},
    "edge":     {"data_dir": "Microsoft Edge",             "keychain": "Microsoft Edge Safe Storage"},
    "chromium": {"data_dir": "Chromium",                   "keychain": "Chromium Safe Storage"},
}

CHROMIUM_EPOCH_OFFSET = 11644473600000000
BASE_DIR = os.path.expanduser("~/Library/Application Support")


def get_keychain_password(service):
    """Get encryption password from macOS Keychain. 10s timeout for dialog."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        print(f"Keychain timed out. Look for a dialog asking to allow '{service}'.", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        stderr = result.stderr.strip().lower()
        if "not found" in stderr or "could not be found" in stderr:
            print(f"No Keychain entry for '{service}'. Is this browser installed?", file=sys.stderr)
        elif "denied" in stderr or "canceled" in stderr:
            print(f"Keychain access denied. Click 'Allow' in the macOS dialog.", file=sys.stderr)
        else:
            print(f"Keychain error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    return result.stdout.strip()


def derive_key(password):
    """Derive AES-128 key via PBKDF2. Matches gstack: salt='saltysalt', iter=1003, SHA1."""
    return hashlib.pbkdf2_hmac("sha1", password.encode("utf-8"), b"saltysalt", 1003, dklen=16)


def open_cookie_db(db_path, browser_name):
    """Open cookie SQLite DB. If locked (browser running), copy to temp first."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.execute("SELECT 1 FROM cookies LIMIT 1")
        return conn, None
    except sqlite3.OperationalError:
        pass

    # DB locked - copy it (including WAL + SHM for consistency)
    tmp = tempfile.mktemp(suffix=f"-{browser_name}-cookies.db")
    shutil.copy2(db_path, tmp)
    for ext in ("-wal", "-shm"):
        src = db_path + ext
        if os.path.exists(src):
            shutil.copy2(src, tmp + ext)

    try:
        conn = sqlite3.connect(tmp)
        return conn, tmp
    except Exception:
        for f in (tmp, tmp + "-wal", tmp + "-shm"):
            try:
                os.unlink(f)
            except OSError:
                pass
        print(f"Cookie DB is locked. Try closing {browser_name}.", file=sys.stderr)
        sys.exit(1)


def decrypt_cookie_value(encrypted_value, derived_key):
    """
    Decrypt a single cookie value.

    Algorithm (verified against gstack cookie-import-browser.ts lines 568-587):
    1. Skip 3-byte version prefix ("v10" or "v11")
    2. AES-128-CBC with IV = 16 space characters (0x20)
    3. Remove PKCS7 padding
    4. Skip first 32 bytes of Chromium cookie metadata
    5. Remaining bytes = cookie value (UTF-8)
    """
    if not encrypted_value or len(encrypted_value) <= 3:
        return ""

    # Import here to avoid top-level dependency check
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding

    ciphertext = encrypted_value[3:]  # strip "v10"/"v11" prefix
    iv = b"\x20" * 16  # 16 space characters

    cipher = Cipher(algorithms.AES(derived_key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    # Remove PKCS7 padding
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(plaintext) + unpadder.finalize()

    # Skip 32-byte Chromium metadata prefix (verified in gstack source)
    if len(plaintext) <= 32:
        return ""
    return plaintext[32:].decode("utf-8", errors="replace")


def chromium_epoch_to_unix(epoch, has_expires):
    """Convert Chromium epoch (microseconds since 1601-01-01) to Unix seconds."""
    if has_expires == 0 or epoch == 0:
        return -1
    return (epoch - CHROMIUM_EPOCH_OFFSET) // 1000000


def sameSite_map(value):
    """Map Chromium sameSite int to string. Matches gstack: 0=None, 1=Lax, 2=Strict."""
    return {0: "None", 1: "Lax", 2: "Strict"}.get(value, "Lax")


def get_browser_dir(browser_name):
    """Resolve browser data directory."""
    browser = BROWSERS.get(browser_name.lower())
    if not browser:
        supported = ", ".join(BROWSERS.keys())
        print(f"Unknown browser '{browser_name}'. Supported: {supported}", file=sys.stderr)
        sys.exit(1)
    return os.path.join(BASE_DIR, browser["data_dir"]), browser


def list_profiles(browser_name):
    """List available profiles for a browser."""
    browser_dir, _ = get_browser_dir(browser_name)
    if not os.path.exists(browser_dir):
        print(f"Browser directory not found: {browser_dir}", file=sys.stderr)
        return []

    profiles = []
    for entry in sorted(os.listdir(browser_dir)):
        if entry != "Default" and not entry.startswith("Profile "):
            continue
        cookie_path = os.path.join(browser_dir, entry, "Cookies")
        if not os.path.exists(cookie_path):
            continue

        # Try to read display name from Preferences (email > profile name > dir name)
        display_name = entry
        prefs_path = os.path.join(browser_dir, entry, "Preferences")
        try:
            with open(prefs_path) as f:
                prefs = json.load(f)
            email = (prefs.get("account_info") or [{}])[0].get("email")
            if email:
                display_name = email
            else:
                pname = (prefs.get("profile") or {}).get("name")
                if pname:
                    display_name = pname
        except (OSError, json.JSONDecodeError, IndexError, KeyError):
            pass

        profiles.append({"name": entry, "display_name": display_name})

    return profiles


def list_domains(browser_name, profile="Default"):
    """List cookie domains with counts (no decryption needed)."""
    browser_dir, browser = get_browser_dir(browser_name)
    db_path = os.path.join(browser_dir, profile, "Cookies")
    if not os.path.exists(db_path):
        print(f"Cookie DB not found: {db_path}", file=sys.stderr)
        return []

    conn, tmp = open_cookie_db(db_path, browser_name)
    try:
        rows = conn.execute(
            "SELECT host_key, COUNT(*) as cnt FROM cookies GROUP BY host_key ORDER BY cnt DESC"
        ).fetchall()
        return [{"domain": r[0], "count": r[1]} for r in rows]
    finally:
        conn.close()
        if tmp:
            for f in (tmp, tmp + "-wal", tmp + "-shm"):
                try:
                    os.unlink(f)
                except OSError:
                    pass


def export_cookies(browser_name, profile="Default", domains=None):
    """Decrypt and export cookies as JSON-serializable dicts."""
    browser_dir, browser = get_browser_dir(browser_name)
    db_path = os.path.join(browser_dir, profile, "Cookies")
    if not os.path.exists(db_path):
        print(f"Cookie DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    # Get encryption key
    password = get_keychain_password(browser["keychain"])
    derived_key = derive_key(password)

    # Open DB
    conn, tmp = open_cookie_db(db_path, browser_name)

    try:
        if domains:
            # Filter by domains - also match with leading dot
            all_domains = set()
            for d in domains:
                all_domains.add(d)
                if not d.startswith("."):
                    all_domains.add("." + d)
            placeholders = ",".join("?" * len(all_domains))
            query = f"""
                SELECT host_key, name, value, encrypted_value, path,
                       expires_utc, is_secure, is_httponly, has_expires, samesite
                FROM cookies
                WHERE host_key IN ({placeholders})
                ORDER BY host_key, name
            """
            rows = conn.execute(query, list(all_domains)).fetchall()
        else:
            rows = conn.execute("""
                SELECT host_key, name, value, encrypted_value, path,
                       expires_utc, is_secure, is_httponly, has_expires, samesite
                FROM cookies
                ORDER BY host_key, name
            """).fetchall()

        cookies = []
        failed = 0
        for host_key, name, value, enc_val, path, expires, secure, httponly, has_exp, samesite in rows:
            try:
                if value:
                    cookie_value = value
                else:
                    cookie_value = decrypt_cookie_value(enc_val, derived_key)

                cookies.append({
                    "name": name,
                    "value": cookie_value,
                    "domain": host_key,
                    "path": path or "/",
                    "expires": chromium_epoch_to_unix(expires, has_exp),
                    "secure": secure == 1,
                    "httpOnly": httponly == 1,
                    "sameSite": sameSite_map(samesite),
                })
            except Exception:
                failed += 1

        return cookies, failed

    finally:
        conn.close()
        if tmp:
            for f in (tmp, tmp + "-wal", tmp + "-shm"):
                try:
                    os.unlink(f)
                except OSError:
                    pass


def main():
    parser = argparse.ArgumentParser(
        description="Decrypt and export cookies from Chromium-based browsers."
    )
    parser.add_argument("--browser", "-b", default="chrome",
                        help="Browser name: chrome, arc, brave, edge, chromium (default: chrome)")
    parser.add_argument("--profile", "-p", default="Default",
                        help="Profile directory name (default: Default)")
    parser.add_argument("--domains", "-d", nargs="+",
                        help="Domain(s) to export (e.g. github.com .google.com)")
    parser.add_argument("--output", "-o",
                        help="Output file path (default: stdout)")
    parser.add_argument("--list-profiles", action="store_true",
                        help="List available profiles for the browser")
    parser.add_argument("--list-domains", action="store_true",
                        help="List all cookie domains with counts")
    args = parser.parse_args()

    if args.list_profiles:
        profiles = list_profiles(args.browser)
        if not profiles:
            print("No profiles found.", file=sys.stderr)
            sys.exit(1)
        for p in profiles:
            print(f"{p['name']}: {p['display_name']}")
        return

    if args.list_domains:
        domains = list_domains(args.browser, args.profile)
        if not domains:
            print("No cookies found.", file=sys.stderr)
            sys.exit(1)
        for d in domains:
            print(f"{d['count']:>6}  {d['domain']}")
        return

    # Export cookies
    cookies, failed = export_cookies(args.browser, args.profile, args.domains)

    output = json.dumps(cookies, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Exported {len(cookies)} cookies to {args.output}" +
              (f" ({failed} failed)" if failed else ""), file=sys.stderr)
    else:
        print(output)
        if failed:
            print(f"({failed} cookies failed to decrypt)", file=sys.stderr)


if __name__ == "__main__":
    main()
