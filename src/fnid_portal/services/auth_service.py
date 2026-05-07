"""
FNID Command Centre v2.0 - Authentication Service
Production-grade security with JCF RBAC
"""
import bcrypt
from datetime import datetime
from flask_jwt_extended import create_access_token, create_refresh_token
from ..models.personnel import Personnel
from .. import db

class AuthService:
    @staticmethod
    def authenticate(reg_number, password):
        """Authenticate officer and return tokens."""
        officer = Personnel.query.get(reg_number)
        if not officer or not officer.is_active:
            return None, 'Invalid credentials or inactive account'

        if not officer.password_hash:
            return None, 'Account not configured for password login'

        if not bcrypt.checkpw(password.encode('utf-8'), officer.password_hash.encode('utf-8')):
            return None, 'Invalid credentials'

        officer.last_login = datetime.utcnow()
        db.session.commit()

        # Create tokens with officer claims
        additional_claims = {
            'reg_number': officer.reg_number,
            'rank': officer.rank,
            'role': officer.role,
            'unit': officer.unit,
            'division_id': officer.division_id,
            'station_id': officer.station_id,
            'full_name': officer.full_name
        }

        access_token = create_access_token(
            identity=officer.reg_number,
            additional_claims=additional_claims
        )
        refresh_token = create_refresh_token(identity=officer.reg_number)

        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'officer': {
                'reg_number': officer.reg_number,
                'full_name': officer.full_name,
                'rank': officer.rank,
                'role': officer.role,
                'unit': officer.unit
            }
        }, None

    @staticmethod
    def hash_password(password):
        """Hash password with bcrypt."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')

    @staticmethod
    def require_role(officer, roles):
        """Check if officer has required role."""
        if isinstance(roles, str):
            roles = [roles]
        return officer.role in roles
