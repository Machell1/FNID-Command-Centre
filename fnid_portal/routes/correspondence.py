"""
Correspondence Tracking Routes

Inward/Outward correspondence register for case-related documents,
court orders, DPP directives, and inter-agency communications.

Officers can compose the full memo body in-app, save it to the case file,
and print or export it as a PDF on JCF letterhead.
"""

from datetime import datetime
from io import BytesIO

from flask import (
    Blueprint, flash, redirect, render_template, request, send_file, url_for,
)
from flask_login import current_user, login_required

from ..models import get_db, log_audit
from ..pdf_export import render_pdf
from ..rbac import permission_required

bp = Blueprint("correspondence", __name__, url_prefix="/correspondence")

DIRECTION_OPTIONS = ["Incoming", "Outgoing"]

DOCUMENT_TYPES = [
    "Letter",
    "Memo",
    "Fax",
    "Email",
    "Court Order",
    "Subpoena",
    "DPP Directive",
    "Other",
]

ACTION_STATUSES = ["Pending", "In Progress", "Completed", "N/A"]


@bp.route("/")
@login_required
@permission_required("registry", "read")
def correspondence_list():
    """List all correspondence with optional filters."""
    case_id = request.args.get("case_id", "").strip()
    direction = request.args.get("direction", "").strip()
    status = request.args.get("status", "").strip()

    conn = get_db()
    try:
        query = "SELECT * FROM correspondence WHERE 1=1"
        params = []

        if case_id:
            query += " AND case_id = ?"
            params.append(case_id)
        if direction:
            query += " AND direction = ?"
            params.append(direction)
        if status:
            query += " AND action_status = ?"
            params.append(status)

        query += " ORDER BY date DESC"
        items = conn.execute(query, params).fetchall()

        return render_template(
            "correspondence/list.html",
            items=items,
            filter_case_id=case_id,
            filter_direction=direction,
            filter_status=status,
            directions=DIRECTION_OPTIONS,
            action_statuses=ACTION_STATUSES,
        )
    finally:
        conn.close()


@bp.route("/<int:id>")
@login_required
@permission_required("registry", "read")
def correspondence_detail(id):
    """View full correspondence detail."""
    conn = get_db()
    try:
        item = conn.execute(
            "SELECT * FROM correspondence WHERE id = ?", (id,)
        ).fetchone()
        if not item:
            flash("Correspondence record not found.", "danger")
            return redirect(url_for("correspondence.correspondence_list"))

        return render_template(
            "correspondence/detail.html",
            item=item,
            action_statuses=ACTION_STATUSES,
        )
    finally:
        conn.close()


@bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("registry", "create")
def new_correspondence():
    """Create a new correspondence record."""
    if request.method == "POST":
        conn = get_db()
        try:
            case_id = request.form.get("case_id", "").strip() or None
            direction = request.form.get("direction", "").strip()
            date = request.form.get("date", "").strip()
            reference_number = request.form.get("reference_number", "").strip() or None
            from_entity = request.form.get("from_entity", "").strip() or None
            to_entity = request.form.get("to_entity", "").strip() or None
            subject = request.form.get("subject", "").strip()
            document_type = request.form.get("document_type", "").strip() or None
            action_required = request.form.get("action_required", "").strip() or None
            action_deadline = request.form.get("action_deadline", "").strip() or None
            notes = request.form.get("notes", "").strip() or None

            if not direction or not date or not subject:
                flash("Direction, date, and subject are required.", "danger")
                return render_template(
                    "correspondence/form.html",
                    item=request.form,
                    is_edit=False,
                    directions=DIRECTION_OPTIONS,
                    document_types=DOCUMENT_TYPES,
                )

            body = request.form.get("body", "").strip() or None
            cursor = conn.execute(
                """INSERT INTO correspondence
                   (case_id, direction, date, reference_number, from_entity,
                    to_entity, subject, document_type, logged_by, logged_at,
                    action_required, action_deadline, action_status, notes, body)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)""",
                (
                    case_id, direction, date, reference_number, from_entity,
                    to_entity, subject, document_type,
                    current_user.badge_number, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    action_required, action_deadline, notes, body,
                ),
            )
            conn.commit()
            new_id = cursor.lastrowid

            log_audit(
                "correspondence", str(new_id), "CREATE",
                current_user.badge_number, current_user.full_name,
                f"New {direction} correspondence: {subject}",
            )

            flash("Correspondence record created successfully.", "success")
            return redirect(url_for("correspondence.correspondence_detail", id=new_id))
        finally:
            conn.close()

    return render_template(
        "correspondence/form.html",
        item=None,
        is_edit=False,
        directions=DIRECTION_OPTIONS,
        document_types=DOCUMENT_TYPES,
    )


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("registry", "update")
def edit_correspondence(id):
    """Edit an existing correspondence record."""
    conn = get_db()
    try:
        item = conn.execute(
            "SELECT * FROM correspondence WHERE id = ?", (id,)
        ).fetchone()
        if not item:
            flash("Correspondence record not found.", "danger")
            return redirect(url_for("correspondence.correspondence_list"))

        if request.method == "POST":
            case_id = request.form.get("case_id", "").strip() or None
            direction = request.form.get("direction", "").strip()
            date = request.form.get("date", "").strip()
            reference_number = request.form.get("reference_number", "").strip() or None
            from_entity = request.form.get("from_entity", "").strip() or None
            to_entity = request.form.get("to_entity", "").strip() or None
            subject = request.form.get("subject", "").strip()
            document_type = request.form.get("document_type", "").strip() or None
            action_required = request.form.get("action_required", "").strip() or None
            action_deadline = request.form.get("action_deadline", "").strip() or None
            action_status = request.form.get("action_status", "").strip()
            notes = request.form.get("notes", "").strip() or None

            if not direction or not date or not subject:
                flash("Direction, date, and subject are required.", "danger")
                return render_template(
                    "correspondence/form.html",
                    item=request.form,
                    is_edit=True,
                    record_id=id,
                    directions=DIRECTION_OPTIONS,
                    document_types=DOCUMENT_TYPES,
                )

            body = request.form.get("body", "").strip() or None
            conn.execute(
                """UPDATE correspondence SET
                   case_id=?, direction=?, date=?, reference_number=?,
                   from_entity=?, to_entity=?, subject=?, document_type=?,
                   action_required=?, action_deadline=?, action_status=?,
                   notes=?, body=?
                   WHERE id=?""",
                (
                    case_id, direction, date, reference_number, from_entity,
                    to_entity, subject, document_type,
                    action_required, action_deadline, action_status,
                    notes, body, id,
                ),
            )
            conn.commit()

            log_audit(
                "correspondence", str(id), "UPDATE",
                current_user.badge_number, current_user.full_name,
                f"Updated correspondence: {subject}",
            )

            flash("Correspondence record updated successfully.", "success")
            return redirect(url_for("correspondence.correspondence_detail", id=id))

        return render_template(
            "correspondence/form.html",
            item=item,
            is_edit=True,
            record_id=id,
            directions=DIRECTION_OPTIONS,
            document_types=DOCUMENT_TYPES,
            action_statuses=ACTION_STATUSES,
        )
    finally:
        conn.close()


