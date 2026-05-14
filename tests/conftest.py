"""Pytest configuration for the FNID Command Centre."""
import os

import pytest
from werkzeug.security import generate_password_hash


@pytest.fixture
def app(tmp_path):
    """Primary fnid_portal Flask app with a disposable SQLite DB."""
    db_path = str(tmp_path / "fnid_test.db")
    os.environ["FNID_DB_PATH"] = db_path
    os.environ["FLASK_ENV"] = "testing"

    from fnid_portal import create_app, models

    models.configure(db_path)
    application = create_app("testing")
    application.config["DB_PATH"] = db_path
    yield application


@pytest.fixture
def client(app):
    """Unauthenticated test client."""
    return app.test_client()


@pytest.fixture
def db(app):
    """Open SQLite connection scoped to the test app context."""
    from fnid_portal.models import get_db

    with app.app_context():
        conn = get_db()
        try:
            yield conn
        finally:
            conn.close()


def _seed_test_officer(app, badge, role="admin", admin_tier=1):
    """Insert (or update) an officer row, return the plaintext password."""
    from fnid_portal.models import get_db

    password = "TestPass123!"
    with app.app_context():
        conn = get_db()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO officers
                    (badge_number, full_name, rank, section, role,
                     password_hash, unit_access, must_change_password,
                     admin_tier, is_active, verification_status)
                VALUES (?, ?, ?, ?, ?, ?, 'all', 0, ?, 1, 'active')
                """,
                (
                    badge,
                    f"Test {role.title()}",
                    "Inspector of Police",
                    "FNID Headquarters - Area 3",
                    role,
                    generate_password_hash(password),
                    admin_tier,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return password


def _login_client(app, badge, role, admin_tier):
    password = _seed_test_officer(app, badge, role=role, admin_tier=admin_tier)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess.clear()
    resp = client.post(
        "/login",
        data={"badge_number": badge, "password": password},
        follow_redirects=False,
    )
    assert resp.status_code in (200, 302), (
        f"Login failed for {badge}: {resp.status_code} {resp.data[:200]!r}"
    )
    return client


@pytest.fixture
def admin_client(app):
    """Test client logged in as an admin."""
    return _login_client(app, "TEST-ADMIN", role="admin", admin_tier=1)


@pytest.fixture
def logged_in_client(app):
    """Test client logged in as a regular investigating officer."""
    return _login_client(app, "TEST-OFFICER", role="io", admin_tier=None)


@pytest.fixture
def io_client(app):
    """Alias for logged_in_client — kept for legacy test imports."""
    return _login_client(app, "TEST-IO", role="io", admin_tier=None)
