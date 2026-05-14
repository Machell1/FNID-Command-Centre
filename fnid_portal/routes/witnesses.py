"""
Witness Statement Management Routes

Manages witness statements for JCF investigations, including recording
witness details, statement metadata, special measures requirements,
and court availability tracking.
"""

from datetime import datetime
from io import BytesIO

from flask import (
    Blueprint, flash, make_response, redirect, render_template, request,
    send_file, url_for,
)
from flask_login import current_user, login_required

from ..models import generate_id, get_db, log_audit
from ..pdf_export import render_pdf
from ..rbac import permission_required

bp = Blueprint("witnesses", __name__, url_prefix="/witnesses")


# ── Witness List ─────────────────────────────────────────────────────

@bp.route("/")
@login_required
@permission_required("cases", "read")
def witness_list():
    """List all witness statements with filters."""
    conn = get_db()
    try:
        case_filter = request.args.get("case_id", "")
        type_filter = request.args.get("witness_type", "")

        query = "SELECT * FROM witness_statements WHERE 1=1"
        params = []

        if case_filter:
            query += " AND linked_case_id LIKE ?"
            params.append(f"%{case_filter}%")
        if type_filter:
            query += " AND witness_type = ?"
            params.append(type_filter)

        query += " ORDER BY created_at DESC"
        witnesses = conn.execute(query, params).fetchall()

        # Distinct types for filter
        types = conn.execute(
            "SELECT DISTINCT witness_type FROM witness_statements WHERE witness_type IS NOT NULL ORDER BY witness_type"
        ).fetchall()

        return render_template(
            "witnesses/list.html",
            witnesses=witnesses,
            types=[t["witness_type"] for t in types],
            case_filter=case_filter,
            type_filter=type_filter,
        )
    finally:
        conn.close()


# ── Witness Detail ───────────────────────────────────────────────────

@bp.route("/<statement_id>")
@login_required
@permission_required("cases", "read")
def witness_detail(statement_id):
    """Full detail view of a witness statement."""
    conn = get_db()
    try:
        entry = conn.execute(
            "SELECT * FROM witness_statements WHERE statement_id = ?",
            (statement_id,)
        ).fetchone()

        if not entry:
            flash("Witness statement not found.", "danger")
            return redirect(url_for("witnesses.witness_list"))

        return render_template(
            "witnesses/detail.html",
            entry=entry,
        )
    finally:
        conn.close()


# ── New Witness Statement ────────────────────────────────────────────

@bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("cases", "create")
def new_witness():
    """Create a new witness statement record."""
    conn = get_db()
    try:
        if request.method == "POST":
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            statement_id = generate_id("WIT", "witness_statements", "statement_id")

            conn.execute("""
                INSERT INTO witness_statements (
                    statement_id, linked_case_id, witness_name, witness_type,
                    witness_address, witness_phone, relation_to_case,
                    statement_date, statement_taken_by, statement_pages,
                    statement_signed, witness_willing, special_measures_needed,
                    special_measures_type, available_for_court,
                    record_status, submitted_by, submitted_date, notes,
                    statement_text,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                statement_id,
                request.form.get("linked_case_id", ""),
                request.form.get("witness_name", ""),
                request.form.get("witness_type", ""),
                request.form.get("witness_address", ""),
                request.form.get("witness_phone", ""),
                request.form.get("relation_to_case", ""),
                request.form.get("statement_date", ""),
                request.form.get("statement_taken_by", ""),
                request.form.get("statement_pages", ""),
                request.form.get("statement_signed", "No"),
                request.form.get("witness_willing", "Yes"),
                request.form.get("special_measures_needed", "No"),
                request.form.get("special_measures_type", ""),
                request.form.get("available_for_court", "Yes"),
                request.form.get("record_status", "Draft"),
                current_user.badge_number,
                now,
                request.form.get("notes", ""),
                request.form.get("statement_text", ""),
                current_user.badge_number,
                now,
                now,
            ))
            conn.commit()

            log_audit("witness_statements", statement_id, "CREATE",
                      current_user.badge_number, current_user.full_name,
                      f"New witness statement for case {request.form.get('linked_case_id', '')}")

            flash("Witness statement created successfully.", "success")
            return redirect(url_for("witnesses.witness_detail", statement_id=statement_id))

        case_id = request.args.get("case_id", "")

        return render_template(
            "witnesses/form.html",
            entry=None,
            case_id=case_id,
            is_edit=False,
        )
    finally:
        conn.close()


# ── Edit Witness Statement ───────────────────────────────────────────

@bp.route("/<statement_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("cases", "update")
def edit_witness(statement_id):
    """Edit an existing witness statement."""
    conn = get_db()
    try:
        entry = conn.execute(
            "SELECT * FROM witness_statements WHERE statement_id = ?",
            (statement_id,)
        ).fetchone()

        if not entry:
            flash("Witness statement not found.", "danger")
            return redirect(url_for("witnesses.witness_list"))

        if request.method == "POST":
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn.execute("""
                UPDATE witness_statements SET
                    linked_case_id = ?, witness_name = ?, witness_type = ?,
                    witness_address = ?, witness_phone = ?, relation_to_case = ?,
                    statement_date = ?, statement_taken_by = ?, statement_pages = ?,
                    statement_signed = ?, witness_willing = ?,
                    special_measures_needed = ?, special_measures_type = ?,
                    available_for_court = ?, record_status = ?, notes = ?,
                    statement_text = ?, updated_at = ?
                WHERE statement_id = ?
            """, (
                request.form.get("linked_case_id", ""),
                request.form.get("witness_name", ""),
                request.form.get("witness_type", ""),
                request.form.get("witness_address", ""),
                request.form.get("witness_phone", ""),
                request.form.get("relation_to_case", ""),
                request.form.get("statement_date", ""),
                request.form.get("statement_taken_by", ""),
                request.form.get("statement_pages", ""),
                request.form.get("statement_signed", "No"),
                request.form.get("witness_willing", "Yes"),
                request.form.get("special_measures_needed", "No"),
                request.form.get("special_measures_type", ""),
                request.form.get("available_for_court", "Yes"),
                request.form.get("record_status", "Draft"),
                request.form.get("notes", ""),
                request.form.get("statement_text", ""),
                now,
                statement_id,
            ))
            conn.commit()

            log_audit("witness_statements", statement_id, "UPDATE",
                      current_user.badge_number, current_user.full_name,
                      f"Updated witness statement {statement_id}")

            flash("Witness statement updated successfully.", "success")
            return redirect(url_for("witnesses.witness_detail", statement_id=statement_id))

        return render_template(
            "witnesses/form.html",
            entry=entry,
            case_id=entry["linked_case_id"],
            is_edit=True,
        )
    finally:
        conn.close()


# ── Print & PDF Export ───────────────────────────────────────────────


def _fetch_statement(conn, statement_id):
    row = conn.execute(
        "SELECT * FROM witness_statements WHERE statement_id = ?",
        (statement_id,),
    ).fetchone()
    return row


@bp.route("/<statement_id>/print")
@login_required
@permission_required("cases", "read")
def print_statement(statement_id):
    """Render a print-ready statement page (officer hits Ctrl+P from here)."""
    conn = get_db()
    try:
        entry = _fetch_statement(conn, statement_id)
        if not entry:
            flash("Witness statement not found.", "danger")
            return redirect(url_for("witnesses.witness_list"))
        return render_template(
            "witnesses/print.html", entry=entry, mode="print",
        )
    finally:
        conn.close()


@bp.route("/<statement_id>/pdf")
@login_required
@permission_required("cases", "read")
def pdf_statement(statement_id):
    """Generate a PDF download of the statement."""
    conn = get_db()
    try:
        entry = _fetch_statement(conn, statement_id)
        if not entry:
            flash("Witness statement not found.", "danger")
            return redirect(url_for("witnesses.witness_list"))

        html = render_template("witnesses/print.html", entry=entry, mode="pdf")
        pdf_buf = render_pdf(html)
        if pdf_buf is None:
            # Fall back to the print view if PDF generation failed.
            return html, 200, {"Content-Type": "text/html"}

        filename = f"Statement_{entry['statement_id']}.pdf"
        return send_file(
            BytesIO(pdf_buf.read()),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    finally:
        conn.close()


# ── Case Witnesses ───────────────────────────────────────────────────

@bp.route("/case/<path:case_id>")
@login_required
@permission_required("cases", "read")
def case_witnesses(case_id):
    """All witnesses for a specific case with summary stats."""
    conn = get_db()
    try:
        witnesses = conn.execute(
            "SELECT * FROM witness_statements WHERE linked_case_id = ? ORDER BY created_at DESC",
            (case_id,)
        ).fetchall()

        # Summary stats
        total = len(witnesses)
        signed = sum(1 for w in witnesses if w["statement_signed"] == "Yes")
        willing = sum(1 for w in witnesses if w["witness_willing"] == "Yes")
        available = sum(1 for w in witnesses if w["available_for_court"] == "Yes")
        special_measures = sum(1 for w in witnesses if w["special_measures_needed"] == "Yes")

        # Group by type
        type_counts = {}
        for w in witnesses:
            wtype = w["witness_type"] or "Unknown"
            type_counts[wtype] = type_counts.get(wtype, 0) + 1

        return render_template(
            "witnesses/list.html",
            witnesses=witnesses,
            types=list(type_counts.keys()),
            case_filter=case_id,
            type_filter="",
            is_case_view=True,
            case_id=case_id,
            total=total,
            signed=signed,
            willing=willing,
            available=available,
            special_measures=special_measures,
            type_counts=type_counts,
        )
    finally:
        conn.close()
