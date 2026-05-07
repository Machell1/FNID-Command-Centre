"""
Workflow Dashboard Routes

Visual workflow tracker and case advancement interface.
"""


from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import get_db
from ..rbac import permission_required
from ..workflow import STAGE_REQUIREMENTS, VALID_TRANSITIONS, advance_case_stage, get_workflow_status

bp = Blueprint("workflow", __name__, url_prefix="/workflow")


@bp.route("/overview")
@login_required
@permission_required("cases", "read")
def overview():
    """Command view: all active cases by workflow stage."""
    conn = get_db()
    try:
        stage_counts = conn.execute("""
            SELECT current_stage, COUNT(*) as cnt
            FROM cases
            WHERE case_status NOT LIKE 'Case Closed%'
            GROUP BY current_stage
            ORDER BY cnt DESC
        """).fetchall()

        total_active = conn.execute("""
            SELECT COUNT(*) FROM cases
            WHERE case_status NOT LIKE 'Case Closed%'
        """).fetchone()[0]

        # Cases needing attention (stuck in stage >14 days)
        stale = conn.execute("""
            SELECT c.case_id, c.current_stage, c.oic_name, c.classification, c.updated_at
            FROM cases c
            WHERE c.case_status NOT LIKE 'Case Closed%'
            AND c.updated_at < datetime('now', '-14 days')
            ORDER BY c.updated_at ASC
            LIMIT 20
        """).fetchall()

        return render_template(
            "workflow/overview.html",
            stage_counts=stage_counts,
            total_active=total_active,
            stale_cases=stale,
            valid_transitions=VALID_TRANSITIONS,
        )
    finally:
        conn.close()


@bp.route("/case/<path:case_id>")
@login_required
@permission_required("cases", "read")
def case_tracker(case_id):
    """Visual workflow tracker for a specific case."""
    status = get_workflow_status(case_id)
    if not status:
        flash("Case not found.", "danger")
        return redirect(url_for("workflow.overview"))

    return render_template(
        "workflow/tracker.html",
        status=status,
        case_id=case_id,
        stage_requirements=STAGE_REQUIREMENTS,
    )


@bp.route("/advance/<path:case_id>", methods=["POST"])
@login_required
@permission_required("cases", "update")
def advance(case_id):
    """Advance a case to the next workflow stage."""
    to_stage = request.form.get("to_stage", "")
    notes = request.form.get("notes", "")

    if not to_stage:
        flash("Target stage is required.", "danger")
        return redirect(url_for("workflow.case_tracker", case_id=case_id))

    success, message = advance_case_stage(
        case_id, to_stage,
        current_user.badge_number, current_user.full_name,
        notes=notes
    )

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for("workflow.case_tracker", case_id=case_id))
