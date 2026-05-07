"""
SOP Compliance Checklists Routes

Standard Operating Procedure compliance tracking for JCF investigations.
Covers all mandatory steps from initial response through file preparation,
with grouped sections and compliance percentage calculations.
"""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import get_db, log_audit
from ..rbac import permission_required

bp = Blueprint("sop", __name__, url_prefix="/sop")


# ── Checklist field groupings ────────────────────────────────────────

CHECKLIST_SECTIONS = {
    "Initial Response": [
        "station_diary_entry", "crime_report_filed",
        "offence_register_updated", "occurrence_book_entry",
    ],
    "Scene Management": [
        "scene_log_started", "scene_photographed",
        "scene_sketch", "scene_video",
    ],
    "Suspect Processing": [
        "suspect_cautioned", "rights_advised", "attorney_access",
        "detainee_book_entry", "property_book_entry", "lockup_time_recorded",
    ],
    "Evidential": [
        "forty_eight_hr_compliance", "charge_sheet_prepared",
        "exhibit_register_updated", "exhibits_photographed",
        "exhibits_sealed_tagged", "chain_of_custody_started",
        "forensic_submissions_made", "ballistic_submission",
        "drug_field_test", "ibis_etrace_submitted",
    ],
    "Statements": [
        "victim_statement", "witness_statements",
        "suspect_statement_cautioned", "officer_statements",
        "expert_statements",
    ],
    "Identification": [
        "id_parade_required", "id_parade_conducted",
        "cctv_canvass", "neighbourhood_enquiry",
    ],
    "Forensics & Certificates": [
        "forensic_certs_received", "ballistic_cert_received",
        "post_mortem_received",
    ],
    "File Preparation": [
        "all_statements_compiled", "exhibit_list_complete",
        "case_summary_prepared", "evidential_sufficiency_met",
        "public_interest_assessed", "dpp_file_complete",
        "disclosure_schedule", "unused_material_listed",
        "disclosure_served", "pii_application",
        "supplementary_disclosure",
    ],
}

# All checklist fields flattened
ALL_CHECKLIST_FIELDS = []
for fields in CHECKLIST_SECTIONS.values():
    ALL_CHECKLIST_FIELDS.extend(fields)

# Fields that default to N/A rather than No
NA_DEFAULT_FIELDS = {
    "id_parade_required", "id_parade_conducted",
    "pii_application", "supplementary_disclosure",
    "post_mortem_received",
}


def _field_label(field_name):
    """Convert snake_case to Title Case label."""
    return field_name.replace("_", " ").title()


def _calc_compliance(entry):
    """Calculate compliance % for a checklist entry."""
    yes_count = 0
    applicable = 0
    for f in ALL_CHECKLIST_FIELDS:
        val = entry[f] if entry[f] else "No"
        if val == "N/A":
            continue
        applicable += 1
        if val == "Yes":
            yes_count += 1
    if applicable == 0:
        return 0
    return round((yes_count / applicable) * 100, 1)


# ── List all checklists ─────────────────────────────────────────────

@bp.route("/")
@login_required
@permission_required("cases", "read")
def sop_list():
    """List all SOP checklists with compliance percentages."""
    conn = get_db()
    try:
        case_filter = request.args.get("case_id", "")

        query = "SELECT * FROM sop_checklists WHERE 1=1"
        params = []

        if case_filter:
            query += " AND linked_case_id LIKE ?"
            params.append(f"%{case_filter}%")

        query += " ORDER BY created_at DESC"
        checklists = conn.execute(query, params).fetchall()

        # Calculate compliance for each
        checklist_data = []
        for c in checklists:
            compliance = _calc_compliance(c)
            checklist_data.append({"entry": c, "compliance": compliance})

        return render_template(
            "sop/list.html",
            checklist_data=checklist_data,
            case_filter=case_filter,
        )
    finally:
        conn.close()


# ── Detail View ──────────────────────────────────────────────────────

@bp.route("/<int:id>")
@login_required
@permission_required("cases", "read")
def sop_detail(id):
    """View checklist with sections grouped logically."""
    conn = get_db()
    try:
        entry = conn.execute(
            "SELECT * FROM sop_checklists WHERE id = ?", (id,)
        ).fetchone()

        if not entry:
            flash("SOP checklist not found.", "danger")
            return redirect(url_for("sop.sop_list"))

        compliance = _calc_compliance(entry)

        return render_template(
            "sop/detail.html",
            entry=entry,
            compliance=compliance,
            sections=CHECKLIST_SECTIONS,
            field_label=_field_label,
        )
    finally:
        conn.close()


# ── New Checklist ────────────────────────────────────────────────────

@bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("cases", "create")
def new_sop():
    """Create a new SOP compliance checklist."""
    conn = get_db()
    try:
        if request.method == "POST":
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Build field values
            field_values = {}
            for f in ALL_CHECKLIST_FIELDS:
                default = "N/A" if f in NA_DEFAULT_FIELDS else "No"
                field_values[f] = request.form.get(f, default)

            field_names = ", ".join(ALL_CHECKLIST_FIELDS)
            placeholders = ", ".join(["?"] * len(ALL_CHECKLIST_FIELDS))

            cursor = conn.execute(f"""
                INSERT INTO sop_checklists (
                    linked_case_id, oic_name, checklist_date,
                    {field_names},
                    overall_compliance, compliance_notes, record_status,
                    submitted_by, submitted_date, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, {placeholders}, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.form.get("linked_case_id", ""),
                request.form.get("oic_name", ""),
                request.form.get("checklist_date", now[:10]),
                *[field_values[f] for f in ALL_CHECKLIST_FIELDS],
                request.form.get("overall_compliance", ""),
                request.form.get("compliance_notes", ""),
                request.form.get("record_status", "Draft"),
                current_user.badge_number,
                now,
                current_user.badge_number,
                now,
                now,
            ))
            conn.commit()
            new_id = cursor.lastrowid

            log_audit("sop_checklists", str(new_id), "CREATE",
                      current_user.badge_number, current_user.full_name,
                      f"New SOP checklist for case {request.form.get('linked_case_id', '')}")

            flash("SOP checklist created successfully.", "success")
            return redirect(url_for("sop.sop_detail", id=new_id))

        case_id = request.args.get("case_id", "")

        return render_template(
            "sop/form.html",
            entry=None,
            case_id=case_id,
            is_edit=False,
            sections=CHECKLIST_SECTIONS,
            field_label=_field_label,
            na_defaults=NA_DEFAULT_FIELDS,
        )
    finally:
        conn.close()


# ── Edit Checklist ───────────────────────────────────────────────────

@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("cases", "update")
def edit_sop(id):
    """Edit an existing SOP compliance checklist."""
    conn = get_db()
    try:
        entry = conn.execute(
            "SELECT * FROM sop_checklists WHERE id = ?", (id,)
        ).fetchone()

        if not entry:
            flash("SOP checklist not found.", "danger")
            return redirect(url_for("sop.sop_list"))

        if request.method == "POST":
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            set_clauses = []
            params = []
            for f in ALL_CHECKLIST_FIELDS:
                default = "N/A" if f in NA_DEFAULT_FIELDS else "No"
                set_clauses.append(f"{f} = ?")
                params.append(request.form.get(f, default))

            set_clause = ", ".join(set_clauses)

            conn.execute(f"""
                UPDATE sop_checklists SET
                    linked_case_id = ?, oic_name = ?, checklist_date = ?,
                    {set_clause},
                    overall_compliance = ?, compliance_notes = ?,
                    record_status = ?, updated_at = ?
                WHERE id = ?
            """, (
                request.form.get("linked_case_id", ""),
                request.form.get("oic_name", ""),
                request.form.get("checklist_date", ""),
                *params,
                request.form.get("overall_compliance", ""),
                request.form.get("compliance_notes", ""),
                request.form.get("record_status", "Draft"),
                now,
                id,
            ))
            conn.commit()

            log_audit("sop_checklists", str(id), "UPDATE",
                      current_user.badge_number, current_user.full_name,
                      f"Updated SOP checklist #{id}")

            flash("SOP checklist updated successfully.", "success")
            return redirect(url_for("sop.sop_detail", id=id))

        return render_template(
            "sop/form.html",
            entry=entry,
            case_id=entry["linked_case_id"],
            is_edit=True,
            sections=CHECKLIST_SECTIONS,
            field_label=_field_label,
            na_defaults=NA_DEFAULT_FIELDS,
        )
    finally:
        conn.close()


# ── Case Compliance Summary ──────────────────────────────────────────

@bp.route("/compliance/<path:case_id>")
@login_required
@permission_required("cases", "read")
def case_compliance(case_id):
    """Compliance summary for a specific case."""
    conn = get_db()
    try:
        checklists = conn.execute(
            "SELECT * FROM sop_checklists WHERE linked_case_id = ? ORDER BY created_at DESC",
            (case_id,)
        ).fetchall()

        if not checklists:
            flash(f"No SOP checklists found for case {case_id}.", "warning")
            return redirect(url_for("sop.sop_list"))

        checklist_data = []
        for c in checklists:
            compliance = _calc_compliance(c)
            checklist_data.append({"entry": c, "compliance": compliance})

        # Section-level compliance from most recent checklist
        latest = checklists[0]
        section_compliance = {}
        for section_name, fields in CHECKLIST_SECTIONS.items():
            yes_count = 0
            applicable = 0
            for f in fields:
                val = latest[f] if latest[f] else "No"
                if val == "N/A":
                    continue
                applicable += 1
                if val == "Yes":
                    yes_count += 1
            if applicable > 0:
                section_compliance[section_name] = round((yes_count / applicable) * 100, 1)
            else:
                section_compliance[section_name] = 0

        overall = _calc_compliance(latest)

        return render_template(
            "sop/detail.html",
            entry=latest,
            compliance=overall,
            sections=CHECKLIST_SECTIONS,
            field_label=_field_label,
            case_id=case_id,
            checklist_data=checklist_data,
            section_compliance=section_compliance,
            is_case_view=True,
        )
    finally:
        conn.close()
