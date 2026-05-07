"""Main routes: home page, command dashboard, and alerts."""

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..constants import UNIT_PORTALS
from ..deadlines import get_alerts_for_user
from ..models import get_db

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def home():
    # Redirect single-unit basic users directly to their unit
    single_unit = current_user.get_single_unit()
    if single_unit:
        return redirect(url_for("units.unit_home", unit=single_unit))

    # Regular users get a limited dashboard
    if getattr(current_user, "role", "viewer") == "user":
        return _user_dashboard()

    conn = get_db()
    stats = {}
    table_map = {
        "intel": "intel_reports",
        "operations": "operations",
        "seizures": "firearm_seizures",
        "arrests": "arrests",
        "forensics": "chain_of_custody",
        "registry": "cases",
    }

    # Filter visible portals for multi-unit (non-"all") users
    user_units = current_user.get_assigned_units()
    visible_portals = {k: v for k, v in UNIT_PORTALS.items() if k in user_units}

    for unit_key in visible_portals:
        table = table_map.get(unit_key, "cases")
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        stats[unit_key] = count

    # Get alerts for current user
    alerts = []
    try:
        badge = getattr(current_user, "badge_number", None)
        role = getattr(current_user, "role", "viewer")
        alerts = get_alerts_for_user(badge=badge, role=role)
    except Exception:
        pass

    # Recent activity (last 10 audit entries)
    recent = conn.execute("""
        SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 10
    """).fetchall()

    conn.close()
    return render_template("home.html", stats=stats, alerts=alerts, recent=recent,
                           visible_portals=visible_portals)


def _user_dashboard():
    """Render limited dashboard for regular users."""
    conn = get_db()
    stats = {
        "cases": conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
        "operations": conn.execute("SELECT COUNT(*) FROM operations").fetchone()[0],
        "seizures": conn.execute("SELECT COUNT(*) FROM firearm_seizures").fetchone()[0],
        "arrests": conn.execute("SELECT COUNT(*) FROM arrests").fetchone()[0],
    }

    # Limited set of portals for regular users (read-only)
    user_portals = {}
    for key in ("registry", "operations", "seizures", "arrests"):
        if key in UNIT_PORTALS:
            user_portals[key] = UNIT_PORTALS[key]

    alerts = []
    try:
        badge = getattr(current_user, "badge_number", None)
        alerts = get_alerts_for_user(badge=badge, role="user")
    except Exception:
        pass

    recent = conn.execute("""
        SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 10
    """).fetchall()

    conn.close()
    return render_template("user_dashboard.html", stats=stats, alerts=alerts,
                           recent=recent, visible_portals=user_portals)


@bp.route("/command")
@login_required
def command_dashboard():
    conn = get_db()
    stats = {
        "intel": conn.execute("SELECT COUNT(*) FROM intel_reports").fetchone()[0],
        "operations": conn.execute("SELECT COUNT(*) FROM operations").fetchone()[0],
        "firearms": conn.execute("SELECT COUNT(*) FROM firearm_seizures").fetchone()[0],
        "narcotics": conn.execute("SELECT COUNT(*) FROM narcotics_seizures").fetchone()[0],
        "arrests": conn.execute("SELECT COUNT(*) FROM arrests").fetchone()[0],
        "exhibits": conn.execute("SELECT COUNT(*) FROM chain_of_custody").fetchone()[0],
        "cases": conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
        "compliant_48": conn.execute(
            "SELECT COUNT(*) FROM arrests WHERE charge_within_48hr='Yes'"
        ).fetchone()[0],
        "at_dpp": conn.execute(
            "SELECT COUNT(*) FROM cases WHERE case_status LIKE 'Referred to DPP%'"
        ).fetchone()[0],
        "sop_compliant": conn.execute(
            "SELECT COUNT(*) FROM cases WHERE sop_compliance LIKE 'Fully%'"
        ).fetchone()[0],
        "open_cases": conn.execute(
            "SELECT COUNT(*) FROM cases WHERE case_status LIKE 'Open%'"
        ).fetchone()[0],
        "suspended_cases": conn.execute(
            "SELECT COUNT(*) FROM cases WHERE current_stage = 'suspended'"
        ).fetchone()[0],
        "pending_reviews": conn.execute(
            "SELECT COUNT(*) FROM case_reviews WHERE status = 'Scheduled'"
        ).fetchone()[0],
        "overdue_files": conn.execute(
            "SELECT COUNT(*) FROM file_movements WHERE status = 'Overdue'"
        ).fetchone()[0],
        "active_alerts": conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE is_dismissed = 0"
        ).fetchone()[0],
    }

    charts = {
        "cases_by_status": conn.execute(
            "SELECT case_status, COUNT(*) as cnt FROM cases GROUP BY case_status"
        ).fetchall(),
        "cases_by_parish": conn.execute(
            "SELECT parish, COUNT(*) as cnt FROM cases GROUP BY parish"
        ).fetchall(),
        "seizures_by_parish": conn.execute(
            "SELECT parish, COUNT(*) as cnt FROM firearm_seizures GROUP BY parish"
        ).fetchall(),
        "cases_by_stage": conn.execute(
            "SELECT current_stage, COUNT(*) as cnt FROM cases "
            "WHERE current_stage IS NOT NULL GROUP BY current_stage"
        ).fetchall(),
        "monthly_cases": conn.execute("""
            SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as cnt
            FROM cases WHERE created_at IS NOT NULL
            GROUP BY month ORDER BY month DESC LIMIT 12
        """).fetchall(),
        "monthly_seizures": conn.execute("""
            SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as cnt
            FROM firearm_seizures WHERE created_at IS NOT NULL
            GROUP BY month ORDER BY month DESC LIMIT 12
        """).fetchall(),
        "monthly_arrests": conn.execute("""
            SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as cnt
            FROM arrests WHERE created_at IS NOT NULL
            GROUP BY month ORDER BY month DESC LIMIT 12
        """).fetchall(),
    }
    conn.close()
    return render_template("command/dashboard.html", stats=stats, charts=charts)
