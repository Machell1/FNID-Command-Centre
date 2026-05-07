"""
FNID Role-Based Access Control (RBAC)

Defines roles, permissions, and access control decorators for the
JCF case management system.
"""

from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user

# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------
ROLES = {
    "admin": "System Administrator",
    "dco": "Divisional Crime Officer",
    "ddi": "Divisional Detective Inspector",
    "station_mgr": "Station Manager",
    "supervisor": "Supervisor",
    "registrar": "Registrar",
    "io": "Investigating Officer",
    "plo": "Police Liaison Officer",
    "intel_officer": "Intelligence Officer",
    "transport_officer": "Transport Officer",
    "user": "Regular User",
    "viewer": "Read-Only Viewer",
}

# Role hierarchy — higher roles inherit lower role permissions
ROLE_HIERARCHY = {
    "admin": 100,
    "ddi": 90,
    "dco": 80,
    "station_mgr": 70,
    "supervisor": 65,
    "registrar": 60,
    "intel_officer": 55,
    "io": 50,
    "plo": 40,
    "transport_officer": 35,
    "user": 15,
    "viewer": 10,
}

# Admin tier definitions
ADMIN_TIERS = {
    1: "Tier 1 - Full System Administration",
    2: "Tier 2 - Operational Administration",
    3: "Tier 3 - Unit Administration",
    4: "Tier 4 - View-Only Administration",
}

# ---------------------------------------------------------------------------
# Permission matrix: {resource: {action: set_of_allowed_roles}}
# CONFIGURABLE — adjust per policy when FO 4032 field layouts are confirmed
# ---------------------------------------------------------------------------
PERMISSIONS = {
    "cases": {
        "create": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar", "io", "user"},
        "read": {
            "admin", "dco", "ddi", "station_mgr", "supervisor", "registrar",
            "io", "plo", "intel_officer", "user", "viewer",
        },
        "update": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar", "io", "user"},
        "delete": {"admin", "dco"},
        "assign": {"admin", "dco", "ddi", "station_mgr", "supervisor"},
        "approve": {"admin", "dco", "ddi", "station_mgr", "supervisor"},
        "suspend": {"admin", "dco", "ddi"},
        "close": {"admin", "dco", "ddi", "station_mgr", "supervisor"},
        "reopen": {"admin", "dco", "ddi"},
    },
    "cr_forms": {
        "create": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar", "io", "user"},
        "read": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar", "io", "plo", "user", "viewer"},
        "update": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar", "io", "user"},
        "delete": {"admin", "dco"},
        "approve": {"admin", "dco", "ddi", "station_mgr", "supervisor"},
        "export_pdf": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar", "io", "plo", "user"},
    },
    "intel": {
        "create": {"admin", "dco", "ddi", "intel_officer"},
        "read": {"admin", "dco", "ddi", "intel_officer"},
        "update": {"admin", "dco", "ddi", "intel_officer"},
        "delete": {"admin", "dco"},
        "targets": {"admin", "dco", "ddi", "intel_officer"},
        "link_analysis": {"admin", "dco", "ddi", "intel_officer"},
    },
    "operations": {
        "create": {"admin", "dco", "ddi", "station_mgr", "supervisor", "io", "user"},
        "read": {"admin", "dco", "ddi", "station_mgr", "supervisor", "io", "intel_officer", "user", "viewer"},
        "update": {"admin", "dco", "ddi", "station_mgr", "supervisor", "io", "user"},
        "delete": {"admin", "dco"},
    },
    "seizures": {
        "create": {"admin", "dco", "ddi", "station_mgr", "supervisor", "io", "user"},
        "read": {
            "admin", "dco", "ddi", "station_mgr", "supervisor", "registrar",
            "io", "intel_officer", "plo", "user", "viewer",
        },
        "update": {"admin", "dco", "ddi", "station_mgr", "supervisor", "io", "user"},
        "delete": {"admin", "dco"},
    },
    "arrests": {
        "create": {"admin", "dco", "ddi", "station_mgr", "supervisor", "io", "user"},
        "read": {
            "admin", "dco", "ddi", "station_mgr", "supervisor", "registrar",
            "io", "plo", "user", "viewer",
        },
        "update": {"admin", "dco", "ddi", "station_mgr", "supervisor", "io", "user"},
        "delete": {"admin", "dco"},
    },
    "forensics": {
        "create": {"admin", "dco", "ddi", "registrar", "io", "user"},
        "read": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar", "io", "plo", "user", "viewer"},
        "update": {"admin", "dco", "ddi", "registrar", "io", "user"},
        "delete": {"admin", "dco"},
    },
    "file_movement": {
        "create": {"admin", "dco", "ddi", "registrar", "io"},
        "read": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar", "io", "viewer"},
        "update": {"admin", "dco", "ddi", "registrar"},
        "checkout_original": {"admin", "dco", "registrar"},
        "checkout_working": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar", "io"},
    },
    "mcr": {
        "create": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar"},
        "compile": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar"},
        "read": {
            "admin", "dco", "ddi", "station_mgr", "supervisor", "registrar",
            "io", "intel_officer", "plo", "user", "viewer",
        },
    },
    "admin": {
        "access": {"admin", "dco"},
        "users": {"admin"},
        "settings": {"admin", "dco"},
        "backup": {"admin"},
        "audit_log": {"admin", "dco", "ddi"},
    },
    "witnesses": {
        "read_identity": {"admin", "dco", "ddi", "io"},
        "read_pseudonym": {"admin", "dco", "ddi", "intel_officer", "io"},
    },
    "transport": {
        "create": {"admin", "dco", "transport_officer"},
        "read": {"admin", "dco", "ddi", "station_mgr", "supervisor", "transport_officer", "viewer"},
        "update": {"admin", "dco", "transport_officer"},
    },
    "documents": {
        "upload": {
            "admin", "dco", "ddi", "station_mgr", "supervisor", "registrar",
            "io", "intel_officer", "plo", "transport_officer", "user",
        },
        "read": {
            "admin", "dco", "ddi", "station_mgr", "supervisor", "registrar",
            "io", "intel_officer", "plo", "transport_officer", "user", "viewer",
        },
        "delete": {"admin", "dco"},
    },
    "kpis": {
        "read": {
            "admin", "dco", "ddi", "station_mgr", "supervisor", "registrar",
            "io", "intel_officer", "plo", "transport_officer", "user", "viewer",
        },
        "manage": {"admin"},
    },
    "workflow": {
        "read": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar", "io", "intel_officer"},
        "advance": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar", "io"},
    },
    "assistants": {
        "read": {
            "admin", "dco", "ddi", "station_mgr", "supervisor", "registrar",
            "io", "plo", "intel_officer", "user", "viewer",
        },
        "run": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar", "io", "plo", "user"},
        "approve": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar"},
        "manage": {"admin", "dco"},
        "rollback": {"admin", "dco", "ddi", "station_mgr", "supervisor", "registrar"},
    },
    "maintenance": {
        "access": {"admin"},
    },
}


