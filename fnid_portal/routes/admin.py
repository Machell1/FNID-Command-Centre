"""
Admin Routes

System settings, user management, backups, and audit log viewing.
Restricted to admin and DCO roles.
"""

import os
import shutil
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from ..models import get_db, log_audit
from ..rbac import role_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@login_required
@role_required("admin", "dco")
def admin_dashboard():
    """Admin dashboard overview."""
    conn = get_db()
    try:
        stats = {
            "officers": conn.execute("SELECT COUNT(*) FROM officers WHERE is_active = 1").fetchone()[0],
            "cases": conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
            "active_alerts": conn.execute("SELECT COUNT(*) FROM alerts WHERE is_dismissed = 0").fetchone()[0],
            "audit_entries": conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0],
        }
        recent_audit = conn.execute("""
            SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 20
        """).fetchall()

        return render_template("admin/dashboard.html",
                             stats=stats, recent_audit=recent_audit)
    finally:
        conn.close()


@bp.route("/settings", methods=["GET", "POST"])
@login_required
@role_required("admin", "dco")
def settings():
    """View and edit system settings."""
    conn = get_db()
    try:
        if request.method == "POST":
            for key in request.form:
                if key.startswith("setting_"):
                    setting_key = key[8:]  # Remove "setting_" prefix
                    value = request.form.get(key, "")
                    conn.execute("""
                        UPDATE system_settings SET value = ?,
                            updated_by = ?, updated_at = datetime('now')
                        WHERE key = ?
                    """, (value, current_user.badge_number, setting_key))

            conn.commit()
            log_audit("system_settings", "bulk", "UPDATE",
                     current_user.badge_number, current_user.full_name)
            flash("Settings updated.", "success")
            return redirect(url_for("admin.settings"))

        settings_data = conn.execute("""
            SELECT * FROM system_settings ORDER BY category, key
        """).fetchall()

        # Group by category
        categories = {}
        for s in settings_data:
            cat = s["category"]
            categories.setdefault(cat, []).append(s)

        return render_template("admin/settings.html", categories=categories)
    finally:
        conn.close()


@bp.route("/users")
@login_required
@role_required("admin", "dco")
def users():
    """User management list."""
    conn = get_db()
    try:
        officers = conn.execute("""
            SELECT * FROM officers ORDER BY is_active DESC, full_name
        """).fetchall()

        return render_template("admin/users.html", officers=officers)
    finally:
        conn.close()


@bp.route("/users/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def new_user():
    """Create a new user account."""
    if request.method == "POST":
        from ..auth import create_officer, validate_password_strength
        from ..constants import FNID_SECTIONS, JCF_RANKS
        from ..rbac import ROLES

        badge = request.form.get("badge_number", "").strip()
        name = request.form.get("full_name", "").strip()
        rank = request.form.get("rank", "").strip()
        section = request.form.get("section", "").strip()
        role = request.form.get("role", "io")
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        email = request.form.get("email", "").strip()

        if not badge or not name or not rank:
            flash("Badge, name, and rank are required.", "danger")
            return redirect(url_for("admin.new_user"))
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("admin.new_user"))
        if password:
            valid, message = validate_password_strength(password, badge, name)
            if not valid:
                flash(message, "danger")
                return redirect(url_for("admin.new_user"))

        try:
            create_officer(badge, name, rank, section, role,
                         password=password or None, email=email or None)
            log_audit("officers", badge, "CREATE",
                     current_user.badge_number, current_user.full_name,
                     f"Created user {name} with role {role}")
            flash(f"User {name} ({badge}) created.", "success")
            return redirect(url_for("admin.users"))
        except Exception:
            flash("An error occurred creating the user. Please try again.", "danger")

    from ..constants import FNID_SECTIONS, JCF_RANKS
    from ..rbac import ROLES
    return render_template("admin/user_form.html",
                         ranks=JCF_RANKS, sections=FNID_SECTIONS,
                         roles=ROLES, officer=None, is_new=True)


