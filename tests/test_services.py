"""
FNID Command Centre v2.0 - Service Layer Tests (v2 API variant)

Skipped automatically when v2 SQLAlchemy dependencies are absent.
"""
import pytest
from datetime import datetime, timedelta

v2_deps = pytest.importorskip("flask_sqlalchemy")

from src.fnid_portal import db as v2_db  # noqa: E402
from src.fnid_portal.models.base import Case, Investigation  # noqa: E402
from src.fnid_portal.models.personnel import Personnel, Area, Division, Station  # noqa: E402
from src.fnid_portal.services.registry_service import RegistryService  # noqa: E402
from src.fnid_portal.services.auth_service import AuthService  # noqa: E402
from src.fnid_portal.services.audit_service import AuditService  # noqa: E402


def test_classify_offence():
    result = RegistryService.classify_offence("FIREARMS")
    assert result["registry"] == "DCRR"
    assert result["is_major"] is True

    result = RegistryService.classify_offence("LARCENY_SIMPLE")
    assert result["registry"] == "MINOR"
    assert result["is_major"] is False


def test_audit_log_creation(v2_app):
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
            reg_number="AUDIT001",
            rank="INSPECTOR",
            full_name="Audit Test",
            email="audit@test.jm",
            password_hash=AuthService.hash_password("pass"),
            division_id=division.division_id,
            station_id=station.station_id,
            unit="FNID",
            role="REGISTRAR",
        )
        v2_db.session.add(officer)
        v2_db.session.commit()

        hash_val = AuditService.log_action(
            officer=officer,
            action="CREATE",
            table_name="cases",
            record_id="test-123",
            new_values={"status": "OPEN"},
        )

        assert hash_val is not None
        assert len(hash_val) == 64  # SHA-256 hex


def test_vetting_deadline_calculation(v2_app):
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
            reg_number="VET001",
            rank="CONSTABLE",
            full_name="Vet Test",
            email="vet@test.jm",
            password_hash=AuthService.hash_password("pass"),
            division_id=division.division_id,
            station_id=station.station_id,
            unit="FNID",
            role="INVESTIGATING_OFFICER",
        )
        v2_db.session.add(officer)
        v2_db.session.commit()

        case = Case(
            cr_number="TEST_2024/01/01/MT/SD1/M",
            registry_type="DCRR",
            area_id=area.area_id,
            division_id=division.division_id,
            station_id=station.station_id,
            crime_category="FIREARMS",
            offence_code="FIREARMS",
            offence_description="Test",
            investigated_by="NON_UNIFORMED",
            date_reported=datetime.utcnow(),
            status="OPEN",
            created_by="VET001",
        )
        v2_db.session.add(case)
        v2_db.session.flush()

        investigation = Investigation(
            case_id=case.case_id,
            io_reg_number="VET001",
            io_assigned_by="VET001",
            investigation_status="PENDING",
        )
        v2_db.session.add(investigation)
        v2_db.session.commit()

        assert investigation.preliminary_vetting_due is not None
        expected_deadline = investigation.io_assigned_at + timedelta(hours=72)
        assert abs((investigation.preliminary_vetting_due - expected_deadline).total_seconds()) < 5