def _fetch(conn, id):
    return conn.execute(
        "SELECT * FROM correspondence WHERE id = ?", (id,)
    ).fetchone()


@bp.route("/<int:id>/print")
@login_required
@permission_required("registry", "read")
def print_memo(id):
    """Print-ready memo on JCF letterhead."""
    conn = get_db()
    try:
        item = _fetch(conn, id)
        if not item:
            flash("Correspondence record not found.", "danger")
            return redirect(url_for("correspondence.correspondence_list"))
        return render_template(
            "correspondence/print.html", item=item, mode="print",
        )
    finally:
        conn.close()


@bp.route("/<int:id>/pdf")
@login_required
@permission_required("registry", "read")
def pdf_memo(id):
    """Generate a PDF download of the memo."""
    conn = get_db()
    try:
        item = _fetch(conn, id)
        if not item:
            flash("Correspondence record not found.", "danger")
            return redirect(url_for("correspondence.correspondence_list"))

        html = render_template("correspondence/print.html", item=item, mode="pdf")
        pdf_buf = render_pdf(html)
        if pdf_buf is None:
            return html, 200, {"Content-Type": "text/html"}

        slug = (item["subject"] or "memo").replace(" ", "_")[:40]
        filename = f"Memo_{id}_{slug}.pdf"
        return send_file(
            BytesIO(pdf_buf.read()),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    finally:
        conn.close()


@bp.route("/case/<path:case_id>")
@login_required
@permission_required("registry", "read")
def case_correspondence(case_id):
    """List all correspondence for a specific case."""
    conn = get_db()
    try:
        case = conn.execute(
            "SELECT * FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()

        items = conn.execute(
            "SELECT * FROM correspondence WHERE case_id = ? ORDER BY date DESC",
            (case_id,),
        ).fetchall()

        return render_template(
            "correspondence/list.html",
            items=items,
            case=case,
            case_id=case_id,
            filter_case_id=case_id,
            filter_direction="",
            filter_status="",
            directions=DIRECTION_OPTIONS,
            action_statuses=ACTION_STATUSES,
        )
    finally:
        conn.close()


@bp.route("/<int:id>/action", methods=["POST"])
@login_required
@permission_required("registry", "update")
def update_action(id):
    """Update the action status of a correspondence record."""
    conn = get_db()
    try:
        item = conn.execute(
            "SELECT * FROM correspondence WHERE id = ?", (id,)
        ).fetchone()
        if not item:
            flash("Correspondence record not found.", "danger")
            return redirect(url_for("correspondence.correspondence_list"))

        new_status = request.form.get("action_status", "").strip()
        if new_status not in ACTION_STATUSES:
            flash("Invalid action status.", "danger")
            return redirect(url_for("correspondence.correspondence_detail", id=id))

        conn.execute(
            "UPDATE correspondence SET action_status = ? WHERE id = ?",
            (new_status, id),
        )
        conn.commit()

        log_audit(
            "correspondence", str(id), "UPDATE",
            current_user.badge_number, current_user.full_name,
            f"Action status changed to {new_status}",
        )

        flash(f"Action status updated to {new_status}.", "success")
        return redirect(url_for("correspondence.correspondence_detail", id=id))
    finally:
        conn.close()
