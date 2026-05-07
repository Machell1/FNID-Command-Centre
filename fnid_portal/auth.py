"""
FNID Authentication - Flask-Login integration with password hashing.

Provides the User model, login manager setup, and password utilities.
"""

import re
from datetime import datetime, timedelta

from flask_login import LoginManager, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .models import get_db

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"
login_manager.login_message = "Please sign in to access this page."
login_manager.session_protection = "strong"


class User(UserMixin):
    """Flask-Login compatible user wrapping the officers table."""

    def __init__(self, badge_number, full_name, rank, section, role="io",
                 password_hash=None, email=None, is_active=True,
                 unit_access="all", must_change_password=False,
                 admin_tier=None, verification_status="active",
                 registered_at=None, locked_at=None, duty_assignment=None):
        self.id = badge_number  # Flask-Login uses .id
        self.badge_number = badge_number
        self.full_name = full_name
        self.rank = rank
        self.section = section
        self.role = role or "io"
        self.password_hash = password_hash
        self.email = email
        self._is_active = is_active
        self.unit_access = unit_access
        self.must_change_password = must_change_password
        self.admin_tier = admin_tier
        self.verification_status = verification_status or "active"
        self.registered_at = registered_at
        self.locked_at = locked_at
        self.duty_assignment = duty_assignment

    @property
    def is_active(self):
        return bool(self._is_active)

    @property
    def is_tier1_admin(self):
        return self.admin_tier is not None and self.admin_tier <= 1

    def is_verified(self):
        """True if verification_status is 'active' or 12h elapsed since registration."""
        if self.verification_status == "active":
            return True
        if self.registered_at:
            try:
                reg_time = datetime.fromisoformat(self.registered_at)
                return datetime.now() - reg_time > timedelta(hours=12)
            except (ValueError, TypeError):
                pass
        return False

    def is_locked(self):
        """True if locked_at is set and less than 30 minutes ago."""
        if not self.locked_at:
            return False
        try:
            lock_time = datetime.fromisoformat(self.locked_at)
            return datetime.now() - lock_time < timedelta(minutes=30)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def from_row(row):
        """Create a User from a sqlite3.Row."""
        if row is None:
            return None
        keys = row.keys()
        return User(
            badge_number=row["badge_number"],
            full_name=row["full_name"],
            rank=row["rank"],
            section=row["section"],
            role=row["role"] if "role" in keys else "io",
            password_hash=row["password_hash"] if "password_hash" in keys else None,
            email=row["email"] if "email" in keys else None,
            is_active=bool(row["is_active"]) if "is_active" in keys else True,
            unit_access=row["unit_access"] if "unit_access" in keys else "all",
            must_change_password=(
                row["must_change_password"]
                if "must_change_password" in keys else False
            ),
            admin_tier=row["admin_tier"] if "admin_tier" in keys else None,
            verification_status=(
                row["verification_status"]
                if "verification_status" in keys else "active"
            ),
            registered_at=row["registered_at"] if "registered_at" in keys else None,
            locked_at=row["locked_at"] if "locked_at" in keys else None,
            duty_assignment=row["duty_assignment"] if "duty_assignment" in keys else None,
        )

    def get_assigned_units(self):
        """Return list of unit keys this user can access."""
        from .constants import UNIT_PORTALS
        if not self.unit_access or self.unit_access == "all":
            return list(UNIT_PORTALS.keys())
        units = [u.strip() for u in self.unit_access.split(",") if u.strip()]
        return [u for u in units if u in UNIT_PORTALS]

    def get_single_unit(self):
        """Return unit key if user has exactly one assigned unit and is non-supervisory, else None."""
        SUPERVISOR_ROLES = {"admin", "dco", "ddi", "station_mgr", "supervisor"}
        if self.role in SUPERVISOR_ROLES:
            return None
        if not self.unit_access or self.unit_access == "all":
            return None
        units = self.get_assigned_units()
        if len(units) == 1:
            return units[0]
        return None

    def check_password(self, password):
        """Verify password against stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def has_password(self):
        """Check if the user has set a password."""
        return bool(self.password_hash)


@login_manager.user_loader
def load_user(badge_number):
    """Flask-Login user loader callback."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM officers WHERE badge_number = ?", (badge_number,)
        ).fetchone()
        return User.from_row(row)
    finally:
        conn.close()


def set_password(badge_number, password):
    """Set (or reset) password for an officer."""
    pw_hash = generate_password_hash(password)
    conn = get_db()
    try:
        conn.execute(
            "UPDATE officers SET password_hash = ?, must_change_password = 0 WHERE badge_number = ?",
            (pw_hash, badge_number),
        )
        # Invalidate all existing sessions
        conn.execute(
            "UPDATE user_sessions SET logout_at = datetime('now') WHERE badge_number = ? AND logout_at IS NULL",
            (badge_number,),
        )
        conn.commit()
    finally:
        conn.close()


def create_officer(badge_number, full_name, rank, section, role="io",
                   password=None, email=None):
    """Create a new officer account."""
    pw_hash = generate_password_hash(password) if password else None
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO officers (badge_number, full_name, rank, section, role,
                                  password_hash, email, must_change_password)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (badge_number, full_name, rank, section, role, pw_hash, email,
              1 if password else 0))
        conn.commit()
    finally:
        conn.close()


def validate_password_strength(password, badge_number=None, full_name=None):
    """Validate password meets FNID security policy.

    Returns (is_valid, error_message) tuple.
    """
    if len(password) < 10:
        return False, "Password must be at least 10 characters."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_+=\[\]\\/'`;~]", password):
        return False, "Password must contain at least one special character."
    if badge_number and password.lower() == badge_number.lower():
        return False, "Password cannot be the same as your badge number."
    if full_name and password.lower() == full_name.lower():
        return False, "Password cannot be the same as your full name."
    return True, ""
