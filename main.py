from flask import Flask
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
# Shutdown timer
# -----------------------
def _shutdown_timer():
    """Background thread: shuts down exactly 30 minutes after startup."""
    time.sleep(1800)
    print("\n[Timer] 30 minutes elapsed — shutting down. Goodbye!")
    os._exit(0)

# -----------------------
# Run + auto-open browser
# -----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    url  = f"http://127.0.0.1:{port}/"

    # Start shutdown timer
    t = threading.Thread(target=_shutdown_timer, daemon=True)
    t.start()

    # Open browser after Flask is up
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    print(f"Starting Movie Poster Grid → {url}")
    print("Server will automatically shut down in 30 minutes.\n")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )