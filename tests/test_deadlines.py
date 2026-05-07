"""Tests for the FNID deadline and review engine."""

from datetime import datetime, timedelta

from fnid_portal.deadlines import (
    check_all_deadlines,
    dismiss_alert,
    get_alerts_for_user,
    schedule_review,
)


def _insert_sample_case(conn, case_id="TEST/SD/A3/FNID/2026/0001"):
    """Insert a minimal case record for testing."""
    conn.execute("""
        INSERT INTO cases (
            case_id, registration_date, classification, oic_badge,
            oic_name, oic_rank, parish, offence_description,
            law_and_section, created_by, current_stage
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (case_id, "2026-01-01", "Firearms - Possession", "T001",
          "Test Officer", "Inspector", "Manchester", "Test offence",
          "s.5 Firearms Act", "Test Officer", "investigation"))
    conn.commit()
    return case_id


def test_schedule_review_creates_record(app):
    """schedule_review inserts a row into case_reviews."""
    with app.app_context():
        from fnid_portal.models import get_db

        conn = get_db()
        case_id = _insert_sample_case(conn)
        conn.close()

        schedule_review(case_id, "first_review", days_from_now=14,
                        created_by="Test Officer")

        conn = get_db()
        row = conn.execute(
            "SELECT * FROM case_reviews WHERE case_id = ?", (case_id,)
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["review_type"] == "first_review"
        assert row["status"] == "Scheduled"
        assert row["created_by"] == "Test Officer"


def test_check_all_deadlines_generates_overdue_review_alert(app):
    """check_all_deadlines creates an alert for a past-due scheduled review."""
    with app.app_context():
        from fnid_portal.models import get_db

        conn = get_db()
        case_id = _insert_sample_case(conn)

        # Insert a review that is already past due
        past_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO case_reviews
            (case_id, review_type, scheduled_date, status, created_by)
            VALUES (?, 'first_review', ?, 'Scheduled', 'SYSTEM')
        """, (case_id, past_date))
        conn.commit()
        conn.close()

        check_all_deadlines()

        conn = get_db()
        alerts = conn.execute(
            "SELECT * FROM alerts WHERE target_type = 'case_review' AND is_dismissed = 0"
        ).fetchall()
        conn.close()

        assert len(alerts) >= 1
        assert "Overdue" in alerts[0]["title"]


def test_get_alerts_for_user_returns_filtered(app):
    """get_alerts_for_user returns alerts matching the given badge/role."""
    with app.app_context():
        from fnid_portal.models import get_db

        conn = get_db()
        # Insert alerts: one targeted, one general
        conn.execute("""
            INSERT INTO alerts (alert_type, target_type, target_id,
                                title, message, severity, target_badge)
            VALUES ('test', 'case', 'C001', 'Targeted Alert', 'For T001', 'warning', 'T001')
        """)
        conn.execute("""
            INSERT INTO alerts (alert_type, target_type, target_id,
                                title, message, severity)
            VALUES ('test', 'case', 'C002', 'General Alert', 'For all', 'info')
        """)
        conn.commit()
        conn.close()

        alerts = get_alerts_for_user(badge="T001", role="io")
        assert len(alerts) >= 1
        # The targeted alert should be present
        titles = [a["title"] for a in alerts]
        assert "Targeted Alert" in titles


def test_dismiss_alert_marks_dismissed(app):
    """dismiss_alert sets is_dismissed=1 on the alert."""
    with app.app_context():
        from fnid_portal.models import get_db

        conn = get_db()
        conn.execute("""
            INSERT INTO alerts (alert_type, target_type, target_id,
                                title, message, severity)
            VALUES ('test', 'case', 'C099', 'Dismissable', 'Test', 'info')
        """)
        conn.commit()
        alert_id = conn.execute(
            "SELECT id FROM alerts WHERE target_id = 'C099'"
        ).fetchone()["id"]
        conn.close()

        dismiss_alert(alert_id, badge="T001")

        conn = get_db()
        row = conn.execute(
            "SELECT is_dismissed FROM alerts WHERE id = ?", (alert_id,)
        ).fetchone()
        conn.close()

        assert row["is_dismissed"] == 1


def test_file_overdue_generates_alert(app):
    """A file_movement with a past expected_return triggers an overdue alert."""
    with app.app_context():
        from fnid_portal.models import get_db

        conn = get_db()
        case_id = _insert_sample_case(conn)

        past_return = (datetime.now() - timedelta(hours=72)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO file_movements
            (case_id, file_type, movement_type, moved_to, moved_by,
             reason, expected_return, status)
            VALUES (?, 'Working File', 'Checkout', 'DCO Office', 'T001',
                    'Review', ?, 'Out')
        """, (case_id, past_return))
        conn.commit()
        conn.close()

        check_all_deadlines()

        conn = get_db()
        alerts = conn.execute(
            "SELECT * FROM alerts WHERE alert_type = 'overdue_file' AND is_dismissed = 0"
        ).fetchall()
        conn.close()

        assert len(alerts) >= 1
        assert "Overdue file" in alerts[0]["title"]


def test_check_deadlines_idempotent(app):
    """Running check_all_deadlines twice does not create duplicate alerts."""
    with app.app_context():
        from fnid_portal.models import get_db

        conn = get_db()
        case_id = _insert_sample_case(conn, case_id="TEST/SD/A3/FNID/2026/9999")
        past_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO case_reviews
            (case_id, review_type, scheduled_date, status, created_by)
            VALUES (?, 'followup_28day', ?, 'Scheduled', 'SYSTEM')
        """, (case_id, past_date))
        conn.commit()
        conn.close()

        check_all_deadlines()
        check_all_deadlines()  # second run

        conn = get_db()
        alerts = conn.execute(
            "SELECT * FROM alerts WHERE target_type = 'case_review' AND is_dismissed = 0"
        ).fetchall()
        conn.close()

        # Should only have one alert per review, not duplicates
        review_ids = [a["target_id"] for a in alerts]
        assert len(review_ids) == len(set(review_ids)), "Duplicate alerts found"
