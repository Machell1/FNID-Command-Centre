"""
FNID Command Centre v2.0 - Authentication Routes
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from ..services.auth_service import AuthService
from ..models.personnel import Personnel

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('reg_number') or not data.get('password'):
        return jsonify({'message': 'Registration number and password required'}), 400

    result, error = AuthService.authenticate(data['reg_number'], data['password'])
    if error:
        return jsonify({'message': error}), 401

    return jsonify(result), 200

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    reg_number = get_jwt_identity()
    officer = Personnel.query.get(reg_number)
    if not officer:
        return jsonify({'message': 'Officer not found'}), 404

    return jsonify({
        'reg_number': officer.reg_number,
        'full_name': officer.full_name,
        'rank': officer.rank,
        'role': officer.role,
        'unit': officer.unit,
        'division_id': officer.division_id,
        'station_id': officer.station_id
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    from flask_jwt_extended import create_access_token
    reg_number = get_jwt_identity()
    officer = Personnel.query.get(reg_number)

    additional_claims = {
        'reg_number': officer.reg_number,
        'rank': officer.rank,
        'role': officer.role,
        'unit': officer.unit,
        'division_id': officer.division_id,
        'station_id': officer.station_id,
        'full_name': officer.full_name
    }

    access_token = create_access_token(identity=reg_number, additional_claims=additional_claims)
    return jsonify({'access_token': access_token}), 200
