"""
Evidence Chain of Custody Enhancement Routes

Comprehensive evidence management: exhibit registration, chain of custody
tracking with gap detection, transfer logging, and lab submission/certificate
tracking via IFSLM.
"""

from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import generate_id, get_db, log_audit
from ..rbac import permission_required

bp = Blueprint("evidence", __name__, url_prefix="/evidence")


# ── Helpers ──────────────────────────────────────────────────────────

def _detect_chain_gaps(conn, exhibit_tag):
    """Detect gaps >24 hrs between transfers where location is unaccounted.

    Returns a list of dicts describing each gap found.
    """
    rows = conn.execute("""
        SELECT * FROM chain_of_custody
        WHERE exhibit_tag = ?
        ORDER BY seized_date
    """, (exhibit_tag,)).fetchall()

    if not rows:
        return []

    # Collect all transfer timestamps from audit log
    transfers = conn.execute("""
        SELECT * FROM audit_log
        WHERE table_name = 'chain_of_custody' AND record_id = ?
              AND action IN ('TRANSFER', 'CREATE')
        ORDER BY timestamp
    """, (exhibit_tag,)).fetchall()

    gaps = []
    prev_time = None
    prev_location = None

    for t in transfers:
        ts = t["timestamp"]
        try:
            current_time = datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            continue

        if prev_time is not None:
            delta = current_time - prev_time
            if delta > timedelta(hours=24):
                gaps.append({
                    "from_time": prev_time.strftime("%Y-%m-%d %H:%M"),
                    "to_time": current_time.strftime("%Y-%m-%d %H:%M"),
                    "hours": round(delta.total_seconds() / 3600, 1),
                    "last_known_location": prev_location or "Unknown",
                })

        prev_time = current_time
        prev_location = t.get("details", "")

    # Also check transfer_date vs now for current exhibits
    if rows:
        exhibit = rows[0]
        last_date = exhibit["transfer_date"]
        if last_date and exhibit["disposal_status"] not in ("Destroyed", "Returned", "Forfeited"):
            try:
                last_dt = datetime.strptime(last_date, "%Y-%m-%d")
                delta = datetime.now() - last_dt
                if delta > timedelta(hours=24):
                    gaps.append({
                        "from_time": last_dt.strftime("%Y-%m-%d %H:%M"),
                        "to_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "hours": round(delta.total_seconds() / 3600, 1),
                        "last_known_location": exhibit["storage_location"] or "Unknown",
                    })
            except (ValueError, TypeError):
                pass

    return gaps


# ── Evidence Dashboard ───────────────────────────────────────────────

@bp.route("/")
@login_required
@permission_required("forensics", "read")
def evidence_dashboard():
    """Evidence management dashboard with KPIs."""
    conn = get_db()
    try:
        total_exhibits = conn.execute(
            "SELECT COUNT(*) as cnt FROM chain_of_custody"
        ).fetchone()["cnt"]

        pending_lab = conn.execute("""
            SELECT COUNT(*) as cnt FROM lab_tracking
            WHERE certificate_status IS NULL
               OR certificate_status NOT IN ('Issued', 'Received')
        """).fetchone()["cnt"]

        certs_overdue = conn.execute("""
            SELECT COUNT(*) as cnt FROM lab_tracking
            WHERE expected_date IS NOT NULL
              AND expected_date < date('now')
              AND (certificate_status IS NULL
                   OR certificate_status NOT IN ('Issued', 'Received'))
        """).fetchone()["cnt"]

        # Chain gaps: count exhibits with potential gaps
        all_exhibits = conn.execute(
            "SELECT exhibit_tag FROM chain_of_custody"
        ).fetchall()
        chain_gap_count = 0
        for ex in all_exhibits:
            if _detect_chain_gaps(conn, ex["exhibit_tag"]):
                chain_gap_count += 1

        recent_exhibits = conn.execute("""
            SELECT * FROM chain_of_custody ORDER BY created_at DESC LIMIT 10
        """).fetchall()

        recent_lab = conn.execute("""
            SELECT * FROM lab_tracking ORDER BY created_at DESC LIMIT 10
        """).fetchall()

        return render_template(
            "evidence/dashboard.html",
            total_exhibits=total_exhibits,
            pending_lab=pending_lab,
            certs_overdue=certs_overdue,
            chain_gap_count=chain_gap_count,
            recent_exhibits=recent_exhibits,
            recent_lab=recent_lab,
        )
    finally:
        conn.close()


# ── Exhibit list ─────────────────────────────────────────────────────

