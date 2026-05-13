"""Regression tests for the React dashboard JSON API."""

from werkzeug.security import generate_password_hash


def _login_dashboard_client(tmp_path, monkeypatch):
    monkeypatch.setenv("FNID_DB_PATH", str(tmp_path / "fnid_dashboard.db"))
    monkeypatch.setenv("FLASK_ENV", "testing")

    from fnid_portal import create_app
    from fnid_portal.models import get_db

    app = create_app("testing")
    badge = "DASH-ADMIN"
    password = "TestPass123!"

    with app.app_context():
        conn = get_db()
        conn.execute("""
            INSERT INTO officers
                (badge_number, full_name, rank, section, role, password_hash,
                 unit_access, must_change_password, is_active, verification_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, 'active')
        """, (
            badge,
            "Dashboard Admin",
            "Inspector",
            "FNID Headquarters - Area 3",
            "admin",
            generate_password_hash(password),
            "all",
        ))
        conn.execute("""
            INSERT INTO cases
                (case_id, registration_date, classification, oic_badge, oic_name,
                 oic_rank, parish, offence_description, law_and_section,
                 case_status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "DASH-CASE-1",
            "2026-05-13",
            "Major Investigation",
            badge,
            "Dashboard Admin",
            "Inspector",
            "Manchester",
            "Dashboard schema regression",
            "Test Law",
            "Open - Active Investigation",
            badge,
        ))
        conn.execute("""
            INSERT INTO alerts
                (alert_type, target_type, target_id, title, message, severity,
                 target_badge, is_dismissed)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            "deadline",
            "case",
            "DASH-CASE-1",
            "Critical dashboard alert",
            "A dashboard alert should be returned.",
            "critical",
            badge,
        ))
        conn.commit()
        conn.close()

    client = app.test_client()
    login = client.post(
        "/api/v1/auth/login",
        json={"badge_number": badge, "password": password},
    )
    assert login.status_code == 200
    return client


def test_dashboard_api_uses_current_sqlite_schema(tmp_path, monkeypatch):
    client = _login_dashboard_client(tmp_path, monkeypatch)

    home = client.get("/api/v1/dashboard/")
    assert home.status_code == 200
    home_data = home.get_json()
    assert home_data["stats"]["cases"] == 1
    assert home_data["recent_activity"][0]["time"]
    assert home_data["alerts"][0]["title"] == "Critical dashboard alert"

    command = client.get("/api/v1/dashboard/command")
    assert command.status_code == 200
    command_data = command.get_json()
    assert command_data["case_status"] == [
        {"status": "Open - Active Investigation", "count": 1}
    ]

    count = client.get("/api/v1/dashboard/notifications/count")
    assert count.status_code == 200
    assert count.get_json() == {"total": 1, "critical": 1}
