from flask import Flask
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
# Shutdown timer (the "watchdog")
# -----------------------
WATCHDOG_MINUTES = 30

def _shutdown_timer():
    """Background thread: shuts down WATCHDOG_MINUTES after startup."""
    time.sleep(WATCHDOG_MINUTES * 60)
    print(f"\n[Timer] {WATCHDOG_MINUTES} minutes elapsed — shutting down. Goodbye!")
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
                   help=f"Don't auto-shutdown after {WATCHDOG_MINUTES} minutes. Env: WATCHDOG=0")
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
        threading.Thread(target=_shutdown_timer, daemon=True).start()
        print(f"Server will automatically shut down in {WATCHDOG_MINUTES} minutes "
              f"(disable with --no-watchdog or WATCHDOG=0).\n")
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
