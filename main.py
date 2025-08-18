from flask import Flask
from routes import main_bp
from flask_compress import Compress  # <-- added

app = Flask(__name__)
Compress(app)  # <-- added: enables gzip/brotli compression for HTML, CSS, JS, JSON

app.register_blueprint(main_bp)

# Needed for Render deployment
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
