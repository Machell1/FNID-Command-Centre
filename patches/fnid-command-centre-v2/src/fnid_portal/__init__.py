"""
FNID Command Centre v2.0 - Application Factory
JCF SOP Compliant - Production Ready
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_cors import CORS
from .config import config_by_name

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address)
talisman = Talisman()

def create_app(config_name='production'):
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')

    # Load configuration
    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # Security headers in production
    if config_name == 'production':
        talisman.init_app(app, 
                         force_https=True,
                         strict_transport_security=True,
                         content_security_policy=app.config.get('CONTENT_SECURITY_POLICY', {}))

    # CORS
    CORS(app, origins=app.config.get('CORS_ORIGINS', ['https://fnid.jcf.gov.jm']))

    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.registry import registry_bp
    from .routes.investigation import investigation_bp
    from .routes.seizures import seizures_bp
    from .routes.intelligence import intelligence_bp
    from .routes.court import court_bp
    from .routes.forensics import forensics_bp
    from .routes.api import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(registry_bp, url_prefix='/registry')
    app.register_blueprint(investigation_bp, url_prefix='/investigation')
    app.register_blueprint(seizures_bp, url_prefix='/seizures')
    app.register_blueprint(intelligence_bp, url_prefix='/intelligence')
    app.register_blueprint(court_bp, url_prefix='/court')
    app.register_blueprint(forensics_bp, url_prefix='/forensics')
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {'message': 'Token has expired', 'error': 'token_expired'}, 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {'message': 'Signature verification failed', 'error': 'invalid_token'}, 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return {'message': 'Request does not contain an access token', 'error': 'authorization_required'}, 401

    # Error handlers
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return {'message': 'Rate limit exceeded', 'error': 'rate_limit'}, 429

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return {'message': 'Internal server error', 'error': 'internal_error'}, 500

    # Create tables (development only - use migrations in production)
    with app.app_context():
        if config_name == 'development':
            db.create_all()

    return app
