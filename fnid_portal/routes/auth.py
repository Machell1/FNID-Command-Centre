"""Authentication routes — password-based with Flask-Login."""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import generate_password_hash

from ..auth import User, set_password, validate_password_strength
from ..constants import FNID_SECTIONS, JCF_RANKS
from ..models import get_db, get_setting, log_audit

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        badge = request.form.get("badge_number", "").strip()
        password = request.form.get("password", "").strip()

        if not badge:
            flash("Badge number is required.", "danger")
            return redirect(url_for("auth.login"))

        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM officers WHERE badge_number = ?", (badge,)
            ).fetchone()

            allow_legacy = get_setting("allow_legacy_login", "false") == "true"
            ip_addr = request.remote_addr or "unknown"

            if row:
                user = User.from_row(row)

                # Check if account is active
                if not user.is_active:
                    flash("Account is deactivated. Contact your administrator.", "danger")
                    log_audit("officers", badge, "LOGIN_BLOCKED", badge, "",
                              f"Deactivated account login attempt from {ip_addr}")
                    return redirect(url_for("auth.login"))

                # Check if account is locked
                if user.is_locked():
                    flash("Account locked. Contact administrator or wait 30 minutes.", "danger")
                    log_audit("officers", badge, "LOGIN_BLOCKED_LOCKED", badge, "",
                              f"Locked account login attempt from {ip_addr}")
                    return redirect(url_for("auth.login"))

                # Password-based auth
                if user.has_password():
                    if not password:
                        flash("Password is required.", "danger")
                        return redirect(url_for("auth.login"))
                    if not user.check_password(password):
                        # Increment failed attempts
                        new_attempts = (row["failed_attempts"] or 0) + 1
                        if new_attempts >= 5:
                            conn.execute("""
                                UPDATE officers SET failed_attempts = ?,
                                    locked_at = ? WHERE badge_number = ?
                            """, (new_attempts, datetime.now().isoformat(), badge))
                            conn.commit()
                            log_audit("officers", badge, "ACCOUNT_LOCKED", badge, "",
                                      f"Account locked after {new_attempts} failed attempts from {ip_addr}")
                            flash("Account locked due to too many failed attempts.", "danger")
                        else:
                            conn.execute("""
                                UPDATE officers SET failed_attempts = ?
                                WHERE badge_number = ?
                            """, (new_attempts, badge))
                            conn.commit()
                            log_audit("officers", badge, "LOGIN_FAILED", badge, "",
                                      f"Failed login attempt from {ip_addr}")
                            flash("Invalid credentials.", "danger")
                        return redirect(url_for("auth.login"))

                    # Reset failed attempts on success
                    conn.execute("""
                        UPDATE officers SET failed_attempts = 0, locked_at = NULL,
                            last_login = ? WHERE badge_number = ?
                    """, (datetime.now().isoformat(), badge))
                    conn.commit()
                elif allow_legacy:
                    # Legacy: badge-only login (no password set)
                    conn.execute("""
                        UPDATE officers SET last_login = ? WHERE badge_number = ?
                    """, (datetime.now().isoformat(), badge))
                    conn.commit()
                else:
                    flash("Password required. Contact admin to set one.", "danger")
                    return redirect(url_for("auth.login"))

                # Check verification status
                if not user.is_verified():
                    login_user(user)
                    session["officer_badge"] = badge
                    session["officer_name"] = user.full_name
                    return redirect(url_for("auth.pending_verification"))

                login_user(user)

                # Log session
                conn.execute("""
                    INSERT INTO user_sessions (badge_number, ip_address, user_agent)
                    VALUES (?, ?, ?)
                """, (badge, ip_addr, request.user_agent.string[:200] if request.user_agent else ""))
                conn.commit()

                # Set session values for template compatibility
                session["officer_badge"] = badge
                session["officer_name"] = user.full_name
                session["officer_rank"] = user.rank
                session["officer_section"] = user.section
                session["officer_role"] = user.role

                log_audit("officers", badge, "LOGIN", badge, user.full_name,
                          f"Login from {ip_addr}")
                flash(f"Welcome, {user.rank} {user.full_name}.", "success")

                # Check if password change required
                if user.must_change_password:
                    flash("You must change your password.", "warning")
                    return redirect(url_for("auth.change_password"))

                # Route by role after login
                single_unit = user.get_single_unit()
                if single_unit:
                    return redirect(url_for("units.unit_home", unit=single_unit))
                # Regular users go to user dashboard (via main.home)
                return redirect(url_for("main.home"))
            else:
                # Auto-account creation removed for security
                log_audit("officers", badge, "LOGIN_UNKNOWN_BADGE", "", "",
                          f"Unknown badge login attempt from {ip_addr}")
                flash("Account not found. Contact administrator.", "danger")
                return redirect(url_for("auth.login"))
        finally:
            conn.close()

    allow_legacy = get_setting("allow_legacy_login", "false") == "true"
    return render_template("login.html",
                         ranks=JCF_RANKS,
                         sections=FNID_SECTIONS,
                         allow_legacy=allow_legacy)


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Activate account — officers claim their pre-seeded roster account
    by verifying their JCF email and setting a unique password."""
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        ip_addr = request.remote_addr or "unknown"

        # Require JCF webmail email
        if not email:
            flash("A valid JCF email address is required.", "danger")
            return redirect(url_for("auth.register"))
        if not email.endswith("@jcf.gov.jm"):
            flash("Only JCF webmail addresses (@jcf.gov.jm) are accepted.", "danger")
            return redirect(url_for("auth.register"))

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register"))

        conn = get_db()
        try:
            # Look up the officer by their roster email
            row = conn.execute(
                "SELECT * FROM officers WHERE email = ?", (email,)
            ).fetchone()

            if not row:
                log_audit("officers", email, "REGISTER_UNKNOWN_EMAIL", "", "",
                          f"Unrecognised email registration attempt from {ip_addr}")
                flash("Email not found on the authorised roster. "
                      "Only FNID Area 3 personnel may register.", "danger")
                return redirect(url_for("auth.register"))

            badge = row["badge_number"]
            name = row["full_name"]

            # Check if already activated (must_change_password = 0 means already set)
            if not row["must_change_password"]:
                flash("This account has already been activated. Please sign in.", "info")
                return redirect(url_for("auth.login"))

            # Validate password strength
            is_valid, err_msg = validate_password_strength(password, badge, name)
            if not is_valid:
                flash(err_msg, "danger")
                return redirect(url_for("auth.register"))

            # Activate the account with the officer's chosen password
            conn.execute("""
                UPDATE officers SET password_hash = ?, must_change_password = 0,
                    verification_status = 'active'
                WHERE badge_number = ?
            """, (generate_password_hash(password), badge))
            conn.commit()

            log_audit("officers", badge, "ACCOUNT_ACTIVATED", badge, name,
                      f"Account activated via email verification from {ip_addr}")
            flash(f"Account activated for {row['rank']} {name}. "
                  f"Your badge number is {badge}. Please sign in.", "success")
            return redirect(url_for("auth.login"))
        finally:
            conn.close()

    return render_template("register.html", ranks=JCF_RANKS, sections=FNID_SECTIONS)


@bp.route("/pending-verification")
@login_required
def pending_verification():
    """Show pending verification status page."""
    if current_user.is_verified():
        return redirect(url_for("main.home"))
    return render_template("pending_verification.html")


@bp.route("/logout")
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
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change current user's password."""
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")

        if new_pw != confirm_pw:
            flash("New passwords do not match.", "danger")
            return redirect(url_for("auth.change_password"))

        # Validate password strength
        is_valid, err_msg = validate_password_strength(
            new_pw, current_user.badge_number, current_user.full_name
        )
        if not is_valid:
            flash(err_msg, "danger")
            return redirect(url_for("auth.change_password"))

        # If user has an existing password, verify it
        if current_user.has_password() and not current_user.must_change_password:
            if not current_user.check_password(current_pw):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("auth.change_password"))

        set_password(current_user.badge_number, new_pw)
        ip_addr = request.remote_addr or "unknown"
        log_audit("officers", current_user.badge_number, "PASSWORD_CHANGE",
                 current_user.badge_number, current_user.full_name,
                 f"Password changed from {ip_addr}")
        flash("Password changed successfully.", "success")
        return redirect(url_for("main.home"))

    return render_template("change_password.html")
