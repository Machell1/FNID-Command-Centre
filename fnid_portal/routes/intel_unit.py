"""
Enhanced Intelligence Module Routes

Permission-restricted intelligence capabilities including target profiles,
link analysis, and operational tasking.
"""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import generate_id, get_db, log_audit
from ..rbac import permission_required
from . import _cfg_module

bp = Blueprint("intel_unit", __name__, url_prefix="/intel")


@bp.route("/targets")
@login_required
@permission_required("intel", "targets")
def target_list():
    """List all intelligence target profiles."""
    conn = get_db()
    try:
        targets = conn.execute("""
            SELECT * FROM intel_targets ORDER BY
                CASE threat_level
                    WHEN 'Critical' THEN 0 WHEN 'High' THEN 1
                    WHEN 'Medium' THEN 2 ELSE 3
                END,
                updated_at DESC
        """).fetchall()

        return render_template("intel/targets.html", targets=targets)
    finally:
        conn.close()


@bp.route("/targets/new", methods=["GET", "POST"])
@login_required
@permission_required("intel", "targets")
def new_target():
    """Create a new target profile."""
    if request.method == "POST":
        conn = get_db()
        try:
            target_id = generate_id("TGT", "intel_targets", "target_id")
            now = datetime.now().isoformat()
            name = current_user.full_name

            conn.execute("""
                INSERT INTO intel_targets
                (target_id, target_name, aliases, description, parish, area,
                 linked_cases, linked_intel, modus_operandi, threat_level,
                 status, notes, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                target_id,
                request.form.get("target_name", ""),
                request.form.get("aliases", ""),
                request.form.get("description", ""),
                request.form.get("parish", ""),
                request.form.get("area", ""),
                request.form.get("linked_cases", ""),
                request.form.get("linked_intel", ""),
                request.form.get("modus_operandi", ""),
                request.form.get("threat_level", "Medium"),
                request.form.get("status", "Active"),
                request.form.get("notes", ""),
                name, now, now,
            ))
            conn.commit()
            log_audit("intel_targets", target_id, "CREATE",
                     current_user.badge_number, name)
            flash(f"Target profile {target_id} created.", "success")
            return redirect(url_for("intel_unit.target_list"))
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}", "danger")
        finally:
            conn.close()

    cfg = _cfg_module()
    return render_template("intel/target_form.html", target=None, cfg=cfg, is_new=True)


@bp.route("/targets/<target_id>")
@login_required
@permission_required("intel", "targets")
def target_detail(target_id):
    """Target profile detail view."""
    conn = get_db()
    try:
        target = conn.execute(
            "SELECT * FROM intel_targets WHERE target_id = ?", (target_id,)
        ).fetchone()
        if not target:
            flash("Target not found.", "danger")
            return redirect(url_for("intel_unit.target_list"))

        # Get linked intel reports
        linked_intel = []
        if target["linked_intel"]:
            intel_ids = [x.strip() for x in target["linked_intel"].split(",") if x.strip()]
            for iid in intel_ids:
                row = conn.execute(
                    "SELECT * FROM intel_reports WHERE intel_id = ?", (iid,)
                ).fetchone()
                if row:
                    linked_intel.append(row)

        # Get linked cases
        linked_cases = []
        if target["linked_cases"]:
            case_ids = [x.strip() for x in target["linked_cases"].split(",") if x.strip()]
            for cid in case_ids:
                row = conn.execute(
                    "SELECT * FROM cases WHERE case_id = ?", (cid,)
                ).fetchone()
                if row:
                    linked_cases.append(row)

        return render_template("intel/target_detail.html",
                             target=target,
                             linked_intel=linked_intel,
                             linked_cases=linked_cases)
    finally:
        conn.close()


@bp.route("/link-analysis")
@login_required
@permission_required("intel", "link_analysis")
def link_analysis():
    """Link analysis view — recurring MO, locations, suspects."""
    conn = get_db()
    try:
        # Recurring parishes in recent intel
        parish_freq = conn.execute("""
            SELECT parish, COUNT(*) as cnt FROM intel_reports
            WHERE date_received >= date('now', '-90 days')
            GROUP BY parish ORDER BY cnt DESC
        """).fetchall()

        # Recurring target persons
        target_freq = conn.execute("""
            SELECT target_person, COUNT(*) as cnt FROM intel_reports
            WHERE target_person IS NOT NULL AND target_person != ''
              AND date_received >= date('now', '-90 days')
            GROUP BY target_person ORDER BY cnt DESC LIMIT 20
        """).fetchall()

        # Recurring locations in operations
        location_freq = conn.execute("""
            SELECT target_location, parish, COUNT(*) as cnt FROM operations
            WHERE target_location IS NOT NULL AND target_location != ''
              AND op_date >= date('now', '-90 days')
            GROUP BY target_location ORDER BY cnt DESC LIMIT 20
        """).fetchall()

        # Active targets by threat level
        targets = conn.execute("""
            SELECT threat_level, COUNT(*) as cnt FROM intel_targets
            WHERE status = 'Active'
            GROUP BY threat_level
        """).fetchall()

        return render_template("intel/link_analysis.html",
                             parish_freq=parish_freq,
                             target_freq=target_freq,
                             location_freq=location_freq,
                             targets=targets)
    finally:
        conn.close()


@bp.route("/tasking", methods=["GET", "POST"])
@login_required
@permission_required("intel", "targets")
def tasking():
    """Tasking recommendations to operational teams."""
    conn = get_db()
    try:
        if request.method == "POST":
            # Create a tasking note as an intel report
            task_id = generate_id("TASK", "intel_reports", "intel_id")
            now = datetime.now()
            name = current_user.full_name

            conn.execute("""
                INSERT INTO intel_reports
                (intel_id, date_received, source, priority, subject_matter,
                 parish, substance_of_intel, triage_decision,
                 triage_by, triage_date, record_status, created_by,
                 created_at, updated_at)
                VALUES (?, ?, 'FNID Direct (923-6184)', ?, ?, ?, ?, ?, ?, ?, 'Submitted', ?, ?, ?)
            """, (
                task_id,
                now.strftime("%Y-%m-%d"),
                request.form.get("priority", "Medium"),
                request.form.get("subject_matter", ""),
                request.form.get("parish", ""),
                request.form.get("task_details", ""),
                request.form.get("triage_decision", "Action - Mount Operation"),
                name,
                now.strftime("%Y-%m-%d"),
                name,
                now.isoformat(),
                now.isoformat(),
            ))
            conn.commit()
            log_audit("intel_reports", task_id, "TASKING",
                     current_user.badge_number, name)
            flash(f"Tasking {task_id} created.", "success")
            return redirect(url_for("intel_unit.tasking"))

        # Get recent taskings
        taskings = conn.execute("""
            SELECT * FROM intel_reports
            WHERE intel_id LIKE 'TASK-%'
            ORDER BY created_at DESC LIMIT 50
        """).fetchall()

        # Get active targets for reference
        active_targets = conn.execute("""
            SELECT * FROM intel_targets WHERE status = 'Active'
            ORDER BY threat_level, target_name
        """).fetchall()

        cfg = _cfg_module()
        return render_template("intel/tasking.html",
                             taskings=taskings,
                             active_targets=active_targets, cfg=cfg)
    finally:
        conn.close()
