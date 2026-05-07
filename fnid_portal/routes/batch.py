"""Batch operations — bulk assignment, status transitions, form generation."""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import get_db, log_audit
from ..rbac import role_required

bp = Blueprint("batch", __name__, url_prefix="/batch")


@bp.route("/")
@login_required
@role_required("admin", "dco", "ddi", "station_mgr")
def batch_home():
    """Batch operations hub."""
    return render_template("batch/home.html")


@bp.route("/assign", methods=["GET", "POST"])
@login_required
@role_required("admin", "dco", "ddi", "station_mgr")
def bulk_assign():
    """Bulk assign cases to an investigating officer."""
    conn = get_db()
    try:
        if request.method == "POST":
            case_ids = request.form.getlist("case_ids")
            io_badge = request.form.get("io_badge", "").strip()
            if not case_ids or not io_badge:
                flash("Select cases and an officer.", "danger")
                return redirect(url_for("batch.bulk_assign"))

            # Verify officer exists
            officer = conn.execute(
                "SELECT badge_number, full_name FROM officers WHERE badge_number = ?",
                (io_badge,)
            ).fetchone()
            if not officer:
                flash("Officer not found.", "danger")
                return redirect(url_for("batch.bulk_assign"))

            now = datetime.now().isoformat()
            assigned_count = 0
            for cid in case_ids:
                conn.execute("""
                    UPDATE cases SET assigned_io_badge = ?, assigned_date = ?,
                        current_stage = CASE WHEN current_stage IN ('intake', 'appreciation', 'vetting')
                            THEN 'assignment' ELSE current_stage END,
                        updated_at = ?
                    WHERE case_id = ?
                """, (io_badge, now[:10], now, cid))
                conn.execute("""
                    INSERT INTO case_lifecycle (case_id, from_stage, to_stage, changed_by, notes)
                    VALUES (?, 'batch', 'assignment', ?, ?)
                """, (cid, current_user.badge_number,
                      f"Bulk assigned to {officer['full_name']}"))
                log_audit("cases", cid, "BATCH_ASSIGN",
                          current_user.badge_number, current_user.full_name,
                          f"Assigned to {officer['full_name']} ({io_badge})")
                assigned_count += 1

            conn.commit()
            flash(f"{assigned_count} cases assigned to {officer['full_name']}.", "success")
            return redirect(url_for("batch.batch_home"))

        # GET — show unassigned or reassignable cases
        unassigned = conn.execute("""
            SELECT case_id, classification, parish, suspect_name, oic_name,
                   current_stage, created_at
            FROM cases
            WHERE assigned_io_badge IS NULL
               OR current_stage IN ('intake', 'appreciation', 'vetting')
            ORDER BY created_at DESC
        """).fetchall()

        officers = conn.execute("""
            SELECT badge_number, full_name, rank, role FROM officers
            WHERE role IN ('io', 'dco', 'ddi') AND is_active = 1
            ORDER BY full_name
        """).fetchall()

        return render_template("batch/assign.html",
                               cases=unassigned, officers=officers)
    finally:
        conn.close()


@bp.route("/transition", methods=["GET", "POST"])
@login_required
@role_required("admin", "dco", "ddi", "station_mgr")
def bulk_transition():
    """Bulk transition cases to a new stage."""
    conn = get_db()
    try:
        if request.method == "POST":
            case_ids = request.form.getlist("case_ids")
            target_stage = request.form.get("target_stage", "").strip()
            notes = request.form.get("notes", "").strip()

            valid_stages = [
                "intake", "appreciation", "vetting", "assignment",
                "investigation", "follow_up", "review",
                "court_preparation", "before_court", "closed", "suspended",
            ]
            if target_stage not in valid_stages:
                flash("Invalid target stage.", "danger")
                return redirect(url_for("batch.bulk_transition"))
            if not case_ids:
                flash("Select at least one case.", "danger")
                return redirect(url_for("batch.bulk_transition"))

            now = datetime.now().isoformat()
            count = 0
            for cid in case_ids:
                row = conn.execute(
                    "SELECT current_stage FROM cases WHERE case_id = ?", (cid,)
                ).fetchone()
                from_stage = row["current_stage"] if row else "unknown"
                conn.execute("""
                    UPDATE cases SET current_stage = ?, updated_at = ?
                    WHERE case_id = ?
                """, (target_stage, now, cid))
                conn.execute("""
                    INSERT INTO case_lifecycle (case_id, from_stage, to_stage, changed_by, notes)
                    VALUES (?, ?, ?, ?, ?)
                """, (cid, from_stage, target_stage,
                      current_user.badge_number,
                      f"Batch transition. {notes}"))
                log_audit("cases", cid, "BATCH_TRANSITION",
                          current_user.badge_number, current_user.full_name,
                          f"{from_stage} -> {target_stage}")
                count += 1

            conn.commit()
            flash(f"{count} cases transitioned to '{target_stage}'.", "success")
            return redirect(url_for("batch.batch_home"))

        # GET — list cases grouped by current stage
        cases = conn.execute("""
            SELECT case_id, classification, parish, suspect_name,
                   current_stage, assigned_io_badge, oic_name
            FROM cases
            WHERE current_stage NOT IN ('closed')
            ORDER BY current_stage, created_at DESC
        """).fetchall()

        stages = [
            "intake", "appreciation", "vetting", "assignment",
            "investigation", "follow_up", "review",
            "court_preparation", "before_court", "suspended", "closed",
        ]
        return render_template("batch/transition.html",
                               cases=cases, stages=stages)
    finally:
        conn.close()


@bp.route("/review", methods=["GET", "POST"])
@login_required
@role_required("admin", "dco", "ddi", "station_mgr")
def bulk_review():
    """Schedule bulk case reviews."""
    conn = get_db()
    try:
        if request.method == "POST":
            case_ids = request.form.getlist("case_ids")
            review_date = request.form.get("review_date", "")
            review_type = request.form.get("review_type", "28-day review")

            if not case_ids or not review_date:
                flash("Select cases and a review date.", "danger")
                return redirect(url_for("batch.bulk_review"))

            count = 0
            for cid in case_ids:
                conn.execute("""
                    INSERT INTO case_reviews
                    (case_id, review_type, scheduled_date, reviewer_badge, status)
                    VALUES (?, ?, ?, ?, 'Scheduled')
                """, (cid, review_type, review_date,
                      current_user.badge_number))
                conn.execute("""
                    UPDATE cases SET next_review_date = ?, updated_at = ?
                    WHERE case_id = ?
                """, (review_date, datetime.now().isoformat(), cid))
                count += 1

            conn.commit()
            log_audit("case_reviews", "batch", "BATCH_REVIEW",
                      current_user.badge_number, current_user.full_name,
                      f"Scheduled {count} reviews for {review_date}")
            flash(f"{count} case reviews scheduled for {review_date}.", "success")
            return redirect(url_for("batch.batch_home"))

        # GET — cases due or overdue for review
        cases = conn.execute("""
            SELECT case_id, classification, parish, assigned_io_badge, oic_name,
                   current_stage, last_review_date, next_review_date
            FROM cases
            WHERE current_stage NOT IN ('closed', 'suspended')
            ORDER BY next_review_date ASC NULLS FIRST
        """).fetchall()

        return render_template("batch/review.html", cases=cases)
    finally:
        conn.close()