@bp.route("/exhibits")
@login_required
@permission_required("forensics", "read")
def exhibit_list():
    """All exhibits table with filters."""
    conn = get_db()
    try:
        type_filter = request.args.get("type", "")
        case_filter = request.args.get("case", "")
        status_filter = request.args.get("status", "")

        query = "SELECT * FROM chain_of_custody WHERE 1=1"
        params = []

        if type_filter:
            query += " AND exhibit_type = ?"
            params.append(type_filter)
        if case_filter:
            query += " AND linked_case_id LIKE ?"
            params.append(f"%{case_filter}%")
        if status_filter:
            query += " AND record_status = ?"
            params.append(status_filter)

        query += " ORDER BY created_at DESC"
        exhibits = conn.execute(query, params).fetchall()

        # Distinct types for filter
        types = conn.execute(
            "SELECT DISTINCT exhibit_type FROM chain_of_custody WHERE exhibit_type IS NOT NULL ORDER BY exhibit_type"
        ).fetchall()

        return render_template(
            "evidence/exhibit_list.html",
            exhibits=exhibits,
            types=[t["exhibit_type"] for t in types],
            type_filter=type_filter,
            case_filter=case_filter,
            status_filter=status_filter,
        )
    finally:
        conn.close()


# ── Exhibit detail ───────────────────────────────────────────────────

@bp.route("/exhibits/<exhibit_tag>")
@login_required
@permission_required("forensics", "read")
def exhibit_detail(exhibit_tag):
    """Full exhibit detail with chain of custody timeline and lab status."""
    conn = get_db()
    try:
        exhibit = conn.execute(
            "SELECT * FROM chain_of_custody WHERE exhibit_tag = ?",
            (exhibit_tag,)
        ).fetchone()
        if not exhibit:
            flash("Exhibit not found.", "danger")
            return redirect(url_for("evidence.exhibit_list"))

        # Transfer history from audit log
        transfers = conn.execute("""
            SELECT * FROM audit_log
            WHERE table_name = 'chain_of_custody' AND record_id = ?
            ORDER BY timestamp
        """, (exhibit_tag,)).fetchall()

        # Lab submissions for this exhibit
        lab_records = conn.execute("""
            SELECT * FROM lab_tracking WHERE exhibit_tag = ?
            ORDER BY submission_date DESC
        """, (exhibit_tag,)).fetchall()

        # Linked case
        case = None
        if exhibit["linked_case_id"]:
            case = conn.execute(
                "SELECT * FROM cases WHERE case_id = ?",
                (exhibit["linked_case_id"],)
            ).fetchone()

        # Gap detection
        gaps = _detect_chain_gaps(conn, exhibit_tag)

        return render_template(
            "evidence/exhibit_detail.html",
            exhibit=exhibit,
            transfers=transfers,
            lab_records=lab_records,
            case=case,
            gaps=gaps,
        )
    finally:
        conn.close()


# ── New exhibit ──────────────────────────────────────────────────────

@bp.route("/exhibits/new", methods=["GET", "POST"])
@login_required
@permission_required("forensics", "create")
def new_exhibit():
    """Register a new exhibit."""
    if request.method == "POST":
        conn = get_db()
        try:
            exhibit_tag = generate_id("EXH", "chain_of_custody", "exhibit_tag")
            now = datetime.now()
            name = current_user.full_name

            conn.execute("""
                INSERT INTO chain_of_custody (
                    exhibit_tag, linked_case_id, exhibit_type, description,
                    seized_location, seized_by, seized_date,
                    current_custodian, storage_location,
                    condition, photos_taken, seal_intact,
                    disposal_status, notes,
                    created_by, created_at, updated_at, record_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exhibit_tag,
                request.form.get("linked_case_id") or None,
                request.form.get("exhibit_type", ""),
                request.form.get("description", ""),
                request.form.get("seized_location", ""),
                request.form.get("seized_by", name),
                request.form.get("seized_date", now.strftime("%Y-%m-%d")),
                request.form.get("current_custodian", name),
                request.form.get("storage_location", "Evidence Room"),
                request.form.get("condition", "Good"),
                request.form.get("photos_taken", "No"),
                request.form.get("seal_intact", "Yes"),
                "Held as Evidence",
                request.form.get("notes", ""),
                name,
                now.isoformat(),
                now.isoformat(),
                "Draft",
            ))
            conn.commit()

            log_audit("chain_of_custody", exhibit_tag, "CREATE",
                      current_user.badge_number, name,
                      f"New exhibit registered: {exhibit_tag}")

            flash(f"Exhibit {exhibit_tag} registered.", "success")
            return redirect(url_for("evidence.exhibit_detail",
                                    exhibit_tag=exhibit_tag))

        except Exception as e:
            conn.rollback()
            current_app.logger.exception("Exhibit registration error"); flash("An error occurred registering the exhibit.", "danger")
        finally:
            conn.close()

    return render_template("evidence/exhibit_list.html",
                           exhibits=[], types=[], is_new_form=True,
                           type_filter="", case_filter="", status_filter="")


# ── Transfer exhibit ─────────────────────────────────────────────────

@bp.route("/exhibits/<exhibit_tag>/transfer", methods=["POST"])
@login_required
@permission_required("forensics", "update")
def transfer_exhibit(exhibit_tag):
    """Record an exhibit transfer."""
    conn = get_db()
    try:
        exhibit = conn.execute(
            "SELECT * FROM chain_of_custody WHERE exhibit_tag = ?",
            (exhibit_tag,)
        ).fetchone()
        if not exhibit:
            flash("Exhibit not found.", "danger")
            return redirect(url_for("evidence.exhibit_list"))

        new_location = request.form.get("new_location", "")
        transferred_to = request.form.get("transferred_to", "")
        reason = request.form.get("reason", "")
        seal_check = request.form.get("seal_check", "")

        if not new_location or not transferred_to:
            flash("New location and transferred-to are required.", "danger")
            return redirect(url_for("evidence.exhibit_detail",
                                    exhibit_tag=exhibit_tag))

        now = datetime.now()
        name = current_user.full_name
        old_location = exhibit["storage_location"] or ""
        old_custodian = exhibit["current_custodian"] or ""

        conn.execute("""
            UPDATE chain_of_custody SET
                storage_location = ?,
                current_custodian = ?,
                transfer_date = ?,
                transfer_from = ?,
                transfer_to = ?,
                transfer_reason = ?,
                seal_intact = ?,
                updated_at = ?
            WHERE exhibit_tag = ?
        """, (
            new_location,
            transferred_to,
            now.strftime("%Y-%m-%d"),
            old_custodian,
            transferred_to,
            reason,
            seal_check or "Yes",
            now.isoformat(),
            exhibit_tag,
        ))
        conn.commit()

        details = (f"Transfer: {old_location} -> "
                   f"{new_location} | To: {transferred_to} | "
                   f"Reason: {reason} | Seal: {seal_check}")

        log_audit("chain_of_custody", exhibit_tag, "TRANSFER",
                  current_user.badge_number, name, details)

        flash(f"Exhibit {exhibit_tag} transferred to {new_location}.", "success")

    except Exception as e:
        conn.rollback()
        current_app.logger.exception("Transfer recording error"); flash("An error occurred recording the transfer.", "danger")
    finally:
        conn.close()

    return redirect(url_for("evidence.exhibit_detail", exhibit_tag=exhibit_tag))


# ── Chain audit ──────────────────────────────────────────────────────

@bp.route("/audit/<path:case_id>")
@login_required
@permission_required("forensics", "read")
def chain_audit(case_id):
    """Chain of custody audit for a case."""
    conn = get_db()
    try:
        case = conn.execute(
            "SELECT * FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()

        exhibits = conn.execute("""
            SELECT * FROM chain_of_custody WHERE linked_case_id = ?
            ORDER BY seized_date
        """, (case_id,)).fetchall()

        # Build audit data per exhibit
        audit_data = []
        total_gaps = 0
        for exhibit in exhibits:
            tag = exhibit["exhibit_tag"]
            gaps = _detect_chain_gaps(conn, tag)
            total_gaps += len(gaps)

            transfers = conn.execute("""
                SELECT * FROM audit_log
                WHERE table_name = 'chain_of_custody' AND record_id = ?
                ORDER BY timestamp
            """, (tag,)).fetchall()

            lab_records = conn.execute("""
                SELECT * FROM lab_tracking WHERE exhibit_tag = ?
            """, (tag,)).fetchall()

            audit_data.append({
                "exhibit": exhibit,
                "transfers": transfers,
                "gaps": gaps,
                "lab_records": lab_records,
                "integrity": "PASS" if not gaps else "FAIL - Chain Gap Detected",
            })

        return render_template(
            "evidence/chain_audit.html",
            case=case,
            case_id=case_id,
            audit_data=audit_data,
            total_exhibits=len(exhibits),
            total_gaps=total_gaps,
        )
    finally:
        conn.close()


# ── Lab dashboard ────────────────────────────────────────────────────

@bp.route("/lab")
@login_required
@permission_required("forensics", "read")
def lab_dashboard():
    """Lab tracking dashboard."""
    conn = get_db()
    try:
        pending = conn.execute("""
            SELECT * FROM lab_tracking
            WHERE certificate_status IS NULL
               OR certificate_status NOT IN ('Issued', 'Received')
            ORDER BY submission_date
        """).fetchall()

        overdue = conn.execute("""
            SELECT * FROM lab_tracking
            WHERE expected_date IS NOT NULL
              AND expected_date < date('now')
              AND (certificate_status IS NULL
                   OR certificate_status NOT IN ('Issued', 'Received'))
            ORDER BY expected_date
        """).fetchall()

        completed = conn.execute("""
            SELECT * FROM lab_tracking
            WHERE certificate_status IN ('Issued', 'Received')
            ORDER BY completion_date DESC
            LIMIT 20
        """).fetchall()

        all_records = conn.execute("""
            SELECT * FROM lab_tracking ORDER BY created_at DESC
        """).fetchall()

        # Summary counts
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM lab_tracking"
        ).fetchone()["cnt"]
        issued_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM lab_tracking
            WHERE certificate_status IN ('Issued', 'Received')
        """).fetchone()["cnt"]

        # By exam type
        by_type = conn.execute("""
            SELECT exam_type, COUNT(*) as cnt
            FROM lab_tracking GROUP BY exam_type ORDER BY cnt DESC
        """).fetchall()

        return render_template(
            "evidence/lab_dashboard.html",
            pending=pending,
            overdue=overdue,
            completed=completed,
            all_records=all_records,
            total=total,
            issued_count=issued_count,
            pending_count=len(pending),
            overdue_count=len(overdue),
            by_type=by_type,
        )
    finally:
        conn.close()


