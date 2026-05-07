"""Smoke tests for the FNID Portal application."""


def test_login_page_loads(client):
    """Login page should be accessible."""
    response = client.get("/login")
    assert response.status_code == 200
    assert b"FNID" in response.data


def test_home_redirects_when_not_logged_in(client):
    """Home page should redirect to login when not authenticated."""
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_creates_session(logged_in_client):
    """Posting valid credentials should create a session and redirect."""
    response = logged_in_client.get("/")
    assert response.status_code == 200
    assert b"Test Officer" in response.data


def test_home_loads_when_logged_in(logged_in_client):
    """Home page should load when logged in."""
    response = logged_in_client.get("/")
    assert response.status_code == 200
    assert b"Intelligence Unit" in response.data


def test_unit_pages_load(logged_in_client):
    """Each unit home page should load successfully."""
    for unit in ["intel", "operations", "seizures", "arrests", "forensics", "registry"]:
        response = logged_in_client.get(f"/unit/{unit}")
        assert response.status_code == 200, f"Unit {unit} failed to load"


def test_operational_pages_use_case_reference_language_and_show_ai(logged_in_client):
    """Officer-facing pages should use Case Reference No. and expose the AI assistant."""
    seizures = logged_in_client.get("/unit/seizures")
    assert seizures.status_code == 200
    assert b"AI Assistant" in seizures.data
    assert b"/assistants/workstation" in seizures.data

    registry = logged_in_client.get("/unit/registry")
    assert registry.status_code == 200
    assert b"Case Reference No." in registry.data
    assert b"Case ID" not in registry.data
    assert b"No Major Crime Register entries yet." not in registry.data


def test_unit_dashboards_load(logged_in_client):
    """Each unit dashboard should load successfully."""
    for unit in ["intel", "operations", "seizures", "arrests", "forensics", "registry"]:
        response = logged_in_client.get(f"/unit/{unit}/dashboard")
        assert response.status_code == 200, f"Dashboard {unit} failed to load"


def test_command_dashboard_loads(logged_in_client):
    """Command dashboard should load successfully."""
    response = logged_in_client.get("/command")
    assert response.status_code == 200


def test_api_stats_returns_json(logged_in_client):
    """API stats endpoint should return JSON."""
    response = logged_in_client.get("/api/stats/command")
    assert response.status_code == 200
    data = response.get_json()
    assert "intel" in data
    assert "cases" in data


def test_invalid_unit_redirects(logged_in_client):
    """Accessing an invalid unit should redirect."""
    response = logged_in_client.get("/unit/nonexistent")
    assert response.status_code == 302


def test_logout_clears_session(logged_in_client):
    """Logout should clear the session."""
    response = logged_in_client.get("/logout")
    assert response.status_code == 302
    # After logout, home should redirect to login
    response = logged_in_client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_new_record_form_loads(logged_in_client):
    """New record form should load for each unit."""
    response = logged_in_client.get("/unit/intel/new")
    assert response.status_code == 200


def test_case_intake_form_loads(admin_client):
    """Case intake should render with policy case-number helpers."""
    response = admin_client.get("/cases/intake")
    assert response.status_code == 200
    assert b"Case Intake" in response.data


def test_case_list_loads(admin_client):
    """Case list should render with status/parish filters."""
    response = admin_client.get("/cases/")
    assert response.status_code == 200
    assert b"Case Management" in response.data
    assert b"All Statuses" in response.data


def test_admin_surfaces_load(admin_client):
    """Admin settings, audit, users, and backups should render for admins."""
    for path in ["/admin/settings", "/admin/audit-log", "/admin/users", "/admin/backup"]:
        response = admin_client.get(path)
        assert response.status_code == 200, f"{path} failed to load"


def test_security_headers_present(logged_in_client):
    """Baseline browser security headers should be present on protected pages."""
    response = logged_in_client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert "connect-src 'self'" in response.headers["Content-Security-Policy"]
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert "geolocation=()" in response.headers["Permissions-Policy"]
    assert "no-store" in response.headers["Cache-Control"]


def test_admin_forms_include_csrf_and_setting_prefix(admin_client):
    """Admin forms should carry CSRF tokens and setting_ field names."""
    response = admin_client.get("/admin/settings")
    assert response.status_code == 200
    assert b'name="csrf_token"' in response.data
    assert b'name="setting_' in response.data


def test_admin_rejects_weak_new_user_password(admin_client):
    """Admin-created accounts must use the platform password policy."""
    response = admin_client.post("/admin/users/new", data={
        "badge_number": "WEAK001",
        "full_name": "Weak Password User",
        "rank": "Inspector of Police",
        "section": "FNID Headquarters - Area 3",
        "role": "io",
        "password": "short",
        "confirm_password": "short",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Password must be at least 10 characters" in response.data


def test_registry_can_choose_major_crime_register(admin_client, db):
    """Registry intake may use Major Crime Register without breaking the case workflow."""
    response = admin_client.post("/cases/intake", data={
        "station_code": "FNID",
        "primary_register_type": "major_crime_register",
        "diary_number": "QA-42",
        "registration_date": "2026-05-04",
        "division": "FNID Area 3",
        "parish": "Manchester",
        "crime_type": "major",
        "workflow_type": "non-uniformed",
        "classification": "Firearms - Possession",
        "offence_description": "Unauthorised Possession of Firearm",
        "law_and_section": "s.35 Firearms Act 2022",
        "suspect_name": "QA Suspect",
        "victim_name": "QA Complainant",
    })

    assert response.status_code == 302
    case = db.execute(
        "SELECT * FROM cases WHERE primary_register_type = 'major_crime_register' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert case is not None
    assert case["primary_register_number"].startswith("MCRG/FNID/2026/")

    major = db.execute(
        "SELECT * FROM major_crime_register WHERE case_id = ?",
        (case["case_id"],),
    ).fetchone()
    assert major is not None

    detail = admin_client.get(f"/cases/{case['case_id']}")
    assert detail.status_code == 200
    timeline = admin_client.get(f"/cases/{case['case_id']}/timeline")
    assert timeline.status_code == 200


def test_import_page_loads(logged_in_client):
    """Import page should load."""
    response = logged_in_client.get("/import")
    assert response.status_code == 200
