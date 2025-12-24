from flask import Flask, request
from routes import main_bp

# Make Flask-Compress optional so the app still runs without it
try:
    from flask_compress import Compress
except Exception:
    Compress = None

import os
import threading
import webbrowser
import sys

# -----------------------
# Flask app setup
# -----------------------
app = Flask(__name__)

if Compress:
    Compress(app)  # enables gzip/brotli if available

app.register_blueprint(main_bp)

# -----------------------
# Shutdown endpoint
# -----------------------
@app.route("/shutdown", methods=["POST"])
def shutdown():
    func = request.environ.get("werkzeug.server.shutdown")
    if func is None:
        sys.exit(0)
    func()
    return "Server shutting down..."

# -----------------------
# Run + auto-open browser
# -----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    url = f"http://127.0.0.1:{port}/"

    def open_browser():
        webbrowser.open(url)

    # Open browser shortly after server starts
    threading.Timer(1.0, open_browser).start()

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )
