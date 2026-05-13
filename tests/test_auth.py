"""
FNID Command Centre v2.0 - Authentication Tests (v2 API variant)

These tests exercise the SQLAlchemy/JWT-based src.fnid_portal app.
They are skipped when the v2 dependencies are not installed.
"""
import pytest

v2_deps = pytest.importorskip("flask_sqlalchemy")

from src.fnid_portal import db as v2_db  # noqa: E402
from src.fnid_portal.models.personnel import Personnel, Area, Division, Station  # noqa: E402
from src.fnid_portal.services.auth_service import AuthService  # noqa: E402


@pytest.fixture
def _v2_seed(v2_app):
    """Insert reference rows needed by every v2 auth test."""
    with v2_app.app_context():
        area = Area(area_code="A3", area_name="Area 3", acp_reg_number="ACP001")
        v2_db.session.add(area)
        v2_db.session.flush()

        division = Division(area_id=area.area_id, division_code="M", division_name="Manchester",
                           division_type="SUPER", commander_reg_number="SP001", dco_reg_number="SP002")
        v2_db.session.add(division)
        v2_db.session.flush()

        station = Station(division_id=division.division_id, station_code="MT", station_name="Mandeville",
                         station_type="GEOGRAPHIC")
        v2_db.session.add(station)
        v2_db.session.flush()

        officer = Personnel(
            reg_number="AUTH001",
            rank="INSPECTOR",
            full_name="Auth Test",
            email="auth@test.jm",
            password_hash=AuthService.hash_password("password123"),
            division_id=division.division_id,
            station_id=station.station_id,
            unit="FNID",
            role="REGISTRAR",
            is_active=True,
        )
        v2_db.session.add(officer)
        v2_db.session.commit()


def test_login_success(v2_client, _v2_seed):
    response = v2_client.post("/auth/login", json={
        "reg_number": "AUTH001",
        "password": "password123",
    })
    assert response.status_code == 200
    data = response.get_json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["officer"]["reg_number"] == "AUTH001"


def test_login_invalid_credentials(v2_client):
    response = v2_client.post("/auth/login", json={
        "reg_number": "INVALID",
        "password": "wrong",
    })
    assert response.status_code == 401


def test_protected_route_without_token(v2_client):
    response = v2_client.get("/api/v1/cases")
    assert response.status_code == 401


def test_protected_route_with_token(v2_client, auth_headers):
    response = v2_client.get("/api/v1/cases", headers=auth_headers)
    assert response.status_code == 200
