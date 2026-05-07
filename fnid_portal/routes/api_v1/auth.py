"""JSON API authentication endpoints for the React SPA."""

from datetime import datetime

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import generate_password_hash

from ...auth import User, set_password, validate_password_strength
from ...constants import FNID_SECTIONS, JCF_RANKS
from ...models import get_db, get_setting, log_audit
from ...rbac import PERMISSIONS

bp = Blueprint("api_auth", __name__, url_prefix="/api/v1/auth")


def _user_json(user):
    """Build JSON-safe user profile dict with permissions."""
    permissions = {}
    role = getattr(user, "role", "viewer")
    for resource, actions in PERMISSIONS.items():
        allowed = {}
        for action, roles in actions.items():
            if role == "admin" or role in roles:
                allowed[action] = True
        if allowed:
            permissions[resource] = allowed

    return {
        "badge_number": user.badge_number,
        "full_name": user.full_name,
        "rank": user.rank,
        "section": user.section,
        "role": user.role,
        "unit_access": user.unit_access,
        "admin_tier": user.admin_tier,
        "permissions": permissions,
    }


@bp.route("/me")
def me():
    """Return current authenticated user info or 401."""
    if not current_user.is_authenticated:
        return jsonify({"authenticated": False}), 401
    data = _user_json(current_user)
    data["authenticated"] = True
    return jsonify(data)


@bp.route("/login", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return jsonify({"ok": True, "user": _user_json(current_user)})

    data = request.get_json(silent=True) or {}
    badge = data.get("badge_number", "").strip()
    password = data.get("password", "").strip()

    if not badge:
        return jsonify({"ok": False, "error": "Badge number is required."}), 400

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM officers WHERE badge_number = ?", (badge,)
        ).fetchone()

        allow_legacy = get_setting("allow_legacy_login", "false") == "true"
        ip_addr = request.remote_addr or "unknown"

        if not row:
            log_audit("officers", badge, "LOGIN_UNKNOWN_BADGE", "", "",
                      f"Unknown badge login attempt from {ip_addr}")
            return jsonify({"ok": False, "error": "Account not found. Contact administrator."}), 401

        user = User.from_row(row)

        if not user.is_active:
            log_audit("officers", badge, "LOGIN_BLOCKED", badge, "",
                      f"Deactivated account login attempt from {ip_addr}")
            return jsonify({"ok": False, "error": "Account is deactivated. Contact your administrator."}), 403

        if user.is_locked():
            log_audit("officers", badge, "LOGIN_BLOCKED_LOCKED", badge, "",
                      f"Locked account login attempt from {ip_addr}")
            return jsonify({"ok": False, "error": "Account locked. Contact administrator or wait 30 minutes."}), 403

        if user.has_password():
            if not password:
                return jsonify({"ok": False, "error": "Password is required."}), 400
            if not user.check_password(password):
                new_attempts = (row["failed_attempts"] or 0) + 1
                if new_attempts >= 5:
                    conn.execute("""
                        UPDATE officers SET failed_attempts = ?,
                            locked_at = ? WHERE badge_number = ?
                    """, (new_attempts, datetime.now().isoformat(), badge))
                    conn.commit()
                    log_audit("officers", badge, "ACCOUNT_LOCKED", badge, "",
                              f"Account locked after {new_attempts} failed attempts from {ip_addr}")
                    return jsonify({"ok": False, "error": "Account locked due to too many failed attempts."}), 403
                else:
                    conn.execute("""
                        UPDATE officers SET failed_attempts = ?
                        WHERE badge_number = ?
                    """, (new_attempts, badge))
                    conn.commit()
                    log_audit("officers", badge, "LOGIN_FAILED", badge, "",
                              f"Failed login attempt from {ip_addr}")
                    return jsonify({"ok": False, "error": "Invalid credentials."}), 401

            conn.execute("""
                UPDATE officers SET failed_attempts = 0, locked_at = NULL,
                    last_login = ? WHERE badge_number = ?
            """, (datetime.now().isoformat(), badge))
            conn.commit()
        elif allow_legacy:
            conn.execute("""
                UPDATE officers SET last_login = ? WHERE badge_number = ?
            """, (datetime.now().isoformat(), badge))
            conn.commit()
        else:
            return jsonify({"ok": False, "error": "Password required. Contact admin to set one."}), 400

        if not user.is_verified():
            login_user(user)
            session["officer_badge"] = badge
            session["officer_name"] = user.full_name
            return jsonify({
                "ok": True,
                "redirect": "pending_verification",
                "user": _user_json(user),
            })

        login_user(user)

        conn.execute("""
            INSERT INTO user_sessions (badge_number, ip_address, user_agent)
            VALUES (?, ?, ?)
        """, (badge, ip_addr, request.user_agent.string[:200] if request.user_agent else ""))
        conn.commit()

        session["officer_badge"] = badge
        session["officer_name"] = user.full_name
        session["officer_rank"] = user.rank
        session["officer_section"] = user.section
        session["officer_role"] = user.role

        log_audit("officers", badge, "LOGIN", badge, user.full_name,
                  f"Login from {ip_addr}")

        result = {"ok": True, "user": _user_json(user)}
        if user.must_change_password:
            result["redirect"] = "change_password"
        return jsonify(result)
    finally:
        conn.close()


