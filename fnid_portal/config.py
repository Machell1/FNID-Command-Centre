"""
FNID Application Configuration.

Path defaults come from `paths.py`. Flask config attributes that depend on
the resolved data directory are filled in by `apply_paths_to_config()` from
the app factory, after the config class has been loaded.
"""
import os
from datetime import timedelta

from . import paths


class Config:
    """Base configuration shared by all environments."""

    # Static defaults — paths are filled in by apply_paths_to_config().
    SECRET_KEY = None
    DB_PATH = None
    UPLOAD_DIR = None
    EXPORT_DIR = None
    LOG_DIR = None

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB upload limit

    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Account lockout
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30

    # Password policy
    MIN_PASSWORD_LENGTH = 10


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    """Installed Windows build. Local HTTP on 127.0.0.1 by default."""

    DEBUG = False
    SESSION_COOKIE_SECURE = False


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SECRET_KEY = "test-secret-key-not-for-production"
    WTF_CSRF_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def apply_paths_to_config(app_config, environment: str) -> None:
    """Resolve and write all path-dependent config values.

    Called from the app factory once the config object has been loaded.
    """
    paths.ensure_data_dir()
    if environment != "testing" or not app_config.get("SECRET_KEY"):
        app_config["SECRET_KEY"] = paths.load_or_create_secret_key()
    app_config["DB_PATH"] = paths.db_path()
    app_config["UPLOAD_DIR"] = paths.uploads_dir()
    app_config["EXPORT_DIR"] = paths.exports_dir()
    app_config["LOG_DIR"] = paths.logs_dir()
