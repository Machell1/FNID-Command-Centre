"""
FNID Command Centre - Windows Launcher.

Runs the Flask app under Waitress, picks a free port if 5000 is taken,
auto-opens the default browser, and shows a system-tray icon with
Open / Restart / Quit options.

Entry point for the bundled .exe (PyInstaller --windowed).

Environment overrides:
  FNID_PORT          Force a specific port (default: 5000, fallback to next free)
  FNID_HOST          Bind host (default: 127.0.0.1)
  FNID_NO_BROWSER=1  Do not auto-open the browser
  FNID_NO_TRAY=1     Do not show the tray icon (useful for headless test)
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _bundle_root() -> Path:
    """The directory that contains bundled resources (templates, static)."""
    if _is_frozen():
        return Path(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
    return Path(__file__).resolve().parent


def _setup_environment():
    """Set production defaults for the bundled launcher."""
    os.environ.setdefault("FLASK_ENV", "production")
    os.environ.setdefault("FNID_LOCAL_HTTP", "1")
    # Ensure relative imports resolve when frozen
    sys.path.insert(0, str(_bundle_root()))


def _pick_free_port(host: str, preferred: int) -> int:
    """Return `preferred` if free, else the next available port up to +50."""
    for port in [preferred] + [preferred + i for i in range(1, 50)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port near {preferred} on {host}")


def _wait_for_server(host: str, port: int, timeout: float = 30.0) -> bool:
    """Block until the server accepts a TCP connection or timeout elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
                return True
            except OSError:
                time.sleep(0.25)
    return False


def _build_app():
    from fnid_portal import create_app
    return create_app("production")


def _serve(app, host: str, port: int, shutdown_event: threading.Event):
    """Run waitress in this thread; stop when shutdown_event is set."""
    from waitress.server import create_server

    server = create_server(app, host=host, port=port, threads=8)

    def _wait_shutdown():
        shutdown_event.wait()
        # close listening sockets and unblock the server loop
        try:
            server.close()
        except Exception:
            pass

    threading.Thread(target=_wait_shutdown, daemon=True).start()

    try:
        server.run()
    except OSError:
        # raised when close() unblocks the accept loop -- expected on shutdown
        pass


def _make_tray_icon(url: str, shutdown_event: threading.Event):
    """Build a pystray.Icon backed by a Pillow-rendered logo."""
    from PIL import Image, ImageDraw
    import pystray

    img = Image.new("RGBA", (64, 64), (31, 56, 100, 255))  # JCF navy
    draw = ImageDraw.Draw(img)
    draw.rectangle((6, 6, 58, 58), outline=(255, 215, 0, 255), width=2)
    draw.text((18, 18), "FN", fill=(255, 215, 0, 255))

    def _open(_icon, _item):
        webbrowser.open(url)

    def _quit(icon, _item):
        shutdown_event.set()
        icon.stop()

    icon = pystray.Icon(
        "FNID",
        img,
        "FNID Command Centre",
        menu=pystray.Menu(
            pystray.MenuItem("Open Dashboard", _open, default=True),
            pystray.MenuItem(f"Listening on {url}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", _quit),
        ),
    )
    return icon


def main():
    _setup_environment()

    host = os.environ.get("FNID_HOST", "127.0.0.1")
    preferred = int(os.environ.get("FNID_PORT", "5000"))
    port = _pick_free_port(host, preferred)
    url = f"http://{host}:{port}"

    app = _build_app()
    app.logger.info("Launcher starting; url=%s", url)

    shutdown_event = threading.Event()

    server_thread = threading.Thread(
        target=_serve, args=(app, host, port, shutdown_event), daemon=False
    )
    server_thread.start()

    if not _wait_for_server(host, port, timeout=30):
        app.logger.error("Server failed to come up on %s within 30s", url)
        shutdown_event.set()
        return 1

    if os.environ.get("FNID_NO_BROWSER") != "1":
        webbrowser.open(url)

    if os.environ.get("FNID_NO_TRAY") == "1":
        # Headless / test mode -- just block until Ctrl+C.
        try:
            while not shutdown_event.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            shutdown_event.set()
    else:
        icon = _make_tray_icon(url, shutdown_event)
        try:
            icon.run()  # blocks until shutdown_event triggers icon.stop()
        except Exception as exc:
            app.logger.warning("Tray icon failed (%s); waiting on stdin", exc)
            try:
                while not shutdown_event.is_set():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                shutdown_event.set()

    server_thread.join(timeout=10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