def can_access(user, resource, action):
    """Check if a user has permission for a specific resource/action.

    Returns True if allowed, False otherwise.
    """
    if user is None or not user.is_authenticated:
        return False

    role = getattr(user, "role", "viewer")

    # Admin always has access
    if role == "admin":
        return True

    resource_perms = PERMISSIONS.get(resource, {})
    action_perms = resource_perms.get(action, set())
    return role in action_perms


def role_required(*roles):
    """Decorator: restrict route to users with one of the specified roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            user_role = getattr(current_user, "role", "viewer")
            if user_role not in roles and user_role != "admin":
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("main.home"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def permission_required(resource, action):
    """Decorator: restrict route based on the permission matrix."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if not can_access(current_user, resource, action):
                flash("You do not have permission to perform this action.", "danger")
                return redirect(url_for("main.home"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_tier_required(max_tier):
    """Decorator: restrict route to admins at or below the specified tier."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            tier = getattr(current_user, "admin_tier", None)
            if tier is None or tier > max_tier:
                flash("Insufficient admin privileges.", "danger")
                return redirect(url_for("main.home"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def verification_required(f):
    """Decorator: block unverified users from accessing a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_verified():
            flash("Your account is pending verification.", "warning")
            return redirect(url_for("auth.pending_verification"))
        return f(*args, **kwargs)
    return decorated_function


def is_supervisor(user):
    """Check if user has a supervisory role."""
    return getattr(user, "role", "viewer") in {
        "admin", "dco", "ddi", "station_mgr", "supervisor"
    }


def can_view_sensitive(user):
    """Check if user can view sensitive witness/source data."""
    return getattr(user, "role", "viewer") in {
        "admin", "dco", "ddi", "intel_officer"
    }
