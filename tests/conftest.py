"""Pytest fixtures for FNID Portal tests."""

import os
import tempfile

import pytest
from fnid_portal import create_app
from fnid_portal.config import TestingConfig
from werkzeug.security import generate_password_hash

TEST_PASSWORD = "TestPass@2026!"


@pytest.fixture()
def app():
    """Create application for testing with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    TestingConfig.DB_PATH = db_path
    TestingConfig.UPLOAD_DIR = tempfile.mkdtemp()
    TestingConfig.EXPORT_DIR = tempfile.mkdtemp()

    app = create_app("testing")

    # Create test officers with known passwords
    from fnid_portal.models import get_db
    with app.app_context():
        conn = get_db()
        pw_hash = generate_password_hash(TEST_PASSWORD)

        # Regular test officer
        conn.execute("""
            INSERT OR IGNORE INTO officers
                (badge_number, full_name, rank, section, role,
                 password_hash, is_active, unit_access,
                 must_change_password, verification_status)
            VALUES (?, ?, ?, ?, ?, ?, 1, 'all', 0, 'active')
        """, ("TEST001", "Test Officer", "Inspector of Police",
              "FNID Headquarters - Area 3", "io", pw_hash))

        # IO test officer
        conn.execute("""
            INSERT OR IGNORE INTO officers
                (badge_number, full_name, rank, section, role,
                 password_hash, is_active, unit_access,
                 must_change_password, verification_status)
            VALUES (?, ?, ?, ?, ?, ?, 1, 'all', 0, 'active')
        """, ("IO-TEST", "IO Test Officer", "Detective Constable",
              "FNID Headquarters - Area 3", "io", pw_hash))

        conn.commit()
        conn.close()

    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture()
def logged_in_client(client):
    """A test client that is already logged in."""
    client.post("/login", data={
        "badge_number": "TEST001",
        "password": TEST_PASSWORD,
    })
    return client


@pytest.fixture()
def admin_client(client, app):
    """A test client logged in as admin."""
    # The admin is created by init_db with a random password,
    # so set a known password first.
    from fnid_portal.models import get_db
    with app.app_context():
        conn = get_db()
        conn.execute(
            "UPDATE officers SET password_hash = ?, must_change_password = 0 WHERE badge_number = 'ADMIN'",
            (generate_password_hash(TEST_PASSWORD),),
        )
        conn.commit()
        conn.close()

    client.post("/login", data={
        "badge_number": "ADMIN",
        "password": TEST_PASSWORD,
    })
    return client


@pytest.fixture()
def io_client(client):
    """A test client logged in as an IO."""
    client.post("/login", data={
        "badge_number": "IO-TEST",
        "password": TEST_PASSWORD,
    })
    return client


@pytest.fixture()
def db(app):
    """Get a database connection for direct testing."""
    from fnid_portal.models import get_db
    conn = get_db()
    yield conn
    conn.close()
