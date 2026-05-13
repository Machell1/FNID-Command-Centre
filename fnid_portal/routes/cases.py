"""
Case Lifecycle Routes

Full case management lifecycle from intake through closure,
following the JCF case management policy.
"""

from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .. import case_numbers
from ..case_numbers import (
    generate_case_reference,
    generate_dcrr_number,
    generate_major_crime_register_number,
)
from ..deadlines import schedule_review
from ..models import get_db, log_audit
from ..official_cr_forms import OFFICIAL_CR_FORM_DEFINITIONS
from ..rbac import permission_required
from . import _cfg_module

bp = Blueprint("cases", __name__, url_prefix="/cases")

# Valid case lifecycle transitions per JCF Case Management Policy
# JCF/FW/PL/C&S/0001/2024 Sections 6.3, 9.1-9.3
VALID_TRANSITIONS = {
    "intake": {"appreciation", "vetting", "assignment"},
    "appreciation": {"vetting", "assignment"},         # Section 9.1 - Appreciating Report
    "vetting": {"assignment", "suspended"},             # Section 9.2.1 - Preliminary Vetting
    "assignment": {"investigation"},                    # Section 9.2.2 - Case Assignment
    "investigation": {"follow_up", "review", "court_preparation", "suspended", "cleared"},
    "follow_up": {"review", "investigation", "court_preparation", "suspended", "cleared"},
    "review": {"investigation", "follow_up", "court_preparation", "suspended", "cleared", "closed"},
    "court_preparation": {"before_court", "investigation"},  # Section 9.3.6
    "before_court": {"cleared", "closed", "investigation"},
    "suspended": {"reopened", "closed", "cold_case"},   # Section 9.3.9 - reviewed every 90 days
    "reopened": {"investigation"},                      # Case reopened with new leads
    "cold_case": {"reopened", "closed"},                # Section 9.3.10 - suspended 3+ years
    "cleared": {"closed"},                              # Section 6.3.3 -> 6.3.4
    "closed": set(),                                    # Section 6.3.4 - Terminal state
}


def _validate_transition(current_stage, target_stage):
    """Check if a stage transition is valid."""
    allowed = VALID_TRANSITIONS.get(current_stage, set())
    return target_stage in allowed


def _record_lifecycle(conn, case_id, stage, entered_by, notes=None):
    """Record a lifecycle stage entry."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Close the previous stage
    conn.execute("""
        UPDATE case_lifecycle SET exited_at = ?, exited_by = ?
        WHERE case_id = ? AND exited_at IS NULL
    """, (now, entered_by, case_id))

    # Enter the new stage
    conn.execute("""
        INSERT INTO case_lifecycle (case_id, stage, entered_at, entered_by, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (case_id, stage, now, entered_by, notes))

    # Update the case's current stage
    conn.execute(
        "UPDATE cases SET current_stage = ?, updated_at = ? WHERE case_id = ?",
        (stage, now, case_id)
    )


@bp.route("/")
@login_required
def case_list():
    """List all cases with filters."""
    conn = get_db()
    try:
        status_filter = request.args.get("status", "")
        parish_filter = request.args.get("parish", "")
        stage_filter = request.args.get("stage", "")

        query = "SELECT * FROM cases WHERE 1=1"
        params = []

        if status_filter:
            query += " AND case_status LIKE ?"
            params.append(f"%{status_filter}%")
        if parish_filter:
            query += " AND parish = ?"
            params.append(parish_filter)
        if stage_filter:
            query += " AND current_stage = ?"
            params.append(stage_filter)

        # IO sees only own cases unless supervisor
        if current_user.role == "io":
            query += " AND (assigned_io_badge = ? OR oic_badge = ? OR created_by = ?)"
            params.extend([current_user.badge_number, current_user.badge_number,
                          current_user.full_name])

        query += " ORDER BY id DESC"
        cases = conn.execute(query, params).fetchall()

        return render_template("cases/list.html", cases=cases,
                             status_filter=status_filter,
                             parish_filter=parish_filter,
                             stage_filter=stage_filter,
                             cfg=_cfg_module())
    finally:
        conn.close()


