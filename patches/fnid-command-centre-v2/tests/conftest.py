"""
FNID Command Centre v2.0 - Pytest Configuration
"""
import pytest
from src.fnid_portal import create_app, db
from src.fnid_portal.models.personnel import Personnel, Area, Division, Station
from src.fnid_portal.services.auth_service import AuthService

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_headers(client):
    # Create test officer
    area = Area(area_code='A3', area_name='Area 3', acp_reg_number='ACP001')
    db.session.add(area)
    db.session.flush()

    division = Division(
        area_id=area.area_id,
        division_code='M',
        division_name='Manchester',
        division_type='SUPER',
        commander_reg_number='SP001',
        dco_reg_number='SP002'
    )
    db.session.add(division)
    db.session.flush()

    station = Station(
        division_id=division.division_id,
        station_code='MT',
        station_name='Mandeville',
        station_type='GEOGRAPHIC'
    )
    db.session.add(station)
    db.session.flush()

    officer = Personnel(
        reg_number='TEST001',
        rank='INSPECTOR',
        full_name='Test Officer',
        email='test@fnid.jcf.gov.jm',
        password_hash=AuthService.hash_password('testpass123'),
        division_id=division.division_id,
        station_id=station.station_id,
        unit='FNID',
        role='REGISTRAR',
        is_active=True
    )
    db.session.add(officer)
    db.session.commit()

    # Login
    response = client.post('/auth/login', json={
        'reg_number': 'TEST001',
        'password': 'testpass123'
    })

    token = response.get_json()['access_token']
    return {'Authorization': f'Bearer {token}'}
