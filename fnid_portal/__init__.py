"""
FNID Area 3 Operational Portal

Flask application factory for the Jamaica Constabulary Force
Firearms & Narcotics Investigation Division, Area 3.

Phase 1: Core case management system with RBAC, CR forms, case lifecycle,
file movement, MCR engine, intelligence, admin, and search modules.

Phase 2: Transport, DCRR views, evidence management, analytics, batch
operations, notifications, and report generation.

Phase 3: DPP prosecution pipeline, SOP compliance checklists, witness
statement management, and disclosure log.

Phase 4: Correspondence tracking, investigator cards, case review
scheduling, and intelligence target profiles.

Phase 5: Security hardening, legal compliance, workflow engine,
member features (registration, documents, KPIs, maintenance).
"""

import os
from datetime import datetime, timedelta

from flask import Flask, redirect, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFProtect

from . import models
from .auth import login_manager
from .config import config_by_name
from .constants import UNIT_PORTALS
from .rbac import ROLES, can_access

csrf = CSRFProtect()


def create_app(config_name=None):
    """Create and configure the Flask application.

    Args:
        config_name: Configuration name ('development', 'production', 'testing').
                     Defaults to FLASK_ENV environment variable or 'development'.
    """
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)

    # Load configuration
    config_cls = config_by_name.get(config_name)
    if config_cls is None:
        raise ValueError(f"Unknown config: {config_name}. Use: {list(config_by_name.keys())}")

    # For production, instantiate to trigger validation
    if config_name == "production":
        config_obj = config_cls()
        app.config.from_object(config_obj)
    else:
        app.config.from_object(config_cls)

    # Store custom paths in app config for easy access
    app.config.setdefault("UPLOAD_DIR", config_cls.UPLOAD_DIR)
    app.config.setdefault("EXPORT_DIR", config_cls.EXPORT_DIR)

    # Ensure data directories exist
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    os.makedirs(app.config["EXPORT_DIR"], exist_ok=True)

    # Configure database
    db_path = getattr(config_cls, "DB_PATH", None)
    if config_name == "production":
        db_path = config_obj.DB_PATH
    app.config["DB_PATH"] = db_path
    models.configure(db_path)

    # Initialize database
    models.init_db()

    # Initialize CSRF protection
    csrf.init_app(app)

    # Initialize Flask-Login
    login_manager.init_app(app)
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(hours=8)

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' https://cdn.jsdelivr.net data:; "
            "style-src 'self' https://cdn.jsdelivr.net https://cdn.datatables.net 'unsafe-inline'; "
            "script-src 'self' https://cdn.jsdelivr.net https://code.jquery.com "
            "https://cdn.datatables.net 'unsafe-inline'; "
            "connect-src 'self'"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        if not app.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Verification gate: block pending users from main routes
    ALLOWED_UNVERIFIED = {
        "auth.login", "auth.register", "auth.pending_verification",
        "auth.logout", "static",
    }

    @app.before_request
    def check_verification():
        if not current_user.is_authenticated:
            return
        endpoint = request.endpoint or ""
        if endpoint in ALLOWED_UNVERIFIED or endpoint.startswith("static"):
            return
        if hasattr(current_user, "is_verified") and not current_user.is_verified():
            if endpoint != "auth.pending_verification":
                return redirect(url_for("auth.pending_verification"))

    # Register context processor
    @app.context_processor
    def inject_globals():
        from flask_login import current_user as _cu
        single_unit = None
        if _cu.is_authenticated and hasattr(_cu, "get_single_unit"):
            single_unit = _cu.get_single_unit()
        return {
            "portals": UNIT_PORTALS,
            "now": datetime.now(),
            "roles": ROLES,
            "can_access": can_access,
            "current_user": _cu,
            "user_single_unit": single_unit,
        }

    # Register blueprints — existing
    from .routes.api import bp as api_bp
    from .routes.auth import bp as auth_bp
    from .routes.data import bp as data_bp
    from .routes.main import bp as main_bp
    from .routes.units import bp as units_bp
    from .routes.upload import bp as upload_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(units_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(api_bp)

    # Register blueprints — Phase 1 new modules
    from .routes.admin import bp as admin_bp
    from .routes.cases import bp as cases_bp
    from .routes.cr_forms import bp as cr_forms_bp
    from .routes.file_movement import bp as file_movement_bp
    from .routes.intel_unit import bp as intel_unit_bp
    from .routes.mcr import bp as mcr_bp
    from .routes.search import bp as search_bp

    app.register_blueprint(cases_bp)
    app.register_blueprint(cr_forms_bp)
    app.register_blueprint(file_movement_bp)
    app.register_blueprint(mcr_bp)
    app.register_blueprint(intel_unit_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(search_bp)

    # Register blueprints — Phase 2 modules
    from .routes.analytics import bp as analytics_bp
    from .routes.batch import bp as batch_bp
    from .routes.dcrr import bp as dcrr_bp
    from .routes.evidence import bp as evidence_bp
    from .routes.notifications import bp as notifications_bp
    from .routes.reports import bp as reports_bp
    from .routes.transport import bp as transport_bp

    app.register_blueprint(transport_bp)
    app.register_blueprint(dcrr_bp)
    app.register_blueprint(evidence_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(notifications_bp)

    # Register blueprints — Phase 3 modules
    from .routes.disclosure import bp as disclosure_bp
    from .routes.dpp import bp as dpp_bp
    from .routes.sop import bp as sop_bp
    from .routes.witnesses import bp as witnesses_bp

    app.register_blueprint(dpp_bp)
    app.register_blueprint(sop_bp)
    app.register_blueprint(witnesses_bp)
    app.register_blueprint(disclosure_bp)

    # Register blueprints — Phase 4 modules
    from .routes.correspondence import bp as correspondence_bp
    from .routes.inv_cards import bp as inv_cards_bp
    from .routes.reviews import bp as reviews_bp
    from .routes.targets import bp as targets_bp

    app.register_blueprint(correspondence_bp)
    app.register_blueprint(inv_cards_bp)
    app.register_blueprint(reviews_bp)
    app.register_blueprint(targets_bp)

    # Register blueprints — Policy & Forms module
    from .routes.policy import bp as policy_bp

    app.register_blueprint(policy_bp)

    # Register blueprints — Phase 5 modules
    from .routes.documents import bp as documents_bp
    from .routes.kpis import bp as kpis_bp
    from .routes.workflow_routes import bp as workflow_bp
    from .routes.assistants import bp as assistants_bp

    app.register_blueprint(documents_bp)
    app.register_blueprint(kpis_bp)
    app.register_blueprint(workflow_bp)
    app.register_blueprint(assistants_bp)

    # Register blueprints — React SPA & API v1
    from .routes.api_v1.auth import bp as api_auth_bp
    from .routes.api_v1.dashboard import bp as api_dashboard_bp
    from .routes.spa import bp as spa_bp

    app.register_blueprint(api_auth_bp)
    app.register_blueprint(api_dashboard_bp)
    app.register_blueprint(spa_bp)

    # Exempt JSON API from CSRF (session cookies still required)
    csrf.exempt(api_auth_bp)
    csrf.exempt(api_dashboard_bp)

    # CSRF token endpoint for the React SPA
    @app.route("/api/v1/csrf-token")
    def csrf_token_endpoint():
        from flask import jsonify
        from flask_wtf.csrf import generate_csrf
        return jsonify({"csrf_token": generate_csrf()})

    # Register CLI commands
    _register_cli(app)

    return app


def _register_cli(app):
    """Register Flask CLI commands."""
    import click

    @app.cli.command("seed")
    @click.option("--force", is_flag=True, help="Drop and re-seed even if data exists")
    def seed_command(force):
        """Seed the database with sample FNID Area 3 test data."""
        from .seed import seed_database
        seed_database(force=force)
        click.echo("Database seeded successfully.")

    @app.cli.command("check-deadlines")
    def check_deadlines_command():
        """Run the deadline checker to generate alerts."""
        from .deadlines import check_all_deadlines
        check_all_deadlines()
        click.echo("Deadline check complete.")
