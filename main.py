from flask import Flask, request, jsonify
from routes import main_bp

try:
    from flask_compress import Compress
except Exception:
    Compress = None

import os
import sys
import time
import threading
import webbrowser

# -----------------------
# Flask app setup
# -----------------------
app = Flask(__name__)

if Compress:
    Compress(app)

app.register_blueprint(main_bp)

# -----------------------
# Heartbeat tracker
# -----------------------
# The browser page sends a /heartbeat ping every 3 seconds.
# If we don't hear from it for more than TIMEOUT seconds, we shut down.
TIMEOUT = 8  # seconds — long enough to survive a page reload

_last_heartbeat = time.time()

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    global _last_heartbeat
    _last_heartbeat = time.time()
    return jsonify(ok=True)

def _watchdog():
    """Background thread: shuts down if browser goes silent."""
    # Give the browser a moment to actually open before we start watching
    time.sleep(6)
    while True:
        time.sleep(2)
        if time.time() - _last_heartbeat > TIMEOUT:
            print("\n[Watchdog] Browser closed — shutting down. Goodbye!")
            os._exit(0)

# -----------------------
# Run + auto-open browser
# -----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    url  = f"http://127.0.0.1:{port}/"

    # Start watchdog
    t = threading.Thread(target=_watchdog, daemon=True)
    t.start()

    # Open browser after Flask is up
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    print(f"Starting Movie Poster Grid → {url}")
    print("Close the browser tab to shut down.\n")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )