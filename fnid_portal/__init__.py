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

import logging
import os
import sys
from datetime import datetime, timedelta

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError, CSRFProtect

from . import models
from .auth import login_manager
from .config import apply_paths_to_config, config_by_name
from .constants import UNIT_PORTALS
from .rbac import ROLES, can_access

csrf = CSRFProtect()


def _configure_logging(app):
    """Set up structured logging.

    - stderr always (for `python main.py` and the launcher's captured output).
    - Rotating file in LOG_DIR whenever it's available (i.e. once the app
      factory has filled it in).
    """
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(name)s: %(message)s"
    )

    level = logging.DEBUG if app.debug else logging.INFO
    app.logger.setLevel(level)
    logging.getLogger("fnid_portal").setLevel(level)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(fmt)
    app.logger.addHandler(stderr_handler)

    log_dir = app.config.get("LOG_DIR")
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                os.path.join(log_dir, "fnid.log"),
                maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
            )
            file_handler.setFormatter(fmt)
            app.logger.addHandler(file_handler)
            logging.getLogger("fnid_portal").addHandler(file_handler)
        except OSError:
            app.logger.warning("Could not set up file logging in %s", log_dir)


def _init_sentry(app):
    """Initialise Sentry error tracking when a DSN is configured."""
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration

        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_RATE", "0.1")),
            environment=os.environ.get("FLASK_ENV", "production"),
        )
        app.logger.info("Sentry error tracking initialised")
    except ImportError:
        app.logger.warning("SENTRY_DSN set but sentry-sdk not installed")


def _init_rate_limiter(app):
    """Attach Flask-Limiter for brute-force protection."""
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(
            get_remote_address,
            app=app,
            default_limits=["200 per minute"],
            storage_uri=os.environ.get("REDIS_URL", "memory://"),
        )
        app.extensions["limiter"] = limiter
        return limiter
    except ImportError:
        app.logger.warning("flask-limiter not installed — rate limiting disabled")
        return None


def _register_error_handlers(app):
    """Global error handlers for a polished production experience."""

    @app.errorhandler(400)
    def bad_request(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Bad request"}), 400
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Forbidden"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def rate_limited(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Too many requests"}), 429
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.exception("Internal server error: %s", e)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "CSRF token missing or expired"}), 400
        return render_template("errors/csrf.html", reason=e.description), 400


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

    app.config.from_object(config_cls)
    apply_paths_to_config(app.config, config_name)

    # Structured logging
    _configure_logging(app)

    # Sentry error tracking (only when SENTRY_DSN is set)
    if config_name != "testing":
        _init_sentry(app)

    # Rate limiting
    limiter = _init_rate_limiter(app)

    # Configure database
    models.configure(app.config["DB_PATH"])

    # Initialize database
    models.init_db()

    # Initialize CSRF protection
    csrf.init_app(app)

    # Initialize Flask-Login
    login_manager.init_app(app)
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(hours=8)

    # Global error handlers
    _register_error_handlers(app)

    # Security headers via Flask-Talisman (when available) or manual fallback
    _csp = {
        "default-src": "'self'",
        "base-uri": "'self'",
        "form-action": "'self'",
        "frame-ancestors": "'none'",
        "object-src": "'none'",
        "img-src": "'self' data: blob:",
        "font-src": "'self' https://cdn.jsdelivr.net data:",
        "style-src": "'self' https://cdn.jsdelivr.net https://cdn.datatables.net 'unsafe-inline'",
        "script-src": "'self' https://cdn.jsdelivr.net https://code.jquery.com https://cdn.datatables.net",
        "connect-src": "'self'",
    }

    # On a single-PC install we serve plain HTTP on 127.0.0.1. The bundled
    # Windows launcher sets FNID_LOCAL_HTTP=1. To deploy behind an HTTPS
    # reverse proxy instead, set FNID_LOCAL_HTTP=0 in the environment.
    local_http = os.environ.get("FNID_LOCAL_HTTP", "1") != "0"
    https_mode = not local_http

    try:
        from flask_talisman import Talisman

        Talisman(
            app,
            force_https=https_mode,
            strict_transport_security=https_mode,
            content_security_policy=_csp,
            frame_options="DENY",
            referrer_policy="strict-origin-when-cross-origin",
            permissions_policy={
                "camera": "()",
                "microphone": "()",
                "geolocation": "()",
                "payment": "()",
            },
            session_cookie_secure=https_mode,
        )
        app.logger.info(
            "Flask-Talisman enabled (https=%s)", https_mode
        )
    except ImportError:
        app.logger.info("flask-talisman not installed — using manual security headers")

        @app.after_request
        def set_security_headers(response):
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            csp_str = "; ".join(f"{k} {v}" for k, v in _csp.items())
            response.headers["Content-Security-Policy"] = csp_str
            response.headers["Permissions-Policy"] = (
                "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"
            )
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            if https_mode:
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

    # Apply stricter rate limits to authentication endpoints
    if limiter:
        limiter.limit("10 per minute")(auth_bp)

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