# ── New lab submission ───────────────────────────────────────────────

@bp.route("/lab/new", methods=["GET", "POST"])
@login_required
@permission_required("forensics", "create")
def new_lab_submission():
    """Submit an exhibit to a lab."""
    conn = get_db()
    try:
        if request.method == "POST":
            lab_ref = generate_id("LAB", "lab_tracking", "lab_ref")
            now = datetime.now()
            name = current_user.full_name

            conn.execute("""
                INSERT INTO lab_tracking (
                    lab_ref, exhibit_tag, linked_case_id,
                    submission_date, submitted_by, lab_type,
                    exam_type, expected_date,
                    certificate_status, notes,
                    created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lab_ref,
                request.form.get("exhibit_tag", ""),
                request.form.get("linked_case_id") or None,
                request.form.get("submission_date", now.strftime("%Y-%m-%d")),
                name,
                request.form.get("lab_type", "IFSLM"),
                request.form.get("exam_type", ""),
                request.form.get("expected_date") or None,
                "Submitted",
                request.form.get("notes", ""),
                name,
                now.isoformat(),
            ))
            conn.commit()

            log_audit("lab_tracking", lab_ref, "CREATE",
                      current_user.badge_number, name,
                      f"Lab submission: {lab_ref}")

            flash(f"Lab submission {lab_ref} created.", "success")
            return redirect(url_for("evidence.lab_dashboard"))

        # Get exhibits for selection
        exhibits = conn.execute("""
            SELECT exhibit_tag, linked_case_id, description
            FROM chain_of_custody
            ORDER BY exhibit_tag
        """).fetchall()

        return render_template(
            "evidence/lab_dashboard.html",
            is_new_form=True,
            exhibits=exhibits,
            pending=[], overdue=[], completed=[], all_records=[],
            total=0, issued_count=0, pending_count=0, overdue_count=0,
            by_type=[],
        )
    finally:
        conn.close()


# ── Update lab status ────────────────────────────────────────────────

@bp.route("/lab/<lab_ref>/update", methods=["POST"])
@login_required
@permission_required("forensics", "update")
def update_lab_status(lab_ref):
    """Update lab tracking status (certificate received, etc.)."""
    conn = get_db()
    try:
        record = conn.execute(
            "SELECT * FROM lab_tracking WHERE lab_ref = ?", (lab_ref,)
        ).fetchone()
        if not record:
            flash("Lab record not found.", "danger")
            return redirect(url_for("evidence.lab_dashboard"))

        cert_status = request.form.get("certificate_status", "")
        completion_date = request.form.get("completion_date") or None
        cert_number = request.form.get("certificate_number") or None
        result = request.form.get("result") or None
        notes = request.form.get("notes") or None

        conn.execute("""
            UPDATE lab_tracking SET
                certificate_status = ?,
                completion_date = ?,
                certificate_number = ?,
                result = ?,
                notes = ?
            WHERE lab_ref = ?
        """, (cert_status, completion_date, cert_number, result, notes, lab_ref))
        conn.commit()

        name = current_user.full_name
        log_audit("lab_tracking", lab_ref, "UPDATE",
                  current_user.badge_number, name,
                  f"Status updated to: {cert_status}")

        flash(f"Lab record {lab_ref} updated.", "success")

    except Exception as e:
        conn.rollback()
        current_app.logger.exception("Evidence operation error"); flash("An error occurred. Please try again.", "danger")
    finally:
        conn.close()

    return redirect(url_for("evidence.lab_dashboard"))
