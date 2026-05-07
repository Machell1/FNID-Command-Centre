"""Internal AI work assistant routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..ai_assistant_engine import (
    AGENT_BLUEPRINTS,
    append_human_guidance,
    apply_action,
    list_agent_profiles,
    persona_for_user,
    rollback_action,
    run_agent,
    seed_agent_profiles,
    set_global_enabled,
    update_profile,
)
from ..models import get_db, get_setting
from ..rbac import permission_required
from ..secret_keys import has_secret

bp = Blueprint("assistants", __name__, url_prefix="/assistants")


@bp.route("/")
@login_required
@permission_required("assistants", "read")
def dashboard():
    conn = get_db()
    try:
        profiles = list_agent_profiles(conn)
        runs = conn.execute(
            """
            SELECT * FROM assistant_runs
            ORDER BY id DESC LIMIT 20
            """
        ).fetchall()
        actions = conn.execute(
            """
            SELECT * FROM assistant_actions
            WHERE status IN ('proposed', 'approved', 'applied')
            ORDER BY id DESC LIMIT 30
            """
        ).fetchall()
        return render_template(
            "assistants/dashboard.html",
            profiles=profiles,
            blueprints=AGENT_BLUEPRINTS,
            runs=runs,
            actions=actions,
            global_enabled=get_setting("ai_assistants_global_enabled", "false") == "true",
            api_key_present=has_secret("DEEPSEEK_API_KEY"),
            tavily_key_present=has_secret("TAVILY_API_KEY"),
            default_agent=persona_for_user(current_user),
        )
    finally:
        conn.close()


@bp.route("/workstation")
@login_required
@permission_required("assistants", "read")
def workstation():
    conn = get_db()
    try:
        default_agent = persona_for_user(current_user)
        badge = current_user.badge_number
        assigned_cases = conn.execute(
            """
            SELECT * FROM cases
            WHERE assigned_io_badge = ? OR oic_badge = ?
            ORDER BY updated_at DESC LIMIT 25
            """,
            (badge, badge),
        ).fetchall()
        registry_queue = conn.execute(
            """
            SELECT c.*, COUNT(a.id) AS assistant_action_count
            FROM cases c
            LEFT JOIN assistant_actions a
                ON a.case_id = c.case_id AND a.status = 'proposed'
            WHERE c.record_status != 'Archived'
            GROUP BY c.id
            ORDER BY assistant_action_count DESC, c.updated_at DESC
            LIMIT 30
            """
        ).fetchall()
        proposed_actions = conn.execute(
            """
            SELECT * FROM assistant_actions
            WHERE status = 'proposed'
              AND (target_badge = ? OR target_badge IS NULL OR target_badge = '')
            ORDER BY id DESC LIMIT 30
            """,
            (badge,),
        ).fetchall()
        return render_template(
            "assistants/workstation.html",
            default_agent=default_agent,
            assigned_cases=assigned_cases,
            registry_queue=registry_queue,
            proposed_actions=proposed_actions,
            global_enabled=get_setting("ai_assistants_global_enabled", "false") == "true",
        )
    finally:
        conn.close()


@bp.route("/settings", methods=["POST"])
@login_required
@permission_required("assistants", "manage")
def settings():
    conn = get_db()
    try:
        set_global_enabled(conn, request.form.get("global_enabled") == "on", current_user.badge_number)
        seed_agent_profiles(conn, current_user.badge_number)
        for agent_key in AGENT_BLUEPRINTS:
            prefix = f"{agent_key}__"
            if any(key.startswith(prefix) for key in request.form.keys()):
                agent_form = {
                    key[len(prefix):]: value
                    for key, value in request.form.items()
                    if key.startswith(prefix)
                }
                update_profile(conn, agent_key, agent_form, current_user.badge_number)
        flash("Assistant harness settings updated.", "success")
    finally:
        conn.close()
    return redirect(url_for("assistants.dashboard"))


@bp.route("/run/<agent_key>", methods=["POST"])
@login_required
@permission_required("assistants", "run")
def run(agent_key):
    if agent_key not in AGENT_BLUEPRINTS:
        flash("Unknown assistant.", "danger")
        return redirect(url_for("assistants.dashboard"))
    case_id = request.form.get("case_id") or None
    guidance = request.form.get("guidance", "")
    conn = get_db()
    try:
        run_id = run_agent(conn, agent_key, current_user, case_id=case_id, guidance=guidance)
    finally:
        conn.close()
    return redirect(url_for("assistants.run_detail", run_id=run_id))


@bp.route("/runs/<run_id>")
@login_required
@permission_required("assistants", "read")
def run_detail(run_id):
    conn = get_db()
    try:
        run = conn.execute("SELECT * FROM assistant_runs WHERE run_id = ?", (run_id,)).fetchone()
        if not run:
            flash("Assistant run not found.", "danger")
            return redirect(url_for("assistants.dashboard"))
        actions = conn.execute(
            "SELECT * FROM assistant_actions WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return render_template("assistants/run_detail.html", run=run, actions=actions)
    finally:
        conn.close()


@bp.route("/runs/<run_id>/intervene", methods=["POST"])
@login_required
@permission_required("assistants", "run")
def intervene(run_id):
    guidance = request.form.get("guidance", "").strip()
    if not guidance:
        flash("Guidance cannot be blank.", "warning")
        return redirect(url_for("assistants.run_detail", run_id=run_id))
    conn = get_db()
    try:
        append_human_guidance(conn, run_id, guidance, current_user)
        flash("Human guidance added. The assistant run is paused for review.", "success")
    finally:
        conn.close()
    return redirect(url_for("assistants.run_detail", run_id=run_id))


@bp.route("/actions/<int:action_id>/apply", methods=["POST"])
@login_required
@permission_required("assistants", "approve")
def apply(action_id):
    conn = get_db()
    try:
        status = apply_action(conn, action_id, current_user, request.form.get("approval_note", ""))
        flash(f"Assistant action {status}.", "success")
        run_id = conn.execute("SELECT run_id FROM assistant_actions WHERE id = ?", (action_id,)).fetchone()["run_id"]
    except ValueError as exc:
        flash(str(exc), "danger")
        run_id = request.form.get("run_id")
    finally:
        conn.close()
    return redirect(url_for("assistants.run_detail", run_id=run_id))


@bp.route("/actions/<int:action_id>/reject", methods=["POST"])
@login_required
@permission_required("assistants", "approve")
def reject(action_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT run_id FROM assistant_actions WHERE id = ?", (action_id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE assistant_actions SET status = 'rejected', updated_at = datetime('now') WHERE id = ?",
                (action_id,),
            )
            conn.commit()
            flash("Assistant action rejected.", "success")
            return redirect(url_for("assistants.run_detail", run_id=row["run_id"]))
    finally:
        conn.close()
    flash("Assistant action not found.", "danger")
    return redirect(url_for("assistants.dashboard"))


@bp.route("/actions/<int:action_id>/rollback", methods=["POST"])
@login_required
@permission_required("assistants", "rollback")
def rollback(action_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT run_id FROM assistant_actions WHERE id = ?", (action_id,)).fetchone()
        rollback_action(conn, action_id, current_user, request.form.get("rollback_notes", ""))
        flash("Assistant action rolled back without deleting the audit trail.", "success")
        return redirect(url_for("assistants.run_detail", run_id=row["run_id"]))
    except ValueError as exc:
        flash(str(exc), "danger")
    finally:
        conn.close()
    return redirect(url_for("assistants.dashboard"))
