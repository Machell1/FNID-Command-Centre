"""
FNID Portal - Main Entry Point

Right-click this file in PyCharm and select "Run 'main'" to start the server.
Or double-click start.bat from File Explorer.

Opens http://127.0.0.1:5000 in your browser automatically.
"""

import threading
import webbrowser

from dotenv import load_dotenv

load_dotenv()

from fnid_portal import create_app

app = create_app()


def open_browser():
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    print("=" * 50)
    print("  FNID Area 3 Operational Portal")
    print("  http://127.0.0.1:5000")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    threading.Timer(1.5, open_browser).start()
    import os
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(host="127.0.0.1", port=5000, debug=debug, use_reloader=False)
