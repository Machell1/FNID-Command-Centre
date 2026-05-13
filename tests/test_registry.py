"""
FNID Command Centre v2.0 - Registry Tests (v2 API variant)
SOP Compliance Validation
"""
import pytest
from datetime import datetime

v2_deps = pytest.importorskip("flask_sqlalchemy")

from src.fnid_portal import db  # noqa: E402
from src.fnid_portal.models.base import Case, DCRREntry, StationRegister  # noqa: E402
from src.fnid_portal.models.personnel import Personnel, Area, Division, Station  # noqa: E402
from src.fnid_portal.services.registry_service import RegistryService  # noqa: E402
from src.fnid_portal.services.auth_service import AuthService  # noqa: E402


def test_create_dcr_case(v2_client, auth_headers):
    # Setup reference data
    area = Area(area_code='A3', area_name='Area 3', acp_reg_number='ACP001')
    db.session.add(area)
    db.session.flush()

    division = Division(area_id=area.area_id, division_code='M', division_name='Manchester',
                       division_type='SUPER', commander_reg_number='SP001', dco_reg_number='SP002')
    db.session.add(division)
    db.session.flush()

    station = Station(division_id=division.division_id, station_code='MT', station_name='Mandeville',
                     station_type='GEOGRAPHIC')
    db.session.add(station)
    db.session.commit()

    # Create case
    response = v2_client.post('/registry/cases', headers=auth_headers, json={
        'area_id': area.area_id,
        'division_id': division.division_id,
        'station_id': station.station_id,
        'offence_code': 'FIREARMS',
        'offence_description': 'Illegal possession of firearm and ammunition',
        'diary_type': 'SD',
        'diary_entry_number': 45,
        'location_of_offence': 'Mandeville Market',
        'location_parish': 'Manchester'
    })

    assert response.status_code == 201
    data = response.get_json()
    assert data['registry_type'] == 'DCRR'
    assert 'cr_number' in data

    # Verify CR# format
    cr = data['cr_number']
    parts = cr.split('_')
    assert len(parts) >= 2
    assert parts[1].startswith('20')  # Year

def test_create_station_case(v2_client, auth_headers):
    area = Area(area_code='A3', area_name='Area 3', acp_reg_number='ACP001')
    db.session.add(area)
    db.session.flush()

    division = Division(area_id=area.area_id, division_code='M', division_name='Manchester',
                       division_type='SUPER', commander_reg_number='SP001', dco_reg_number='SP002')
    db.session.add(division)
    db.session.flush()

    station = Station(division_id=division.division_id, station_code='MT', station_name='Mandeville',
                     station_type='GEOGRAPHIC')
    db.session.add(station)
    db.session.commit()

    response = v2_client.post('/registry/cases', headers=auth_headers, json={
        'area_id': area.area_id,
        'division_id': division.division_id,
        'station_id': station.station_id,
        'offence_code': 'LARCENY_SIMPLE',
        'offence_description': 'Simple larceny under $250,000',
        'diary_type': 'SD',
        'diary_entry_number': 12
    })

    assert response.status_code == 201
    data = response.get_json()
    assert data['registry_type'] == 'MINOR'

def test_cr_number_format_validation(v2_client, auth_headers):
    area = Area(area_code='A3', area_name='Area 3', acp_reg_number='ACP001')
    db.session.add(area)
    db.session.flush()

    division = Division(area_id=area.area_id, division_code='M', division_name='Manchester',
                       division_type='SUPER', commander_reg_number='SP001', dco_reg_number='SP002')
    db.session.add(division)
    db.session.flush()

    station = Station(division_id=division.division_id, station_code='MT', station_name='Mandeville',
                     station_type='GEOGRAPHIC')
    db.session.add(station)
    db.session.commit()

    # Test DCRR format
    cr_dcr, _ = RegistryService.generate_cr_number('DCRR', station.station_id, division.division_id, 'SD', 45, datetime.utcnow())
    assert '_' in cr_dcr
    assert '/SD45/' in cr_dcr
    assert cr_dcr.endswith('/M')

    # Test Station format
    cr_station, _ = RegistryService.generate_cr_number('MAJOR', station.station_id, division.division_id, 'SD', 12, datetime.utcnow())
    assert '_/' in cr_station
    assert cr_station.endswith('/MT')

def test_case_status_transition(v2_client, auth_headers):
    # Setup
    area = Area(area_code='A3', area_name='Area 3', acp_reg_number='ACP001')
    db.session.add(area)
    db.session.flush()

    division = Division(area_id=area.area_id, division_code='M', division_name='Manchester',
                       division_type='SUPER', commander_reg_number='SP001', dco_reg_number='SP002')
    db.session.add(division)
    db.session.flush()

    station = Station(division_id=division.division_id, station_code='MT', station_name='Mandeville',
                     station_type='GEOGRAPHIC')
    db.session.add(station)
    db.session.commit()

    # Create case
    response = v2_client.post('/registry/cases', headers=auth_headers, json={
        'area_id': area.area_id,
        'division_id': division.division_id,
        'station_id': station.station_id,
        'offence_code': 'FIREARMS',
        'offence_description': 'Test case for status transition',
        'diary_type': 'SD',
        'diary_entry_number': 1
    })

    case_id = response.get_json()['case_id']

    # Transition to CLOSED
    response = v2_client.put(f'/registry/cases/{case_id}/status', headers=auth_headers, json={
        'status': 'CLOSED',
        'reason': 'Charges preferred, no other suspects'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'CLOSED'

def test_list_cases_with_filters(v2_client, auth_headers):
    response = v2_client.get('/api/v1/cases?status=OPEN', headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert 'cases' in data
    assert 'meta' in data
