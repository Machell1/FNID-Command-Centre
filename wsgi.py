"""
FNID Command Centre v2.0 - WSGI Entry Point
Production Gunicorn Configuration
"""
from dotenv import load_dotenv

load_dotenv()

from fnid_portal import create_app  # noqa: E402

app = create_app("production")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
