"""
FNID Portal — Development entry point.

For local dev:
    python main.py            # Flask debug server on http://127.0.0.1:5000

The installed Windows build does NOT use this file; it boots `launcher.py`
through PyInstaller's `FNID-Command-Centre.exe`. Keep this script lean: it
exists so a developer can iterate without the bundled launcher.
"""
import os
import threading
import webbrowser

from dotenv import load_dotenv

load_dotenv()

# Default to keeping data inside the repo when developing.
os.environ.setdefault("FNID_USE_REPO_DATA", "1")

from fnid_portal import create_app

app = create_app()


def _open_browser():
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    print("=" * 50)
    print("  FNID Area 3 Operational Portal (dev)")
    print("  http://127.0.0.1:5000")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    if os.environ.get("FNID_NO_BROWSER") != "1":
        threading.Timer(1.5, _open_browser).start()
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(host="127.0.0.1", port=5000, debug=debug, use_reloader=False)