@bp.route("/logout", methods=["POST"])
def logout():
    badge = session.get("officer_badge", "")
    name = session.get("officer_name", "")
    ip_addr = request.remote_addr or "unknown"
    if badge:
        log_audit("officers", badge, "LOGOUT", badge, name,
                  f"Logout from {ip_addr}")
        conn = get_db()
        try:
            conn.execute("""
                UPDATE user_sessions SET logout_at = datetime('now')
                WHERE badge_number = ? AND logout_at IS NULL
            """, (badge,))
            conn.commit()
        finally:
            conn.close()
    logout_user()
    session.clear()
    return jsonify({"ok": True})


@bp.route("/register", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return jsonify({"ok": False, "error": "Already logged in."}), 400

    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    confirm = data.get("confirm_password", "")
    ip_addr = request.remote_addr or "unknown"

    if not email:
        return jsonify({"ok": False, "error": "A valid JCF email address is required."}), 400
    if not email.endswith("@jcf.gov.jm"):
        return jsonify({"ok": False, "error": "Only JCF webmail addresses (@jcf.gov.jm) are accepted."}), 400
    if password != confirm:
        return jsonify({"ok": False, "error": "Passwords do not match."}), 400

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM officers WHERE email = ?", (email,)
        ).fetchone()

        if not row:
            log_audit("officers", email, "REGISTER_UNKNOWN_EMAIL", "", "",
                      f"Unrecognised email registration attempt from {ip_addr}")
            return jsonify({
                "ok": False,
                "error": (
                    "Email not found on the authorised roster. "
                    "Only FNID Area 3 personnel may register."
                ),
            }), 404

        badge = row["badge_number"]
        name = row["full_name"]

        if not row["must_change_password"]:
            return jsonify({"ok": False, "error": "This account has already been activated. Please sign in."}), 400

        is_valid, err_msg = validate_password_strength(password, badge, name)
        if not is_valid:
            return jsonify({"ok": False, "error": err_msg}), 400

        conn.execute("""
            UPDATE officers SET password_hash = ?, must_change_password = 0,
                verification_status = 'active'
            WHERE badge_number = ?
        """, (generate_password_hash(password), badge))
        conn.commit()

        log_audit("officers", badge, "ACCOUNT_ACTIVATED", badge, name,
                  f"Account activated via email verification from {ip_addr}")

        return jsonify({
            "ok": True,
            "message": f"Account activated for {row['rank']} {name}. Your badge number is {badge}. Please sign in.",
        })
    finally:
        conn.close()


@bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")
    confirm_pw = data.get("confirm_password", "")

    if new_pw != confirm_pw:
        return jsonify({"ok": False, "error": "New passwords do not match."}), 400

    is_valid, err_msg = validate_password_strength(
        new_pw, current_user.badge_number, current_user.full_name
    )
    if not is_valid:
        return jsonify({"ok": False, "error": err_msg}), 400

    if current_user.has_password() and not current_user.must_change_password:
        if not current_user.check_password(current_pw):
            return jsonify({"ok": False, "error": "Current password is incorrect."}), 400

    set_password(current_user.badge_number, new_pw)
    ip_addr = request.remote_addr or "unknown"
    log_audit("officers", current_user.badge_number, "PASSWORD_CHANGE",
             current_user.badge_number, current_user.full_name,
             f"Password changed from {ip_addr}")
    return jsonify({"ok": True, "message": "Password changed successfully."})


@bp.route("/config")
def auth_config():
    """Return auth configuration needed by the login form."""
    return jsonify({
        "ranks": JCF_RANKS,
        "sections": FNID_SECTIONS,
        "allow_legacy": get_setting("allow_legacy_login", "false") == "true",
    })
