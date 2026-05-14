"""
Enhanced Intelligence Module Routes

Permission-restricted intelligence capabilities including target profiles,
link analysis, and operational tasking.
"""

from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import generate_id, get_db, log_audit
from ..rbac import permission_required
from . import _cfg_module

bp = Blueprint("intel", __name__, url_prefix="/intel")


# Templates reference target.name / target.mo / target.id; the DB columns are
# target_name / modus_operandi / target_id. We alias in SQL so the row object
# is usable as-is from Jinja without server-side transformation.
_TARGET_COLS = (
    "*, target_id AS id, target_name AS name, modus_operandi AS mo"
)


@bp.route("/targets")
@login_required
@permission_required("intel", "targets")
def targets():
    """List all intelligence target profiles."""
    conn = get_db()
    try:
        rows = conn.execute(f"""
            SELECT {_TARGET_COLS} FROM intel_targets
            ORDER BY
                CASE threat_level
                    WHEN 'Critical' THEN 0 WHEN 'High' THEN 1
                    WHEN 'Medium' THEN 2 ELSE 3
                END,
                updated_at DESC
        """).fetchall()
        return render_template("intel/targets.html", targets=rows)
    finally:
        conn.close()


def _form_to_target_values():
    """Read the target form into a tuple ordered for INSERT/UPDATE."""
    return (
        request.form.get("name", "").strip(),
        request.form.get("aliases", "").strip(),
        request.form.get("description", "").strip(),
        request.form.get("parish", "").strip(),
        request.form.get("area", "").strip(),
        request.form.get("linked_cases", "").strip(),
        request.form.get("linked_intel", "").strip(),
        request.form.get("mo", "").strip(),
        request.form.get("threat_level", "Medium"),
        request.form.get("status", "Active"),
        request.form.get("notes", "").strip(),
    )


