"""
FNID Deadline & Review Engine

Calculates deadlines, generates alerts, and schedules review cycles
based on JCF case management policy. All periods are CONFIGURABLE
via system_settings.
"""

from datetime import datetime, timedelta

from .models import get_db, get_setting


def _get_deadline_setting(key, default):
    """Get a deadline setting, converting to appropriate type."""
    val = get_setting(key, str(default))
    try:
        return int(val) if "." not in val else float(val)
    except (ValueError, TypeError):
        return default


def check_all_deadlines():
    """Scan all active cases and file movements, generate alerts for overdue items.

    This is designed to be called periodically (e.g., on login or via before_request).
    It only creates alerts that don't already exist (idempotent).
    """
    conn = get_db()
    try:
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")

        # 1. Check case review deadlines
        _check_review_deadlines(conn, now, now_str)

        # 2. Check file movement overdue
        _check_file_overdue(conn, now, now_str)

        # 3. Check forensic certificate overdue
        _check_forensic_overdue(conn, now, now_str)

        # 4. Check 48-hour arrest compliance
        _check_arrest_48hr(conn, now, now_str)

        # 5. Check suspended case review (90-day)
        _check_suspended_reviews(conn, now, now_str)

        conn.commit()
    finally:
        conn.close()


def _check_review_deadlines(conn, now, now_str):
    """Generate alerts for overdue and upcoming case reviews."""
    overdue = conn.execute("""
        SELECT cr.id, cr.case_id, cr.review_type, cr.scheduled_date
        FROM case_reviews cr
        WHERE cr.status = 'Scheduled'
          AND cr.scheduled_date < ?
    """, (now_str,)).fetchall()

    for review in overdue:
        _create_alert_if_new(
            conn,
            alert_type="review_due",
            target_type="case_review",
            target_id=str(review["id"]),
            title=f"Overdue: {review['review_type']} review",
            message=f"Case {review['case_id']} — {review['review_type']} review "
                    f"was due {review['scheduled_date']}",
            severity="critical",
            due_date=review["scheduled_date"],
        )

    # Upcoming reviews (within 3 days)
    upcoming_date = (now + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    upcoming = conn.execute("""
        SELECT cr.id, cr.case_id, cr.review_type, cr.scheduled_date
        FROM case_reviews cr
        WHERE cr.status = 'Scheduled'
          AND cr.scheduled_date BETWEEN ? AND ?
    """, (now_str, upcoming_date)).fetchall()

    for review in upcoming:
        _create_alert_if_new(
            conn,
            alert_type="review_due",
            target_type="case_review",
            target_id=str(review["id"]),
            title=f"Upcoming: {review['review_type']} review",
            message=f"Case {review['case_id']} — {review['review_type']} review "
                    f"scheduled for {review['scheduled_date']}",
            severity="warning",
            due_date=review["scheduled_date"],
        )


def _check_file_overdue(conn, now, now_str):
    """Generate alerts for files not returned within the allowed period."""
    overdue_files = conn.execute("""
        SELECT id, case_id, file_type, moved_to, moved_by, moved_at, expected_return
        FROM file_movements
        WHERE status = 'Out'
          AND (expected_return IS NOT NULL AND expected_return < ?)
    """, (now_str,)).fetchall()

    for fm in overdue_files:
        # Mark as overdue
        conn.execute(
            "UPDATE file_movements SET status = 'Overdue' WHERE id = ?",
            (fm["id"],)
        )
        _create_alert_if_new(
            conn,
            alert_type="overdue_file",
            target_type="file_movement",
            target_id=str(fm["id"]),
            title=f"Overdue file: {fm['file_type']}",
            message=f"Case {fm['case_id']} — {fm['file_type']} file checked out to "
                    f"{fm['moved_to']} by {fm['moved_by']}, "
                    f"expected return {fm['expected_return']}",
            severity="critical",
            target_badge=fm["moved_by"],
            due_date=fm["expected_return"],
        )


def _check_forensic_overdue(conn, now, now_str):
    """Alert on forensic certificates overdue beyond threshold."""
    weeks = _get_deadline_setting("forensic_cert_overdue_weeks", 8)
    cutoff = (now - timedelta(weeks=weeks)).strftime("%Y-%m-%d")

    overdue = conn.execute("""
        SELECT id, lab_ref, exhibit_tag, linked_case_id, submission_date
        FROM lab_tracking
        WHERE certificate_status NOT LIKE '%Issued%'
          AND certificate_status NOT LIKE 'N/A%'
          AND submission_date < ?
          AND submission_date IS NOT NULL
    """, (cutoff,)).fetchall()

    for lab in overdue:
        _create_alert_if_new(
            conn,
            alert_type="deadline",
            target_type="lab_tracking",
            target_id=lab["lab_ref"],
            title=f"Overdue forensic cert: {lab['exhibit_tag']}",
            message=f"Lab ref {lab['lab_ref']} submitted {lab['submission_date']} — "
                    f"over {weeks} weeks without certificate",
            severity="warning",
            due_date=lab["submission_date"],
        )


def _check_arrest_48hr(conn, now, now_str):
    """Alert on arrests approaching or past the 48-hour charge deadline."""
    approaching = conn.execute("""
        SELECT id, arrest_id, suspect_name, arrest_date, arrest_time,
               charge_within_48hr, deadline_48hr
        FROM arrests
        WHERE charge_within_48hr IS NULL OR charge_within_48hr = ''
          OR charge_within_48hr = 'No'
    """).fetchall()

    for arrest in approaching:
        if arrest["deadline_48hr"]:
            try:
                deadline = datetime.strptime(arrest["deadline_48hr"], "%Y-%m-%d %H:%M")
                if deadline < now:
                    _create_alert_if_new(
                        conn,
                        alert_type="deadline",
                        target_type="arrest",
                        target_id=arrest["arrest_id"],
                        title=f"48hr BREACH: {arrest['suspect_name']}",
                        message=f"Arrest {arrest['arrest_id']} — 48-hour charge deadline "
                                f"passed ({arrest['deadline_48hr']})",
                        severity="critical",
                        due_date=arrest["deadline_48hr"],
                    )
                elif (deadline - now).total_seconds() < 14400:  # 4 hours
                    _create_alert_if_new(
                        conn,
                        alert_type="deadline",
                        target_type="arrest",
                        target_id=arrest["arrest_id"],
                        title=f"48hr WARNING: {arrest['suspect_name']}",
                        message=f"Arrest {arrest['arrest_id']} — 48-hour charge deadline "
                                f"approaching ({arrest['deadline_48hr']})",
                        severity="warning",
                        due_date=arrest["deadline_48hr"],
                    )
            except ValueError:
                pass


def _check_suspended_reviews(conn, now, now_str):
    """Schedule 90-day reviews for suspended cases that lack one."""
    days = _get_deadline_setting("suspended_review_days", 90)

    suspended = conn.execute("""
        SELECT case_id, suspended_date FROM cases
        WHERE current_stage = 'suspended'
          AND suspended_date IS NOT NULL
    """).fetchall()

    for case in suspended:
        # Check if there's already a scheduled review
        existing = conn.execute("""
            SELECT id FROM case_reviews
            WHERE case_id = ? AND review_type = 'suspended_90day'
              AND status = 'Scheduled'
        """, (case["case_id"],)).fetchone()

        if not existing:
            try:
                suspended_dt = datetime.strptime(case["suspended_date"], "%Y-%m-%d")
                next_review = (suspended_dt + timedelta(days=days)).strftime("%Y-%m-%d")
                conn.execute("""
                    INSERT INTO case_reviews
                    (case_id, review_type, scheduled_date, status, created_by)
                    VALUES (?, 'suspended_90day', ?, 'Scheduled', 'SYSTEM')
                """, (case["case_id"], next_review))
            except ValueError:
                pass


def _create_alert_if_new(conn, *, alert_type, target_type, target_id,
                         title, message, severity="warning",
                         target_role=None, target_badge=None, due_date=None):
    """Create an alert only if an identical active alert doesn't exist."""
    existing = conn.execute("""
        SELECT id FROM alerts
        WHERE alert_type = ? AND target_type = ? AND target_id = ?
          AND is_dismissed = 0
    """, (alert_type, target_type, target_id)).fetchone()

    if not existing:
        conn.execute("""
            INSERT INTO alerts (alert_type, target_type, target_id, title,
                                message, severity, target_role, target_badge, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (alert_type, target_type, target_id, title, message,
              severity, target_role, target_badge, due_date))


def schedule_review(case_id, review_type, days_from_now=None, date=None,
                    created_by="SYSTEM"):
    """Schedule a case review.

    Args:
        case_id: The case reference
        review_type: Type of review (first_review, followup_28day, etc.)
        days_from_now: Schedule N days from today
        date: Specific date string (overrides days_from_now)
        created_by: Badge or name of who scheduled it
    """
    if date is None:
        if days_from_now is None:
            # Use default from settings
            defaults = {
                "preliminary_vetting": "preliminary_vetting_hours",
                "first_review": "first_review_days",
                "followup_28day": "followup_review_days",
                "suspended_90day": "suspended_review_days",
            }
            setting_key = defaults.get(review_type, "followup_review_days")
            days_from_now = _get_deadline_setting(setting_key, 28)

        scheduled = datetime.now() + timedelta(days=days_from_now)
        date = scheduled.strftime("%Y-%m-%d")

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO case_reviews
            (case_id, review_type, scheduled_date, status, created_by)
            VALUES (?, ?, ?, 'Scheduled', ?)
        """, (case_id, review_type, date, created_by))
        conn.commit()
    finally:
        conn.close()


def get_alerts_for_user(badge=None, role=None, include_dismissed=False):
    """Get active alerts filtered by user role and assignment."""
    conn = get_db()
    try:
        conditions = []
        params = []

        if not include_dismissed:
            conditions.append("is_dismissed = 0")

        if badge and role:
            conditions.append(
                "(target_badge = ? OR target_badge IS NULL)"
            )
            params.append(badge)
            # Role-based: show alerts for user's role or all roles
            conditions.append(
                "(target_role = ? OR target_role IS NULL)"
            )
            params.append(role)

        where = " AND ".join(conditions) if conditions else "1=1"

        alerts = conn.execute(f"""
            SELECT * FROM alerts
            WHERE {where}
            ORDER BY
                CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                created_at DESC
            LIMIT 50
        """, params).fetchall()

        return alerts
    finally:
        conn.close()


def dismiss_alert(alert_id, badge=None):
    """Mark an alert as dismissed."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE alerts SET is_dismissed = 1 WHERE id = ?", (alert_id,)
        )
        conn.commit()
    finally:
        conn.close()