@bp.route("/intake", methods=["GET", "POST"])
@login_required
@permission_required("cases", "create")
def intake():
    """Create a new case — full intake form."""
    if request.method == "POST":
        conn = get_db()
        try:
            station_code = request.form.get("station_code", "FNID")
            case_id = generate_case_reference(station_code=station_code)
            register_type = request.form.get("primary_register_type", "dcrr")
            if register_type not in {"dcrr", "major_crime_register"}:
                register_type = "dcrr"
            register_number = (
                generate_major_crime_register_number(station_code=station_code)
                if register_type == "major_crime_register"
                else generate_dcrr_number(station_code=station_code)
            )
            now = datetime.now()
            badge = current_user.badge_number
            name = current_user.full_name

            # Insert into cases table
            conn.execute("""
                INSERT INTO cases (
                    case_id, registration_date, classification, oic_badge, oic_name,
                    oic_rank, parish, division, offence_description, law_and_section,
                    suspect_name, suspect_dob, suspect_address, suspect_occupation,
                    victim_name, victim_address,
                    case_status, dcrr_number, primary_register_type,
                    primary_register_number, station_code, diary_number,
                    crime_type, workflow_type, current_stage,
                    record_status, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                case_id,
                now.strftime("%Y-%m-%d"),
                request.form.get("classification", ""),
                badge,
                name,
                current_user.rank,
                request.form.get("parish", ""),
                request.form.get("division", "FNID Area 3"),
                request.form.get("offence_description", ""),
                request.form.get("law_and_section", ""),
                request.form.get("suspect_name"),
                request.form.get("suspect_dob"),
                request.form.get("suspect_address"),
                request.form.get("suspect_occupation"),
                request.form.get("victim_name"),
                request.form.get("victim_address"),
                "Open - Active Investigation",
                register_number,
                register_type,
                register_number,
                station_code,
                request.form.get("diary_number"),
                request.form.get("crime_type", "major"),
                request.form.get("workflow_type", "non-uniformed"),
                "intake",
                "Draft",
                name,
                now.isoformat(),
                now.isoformat(),
            ))

            register_values = (
                register_number, case_id, now.strftime("%Y-%m-%d"), station_code,
                request.form.get("diary_number"), request.form.get("classification", ""),
                request.form.get("offence_description", ""),
                request.form.get("victim_name"), request.form.get("suspect_name"),
                badge, name, name,
            )
            if register_type == "major_crime_register":
                conn.execute("""
                    INSERT INTO major_crime_register
                        (register_number, case_id, report_date, station,
                         diary_number, classification, offence,
                         complainant_name, suspect_name,
                         oic_badge, oic_name, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, register_values)
            else:
                conn.execute("""
                    INSERT INTO dcrr (dcrr_number, case_id, report_date, station,
                                      diary_number, classification, offence,
                                      complainant_name, suspect_name,
                                      oic_badge, oic_name, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, register_values)

            # Record lifecycle entry
            _record_lifecycle(conn, case_id, "intake", name,
                            "Initial case intake and registration")

            # Schedule preliminary vetting review
            conn.commit()
            schedule_review(case_id, "preliminary_vetting", days_from_now=1,
                          created_by=name)

            log_audit("cases", case_id, "CREATE", badge, name,
                     f"New case intake: {request.form.get('classification')}")

            register_label = "Major Crime Register" if register_type == "major_crime_register" else "DCRR"
            flash(f"Case {case_id} created successfully ({register_label}: {register_number}).", "success")
            return redirect(url_for("cases.case_detail", case_id=case_id))

        except Exception as e:
            conn.rollback()
            current_app.logger.exception("Case creation error"); flash("An error occurred creating the case.", "danger")
        finally:
            conn.close()

    cfg = _cfg_module()
    return render_template("cases/intake.html", cfg=cfg, case_numbers=case_numbers)


@bp.route("/<path:case_id>")
@login_required
@permission_required("cases", "read")
def case_detail(case_id):
    """Case detail view with timeline and linked records."""
    conn = get_db()
    try:
        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not case:
            flash("Case not found.", "danger")
            return redirect(url_for("cases.case_list"))

        # Get lifecycle timeline
        lifecycle = conn.execute("""
            SELECT * FROM case_lifecycle WHERE case_id = ? ORDER BY entered_at
        """, (case_id,)).fetchall()

        # Get linked records
        forms = conn.execute(
            "SELECT * FROM cr_forms WHERE case_id = ? ORDER BY created_at", (case_id,)
        ).fetchall()
        reviews = conn.execute(
            "SELECT * FROM case_reviews WHERE case_id = ? ORDER BY scheduled_date",
            (case_id,)
        ).fetchall()
        movements = conn.execute(
            "SELECT * FROM file_movements WHERE case_id = ? ORDER BY moved_at DESC",
            (case_id,)
        ).fetchall()
        exhibits = conn.execute(
            "SELECT * FROM chain_of_custody WHERE linked_case_id = ?", (case_id,)
        ).fetchall()
        arrests = conn.execute(
            "SELECT * FROM arrests WHERE linked_case_id = ?", (case_id,)
        ).fetchall()
        statements = conn.execute(
            "SELECT * FROM witness_statements WHERE linked_case_id = ?", (case_id,)
        ).fetchall()
        inv_card = conn.execute(
            "SELECT * FROM investigator_cards WHERE case_id = ? AND status = 'Active'",
            (case_id,)
        ).fetchone()

        # Get available officers for assignment
        officers = conn.execute(
            "SELECT badge_number, full_name, rank FROM officers WHERE is_active = 1"
        ).fetchall()

        return render_template("cases/detail.html",
                             case=case, lifecycle=lifecycle,
                             forms=forms, reviews=reviews,
                             movements=movements, exhibits=exhibits,
                             arrests=arrests, statements=statements,
                             inv_card=inv_card, officers=officers,
                             form_definitions=OFFICIAL_CR_FORM_DEFINITIONS)
    finally:
        conn.close()


@bp.route("/<path:case_id>/timeline")
@login_required
@permission_required("cases", "read")
def case_timeline(case_id):
    """Visual case timeline view."""
    conn = get_db()
    try:
        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        lifecycle = conn.execute("""
            SELECT * FROM case_lifecycle WHERE case_id = ? ORDER BY entered_at
        """, (case_id,)).fetchall()
        return render_template("cases/timeline.html", case=case, lifecycle=lifecycle)
    finally:
        conn.close()


@bp.route("/<path:case_id>/assign", methods=["POST"])
@login_required
@permission_required("cases", "assign")
def assign_case(case_id):
    """Assign case to an investigating officer."""
    conn = get_db()
    try:
        io_badge = request.form.get("io_badge")
        if not io_badge:
            flash("No officer selected.", "danger")
            return redirect(url_for("cases.case_detail", case_id=case_id))

        officer = conn.execute(
            "SELECT * FROM officers WHERE badge_number = ?", (io_badge,)
        ).fetchone()
        if not officer:
            flash("Officer not found.", "danger")
            return redirect(url_for("cases.case_detail", case_id=case_id))

        now = datetime.now()
        name = current_user.full_name

        conn.execute("""
            UPDATE cases SET assigned_io_badge = ?, assigned_date = ?,
                             current_stage = 'assignment', updated_at = ?
            WHERE case_id = ?
        """, (io_badge, now.strftime("%Y-%m-%d"), now.isoformat(), case_id))

        # Create investigator card
        conn.execute("""
            INSERT INTO investigator_cards
            (officer_badge, case_id, assigned_date, assignment_type,
             supervisor_badge, status)
            VALUES (?, ?, ?, 'primary', ?, 'Active')
        """, (io_badge, case_id, now.strftime("%Y-%m-%d"), current_user.badge_number))

        _record_lifecycle(conn, case_id, "assignment", name,
                        f"Assigned to {officer['full_name']} ({io_badge})")

        conn.commit()
        schedule_review(case_id, "first_review", created_by=name)

        log_audit("cases", case_id, "ASSIGN", current_user.badge_number, name,
                 f"Assigned to {officer['full_name']}")

        flash(f"Case assigned to {officer['rank']} {officer['full_name']}.", "success")
    except Exception as e:
        conn.rollback()
        current_app.logger.exception("Case assignment error"); flash("An error occurred assigning the case.", "danger")
    finally:
        conn.close()

    return redirect(url_for("cases.case_detail", case_id=case_id))


@bp.route("/<path:case_id>/transition", methods=["POST"])
@login_required
@permission_required("cases", "update")
def transition_case(case_id):
    """Transition case to a new stage."""
    conn = get_db()
    try:
        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not case:
            flash("Case not found.", "danger")
            return redirect(url_for("cases.case_list"))

        target_stage = request.form.get("target_stage")
        notes = request.form.get("notes", "")
        current_stage = case["current_stage"] or "intake"

        if not _validate_transition(current_stage, target_stage):
            flash(f"Invalid transition: {current_stage} → {target_stage}", "danger")
            return redirect(url_for("cases.case_detail", case_id=case_id))

        name = current_user.full_name
        now = datetime.now()

        _record_lifecycle(conn, case_id, target_stage, name, notes)

        # Handle special transitions
        updates = {"current_stage": target_stage, "updated_at": now.isoformat()}

        if target_stage == "suspended":
            updates["suspended_date"] = now.strftime("%Y-%m-%d")
            updates["suspended_reason"] = request.form.get("reason", "")
            updates["case_status"] = "Cold Case - Under Periodic Review"

        elif target_stage == "closed":
            updates["closed_date"] = now.strftime("%Y-%m-%d")
            updates["closed_reason"] = request.form.get("reason", "")
            outcome = request.form.get("outcome", "")
            if outcome:
                updates["case_status"] = outcome

        elif target_stage == "reopened":
            updates["reopened_date"] = now.strftime("%Y-%m-%d")
            updates["case_status"] = "Open - Active Investigation"

        elif target_stage == "review":
            updates["last_review_date"] = now.strftime("%Y-%m-%d")

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        conn.execute(
            f"UPDATE cases SET {set_clause} WHERE case_id = ?",
            list(updates.values()) + [case_id]
        )

        conn.commit()

        # Schedule follow-up reviews
        if target_stage in ("investigation", "follow_up", "reopened"):
            schedule_review(case_id, "followup_28day", created_by=name)
        elif target_stage == "suspended":
            schedule_review(case_id, "suspended_90day", created_by=name)

        log_audit("cases", case_id, "TRANSITION", current_user.badge_number,
                 name, f"{current_stage} → {target_stage}")

        flash(f"Case transitioned to {target_stage}.", "success")
    except Exception as e:
        conn.rollback()
        current_app.logger.exception("Case operation error"); flash("An error occurred. Please try again.", "danger")
    finally:
        conn.close()

    return redirect(url_for("cases.case_detail", case_id=case_id))


@bp.route("/<path:case_id>/review", methods=["GET", "POST"])
@login_required
@permission_required("cases", "approve")
def case_review(case_id):
    """Record a case review."""
    conn = get_db()
    try:
        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not case:
            flash("Case not found.", "danger")
            return redirect(url_for("cases.case_list"))

        if request.method == "POST":
            review_id = request.form.get("review_id")
            now = datetime.now()
            name = current_user.full_name

            conn.execute("""
                UPDATE case_reviews SET
                    actual_date = ?, reviewer_badge = ?, reviewer_name = ?,
                    outcome = ?, findings = ?, directives = ?,
                    next_review_date = ?, status = 'Completed'
                WHERE id = ?
            """, (
                now.strftime("%Y-%m-%d"),
                current_user.badge_number, name,
                request.form.get("outcome"),
                request.form.get("findings"),
                request.form.get("directives"),
                request.form.get("next_review_date"),
                review_id,
            ))

            # Update case
            conn.execute("""
                UPDATE cases SET last_review_date = ?, next_review_date = ?,
                                 updated_at = ?
                WHERE case_id = ?
            """, (now.strftime("%Y-%m-%d"),
                  request.form.get("next_review_date"),
                  now.isoformat(), case_id))

            conn.commit()
            log_audit("case_reviews", str(review_id), "REVIEW_COMPLETE",
                     current_user.badge_number, name)
            flash("Review recorded successfully.", "success")
            return redirect(url_for("cases.case_detail", case_id=case_id))

        reviews = conn.execute("""
            SELECT * FROM case_reviews WHERE case_id = ? ORDER BY scheduled_date DESC
        """, (case_id,)).fetchall()

        return render_template("cases/review.html", case=case, reviews=reviews)
    finally:
        conn.close()


@bp.route("/<path:case_id>/summary")
@login_required
@permission_required("cases", "read")
def case_summary(case_id):
    """Printable case summary."""
    conn = get_db()
    try:
        case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not case:
            flash("Case not found.", "danger")
            return redirect(url_for("cases.case_list"))

        lifecycle = conn.execute(
            "SELECT * FROM case_lifecycle WHERE case_id = ? ORDER BY entered_at",
            (case_id,)
        ).fetchall()
        exhibits = conn.execute(
            "SELECT * FROM chain_of_custody WHERE linked_case_id = ?", (case_id,)
        ).fetchall()
        arrests_data = conn.execute(
            "SELECT * FROM arrests WHERE linked_case_id = ?", (case_id,)
        ).fetchall()
        statements = conn.execute(
            "SELECT * FROM witness_statements WHERE linked_case_id = ?", (case_id,)
        ).fetchall()

        return render_template("cases/summary_print.html",
                             case=case, lifecycle=lifecycle,
                             exhibits=exhibits, arrests=arrests_data,
                             statements=statements)
    finally:
        conn.close()
