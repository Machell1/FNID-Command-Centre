"""JSON API dashboard endpoints for the React SPA."""

from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from ...constants import UNIT_PORTALS
from ...models import get_db

bp = Blueprint("api_dashboard", __name__, url_prefix="/api/v1/dashboard")


@bp.route("/")
@login_required
def home():
    """Return dashboard data for the home page."""
    conn = get_db()
    try:
        stats = {
            "cases": conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
            "intel": conn.execute("SELECT COUNT(*) FROM intel_reports").fetchone()[0],
            "operations": conn.execute("SELECT COUNT(*) FROM operations").fetchone()[0],
            "firearms": conn.execute("SELECT COUNT(*) FROM firearm_seizures").fetchone()[0],
            "narcotics": conn.execute("SELECT COUNT(*) FROM narcotics_seizures").fetchone()[0],
            "arrests": conn.execute("SELECT COUNT(*) FROM arrests").fetchone()[0],
        }

        # Recent activity
        recent = []
        rows = conn.execute("""
            SELECT table_name, action, officer_badge, officer_name,
                   details, created_at
            FROM audit_log ORDER BY created_at DESC LIMIT 10
        """).fetchall()
        for r in rows:
            recent.append({
                "table": r["table_name"],
                "action": r["action"],
                "badge": r["officer_badge"],
                "name": r["officer_name"],
                "details": r["details"],
                "time": r["created_at"],
            })

        # Alerts (overdue deadlines, etc.)
        alerts = []
        try:
            alert_rows = conn.execute("""
                SELECT id, alert_type, severity, title, message, created_at
                FROM notifications
                WHERE badge_number = ? AND read_at IS NULL
                ORDER BY created_at DESC LIMIT 5
            """, (current_user.badge_number,)).fetchall()
            for a in alert_rows:
                alerts.append({
                    "id": a["id"],
                    "type": a["alert_type"],
                    "severity": a["severity"],
                    "title": a["title"],
                    "message": a["message"],
                    "time": a["created_at"],
                })
        except Exception:
            pass

        # Filter portals by user access
        visible_portals = {}
        assigned = set()
        if hasattr(current_user, "get_assigned_units"):
            assigned = current_user.get_assigned_units()
        for key, portal in UNIT_PORTALS.items():
            if not assigned or key in assigned or current_user.role in ("admin", "dco", "ddi"):
                visible_portals[key] = portal

        return jsonify({
            "stats": stats,
            "recent_activity": recent,
            "alerts": alerts,
            "portals": visible_portals,
            "user": {
                "badge_number": current_user.badge_number,
                "full_name": current_user.full_name,
                "rank": current_user.rank,
                "role": current_user.role,
            },
        })
    finally:
        conn.close()


@bp.route("/command")
@login_required
def command():
    """Return command-level dashboard stats for charts."""
    conn = get_db()
    try:
        monthly_data = []
        rows = conn.execute("""
            SELECT strftime('%Y-%m', created_at) AS month,
                   COUNT(*) AS count
            FROM cases
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """).fetchall()
        for r in rows:
            monthly_data.append({"month": r["month"], "count": r["count"]})

        seizure_types = {
            "firearms": conn.execute("SELECT COUNT(*) FROM firearm_seizures").fetchone()[0],
            "narcotics": conn.execute("SELECT COUNT(*) FROM narcotics_seizures").fetchone()[0],
        }

        case_status = []
        rows = conn.execute("""
            SELECT status, COUNT(*) AS count
            FROM cases
            GROUP BY status
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()
        for r in rows:
            case_status.append({"status": r["status"], "count": r["count"]})

        return jsonify({
            "monthly_cases": monthly_data,
            "seizure_types": seizure_types,
            "case_status": case_status,
        })
    finally:
        conn.close()


@bp.route("/notifications/count")
@login_required
def notification_count():
    """Return unread notification count."""
    conn = get_db()
    try:
        total = conn.execute("""
            SELECT COUNT(*) FROM notifications
            WHERE badge_number = ? AND read_at IS NULL
        """, (current_user.badge_number,)).fetchone()[0]
        critical = conn.execute("""
            SELECT COUNT(*) FROM notifications
            WHERE badge_number = ? AND read_at IS NULL AND severity = 'critical'
        """, (current_user.badge_number,)).fetchone()[0]
        return jsonify({"total": total, "critical": critical})
    except Exception:
        return jsonify({"total": 0, "critical": 0})
    finally:
        conn.close()
