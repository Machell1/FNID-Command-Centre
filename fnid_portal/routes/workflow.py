"""
Workflow Routes

Visual case workflow tracking, stage transitions, and overview dashboard.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import get_db
from ..rbac import permission_required, role_required
from ..workflow import CASE_WORKFLOW, VALID_TRANSITIONS, advance_stage, get_workflow_status

bp = Blueprint("workflow", __name__, url_prefix="/workflow")


@bp.route("/overview")
@login_required
@role_required("admin", "dco", "ddi", "station_mgr")
def workflow_overview():
    """Command view: all active cases by workflow stage."""
    conn = get_db()
    try:
        stage_counts = conn.execute("""
            SELECT current_stage, COUNT(*) as cnt
            FROM cases WHERE current_stage != 'closed'
            GROUP BY current_stage ORDER BY cnt DESC
        """).fetchall()

        total_active = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE current_stage != 'closed'"
        ).fetchone()[0]

        # Cases needing attention (stale in stage > 14 days)
        stale = conn.execute("""
            SELECT case_id, current_stage, classification, oic_name, updated_at
            FROM cases
            WHERE current_stage NOT IN ('closed', 'cold_case', 'suspended')
            AND updated_at < datetime('now', '-14 days')
            ORDER BY updated_at ASC LIMIT 20
        """).fetchall()

        return render_template(
            "workflow/overview.html",
            stage_counts=stage_counts,
            total_active=total_active,
            stale=stale,
            workflow_stages=CASE_WORKFLOW,
        )
    finally:
        conn.close()


@bp.route("/case/<path:case_id>")
@login_required
@permission_required("cases", "read")
def case_workflow(case_id):
    """Visual workflow tracker for a specific case."""
    status = get_workflow_status(case_id)
    if not status:
        flash("Case not found.", "danger")
        return redirect(url_for("cases.case_list"))

    return render_template(
        "workflow/tracker.html",
        status=status,
        case_id=case_id,
        workflow_stages=CASE_WORKFLOW,
        valid_transitions=VALID_TRANSITIONS,
    )


@bp.route("/advance/<path:case_id>", methods=["POST"])
@login_required
@permission_required("cases", "update")
def advance_case(case_id):
    """Advance case to next workflow stage."""
    to_stage = request.form.get("to_stage", "")
    notes = request.form.get("notes", "")

    if not to_stage:
        flash("Target stage is required.", "danger")
        return redirect(url_for("workflow.case_workflow", case_id=case_id))

    success, errors = advance_stage(
        case_id, to_stage,
        current_user.badge_number, current_user.full_name,
        notes=notes,
    )

    if success:
        flash(f"Case advanced to '{to_stage}' stage.", "success")
    else:
        for err in errors:
            flash(err, "danger")

    return redirect(url_for("workflow.case_workflow", case_id=case_id))
