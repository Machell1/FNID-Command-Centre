"""
FNID Command Centre - Pytest Configuration

Provides fixtures for both:
  1. The primary fnid_portal app (SQLite, Flask-Login sessions)
  2. The src.fnid_portal v2 API variant (SQLAlchemy, JWT)
"""
import os
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Fixtures for the PRIMARY fnid_portal app (SQLite + Flask-Login)
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create the primary fnid_portal Flask app with a disposable SQLite DB."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    os.environ["FNID_DB_PATH"] = db_path
    os.environ["FLASK_ENV"] = "testing"

    from fnid_portal import create_app
    application = create_app("testing")
    application.config["DB_PATH"] = db_path

    yield application

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Unauthenticated test client."""
    return app.test_client()


@pytest.fixture
def db(app):
    """Return an open SQLite connection inside the app context."""
    from fnid_portal.models import get_db
    with app.app_context():
        conn = get_db()
        yield conn
        conn.close()


def _seed_test_officer(app, badge, role="admin", admin_tier=1):
    """Insert a minimal officer row and return the plaintext password."""
    from werkzeug.security import generate_password_hash
    from fnid_portal.models import get_db

    password = "TestPass123!"
    pw_hash = generate_password_hash(password)

    with app.app_context():
        conn = get_db()
        conn.execute("""
            INSERT OR REPLACE INTO officers
                (badge_number, full_name, rank, section, role,
                 password_hash, unit_access, must_change_password,
                 admin_tier, is_active, verification_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, 1, 'active')
        """, (badge, f"Test {role.title()}", "Inspector of Police",
              "FNID Headquarters - Area 3", role, pw_hash, "all", admin_tier))
        conn.commit()
        conn.close()

    return password


@pytest.fixture
def logged_in_client(app, client):
    """Test client logged in as a regular officer."""
    password = _seed_test_officer(app, "TEST-OFFICER", role="io", admin_tier=None)
    with client.session_transaction() as sess:
        sess.clear()
    client.post("/login", data={
        "badge_number": "TEST-OFFICER",
        "password": password,
    }, follow_redirects=True)
    return client


@pytest.fixture
def admin_client(app, client):
    """Test client logged in as an admin."""
    password = _seed_test_officer(app, "TEST-ADMIN", role="admin", admin_tier=1)
    with client.session_transaction() as sess:
        sess.clear()
    client.post("/login", data={
        "badge_number": "TEST-ADMIN",
        "password": password,
    }, follow_redirects=True)
    return client


@pytest.fixture
def io_client(app, client):
    """Test client logged in as an investigating officer."""
    password = _seed_test_officer(app, "TEST-IO", role="io", admin_tier=None)
    with client.session_transaction() as sess:
        sess.clear()
    client.post("/login", data={
        "badge_number": "TEST-IO",
        "password": password,
    }, follow_redirects=True)
    return client


# ---------------------------------------------------------------------------
# Fixtures for the src/fnid_portal v2 API variant (SQLAlchemy + JWT)
# These are only used by tests/test_auth.py, test_registry.py, test_services.py.
# ---------------------------------------------------------------------------

@pytest.fixture
def v2_app():
    """Create the v2 SQLAlchemy-based app for API tests."""
    try:
        from src.fnid_portal import create_app as v2_create_app, db as v2_db
        application = v2_create_app("testing")
        with application.app_context():
            v2_db.create_all()
            yield application
            v2_db.session.remove()
            v2_db.drop_all()
    except ImportError:
        pytest.skip("src.fnid_portal not available")


@pytest.fixture
def v2_client(v2_app):
    """Test client for the v2 API variant."""
    return v2_app.test_client()


@pytest.fixture
def auth_headers(v2_client):
    """JWT auth headers for v2 API tests."""
    try:
        from src.fnid_portal import db as v2_db
        from src.fnid_portal.models.personnel import Personnel, Area, Division, Station
        from src.fnid_portal.services.auth_service import AuthService
    except ImportError:
        pytest.skip("src.fnid_portal not available")

    area = Area(area_code="T3", area_name="Test Area", acp_reg_number="ACP001")
    v2_db.session.add(area)
    v2_db.session.flush()

    division = Division(
        area_id=area.area_id,
        division_code="TT",
        division_name="Test Division",
        division_type="SUPER",
        commander_reg_number="SP001",
        dco_reg_number="SP002",
    )
    v2_db.session.add(division)
    v2_db.session.flush()

    station = Station(
        division_id=division.division_id,
        station_code="TS",
        station_name="Test Station",
        station_type="GEOGRAPHIC",
    )
    v2_db.session.add(station)
    v2_db.session.flush()

    officer = Personnel(
        reg_number="TEST001",
        rank="INSPECTOR",
        full_name="Test Officer",
        email="test@fnid.jcf.gov.jm",
        password_hash=AuthService.hash_password("testpass123"),
        division_id=division.division_id,
        station_id=station.station_id,
        unit="FNID",
        role="REGISTRAR",
        is_active=True,
    )
    v2_db.session.add(officer)
    v2_db.session.commit()

    response = v2_client.post("/auth/login", json={
        "reg_number": "TEST001",
        "password": "testpass123",
    })

    token = response.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
