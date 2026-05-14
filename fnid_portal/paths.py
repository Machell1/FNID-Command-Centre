"""
Resolve user-data paths for the FNID Command Centre.

When the app runs from the installed Windows build, all user-writable data
must live outside Program Files (which is read-only for non-admins). This
module is the single place that decides where the database, uploads, exports,
and runtime config live.

Resolution order:
1. Environment overrides (FNID_DATA_DIR, FNID_DB_PATH, etc.) — highest priority.
2. %LOCALAPPDATA%\\FNID Command Centre on Windows.
3. ~/.local/share/fnid-command-centre on POSIX (for tests/dev on Linux).
4. <repo>/fnid_portal/data — fallback when running from a source checkout.

Call resolve_data_dir() once at startup; everything else is derived from it.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "FNID Command Centre"


def _is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def _windows_data_dir() -> Path | None:
    if os.name != "nt":
        return None
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        # Fallback if LOCALAPPDATA is missing (rare): use %APPDATA% or home.
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / APP_NAME


def _posix_data_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "fnid-command-centre"
    return Path.home() / ".local" / "share" / "fnid-command-centre"


def _repo_default() -> Path:
    """The legacy in-repo data directory — kept for source-checkout dev."""
    return Path(__file__).resolve().parent / "data"


def resolve_data_dir() -> Path:
    """Return the directory where DB / uploads / exports / logs live."""
    override = os.environ.get("FNID_DATA_DIR")
    if override:
        return Path(override)

    if _is_frozen():
        # When bundled, never write to the install dir.
        return _windows_data_dir() or _posix_data_dir()

    if os.name == "nt":
        # When running from source on Windows, prefer LOCALAPPDATA so that
        # uninstall/clean reinstall leaves user data alone. Tests override via
        # FNID_DATA_DIR.
        if os.environ.get("FNID_USE_REPO_DATA"):
            return _repo_default()
        return _windows_data_dir() or _repo_default()

    return _posix_data_dir() if not os.environ.get("FNID_USE_REPO_DATA") else _repo_default()


def ensure_data_dir() -> Path:
    """Create the data directory tree and return its root."""
    root = resolve_data_dir()
    (root / "uploads").mkdir(parents=True, exist_ok=True)
    (root / "exports").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    return root


def db_path() -> str:
    """Absolute path to the SQLite database file."""
    override = os.environ.get("FNID_DB_PATH")
    if override:
        return override
    return str(resolve_data_dir() / "fnid.db")


def uploads_dir() -> str:
    return os.environ.get("FNID_UPLOAD_DIR") or str(resolve_data_dir() / "uploads")


def exports_dir() -> str:
    return os.environ.get("FNID_EXPORT_DIR") or str(resolve_data_dir() / "exports")


def logs_dir() -> str:
    return os.environ.get("FNID_LOG_DIR") or str(resolve_data_dir() / "logs")


def secret_key_path() -> str:
    """File holding the persistent Flask secret key."""
    return str(resolve_data_dir() / ".secret_key")


def load_or_create_secret_key() -> str:
    """Return the persistent SECRET_KEY, generating one if needed.

    Priority: FNID_SECRET_KEY env var > .secret_key file in data dir.
    """
    env_key = os.environ.get("FNID_SECRET_KEY")
    if env_key:
        return env_key

    path = Path(secret_key_path())
    if path.exists():
        key = path.read_text(encoding="utf-8").strip()
        if key:
            return key

    import secrets
    key = secrets.token_hex(32)
    ensure_data_dir()
    path.write_text(key, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key
