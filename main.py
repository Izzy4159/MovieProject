from flask import Flask, request
from routes import main_bp

try:
    from flask_compress import Compress
except Exception:
    Compress = None

import os
import sys
import time
import socket
import argparse
import threading
import webbrowser

# -----------------------
# Flask app setup
# -----------------------
app = Flask(__name__)

if Compress:
    Compress(app)

app.register_blueprint(main_bp)

ON_RENDER = bool(os.environ.get("RENDER"))   # Render sets RENDER=true on every service

# -----------------------
# Watchdog: stop when the last browser tab closes
# -----------------------
# Every open tab POSTs /heartbeat every 15 s (static/heartbeat.js) and /bye on
# close. Background tabs can be throttled to one timer per minute, hence the
# long grace for a tab that just goes quiet.
WATCHDOG_MINUTES  = 30    # no tab ever connected → stop after this
TAB_QUIET_SECONDS = 180   # a tab that stops checking in is considered closed
EMPTY_GRACE_SECS  = 10    # no tabs left → wait this long (covers a page reload)

_wd_lock     = threading.Lock()
_wd_tabs     = {}                  # tab id → last heartbeat (monotonic)
_wd_state    = {"ever": False, "empty_since": None, "last_request": time.monotonic()}

@app.before_request
def _wd_note_request():
    # Launcher polling /health must not keep an abandoned server alive
    if request.path != "/health":
        _wd_state["last_request"] = time.monotonic()

@app.route("/health")
def health():
    return {"ok": True}

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    tab = (request.form.get("tab") or "")[:40]
    if tab:
        with _wd_lock:
            _wd_tabs[tab] = time.monotonic()
            _wd_state["ever"] = True
            _wd_state["empty_since"] = None
    return ("", 204)

@app.route("/bye", methods=["POST"])
def bye():
    tab = (request.form.get("tab") or request.get_data(as_text=True).partition("tab=")[2])[:40]
    with _wd_lock:
        _wd_tabs.pop(tab, None)
        if not _wd_tabs and _wd_state["empty_since"] is None:
            _wd_state["empty_since"] = time.monotonic()
    return ("", 204)

def _watchdog_loop():
    """Background thread: exits the process once no browser tab is left open."""
    started = time.monotonic()
    while True:
        time.sleep(2)
        now = time.monotonic()
        with _wd_lock:
            for tab, seen in list(_wd_tabs.items()):
                if now - seen > TAB_QUIET_SECONDS:
                    del _wd_tabs[tab]
                    if not _wd_tabs:
                        _wd_state["empty_since"] = now
            if _wd_tabs:
                continue
            if not _wd_state["ever"]:
                if now - started < WATCHDOG_MINUTES * 60:
                    continue
                reason = f"no browser tab connected within {WATCHDOG_MINUTES} minutes"
            else:
                idle_from = max(_wd_state["empty_since"] or now, _wd_state["last_request"])
                if now - idle_from < EMPTY_GRACE_SECS:
                    continue
                reason = "last browser tab closed"
        print(f"\n[Watchdog] {reason} — shutting down. Goodbye!", flush=True)
        os._exit(0)

def _env_flag(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() not in ("0", "false", "no", "off", "")

def _lan_ip() -> str | None:
    """Best-effort local network IP (no packets are actually sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None

def _parse_args():
    p = argparse.ArgumentParser(description="Movie Poster Explorer")
    p.add_argument("--host", default=os.environ.get("HOST") or ("0.0.0.0" if ON_RENDER else "127.0.0.1"),
                   help="Interface to bind (use 0.0.0.0 for LAN/phone access). Env: HOST")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)),
                   help="Port to listen on. Env: PORT")
    p.add_argument("--no-watchdog", action="store_true",
                   help="Keep running after the last browser tab closes. Env: WATCHDOG=0")
    p.add_argument("--no-browser", action="store_true",
                   help="Don't open a browser tab on startup. Env: OPEN_BROWSER=0")
    return p.parse_args()

# -----------------------
# Run + auto-open browser
# -----------------------
if __name__ == "__main__":
    args = _parse_args()
    # Redirected stdout on Windows is cp1252 — don't crash on the → in log lines
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    watchdog     = not args.no_watchdog and _env_flag("WATCHDOG", True) and not ON_RENDER
    open_browser = not args.no_browser and _env_flag("OPEN_BROWSER", True) and not ON_RENDER

    local_url = f"http://127.0.0.1:{args.port}/"
    print(f"Starting Movie Poster Grid → {local_url}")
    if args.host == "0.0.0.0":
        ip = _lan_ip()
        if ip:
            print(f"On your phone (same Wi-Fi) → http://{ip}:{args.port}/")

    if watchdog:
        threading.Thread(target=_watchdog_loop, daemon=True).start()
        print("Server stops automatically when its last browser tab closes "
              "(disable with --no-watchdog or WATCHDOG=0).\n")
    else:
        print("Watchdog disabled — server runs until stopped.\n")

    if open_browser:
        # Open browser after Flask is up
        threading.Timer(1.2, lambda: webbrowser.open(local_url)).start()

    app.run(
        host=args.host,
        port=args.port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
