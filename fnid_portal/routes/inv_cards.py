"""
Investigator Index Card Routes

Manage investigator assignment cards linking officers to cases,
tracking tasks, next actions, and supervisor oversight.
"""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import get_db, log_audit
from ..rbac import permission_required

bp = Blueprint("inv_cards", __name__, url_prefix="/inv-cards")

ASSIGNMENT_TYPES = ["primary", "secondary", "support", "specialist"]
CARD_STATUSES = ["Active", "Completed", "Suspended", "Transferred"]


@bp.route("/")
@login_required
@permission_required("cases", "read")
def card_list():
    """List all investigator cards with filters."""
    officer_badge = request.args.get("officer_badge", "").strip()
    status = request.args.get("status", "").strip()

    conn = get_db()
    try:
        query = """
            SELECT ic.*, o.full_name AS officer_name, c.offence_description
            FROM investigator_cards ic
            LEFT JOIN officers o ON ic.officer_badge = o.badge_number
            LEFT JOIN cases c ON ic.case_id = c.case_id
            WHERE 1=1
        """
        params = []

        if officer_badge:
            query += " AND ic.officer_badge = ?"
            params.append(officer_badge)
        if status:
            query += " AND ic.status = ?"
            params.append(status)

        query += " ORDER BY ic.created_at DESC"
        cards = conn.execute(query, params).fetchall()

        officers = conn.execute(
            "SELECT badge_number, full_name FROM officers ORDER BY full_name"
        ).fetchall()

        return render_template(
            "inv_cards/list.html",
            cards=cards,
            officers=officers,
            filter_officer_badge=officer_badge,
            filter_status=status,
            statuses=CARD_STATUSES,
        )
    finally:
        conn.close()


@bp.route("/<int:id>")
@login_required
@permission_required("cases", "read")
def card_detail(id):
    """View full investigator card detail."""
    conn = get_db()
    try:
        card = conn.execute(
            """SELECT ic.*, o.full_name AS officer_name, o.rank AS officer_rank,
                      c.offence_description, c.case_status,
                      sup.full_name AS supervisor_name
               FROM investigator_cards ic
               LEFT JOIN officers o ON ic.officer_badge = o.badge_number
               LEFT JOIN cases c ON ic.case_id = c.case_id
               LEFT JOIN officers sup ON ic.supervisor_badge = sup.badge_number
               WHERE ic.id = ?""",
            (id,),
        ).fetchone()
        if not card:
            flash("Investigator card not found.", "danger")
            return redirect(url_for("inv_cards.card_list"))

        return render_template("inv_cards/detail.html", card=card)
    finally:
        conn.close()


@bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("cases", "create")
def new_card():
    """Create a new investigator card."""
    conn = get_db()
    try:
        officers = conn.execute(
            "SELECT badge_number, full_name, rank FROM officers ORDER BY full_name"
        ).fetchall()
        cases = conn.execute(
            "SELECT case_id, offence_description FROM cases ORDER BY case_id DESC"
        ).fetchall()

        if request.method == "POST":
            officer_badge = request.form.get("officer_badge", "").strip()
            case_id = request.form.get("case_id", "").strip()
            assigned_date = request.form.get("assigned_date", "").strip()
            assignment_type = request.form.get("assignment_type", "primary").strip()
            tasks_assigned = request.form.get("tasks_assigned", "").strip() or None
            tasks_completed = request.form.get("tasks_completed", "").strip() or None
            next_action = request.form.get("next_action", "").strip() or None
            next_action_date = request.form.get("next_action_date", "").strip() or None
            supervisor_badge = request.form.get("supervisor_badge", "").strip() or None

            if not officer_badge or not case_id or not assigned_date:
                flash("Officer, case, and assigned date are required.", "danger")
                return render_template(
                    "inv_cards/form.html",
                    card=request.form,
                    is_edit=False,
                    officers=officers,
                    cases=cases,
                    assignment_types=ASSIGNMENT_TYPES,
                )

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor = conn.execute(
                """INSERT INTO investigator_cards
                   (officer_badge, case_id, assigned_date, assignment_type,
                    tasks_assigned, tasks_completed, next_action, next_action_date,
                    supervisor_badge, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)""",
                (
                    officer_badge, case_id, assigned_date, assignment_type,
                    tasks_assigned, tasks_completed, next_action, next_action_date,
                    supervisor_badge, now, now,
                ),
            )
            conn.commit()
            new_id = cursor.lastrowid

            log_audit(
                "investigator_cards", str(new_id), "CREATE",
                current_user.badge_number, current_user.full_name,
                f"Investigator card created for {officer_badge} on case {case_id}",
            )

            flash("Investigator card created successfully.", "success")
            return redirect(url_for("inv_cards.card_detail", id=new_id))

        return render_template(
            "inv_cards/form.html",
            card=None,
            is_edit=False,
            officers=officers,
            cases=cases,
            assignment_types=ASSIGNMENT_TYPES,
        )
    finally:
        conn.close()


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("cases", "update")
def edit_card(id):
    """Edit an existing investigator card."""
    conn = get_db()
    try:
        card = conn.execute(
            "SELECT * FROM investigator_cards WHERE id = ?", (id,)
        ).fetchone()
        if not card:
            flash("Investigator card not found.", "danger")
            return redirect(url_for("inv_cards.card_list"))

        officers = conn.execute(
            "SELECT badge_number, full_name, rank FROM officers ORDER BY full_name"
        ).fetchall()
        cases = conn.execute(
            "SELECT case_id, offence_description FROM cases ORDER BY case_id DESC"
        ).fetchall()

        if request.method == "POST":
            officer_badge = request.form.get("officer_badge", "").strip()
            case_id = request.form.get("case_id", "").strip()
            assigned_date = request.form.get("assigned_date", "").strip()
            assignment_type = request.form.get("assignment_type", "primary").strip()
            tasks_assigned = request.form.get("tasks_assigned", "").strip() or None
            tasks_completed = request.form.get("tasks_completed", "").strip() or None
            next_action = request.form.get("next_action", "").strip() or None
            next_action_date = request.form.get("next_action_date", "").strip() or None
            supervisor_badge = request.form.get("supervisor_badge", "").strip() or None
            status = request.form.get("status", "Active").strip()

            if not officer_badge or not case_id or not assigned_date:
                flash("Officer, case, and assigned date are required.", "danger")
                return render_template(
                    "inv_cards/form.html",
                    card=request.form,
                    is_edit=True,
                    record_id=id,
                    officers=officers,
                    cases=cases,
                    assignment_types=ASSIGNMENT_TYPES,
                    statuses=CARD_STATUSES,
                )

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """UPDATE investigator_cards SET
                   officer_badge=?, case_id=?, assigned_date=?, assignment_type=?,
                   tasks_assigned=?, tasks_completed=?, next_action=?, next_action_date=?,
                   supervisor_badge=?, status=?, updated_at=?
                   WHERE id=?""",
                (
                    officer_badge, case_id, assigned_date, assignment_type,
                    tasks_assigned, tasks_completed, next_action, next_action_date,
                    supervisor_badge, status, now, id,
                ),
            )
            conn.commit()

            log_audit(
                "investigator_cards", str(id), "UPDATE",
                current_user.badge_number, current_user.full_name,
                f"Updated investigator card for {officer_badge} on case {case_id}",
            )

            flash("Investigator card updated successfully.", "success")
            return redirect(url_for("inv_cards.card_detail", id=id))

        return render_template(
            "inv_cards/form.html",
            card=card,
            is_edit=True,
            record_id=id,
            officers=officers,
            cases=cases,
            assignment_types=ASSIGNMENT_TYPES,
            statuses=CARD_STATUSES,
        )
    finally:
        conn.close()


@bp.route("/officer/<badge>")
@login_required
@permission_required("cases", "read")
def officer_cards(badge):
    """View all investigator cards for a specific officer."""
    conn = get_db()
    try:
        officer = conn.execute(
            "SELECT * FROM officers WHERE badge_number = ?", (badge,)
        ).fetchone()

        cards = conn.execute(
            """SELECT ic.*, c.offence_description, c.case_status
               FROM investigator_cards ic
               LEFT JOIN cases c ON ic.case_id = c.case_id
               WHERE ic.officer_badge = ?
               ORDER BY ic.created_at DESC""",
            (badge,),
        ).fetchall()

        return render_template(
            "inv_cards/list.html",
            cards=cards,
            officer=officer,
            officers=[],
            filter_officer_badge=badge,
            filter_status="",
            statuses=CARD_STATUSES,
        )
    finally:
        conn.close()


@bp.route("/<int:id>/supervisor-note", methods=["POST"])
@login_required
@permission_required("cases", "update")
def add_supervisor_note(id):
    """Add a supervisor review note to an investigator card."""
    conn = get_db()
    try:
        card = conn.execute(
            "SELECT * FROM investigator_cards WHERE id = ?", (id,)
        ).fetchone()
        if not card:
            flash("Investigator card not found.", "danger")
            return redirect(url_for("inv_cards.card_list"))

        note = request.form.get("supervisor_notes", "").strip()
        if not note:
            flash("Supervisor note cannot be empty.", "danger")
            return redirect(url_for("inv_cards.card_detail", id=id))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = card["supervisor_notes"] or ""
        timestamp_note = f"[{now} - {current_user.full_name}] {note}"
        updated_notes = f"{existing}\n{timestamp_note}".strip()

        conn.execute(
            """UPDATE investigator_cards SET
               supervisor_badge=?, supervisor_notes=?, updated_at=?
               WHERE id=?""",
            (current_user.badge_number, updated_notes, now, id),
        )
        conn.commit()

        log_audit(
            "investigator_cards", str(id), "UPDATE",
            current_user.badge_number, current_user.full_name,
            f"Supervisor note added to card #{id}",
        )

        flash("Supervisor note added successfully.", "success")
        return redirect(url_for("inv_cards.card_detail", id=id))
    finally:
        conn.close()