@bp.route("/users/<badge>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_user(badge):
    """Edit an existing user."""
    conn = get_db()
    try:
        officer = conn.execute(
            "SELECT * FROM officers WHERE badge_number = ?", (badge,)
        ).fetchone()
        if not officer:
            flash("User not found.", "danger")
            return redirect(url_for("admin.users"))

        if request.method == "POST":
            conn.execute("""
                UPDATE officers SET
                    full_name = ?, rank = ?, section = ?, role = ?,
                    email = ?, is_active = ?, unit_access = ?
                WHERE badge_number = ?
            """, (
                request.form.get("full_name", officer["full_name"]),
                request.form.get("rank", officer["rank"]),
                request.form.get("section", officer["section"]),
                request.form.get("role", "io"),
                request.form.get("email", ""),
                1 if request.form.get("is_active") else 0,
                request.form.get("unit_access", "all"),
                badge,
            ))
            conn.commit()
            log_audit("officers", badge, "UPDATE",
                     current_user.badge_number, current_user.full_name)
            flash("User updated.", "success")
            return redirect(url_for("admin.users"))

        from ..constants import FNID_SECTIONS, JCF_RANKS
        from ..rbac import ROLES
        return render_template("admin/user_form.html",
                             ranks=JCF_RANKS, sections=FNID_SECTIONS,
                             roles=ROLES, officer=officer, is_new=False)
    finally:
        conn.close()


@bp.route("/users/<badge>/reset-password", methods=["POST"])
@login_required
@role_required("admin")
def reset_password(badge):
    """Reset a user's password."""
    new_password = request.form.get("new_password", "").strip()
    confirm_password = request.form.get("confirm_new_password", "").strip()
    if not new_password:
        flash("Password cannot be empty.", "danger")
        return redirect(url_for("admin.edit_user", badge=badge))
    if new_password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("admin.edit_user", badge=badge))

    from ..auth import validate_password_strength

    valid, message = validate_password_strength(new_password, badge)
    if not valid:
        flash(message, "danger")
        return redirect(url_for("admin.edit_user", badge=badge))

    conn = get_db()
    try:
        conn.execute("""
            UPDATE officers SET password_hash = ?, must_change_password = 1
            WHERE badge_number = ?
        """, (generate_password_hash(new_password), badge))
        conn.commit()
        log_audit("officers", badge, "PASSWORD_RESET",
                 current_user.badge_number, current_user.full_name)
        flash("Password reset. User must change on next login.", "success")
    finally:
        conn.close()

    return redirect(url_for("admin.edit_user", badge=badge))


@bp.route("/backup", methods=["GET", "POST"])
@login_required
@role_required("admin")
def backup():
    """Database backup controls."""
    backup_dir = os.path.join(
        current_app.config.get("UPLOAD_DIR", "data"), "..", "backups"
    )
    backup_dir = os.path.normpath(backup_dir)
    os.makedirs(backup_dir, exist_ok=True)

    if request.method == "POST":
        from ..config import Config
        db_path = current_app.config.get("DB_PATH") or Config.DB_PATH

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"fnid_backup_{timestamp}.db")

        try:
            shutil.copy2(db_path, backup_path)
            log_audit("system", "backup", "BACKUP",
                     current_user.badge_number, current_user.full_name,
                     f"Created backup: {backup_path}")
            flash(f"Backup created: fnid_backup_{timestamp}.db", "success")
        except Exception as e:
            flash(f"Backup failed: {e}", "danger")

        return redirect(url_for("admin.backup"))

    # List existing backups
    backups = []
    if os.path.exists(backup_dir):
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith(".db"):
                fpath = os.path.join(backup_dir, f)
                backups.append({
                    "filename": f,
                    "size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 2),
                    "created": datetime.fromtimestamp(
                        os.path.getmtime(fpath)
                    ).strftime("%Y-%m-%d %H:%M"),
                })

    return render_template("admin/backup.html", backups=backups)


@bp.route("/audit-log")
@login_required
@role_required("admin", "dco", "ddi")
def audit_log():
    """Searchable audit log viewer."""
    conn = get_db()
    try:
        table_filter = request.args.get("table", "") or request.args.get("table_name", "")
        action_filter = request.args.get("action", "")
        officer_filter = request.args.get("officer", "")
        limit = min(int(request.args.get("limit", 100)), 500)

        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []

        if table_filter:
            query += " AND table_name = ?"
            params.append(table_filter)
        if action_filter:
            query += " AND action = ?"
            params.append(action_filter)
        if officer_filter:
            query += " AND (officer_badge LIKE ? OR officer_name LIKE ?)"
            params.extend([f"%{officer_filter}%", f"%{officer_filter}%"])

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        logs = conn.execute(query, params).fetchall()

        # Get distinct values for filter dropdowns
        tables = conn.execute(
            "SELECT DISTINCT table_name FROM audit_log ORDER BY table_name"
        ).fetchall()
        actions = conn.execute(
            "SELECT DISTINCT action FROM audit_log ORDER BY action"
        ).fetchall()

        return render_template("admin/audit_log.html",
                             logs=logs, tables=tables, actions=actions,
                             table_filter=table_filter,
                             action_filter=action_filter,
                             officer_filter=officer_filter)
    finally:
        conn.close()


