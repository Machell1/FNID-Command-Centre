"""Notification system — in-app alerts, bell icon API, acknowledgment workflow."""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..deadlines import dismiss_alert, get_alerts_for_user
from ..models import get_db, log_audit

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@bp.route("/")
@login_required
def notification_center():
    """All notifications for current user."""
    show_dismissed = request.args.get("dismissed", "0") == "1"
    badge = getattr(current_user, "badge_number", None)
    role = getattr(current_user, "role", "viewer")

    conn = get_db()
    try:
        if show_dismissed:
            alerts = conn.execute("""
                SELECT * FROM alerts ORDER BY is_dismissed ASC, created_at DESC
            """).fetchall()
        else:
            alerts = get_alerts_for_user(badge=badge, role=role)
        return render_template("notifications/center.html",
                               alerts=alerts, show_dismissed=show_dismissed)
    finally:
        conn.close()


@bp.route("/api/count")
@login_required
def api_count():
    """JSON API: unread notification count for the bell badge."""
    badge = getattr(current_user, "badge_number", None)
    role = getattr(current_user, "role", "viewer")
    try:
        alerts = get_alerts_for_user(badge=badge, role=role)
        critical = sum(1 for a in alerts if a["severity"] == "critical")
        return jsonify({
            "total": len(alerts),
            "critical": critical,
        })
    except Exception:
        return jsonify({"total": 0, "critical": 0})


@bp.route("/api/recent")
@login_required
def api_recent():
    """JSON API: recent notifications for dropdown preview."""
    badge = getattr(current_user, "badge_number", None)
    role = getattr(current_user, "role", "viewer")
    try:
        alerts = get_alerts_for_user(badge=badge, role=role)
        items = []
        for a in alerts[:8]:
            items.append({
                "id": a["id"],
                "title": a["title"],
                "message": (a["message"] or "")[:120],
                "severity": a["severity"],
                "created_at": a["created_at"],
            })
        return jsonify({"items": items, "total": len(alerts)})
    except Exception:
        return jsonify({"items": [], "total": 0})


@bp.route("/dismiss/<int:alert_id>", methods=["POST"])
@login_required
def dismiss(alert_id):
    """Dismiss (acknowledge) an alert."""
    try:
        dismiss_alert(alert_id)
        log_audit("alerts", str(alert_id), "DISMISS",
                  current_user.badge_number, current_user.full_name)
    except Exception:
        pass

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    return redirect(url_for("notifications.notification_center"))


@bp.route("/dismiss-all", methods=["POST"])
@login_required
def dismiss_all():
    """Dismiss all alerts for current user."""
    conn = get_db()
    try:
        badge = current_user.badge_number
        # Dismiss alerts targeted to this user or visible to their role
        conn.execute("""
            UPDATE alerts SET is_dismissed = 1
            WHERE is_dismissed = 0
              AND (target_badge = ? OR target_badge IS NULL)
        """, (badge,))
        conn.commit()
        log_audit("alerts", "all", "DISMISS_ALL",
                  badge, current_user.full_name)
    finally:
        conn.close()
    return redirect(url_for("notifications.notification_center"))
