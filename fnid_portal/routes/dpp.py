"""
DPP Prosecution Pipeline Routes

Manages submissions to the Director of Public Prosecutions (DPP),
tracking case files through the prosecution pipeline including rulings,
returns for investigation, and resubmissions.
"""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import get_db, log_audit
from ..rbac import permission_required

bp = Blueprint("dpp", __name__, url_prefix="/dpp")


# ── Pipeline Dashboard ──────────────────────────────────────────────

@bp.route("/")
@login_required
@permission_required("cases", "read")
def dpp_home():
    """Pipeline dashboard with KPIs and filterable table."""
    conn = get_db()
    try:
        status_filter = request.args.get("dpp_status", "")

        # KPIs
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM dpp_pipeline"
        ).fetchone()["cnt"]

        awaiting = conn.execute(
            "SELECT COUNT(*) as cnt FROM dpp_pipeline WHERE dpp_status = 'Awaiting Ruling'"
        ).fetchone()["cnt"]

        approved = conn.execute(
            "SELECT COUNT(*) as cnt FROM dpp_pipeline WHERE ruling_outcome = 'Approved'"
        ).fetchone()["cnt"]

        returned = conn.execute(
            "SELECT COUNT(*) as cnt FROM dpp_pipeline WHERE returned_for_investigation = 'Yes'"
        ).fetchone()["cnt"]

        # Filtered listing
        query = "SELECT * FROM dpp_pipeline WHERE 1=1"
        params = []

        if status_filter:
            query += " AND dpp_status = ?"
            params.append(status_filter)

        query += " ORDER BY created_at DESC"
        entries = conn.execute(query, params).fetchall()

        # Distinct statuses for filter
        statuses = conn.execute(
            "SELECT DISTINCT dpp_status FROM dpp_pipeline WHERE dpp_status IS NOT NULL ORDER BY dpp_status"
        ).fetchall()

        return render_template(
            "dpp/pipeline.html",
            entries=entries,
            total=total,
            awaiting=awaiting,
            approved=approved,
            returned=returned,
            statuses=[s["dpp_status"] for s in statuses],
            status_filter=status_filter,
        )
    finally:
        conn.close()


# ── Detail View ─────────────────────────────────────────────────────

@bp.route("/<int:id>")
@login_required
@permission_required("cases", "read")
def dpp_detail(id):
    """Full detail view of a DPP pipeline entry."""
    conn = get_db()
    try:
        entry = conn.execute(
            "SELECT * FROM dpp_pipeline WHERE id = ?", (id,)
        ).fetchone()

        if not entry:
            flash("DPP submission not found.", "danger")
            return redirect(url_for("dpp.dpp_home"))

        # Linked case info
        linked_case = None
        if entry["linked_case_id"]:
            linked_case = conn.execute(
                "SELECT * FROM cases WHERE case_id = ?",
                (entry["linked_case_id"],)
            ).fetchone()

        return render_template(
            "dpp/detail.html",
            entry=entry,
            linked_case=linked_case,
        )
    finally:
        conn.close()


# ── New DPP Submission ──────────────────────────────────────────────

@bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("cases", "create")
def new_dpp():
    """Create a new DPP pipeline submission."""
    conn = get_db()
    try:
        if request.method == "POST":
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor = conn.execute("""
                INSERT INTO dpp_pipeline (
                    linked_case_id, classification, oic_name, suspect_name,
                    offence_summary, dpp_file_date, crown_counsel, dpp_status,
                    evidential_sufficiency, public_interest_met,
                    voluntary_bill, prelim_exam, returned_for_investigation,
                    return_reason, record_status, submitted_by, submitted_date,
                    notes, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.form.get("linked_case_id", ""),
                request.form.get("classification", ""),
                request.form.get("oic_name", ""),
                request.form.get("suspect_name", ""),
                request.form.get("offence_summary", ""),
                request.form.get("dpp_file_date", ""),
                request.form.get("crown_counsel", ""),
                request.form.get("dpp_status", "Awaiting Ruling"),
                request.form.get("evidential_sufficiency", "No"),
                request.form.get("public_interest_met", "No"),
                request.form.get("voluntary_bill", "No"),
                request.form.get("prelim_exam", "No"),
                request.form.get("returned_for_investigation", "No"),
                request.form.get("return_reason", ""),
                request.form.get("record_status", "Draft"),
                current_user.badge_number,
                now,
                request.form.get("notes", ""),
                current_user.badge_number,
                now,
                now,
            ))
            conn.commit()
            new_id = cursor.lastrowid

            log_audit("dpp_pipeline", str(new_id), "CREATE",
                      current_user.badge_number, current_user.full_name,
                      f"New DPP submission for case {request.form.get('linked_case_id', '')}")

            flash("DPP submission created successfully.", "success")
            return redirect(url_for("dpp.dpp_detail", id=new_id))

        # GET — check for auto-populate from case
        case_id = request.args.get("case_id", "")
        case_data = None
        if case_id:
            case_data = conn.execute(
                "SELECT * FROM cases WHERE case_id = ?", (case_id,)
            ).fetchone()

        return render_template(
            "dpp/form.html",
            entry=None,
            case_data=case_data,
            case_id=case_id,
            is_edit=False,
        )
    finally:
        conn.close()


# ── Edit DPP Submission ─────────────────────────────────────────────

@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("cases", "update")
def edit_dpp(id):
    """Edit an existing DPP pipeline entry."""
    conn = get_db()
    try:
        entry = conn.execute(
            "SELECT * FROM dpp_pipeline WHERE id = ?", (id,)
        ).fetchone()

        if not entry:
            flash("DPP submission not found.", "danger")
            return redirect(url_for("dpp.dpp_home"))

        if request.method == "POST":
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn.execute("""
                UPDATE dpp_pipeline SET
                    linked_case_id = ?, classification = ?, oic_name = ?,
                    suspect_name = ?, offence_summary = ?, dpp_file_date = ?,
                    crown_counsel = ?, dpp_status = ?, evidential_sufficiency = ?,
                    public_interest_met = ?, voluntary_bill = ?, prelim_exam = ?,
                    returned_for_investigation = ?, return_reason = ?,
                    resubmission_date = ?, record_status = ?, notes = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                request.form.get("linked_case_id", ""),
                request.form.get("classification", ""),
                request.form.get("oic_name", ""),
                request.form.get("suspect_name", ""),
                request.form.get("offence_summary", ""),
                request.form.get("dpp_file_date", ""),
                request.form.get("crown_counsel", ""),
                request.form.get("dpp_status", ""),
                request.form.get("evidential_sufficiency", "No"),
                request.form.get("public_interest_met", "No"),
                request.form.get("voluntary_bill", "No"),
                request.form.get("prelim_exam", "No"),
                request.form.get("returned_for_investigation", "No"),
                request.form.get("return_reason", ""),
                request.form.get("resubmission_date", ""),
                request.form.get("record_status", "Draft"),
                request.form.get("notes", ""),
                now,
                id,
            ))
            conn.commit()

            log_audit("dpp_pipeline", str(id), "UPDATE",
                      current_user.badge_number, current_user.full_name,
                      f"Updated DPP submission #{id}")

            flash("DPP submission updated successfully.", "success")
            return redirect(url_for("dpp.dpp_detail", id=id))

        return render_template(
            "dpp/form.html",
            entry=entry,
            case_data=None,
            case_id=entry["linked_case_id"],
            is_edit=True,
        )
    finally:
        conn.close()


# ── Record Ruling ───────────────────────────────────────────────────

@bp.route("/<int:id>/ruling", methods=["POST"])
@login_required
@permission_required("cases", "update")
def record_ruling(id):
    """Record the DPP ruling for a submission."""
    conn = get_db()
    try:
        entry = conn.execute(
            "SELECT * FROM dpp_pipeline WHERE id = ?", (id,)
        ).fetchone()

        if not entry:
            flash("DPP submission not found.", "danger")
            return redirect(url_for("dpp.dpp_home"))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ruling_date = request.form.get("ruling_date", "")
        ruling_outcome = request.form.get("ruling_outcome", "")
        ruling_notes = request.form.get("ruling_notes", "")

        # Validate sufficiency before approving charge
        if "Charge Approved" in ruling_outcome:
            if entry["evidential_sufficiency"] != "Yes":
                flash("Cannot approve charge: evidential sufficiency not met.", "danger")
                return redirect(url_for("dpp.dpp_detail", id=id))
            if entry["public_interest_met"] != "Yes":
                flash("Cannot approve charge: public interest test not met.", "danger")
                return redirect(url_for("dpp.dpp_detail", id=id))

        # Determine if returned for investigation
        returned = "Yes" if "Returned" in ruling_outcome or "Further Investigation" in ruling_outcome else "No"

        conn.execute("""
            UPDATE dpp_pipeline SET
                ruling_date = ?, ruling_outcome = ?, ruling_notes = ?,
                dpp_status = ?, returned_for_investigation = ?, updated_at = ?
            WHERE id = ?
        """, (
            ruling_date,
            ruling_outcome,
            ruling_notes,
            ruling_outcome,
            returned,
            now,
            id,
        ))

        # Auto-transition case back to investigation if returned
        if returned == "Yes" and entry["linked_case_id"]:
            conn.execute("""
                UPDATE cases SET current_stage = 'investigation', updated_at = ?
                WHERE case_id = ? AND current_stage != 'investigation'
            """, (now, entry["linked_case_id"]))

        conn.commit()

        log_audit("dpp_pipeline", str(id), "RULING",
                  current_user.badge_number, current_user.full_name,
                  f"Ruling recorded: {ruling_outcome}")

        flash(f"Ruling recorded: {ruling_outcome}.", "success")
        return redirect(url_for("dpp.dpp_detail", id=id))
    finally:
        conn.close()
