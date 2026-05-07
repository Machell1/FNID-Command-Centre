"""
Disclosure Log Routes

Manages the prosecution disclosure process for JCF cases, tracking
material disclosed to the defence, service methods, acknowledgements,
PII applications, and supplementary disclosure requirements.
"""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import generate_id, get_db, log_audit
from ..rbac import permission_required

bp = Blueprint("disclosure", __name__, url_prefix="/disclosure")


# ── Disclosure List ──────────────────────────────────────────────────

@bp.route("/")
@login_required
@permission_required("cases", "read")
def disclosure_list():
    """List all disclosure records with filters."""
    conn = get_db()
    try:
        case_filter = request.args.get("case_id", "")
        status_filter = request.args.get("disclosure_status", "")

        query = "SELECT * FROM disclosure_log WHERE 1=1"
        params = []

        if case_filter:
            query += " AND linked_case_id LIKE ?"
            params.append(f"%{case_filter}%")
        if status_filter:
            query += " AND disclosure_status = ?"
            params.append(status_filter)

        query += " ORDER BY created_at DESC"
        disclosures = conn.execute(query, params).fetchall()

        # Distinct statuses for filter
        statuses = conn.execute(
            "SELECT DISTINCT disclosure_status FROM disclosure_log "
            "WHERE disclosure_status IS NOT NULL "
            "ORDER BY disclosure_status"
        ).fetchall()

        return render_template(
            "disclosure/list.html",
            disclosures=disclosures,
            statuses=[s["disclosure_status"] for s in statuses],
            case_filter=case_filter,
            status_filter=status_filter,
        )
    finally:
        conn.close()


# ── Disclosure Detail ────────────────────────────────────────────────

@bp.route("/<disclosure_id>")
@login_required
@permission_required("cases", "read")
def disclosure_detail(disclosure_id):
    """Full detail view of a disclosure record."""
    conn = get_db()
    try:
        entry = conn.execute(
            "SELECT * FROM disclosure_log WHERE disclosure_id = ?",
            (disclosure_id,)
        ).fetchone()

        if not entry:
            flash("Disclosure record not found.", "danger")
            return redirect(url_for("disclosure.disclosure_list"))

        return render_template(
            "disclosure/detail.html",
            entry=entry,
        )
    finally:
        conn.close()


# ── New Disclosure ───────────────────────────────────────────────────

@bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("cases", "create")
def new_disclosure():
    """Create a new disclosure record."""
    conn = get_db()
    try:
        if request.method == "POST":
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            disclosure_id = generate_id("DIS", "disclosure_log", "disclosure_id")

            conn.execute("""
                INSERT INTO disclosure_log (
                    disclosure_id, linked_case_id, disclosure_date,
                    disclosure_type, material_disclosed, served_on_defence,
                    defence_solicitor, service_method, service_date,
                    acknowledgement_received, pii_application, pii_outcome,
                    supplementary_needed, supplementary_date,
                    disclosure_status, prepared_by, record_status,
                    submitted_by, submitted_date, notes,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                disclosure_id,
                request.form.get("linked_case_id", ""),
                request.form.get("disclosure_date", ""),
                request.form.get("disclosure_type", ""),
                request.form.get("material_disclosed", ""),
                request.form.get("served_on_defence", "No"),
                request.form.get("defence_solicitor", ""),
                request.form.get("service_method", ""),
                request.form.get("service_date", ""),
                request.form.get("acknowledgement_received", "No"),
                request.form.get("pii_application", "No"),
                request.form.get("pii_outcome", ""),
                request.form.get("supplementary_needed", "No"),
                request.form.get("supplementary_date", ""),
                request.form.get("disclosure_status", "Not Required Yet (pre-charge)"),
                request.form.get("prepared_by", ""),
                request.form.get("record_status", "Draft"),
                current_user.badge_number,
                now,
                request.form.get("notes", ""),
                current_user.badge_number,
                now,
                now,
            ))
            conn.commit()

            log_audit("disclosure_log", disclosure_id, "CREATE",
                      current_user.badge_number, current_user.full_name,
                      f"New disclosure record for case {request.form.get('linked_case_id', '')}")

            flash("Disclosure record created successfully.", "success")
            return redirect(url_for("disclosure.disclosure_detail", disclosure_id=disclosure_id))

        case_id = request.args.get("case_id", "")

        return render_template(
            "disclosure/form.html",
            entry=None,
            case_id=case_id,
            is_edit=False,
        )
    finally:
        conn.close()


# ── Edit Disclosure ──────────────────────────────────────────────────

@bp.route("/<disclosure_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("cases", "update")
def edit_disclosure(disclosure_id):
    """Edit an existing disclosure record."""
    conn = get_db()
    try:
        entry = conn.execute(
            "SELECT * FROM disclosure_log WHERE disclosure_id = ?",
            (disclosure_id,)
        ).fetchone()

        if not entry:
            flash("Disclosure record not found.", "danger")
            return redirect(url_for("disclosure.disclosure_list"))

        if request.method == "POST":
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn.execute("""
                UPDATE disclosure_log SET
                    linked_case_id = ?, disclosure_date = ?,
                    disclosure_type = ?, material_disclosed = ?,
                    served_on_defence = ?, defence_solicitor = ?,
                    service_method = ?, service_date = ?,
                    acknowledgement_received = ?, pii_application = ?,
                    pii_outcome = ?, supplementary_needed = ?,
                    supplementary_date = ?, disclosure_status = ?,
                    prepared_by = ?, record_status = ?, notes = ?,
                    updated_at = ?
                WHERE disclosure_id = ?
            """, (
                request.form.get("linked_case_id", ""),
                request.form.get("disclosure_date", ""),
                request.form.get("disclosure_type", ""),
                request.form.get("material_disclosed", ""),
                request.form.get("served_on_defence", "No"),
                request.form.get("defence_solicitor", ""),
                request.form.get("service_method", ""),
                request.form.get("service_date", ""),
                request.form.get("acknowledgement_received", "No"),
                request.form.get("pii_application", "No"),
                request.form.get("pii_outcome", ""),
                request.form.get("supplementary_needed", "No"),
                request.form.get("supplementary_date", ""),
                request.form.get("disclosure_status", ""),
                request.form.get("prepared_by", ""),
                request.form.get("record_status", "Draft"),
                request.form.get("notes", ""),
                now,
                disclosure_id,
            ))
            conn.commit()

            log_audit("disclosure_log", disclosure_id, "UPDATE",
                      current_user.badge_number, current_user.full_name,
                      f"Updated disclosure record {disclosure_id}")

            flash("Disclosure record updated successfully.", "success")
            return redirect(url_for("disclosure.disclosure_detail", disclosure_id=disclosure_id))

        return render_template(
            "disclosure/form.html",
            entry=entry,
            case_id=entry["linked_case_id"],
            is_edit=True,
        )
    finally:
        conn.close()


# ── Case Disclosures ────────────────────────────────────────────────

@bp.route("/case/<path:case_id>")
@login_required
@permission_required("cases", "read")
def case_disclosures(case_id):
    """All disclosures for a specific case."""
    conn = get_db()
    try:
        disclosures = conn.execute(
            "SELECT * FROM disclosure_log WHERE linked_case_id = ? ORDER BY created_at DESC",
            (case_id,)
        ).fetchall()

        # Summary stats
        total = len(disclosures)
        served = sum(1 for d in disclosures if d["served_on_defence"] == "Yes")
        acknowledged = sum(1 for d in disclosures if d["acknowledgement_received"] == "Yes")
        pii_count = sum(1 for d in disclosures if d["pii_application"] == "Yes")
        supplementary = sum(1 for d in disclosures if d["supplementary_needed"] == "Yes")

        # Distinct statuses for filter
        statuses = list(set(d["disclosure_status"] for d in disclosures if d["disclosure_status"]))
        statuses.sort()

        return render_template(
            "disclosure/list.html",
            disclosures=disclosures,
            statuses=statuses,
            case_filter=case_id,
            status_filter="",
            is_case_view=True,
            case_id=case_id,
            total=total,
            served=served,
            acknowledged=acknowledged,
            pii_count=pii_count,
            supplementary=supplementary,
        )
    finally:
        conn.close()
