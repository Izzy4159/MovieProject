from flask import Flask
from routes import main_bp

app = Flask(__name__)  # No need for static_folder='posters'
app.register_blueprint(main_bp)

# Needed for Render deployment
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
