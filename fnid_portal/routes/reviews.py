"""
Case Review Scheduling Routes

Schedule and track periodic case reviews including 14-day, 28-day,
quarterly, supervisor, command, and ad hoc reviews.
"""

from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import get_db, log_audit
from ..rbac import permission_required

bp = Blueprint("reviews", __name__, url_prefix="/reviews")

REVIEW_TYPES = [
    "14-Day Review",
    "28-Day Review",
    "Quarterly Review",
    "Supervisor Review",
    "Command Review",
    "Ad Hoc Review",
]

REVIEW_STATUSES = ["Scheduled", "Completed", "Overdue"]


@bp.route("/")
@login_required
@permission_required("cases", "read")
def review_list():
    """List all case reviews with filters."""
    status = request.args.get("status", "").strip()
    review_type = request.args.get("review_type", "").strip()

    conn = get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")

        # Mark overdue reviews
        conn.execute(
            """UPDATE case_reviews SET status = 'Overdue'
               WHERE scheduled_date < ? AND status = 'Scheduled'""",
            (today,),
        )
        conn.commit()

        query = """
            SELECT cr.*, c.offence_description
            FROM case_reviews cr
            LEFT JOIN cases c ON cr.case_id = c.case_id
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND cr.status = ?"
            params.append(status)
        if review_type:
            query += " AND cr.review_type = ?"
            params.append(review_type)

        query += " ORDER BY cr.scheduled_date DESC"
        reviews = conn.execute(query, params).fetchall()

        return render_template(
            "reviews/list.html",
            reviews=reviews,
            today=today,
            filter_status=status,
            filter_review_type=review_type,
            review_types=REVIEW_TYPES,
            review_statuses=REVIEW_STATUSES,
        )
    finally:
        conn.close()


@bp.route("/<int:id>")
@login_required
@permission_required("cases", "read")
def review_detail(id):
    """View full review detail."""
    conn = get_db()
    try:
        review = conn.execute(
            """SELECT cr.*, c.offence_description, c.case_status
               FROM case_reviews cr
               LEFT JOIN cases c ON cr.case_id = c.case_id
               WHERE cr.id = ?""",
            (id,),
        ).fetchone()
        if not review:
            flash("Review not found.", "danger")
            return redirect(url_for("reviews.review_list"))

        return render_template("reviews/detail.html", review=review)
    finally:
        conn.close()


@bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("cases", "create")
def new_review():
    """Schedule a new case review."""
    conn = get_db()
    try:
        cases = conn.execute(
            "SELECT case_id, offence_description FROM cases ORDER BY case_id DESC"
        ).fetchall()

        if request.method == "POST":
            case_id = request.form.get("case_id", "").strip()
            review_type = request.form.get("review_type", "").strip()
            scheduled_date = request.form.get("scheduled_date", "").strip()
            reviewer_badge = request.form.get("reviewer_badge", "").strip() or None
            reviewer_name = request.form.get("reviewer_name", "").strip() or None

            if not case_id or not review_type or not scheduled_date:
                flash("Case, review type, and scheduled date are required.", "danger")
                return render_template(
                    "reviews/form.html",
                    review=request.form,
                    is_edit=False,
                    cases=cases,
                    review_types=REVIEW_TYPES,
                )

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor = conn.execute(
                """INSERT INTO case_reviews
                   (case_id, review_type, scheduled_date, reviewer_badge,
                    reviewer_name, status, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, 'Scheduled', ?, ?)""",
                (
                    case_id, review_type, scheduled_date,
                    reviewer_badge, reviewer_name,
                    current_user.badge_number, now,
                ),
            )
            conn.commit()
            new_id = cursor.lastrowid

            log_audit(
                "case_reviews", str(new_id), "CREATE",
                current_user.badge_number, current_user.full_name,
                f"Scheduled {review_type} for case {case_id} on {scheduled_date}",
            )

            flash("Review scheduled successfully.", "success")
            return redirect(url_for("reviews.review_detail", id=new_id))

        return render_template(
            "reviews/form.html",
            review=None,
            is_edit=False,
            cases=cases,
            review_types=REVIEW_TYPES,
        )
    finally:
        conn.close()


@bp.route("/<int:id>/complete", methods=["GET", "POST"])
@login_required
@permission_required("cases", "update")
def complete_review(id):
    """Complete a review with outcome and findings."""
    conn = get_db()
    try:
        review = conn.execute(
            """SELECT cr.*, c.offence_description
               FROM case_reviews cr
               LEFT JOIN cases c ON cr.case_id = c.case_id
               WHERE cr.id = ?""",
            (id,),
        ).fetchone()
        if not review:
            flash("Review not found.", "danger")
            return redirect(url_for("reviews.review_list"))

        if review["status"] == "Completed":
            flash("This review has already been completed.", "warning")
            return redirect(url_for("reviews.review_detail", id=id))

        if request.method == "POST":
            actual_date = request.form.get("actual_date", "").strip()
            outcome = request.form.get("outcome", "").strip()
            findings = request.form.get("findings", "").strip() or None
            directives = request.form.get("directives", "").strip() or None
            next_review_date = request.form.get("next_review_date", "").strip() or None

            if not actual_date or not outcome:
                flash("Actual date and outcome are required.", "danger")
                return render_template(
                    "reviews/complete.html",
                    review=review,
                    form=request.form,
                )

            conn.execute(
                """UPDATE case_reviews SET
                   actual_date=?, outcome=?, findings=?, directives=?,
                   next_review_date=?, status='Completed',
                   reviewer_badge=?, reviewer_name=?
                   WHERE id=?""",
                (
                    actual_date, outcome, findings, directives,
                    next_review_date,
                    current_user.badge_number, current_user.full_name, id,
                ),
            )
            conn.commit()

            log_audit(
                "case_reviews", str(id), "UPDATE",
                current_user.badge_number, current_user.full_name,
                f"Review completed: {outcome}",
            )

            flash("Review completed successfully.", "success")
            return redirect(url_for("reviews.review_detail", id=id))

        return render_template("reviews/complete.html", review=review, form=None)
    finally:
        conn.close()


@bp.route("/calendar")
@login_required
@permission_required("cases", "read")
def review_calendar():
    """Calendar-style view of upcoming reviews grouped by week."""
    conn = get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")

        reviews = conn.execute(
            """SELECT cr.*, c.offence_description
               FROM case_reviews cr
               LEFT JOIN cases c ON cr.case_id = c.case_id
               WHERE cr.scheduled_date >= ? AND cr.status IN ('Scheduled', 'Overdue')
               ORDER BY cr.scheduled_date ASC""",
            (today,),
        ).fetchall()

        # Group by week
        weeks = {}
        for review in reviews:
            try:
                sched = datetime.strptime(review["scheduled_date"], "%Y-%m-%d")
                week_start = sched - timedelta(days=sched.weekday())
                week_key = week_start.strftime("%Y-%m-%d")
                week_end = week_start + timedelta(days=6)
                week_label = (
                    f"{week_start.strftime('%d %b %Y')} - "
                    f"{week_end.strftime('%d %b %Y')}"
                )
            except (ValueError, TypeError):
                week_key = "Unknown"
                week_label = "Unknown"

            if week_key not in weeks:
                weeks[week_key] = {"label": week_label, "reviews": []}
            weeks[week_key]["reviews"].append(review)

        sorted_weeks = sorted(weeks.items(), key=lambda x: x[0])

        return render_template(
            "reviews/calendar.html",
            weeks=sorted_weeks,
            today=today,
        )
    finally:
        conn.close()


@bp.route("/overdue")
@login_required
@permission_required("cases", "read")
def overdue_reviews():
    """List only overdue reviews."""
    conn = get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")

        # Mark overdue
        conn.execute(
            """UPDATE case_reviews SET status = 'Overdue'
               WHERE scheduled_date < ? AND status = 'Scheduled'""",
            (today,),
        )
        conn.commit()

        reviews = conn.execute(
            """SELECT cr.*, c.offence_description
               FROM case_reviews cr
               LEFT JOIN cases c ON cr.case_id = c.case_id
               WHERE cr.status = 'Overdue'
               ORDER BY cr.scheduled_date ASC""",
        ).fetchall()

        return render_template(
            "reviews/list.html",
            reviews=reviews,
            today=today,
            filter_status="Overdue",
            filter_review_type="",
            review_types=REVIEW_TYPES,
            review_statuses=REVIEW_STATUSES,
            is_overdue_view=True,
        )
    finally:
        conn.close()
