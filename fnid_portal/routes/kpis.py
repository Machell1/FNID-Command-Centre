"""
KPI Tracker Routes

Allows Tier1 admins to enter KPIs and all members to view their own.
"""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import get_db, log_audit

bp = Blueprint("kpis", __name__, url_prefix="/kpis")


@bp.route("/")
@login_required
def my_kpis():
    """View current user's KPIs."""
    conn = get_db()
    try:
        kpis = conn.execute(
            "SELECT * FROM member_kpis WHERE officer_badge = ? ORDER BY period DESC",
            (current_user.badge_number,)
        ).fetchall()
        return render_template("kpis/my_kpis.html", kpis=kpis)
    finally:
        conn.close()


@bp.route("/enter", methods=["GET", "POST"])
@login_required
def enter_kpi():
    """Tier1 admin enters KPIs for an officer."""
    admin_tier = getattr(current_user, "admin_tier", None)
    if admin_tier is None or admin_tier > 1:
        flash("Only Tier 1 admins can enter KPIs.", "danger")
        return redirect(url_for("kpis.my_kpis"))

    conn = get_db()
    try:
        if request.method == "POST":
            conn.execute("""
                INSERT INTO member_kpis
                (officer_badge, period, metric_name, metric_value, target_value,
                 notes, entered_by, entered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.form.get("officer_badge", ""),
                request.form.get("period", ""),
                request.form.get("metric_name", ""),
                request.form.get("metric_value", ""),
                request.form.get("target_value", ""),
                request.form.get("notes", ""),
                current_user.badge_number,
                datetime.now().isoformat(),
            ))
            conn.commit()
            log_audit("member_kpis", request.form.get("officer_badge", ""), "CREATE",
                      current_user.badge_number, current_user.full_name,
                      f"KPI entered for {request.form.get('officer_badge', '')}")
            flash("KPI recorded.", "success")
            return redirect(url_for("kpis.enter_kpi"))

        officers = conn.execute(
            "SELECT badge_number, full_name, rank FROM officers WHERE is_active = 1 ORDER BY full_name"
        ).fetchall()
        return render_template("kpis/enter.html", officers=officers)
    finally:
        conn.close()


@bp.route("/member/<badge>")
@login_required
def member_kpis(badge):
    """View a specific member's KPIs (admin/dco or self)."""
    role = getattr(current_user, "role", "io")
    if badge != current_user.badge_number and role not in ("admin", "dco", "ddi"):
        flash("Access denied.", "danger")
        return redirect(url_for("kpis.my_kpis"))

    conn = get_db()
    try:
        officer = conn.execute(
            "SELECT * FROM officers WHERE badge_number = ?", (badge,)
        ).fetchone()
        kpis = conn.execute(
            "SELECT * FROM member_kpis WHERE officer_badge = ? ORDER BY period DESC",
            (badge,)
        ).fetchall()
        return render_template("kpis/my_kpis.html", kpis=kpis, officer=officer)
    finally:
        conn.close()


@bp.route("/<int:kpi_id>/delete", methods=["POST"])
@login_required
def delete_kpi(kpi_id):
    """Tier1 admin deletes a KPI entry."""
    admin_tier = getattr(current_user, "admin_tier", None)
    if admin_tier is None or admin_tier > 1:
        flash("Only Tier 1 admins can delete KPIs.", "danger")
        return redirect(url_for("kpis.my_kpis"))

    conn = get_db()
    try:
        conn.execute("DELETE FROM member_kpis WHERE id = ?", (kpi_id,))
        conn.commit()
        log_audit("member_kpis", str(kpi_id), "DELETE",
                  current_user.badge_number, current_user.full_name)
        flash("KPI deleted.", "success")
    finally:
        conn.close()
    return redirect(url_for("kpis.my_kpis"))