# ── Maintenance Dashboard (Tier 1 Admin) ─────────────────────────

@bp.route("/maintenance")
@login_required
@role_required("admin")
def maintenance():
    """Tier 1 maintenance dashboard."""
    admin_tier = getattr(current_user, "admin_tier", None)
    if admin_tier is None or admin_tier > 1:
        flash("Tier 1 access required.", "danger")
        return redirect(url_for("admin.admin_dashboard"))

    conn = get_db()
    try:
        pending_users = conn.execute(
            "SELECT * FROM officers WHERE verification_status = 'pending' ORDER BY registered_at DESC"
        ).fetchall()
        locked_users = conn.execute(
            "SELECT * FROM officers WHERE locked_at IS NOT NULL ORDER BY locked_at DESC"
        ).fetchall()
        db_path = current_app.config.get("DB_PATH", "")
        db_size = 0
        if db_path and os.path.exists(db_path):
            db_size = round(os.path.getsize(db_path) / (1024 * 1024), 2)

        stats = {
            "total_officers": conn.execute("SELECT COUNT(*) FROM officers").fetchone()[0],
            "active_officers": conn.execute("SELECT COUNT(*) FROM officers WHERE is_active = 1").fetchone()[0],
            "pending_count": len(pending_users),
            "locked_count": len(locked_users),
            "total_cases": conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
            "db_size_mb": db_size,
        }

        return render_template("admin/maintenance.html",
                             stats=stats, pending_users=pending_users,
                             locked_users=locked_users)
    finally:
        conn.close()


@bp.route("/maintenance/approve-user/<badge>", methods=["POST"])
@login_required
@role_required("admin")
def approve_user(badge):
    """Manually approve a pending user."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE officers SET verification_status = 'active' WHERE badge_number = ?",
            (badge,)
        )
        conn.commit()
        log_audit("officers", badge, "VERIFICATION_APPROVED",
                 current_user.badge_number, current_user.full_name)
        flash(f"User {badge} approved.", "success")
    finally:
        conn.close()
    return redirect(url_for("admin.maintenance"))


@bp.route("/maintenance/deactivate-user/<badge>", methods=["POST"])
@login_required
@role_required("admin")
def deactivate_user(badge):
    """Deactivate a user account."""
    if badge == current_user.badge_number:
        flash("Cannot deactivate your own account.", "danger")
        return redirect(url_for("admin.maintenance"))
    conn = get_db()
    try:
        conn.execute(
            "UPDATE officers SET is_active = 0 WHERE badge_number = ?",
            (badge,)
        )
        conn.commit()
        log_audit("officers", badge, "DEACTIVATED",
                 current_user.badge_number, current_user.full_name)
        flash(f"User {badge} deactivated.", "success")
    finally:
        conn.close()
    return redirect(url_for("admin.maintenance"))


@bp.route("/maintenance/unlock-user/<badge>", methods=["POST"])
@login_required
@role_required("admin")
def unlock_user(badge):
    """Unlock a locked user account."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE officers SET locked_at = NULL, failed_attempts = 0 WHERE badge_number = ?",
            (badge,)
        )
        conn.commit()
        log_audit("officers", badge, "ACCOUNT_UNLOCKED",
                 current_user.badge_number, current_user.full_name)
        flash(f"User {badge} unlocked.", "success")
    finally:
        conn.close()
    return redirect(url_for("admin.maintenance"))


@bp.route("/maintenance/vacuum", methods=["POST"])
@login_required
@role_required("admin")
def vacuum_db():
    """Run SQLite VACUUM to optimize database."""
    conn = get_db()
    try:
        conn.execute("VACUUM")
        log_audit("system", "database", "VACUUM",
                 current_user.badge_number, current_user.full_name)
        flash("Database optimized.", "success")
    finally:
        conn.close()
    return redirect(url_for("admin.maintenance"))
