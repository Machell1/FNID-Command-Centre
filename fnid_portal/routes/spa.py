"""SPA catch-all route — serves the React frontend."""

import os

from flask import Blueprint, send_from_directory

bp = Blueprint("spa", __name__)

SPA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "spa")


@bp.route("/app/")
@bp.route("/app/<path:path>")
def serve_spa(path=""):
    """Serve the React SPA for all /app/ routes."""
    if path and os.path.isfile(os.path.join(SPA_DIR, path)):
        return send_from_directory(SPA_DIR, path)
    index = os.path.join(SPA_DIR, "index.html")
    if os.path.isfile(index):
        return send_from_directory(SPA_DIR, "index.html")
    return "<h1>FNID React SPA</h1><p>Run <code>cd frontend && npm run build</code> to build the SPA.</p>", 200
