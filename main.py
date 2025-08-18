from flask import Flask
from routes import main_bp

# Make Flask-Compress optional so the app still runs without it
try:
    from flask_compress import Compress
except Exception:
    Compress = None

app = Flask(__name__)

if Compress:
    Compress(app)  # enables gzip/brotli if available

app.register_blueprint(main_bp)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
