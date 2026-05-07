"""
Case File Movement Routes

Digital Case File Movement Register, Inward/Outward Correspondence Register,
and Investigator Index Card management.
"""

from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import get_db, get_setting, log_audit
from ..rbac import can_access, permission_required

bp = Blueprint("file_movement", __name__)

FILE_TYPES = [
    "Original Case File",
    "Working File",
    "Exhibit File",
    "Forensic Certificate",
    "Court File",
    "DPP Submission",
    "Statement Bundle",
    "Disclosure Package",
]

MOVEMENT_TYPES = [
    "Checkout",
    "Return",
    "Transfer",
    "Court Submission",
    "DPP Submission",
    "Forensic Lab Submission",
]


@bp.route("/cases/<path:case_id>/files")
@login_required
@permission_required("file_movement", "read")
def file_register(case_id):
    """Case file movement register view."""
    conn = get_db()
    try:
        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not case:
            flash("Case not found.", "danger")
            return redirect(url_for("cases.case_list"))

        movements = conn.execute("""
            SELECT * FROM file_movements WHERE case_id = ?
            ORDER BY moved_at DESC
        """, (case_id,)).fetchall()

        # Get currently checked-out files
        checked_out = conn.execute("""
            SELECT * FROM file_movements WHERE case_id = ? AND status IN ('Out', 'Overdue')
        """, (case_id,)).fetchall()

        return render_template("file_movement/register.html",
                             case=case, movements=movements,
                             checked_out=checked_out,
                             file_types=FILE_TYPES,
                             movement_types=MOVEMENT_TYPES)
    finally:
        conn.close()


@bp.route("/cases/<path:case_id>/files/checkout", methods=["POST"])
@login_required
def file_checkout(case_id):
    """Check out a file from the case registry."""
    file_type = request.form.get("file_type", "")
    reason = request.form.get("reason", "")
    destination = request.form.get("destination", "")

    if not file_type or not reason or not destination:
        flash("File type, reason, and destination are required.", "danger")
        return redirect(url_for("file_movement.file_register", case_id=case_id))

    # Check permissions: original files require higher access
    if file_type == "Original Case File":
        if not can_access(current_user, "file_movement", "checkout_original"):
            flash("Only Registrar or DCO can check out original case files.", "danger")
            return redirect(url_for("file_movement.file_register", case_id=case_id))
    else:
        if not can_access(current_user, "file_movement", "checkout_working"):
            flash("You do not have permission to check out files.", "danger")
            return redirect(url_for("file_movement.file_register", case_id=case_id))

    # Calculate expected return
    hours = int(get_setting("file_return_hours", "48"))
    expected_return = (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M")

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO file_movements
            (case_id, file_type, movement_type, moved_from, moved_to,
             moved_by, reason, expected_return, status)
            VALUES (?, ?, 'Checkout', 'Registry', ?, ?, ?, ?, 'Out')
        """, (case_id, file_type, destination,
              current_user.badge_number, reason, expected_return))
        conn.commit()

        log_audit("file_movements", case_id, "CHECKOUT",
                 current_user.badge_number, current_user.full_name,
                 f"{file_type} → {destination}: {reason}")

        flash(f"{file_type} checked out to {destination}. Return by {expected_return}.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("file_movement.file_register", case_id=case_id))


@bp.route("/cases/<path:case_id>/files/return", methods=["POST"])
@login_required
@permission_required("file_movement", "create")
def file_return(case_id):
    """Return a checked-out file."""
    movement_id = request.form.get("movement_id")
    notes = request.form.get("notes", "")

    conn = get_db()
    try:
        now = datetime.now()
        conn.execute("""
            UPDATE file_movements SET
                actual_return = ?, return_logged_by = ?,
                status = 'Returned', notes = ?
            WHERE id = ? AND case_id = ?
        """, (now.strftime("%Y-%m-%d %H:%M"), current_user.badge_number,
              notes, movement_id, case_id))
        conn.commit()

        log_audit("file_movements", case_id, "RETURN",
                 current_user.badge_number, current_user.full_name,
                 f"Movement #{movement_id} returned")

        flash("File returned successfully.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("file_movement.file_register", case_id=case_id))


@bp.route("/cases/<path:case_id>/correspondence")
@login_required
@permission_required("file_movement", "read")
def correspondence_register(case_id):
    """Inward/outward correspondence register."""
    conn = get_db()
    try:
        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not case:
            flash("Case not found.", "danger")
            return redirect(url_for("cases.case_list"))

        correspondence = conn.execute("""
            SELECT * FROM correspondence WHERE case_id = ?
            ORDER BY date DESC, logged_at DESC
        """, (case_id,)).fetchall()

        return render_template("file_movement/correspondence.html",
                             case=case, correspondence=correspondence)
    finally:
        conn.close()


@bp.route("/cases/<path:case_id>/correspondence/new", methods=["POST"])
@login_required
@permission_required("file_movement", "create")
def new_correspondence(case_id):
    """Log new inward or outward correspondence."""
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO correspondence
            (case_id, direction, date, reference_number, from_entity,
             to_entity, subject, document_type, logged_by,
             action_required, action_deadline)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case_id,
            request.form.get("direction", "inward"),
            request.form.get("date", datetime.now().strftime("%Y-%m-%d")),
            request.form.get("reference_number"),
            request.form.get("from_entity"),
            request.form.get("to_entity"),
            request.form.get("subject", ""),
            request.form.get("document_type"),
            current_user.badge_number,
            request.form.get("action_required"),
            request.form.get("action_deadline"),
        ))
        conn.commit()

        log_audit("correspondence", case_id, "CREATE",
                 current_user.badge_number, current_user.full_name)

        flash("Correspondence logged.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("file_movement.correspondence_register", case_id=case_id))


@bp.route("/cases/<path:case_id>/investigator-card")
@login_required
@permission_required("cases", "read")
def investigator_card(case_id):
    """Investigator index card view."""
    conn = get_db()
    try:
        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not case:
            flash("Case not found.", "danger")
            return redirect(url_for("cases.case_list"))

        cards = conn.execute("""
            SELECT ic.*, o.full_name, o.rank
            FROM investigator_cards ic
            LEFT JOIN officers o ON ic.officer_badge = o.badge_number
            WHERE ic.case_id = ?
            ORDER BY ic.assigned_date DESC
        """, (case_id,)).fetchall()

        return render_template("file_movement/investigator_card.html",
                             case=case, cards=cards)
    finally:
        conn.close()
