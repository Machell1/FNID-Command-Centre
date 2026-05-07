"""
FNID Command Centre v2.0 - Authentication Tests
"""
import pytest
from src.fnid_portal import db
from src.fnid_portal.models.personnel import Personnel, Area, Division, Station
from src.fnid_portal.services.auth_service import AuthService

def test_login_success(client):
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
    db.session.flush()

    officer = Personnel(
        reg_number='AUTH001',
        rank='INSPECTOR',
        full_name='Auth Test',
        email='auth@test.jm',
        password_hash=AuthService.hash_password('password123'),
        division_id=division.division_id,
        station_id=station.station_id,
        unit='FNID',
        role='REGISTRAR',
        is_active=True
    )
    db.session.add(officer)
    db.session.commit()

    # Test login
    response = client.post('/auth/login', json={
        'reg_number': 'AUTH001',
        'password': 'password123'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert 'access_token' in data
    assert 'refresh_token' in data
    assert data['officer']['reg_number'] == 'AUTH001'

def test_login_invalid_credentials(client):
    response = client.post('/auth/login', json={
        'reg_number': 'INVALID',
        'password': 'wrong'
    })
    assert response.status_code == 401

def test_protected_route_without_token(client):
    response = client.get('/api/v1/cases')
    assert response.status_code == 401

def test_protected_route_with_token(client, auth_headers):
    response = client.get('/api/v1/cases', headers=auth_headers)
    assert response.status_code == 200
