"""JSON API routes for AJAX chart data."""

from flask import Blueprint, jsonify
from flask_login import login_required

from ..models import get_db

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/stats/<unit>")
@login_required
def api_stats(unit):
    conn = get_db()
    result = {}

    if unit == "command":
        result = {
            "intel": conn.execute("SELECT COUNT(*) FROM intel_reports").fetchone()[0],
            "operations": conn.execute("SELECT COUNT(*) FROM operations").fetchone()[0],
            "firearms": conn.execute("SELECT COUNT(*) FROM firearm_seizures").fetchone()[0],
            "narcotics": conn.execute("SELECT COUNT(*) FROM narcotics_seizures").fetchone()[0],
            "arrests": conn.execute("SELECT COUNT(*) FROM arrests").fetchone()[0],
            "cases": conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
        }

    conn.close()
    return jsonify(result)