@bp.route("/targets/new", methods=["GET", "POST"])
@login_required
@permission_required("intel", "targets")
def new_target():
    """Create a new target profile."""
    if request.method == "POST":
        target_name = request.form.get("name", "").strip()
        if not target_name:
            flash("Target full name is required.", "danger")
            return redirect(url_for("intel.new_target"))

        conn = get_db()
        try:
            target_id = generate_id("TGT", "intel_targets", "target_id")
            now = datetime.now().isoformat()
            values = _form_to_target_values()
            conn.execute(
                """
                INSERT INTO intel_targets
                (target_id, target_name, aliases, description, parish, area,
                 linked_cases, linked_intel, modus_operandi, threat_level,
                 status, notes, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (target_id, *values, current_user.full_name, now, now),
            )
            conn.commit()
            log_audit("intel_targets", target_id, "CREATE",
                      current_user.badge_number, target_name)
            flash(f"Target profile {target_id} created.", "success")
            return redirect(url_for("intel.targets"))
        except Exception:
            conn.rollback()
            current_app.logger.exception("Intel unit error creating target")
            flash("An error occurred saving the target. Please try again.", "danger")
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
            f"SELECT {_TARGET_COLS} FROM intel_targets WHERE target_id = ?",
            (target_id,),
        ).fetchone()
        if not target:
            flash("Target not found.", "danger")
            return redirect(url_for("intel.targets"))

        linked_intel = []
        if target["linked_intel"]:
            intel_ids = [x.strip() for x in target["linked_intel"].split(",") if x.strip()]
            for iid in intel_ids:
                row = conn.execute(
                    "SELECT * FROM intel_reports WHERE intel_id = ?", (iid,)
                ).fetchone()
                if row:
                    linked_intel.append(row)

        linked_cases = []
        if target["linked_cases"]:
            case_ids = [x.strip() for x in target["linked_cases"].split(",") if x.strip()]
            for cid in case_ids:
                row = conn.execute(
                    "SELECT * FROM cases WHERE case_id = ?", (cid,)
                ).fetchone()
                if row:
                    linked_cases.append(row)

        return render_template(
            "intel/target_detail.html",
            target=target,
            linked_intel=linked_intel,
            linked_cases=linked_cases,
        )
    finally:
        conn.close()


@bp.route("/targets/<target_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("intel", "targets")
def edit_target(target_id):
    """Edit an existing target profile."""
    conn = get_db()
    try:
        target = conn.execute(
            f"SELECT {_TARGET_COLS} FROM intel_targets WHERE target_id = ?",
            (target_id,),
        ).fetchone()
        if not target:
            flash("Target not found.", "danger")
            return redirect(url_for("intel.targets"))

        if request.method == "POST":
            target_name = request.form.get("name", "").strip()
            if not target_name:
                flash("Target full name is required.", "danger")
                return redirect(url_for("intel.edit_target", target_id=target_id))

            values = _form_to_target_values()
            conn.execute(
                """
                UPDATE intel_targets
                SET target_name = ?, aliases = ?, description = ?,
                    parish = ?, area = ?, linked_cases = ?, linked_intel = ?,
                    modus_operandi = ?, threat_level = ?, status = ?, notes = ?,
                    updated_at = ?
                WHERE target_id = ?
                """,
                (*values, datetime.now().isoformat(), target_id),
            )
            conn.commit()
            log_audit("intel_targets", target_id, "UPDATE",
                      current_user.badge_number, target_name)
            flash(f"Target {target_id} updated.", "success")
            return redirect(url_for("intel.target_detail", target_id=target_id))

        cfg = _cfg_module()
        return render_template(
            "intel/target_form.html", target=target, cfg=cfg, is_new=False
        )
    finally:
        conn.close()


@bp.route("/link-analysis")
@login_required
@permission_required("intel", "link_analysis")
def link_analysis():
    """Link analysis view — recurring MO, locations, suspects."""
    conn = get_db()
    try:
        parish_rows = conn.execute("""
            SELECT parish, COUNT(*) AS count FROM intel_reports
            WHERE date_received >= date('now', '-90 days')
              AND parish IS NOT NULL AND parish != ''
            GROUP BY parish ORDER BY count DESC
        """).fetchall()
        parish_total = sum(r["count"] for r in parish_rows) or 1
        parish_freq = [
            {"parish": r["parish"], "count": r["count"],
             "pct": round(100.0 * r["count"] / parish_total, 1)}
            for r in parish_rows
        ]

        # Target frequency — join recurring intel target_person with the
        # intel_targets profile (if one exists) so the template can link to it.
        target_rows = conn.execute("""
            SELECT
                ir.target_person AS name,
                COALESCE(t.target_id, '') AS id,
                COALESCE(t.parish, '') AS parish,
                COALESCE(t.threat_level, '') AS threat_level,
                COUNT(*) AS count
            FROM intel_reports ir
            LEFT JOIN intel_targets t ON t.target_name = ir.target_person
            WHERE ir.target_person IS NOT NULL AND ir.target_person != ''
              AND ir.date_received >= date('now', '-90 days')
            GROUP BY ir.target_person
            ORDER BY count DESC LIMIT 20
        """).fetchall()
        target_freq = [dict(r) for r in target_rows]

        loc_rows = conn.execute("""
            SELECT target_location AS location, parish, COUNT(*) AS count
            FROM operations
            WHERE target_location IS NOT NULL AND target_location != ''
              AND op_date >= date('now', '-90 days')
            GROUP BY target_location, parish
            ORDER BY count DESC LIMIT 20
        """).fetchall()
        loc_total = sum(r["count"] for r in loc_rows) or 1
        location_freq = [
            {"location": r["location"], "parish": r["parish"],
             "count": r["count"],
             "pct": round(100.0 * r["count"] / loc_total, 1)}
            for r in loc_rows
        ]

        targets = conn.execute(f"""
            SELECT {_TARGET_COLS} FROM intel_targets
            ORDER BY
                CASE threat_level
                    WHEN 'Critical' THEN 0 WHEN 'High' THEN 1
                    WHEN 'Medium' THEN 2 ELSE 3
                END, target_name
            LIMIT 50
        """).fetchall()

        return render_template(
            "intel/link_analysis.html",
            parish_freq=parish_freq,
            target_freq=target_freq,
            location_freq=location_freq,
            targets=targets,
        )
    finally:
        conn.close()


@bp.route("/tasking", methods=["GET", "POST"])
@login_required
@permission_required("intel", "targets")
def tasking():
    """Tasking recommendations to operational teams."""
    return _handle_tasking()


# Template references intel.create_tasking when POSTing; alias to the same view.
@bp.route("/tasking/create", methods=["POST"], endpoint="create_tasking")
@login_required
@permission_required("intel", "targets")
def create_tasking():
    return _handle_tasking()


def _handle_tasking():
    conn = get_db()
    try:
        if request.method == "POST":
            task_id = generate_id("TASK", "intel_reports", "intel_id")
            now = datetime.now()
            name = current_user.full_name

            conn.execute(
                """
                INSERT INTO intel_reports
                (intel_id, date_received, source, priority, subject_matter,
                 parish, substance_of_intel, triage_decision,
                 triage_by, triage_date, record_status, created_by,
                 created_at, updated_at)
                VALUES (?, ?, 'FNID Direct (923-6184)', ?, ?, ?, ?, ?, ?, ?, 'Submitted', ?, ?, ?)
                """,
                (
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
                ),
            )
            conn.commit()
            log_audit("intel_reports", task_id, "TASKING",
                      current_user.badge_number, name)
            flash(f"Tasking {task_id} created.", "success")
            return redirect(url_for("intel.tasking"))

        taskings = conn.execute("""
            SELECT * FROM intel_reports
            WHERE intel_id LIKE 'TASK-%'
            ORDER BY created_at DESC LIMIT 50
        """).fetchall()

        active_targets = conn.execute(f"""
            SELECT {_TARGET_COLS} FROM intel_targets
            WHERE status = 'Active'
            ORDER BY threat_level, target_name
        """).fetchall()

        cfg = _cfg_module()
        return render_template(
            "intel/tasking.html",
            taskings=taskings,
            active_targets=active_targets,
            cfg=cfg,
        )
    finally:
        conn.close()
