"""
Intelligence Targets Routes

Manage intelligence target profiles including aliases, linked cases,
modus operandi, threat levels, and parish-based mapping.
"""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import generate_id, get_db, log_audit
from ..rbac import permission_required

bp = Blueprint("targets", __name__, url_prefix="/targets")

THREAT_LEVELS = ["Low", "Medium", "High", "Critical"]
TARGET_STATUSES = ["Active", "Inactive", "Arrested", "Deceased", "Deported"]

PARISHES = [
    "Kingston", "St. Andrew", "St. Thomas", "Portland", "St. Mary",
    "St. Ann", "Trelawny", "St. James", "Hanover", "Westmoreland",
    "St. Elizabeth", "Manchester", "Clarendon", "St. Catherine",
]


@bp.route("/")
@login_required
@permission_required("intel", "read")
def target_list():
    """List all intelligence targets with filters."""
    parish = request.args.get("parish", "").strip()
    threat_level = request.args.get("threat_level", "").strip()
    status = request.args.get("status", "").strip()

    conn = get_db()
    try:
        query = "SELECT * FROM intel_targets WHERE 1=1"
        params = []

        if parish:
            query += " AND parish = ?"
            params.append(parish)
        if threat_level:
            query += " AND threat_level = ?"
            params.append(threat_level)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"
        targets = conn.execute(query, params).fetchall()

        return render_template(
            "targets/list.html",
            targets=targets,
            parishes=PARISHES,
            threat_levels=THREAT_LEVELS,
            statuses=TARGET_STATUSES,
            filter_parish=parish,
            filter_threat_level=threat_level,
            filter_status=status,
        )
    finally:
        conn.close()


@bp.route("/<target_id>")
@login_required
@permission_required("intel", "read")
def target_detail(target_id):
    """View full target profile with linked records."""
    conn = get_db()
    try:
        target = conn.execute(
            "SELECT * FROM intel_targets WHERE target_id = ?", (target_id,)
        ).fetchone()
        if not target:
            flash("Target not found.", "danger")
            return redirect(url_for("targets.target_list"))

        # Parse linked cases
        linked_cases = []
        if target["linked_cases"]:
            case_ids = [c.strip() for c in target["linked_cases"].split(",") if c.strip()]
            for cid in case_ids:
                case = conn.execute(
                    "SELECT case_id, offence_description, case_status FROM cases WHERE case_id = ?",
                    (cid,),
                ).fetchone()
                if case:
                    linked_cases.append(case)

        # Parse linked intel
        linked_intel = []
        if target["linked_intel"]:
            intel_ids = [i.strip() for i in target["linked_intel"].split(",") if i.strip()]
            for iid in intel_ids:
                intel = conn.execute(
                    "SELECT * FROM intel_reports WHERE intel_id = ?",
                    (iid,),
                ).fetchone()
                if intel:
                    linked_intel.append(intel)

        return render_template(
            "targets/detail.html",
            target=target,
            linked_cases=linked_cases,
            linked_intel=linked_intel,
        )
    finally:
        conn.close()


@bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required("intel", "create")
def new_target():
    """Create a new intelligence target profile."""
    if request.method == "POST":
        conn = get_db()
        try:
            target_id = generate_id("TGT", "intel_targets", "target_id")
            target_name = request.form.get("target_name", "").strip()
            aliases = request.form.get("aliases", "").strip() or None
            description = request.form.get("description", "").strip() or None
            parish = request.form.get("parish", "").strip() or None
            area = request.form.get("area", "").strip() or None
            linked_cases = request.form.get("linked_cases", "").strip() or None
            linked_intel = request.form.get("linked_intel", "").strip() or None
            modus_operandi = request.form.get("modus_operandi", "").strip() or None
            threat_level = request.form.get("threat_level", "Medium").strip()
            status = request.form.get("status", "Active").strip()
            notes = request.form.get("notes", "").strip() or None

            if not target_name:
                flash("Target name is required.", "danger")
                return render_template(
                    "targets/form.html",
                    target=request.form,
                    is_edit=False,
                    parishes=PARISHES,
                    threat_levels=THREAT_LEVELS,
                    statuses=TARGET_STATUSES,
                )

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """INSERT INTO intel_targets
                   (target_id, target_name, aliases, description, parish, area,
                    linked_cases, linked_intel, modus_operandi, threat_level,
                    status, notes, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    target_id, target_name, aliases, description, parish, area,
                    linked_cases, linked_intel, modus_operandi, threat_level,
                    status, notes, current_user.badge_number, now, now,
                ),
            )
            conn.commit()

            log_audit(
                "intel_targets", target_id, "CREATE",
                current_user.badge_number, current_user.full_name,
                f"Created target profile: {target_name}",
            )

            flash("Target profile created successfully.", "success")
            return redirect(url_for("targets.target_detail", target_id=target_id))
        finally:
            conn.close()

    return render_template(
        "targets/form.html",
        target=None,
        is_edit=False,
        parishes=PARISHES,
        threat_levels=THREAT_LEVELS,
        statuses=TARGET_STATUSES,
    )


@bp.route("/<target_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("intel", "update")
def edit_target(target_id):
    """Edit an existing target profile."""
    conn = get_db()
    try:
        target = conn.execute(
            "SELECT * FROM intel_targets WHERE target_id = ?", (target_id,)
        ).fetchone()
        if not target:
            flash("Target not found.", "danger")
            return redirect(url_for("targets.target_list"))

        if request.method == "POST":
            target_name = request.form.get("target_name", "").strip()
            aliases = request.form.get("aliases", "").strip() or None
            description = request.form.get("description", "").strip() or None
            parish = request.form.get("parish", "").strip() or None
            area = request.form.get("area", "").strip() or None
            linked_cases = request.form.get("linked_cases", "").strip() or None
            linked_intel = request.form.get("linked_intel", "").strip() or None
            modus_operandi = request.form.get("modus_operandi", "").strip() or None
            threat_level = request.form.get("threat_level", "Medium").strip()
            status = request.form.get("status", "Active").strip()
            notes = request.form.get("notes", "").strip() or None

            if not target_name:
                flash("Target name is required.", "danger")
                return render_template(
                    "targets/form.html",
                    target=request.form,
                    is_edit=True,
                    target_id=target_id,
                    parishes=PARISHES,
                    threat_levels=THREAT_LEVELS,
                    statuses=TARGET_STATUSES,
                )

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """UPDATE intel_targets SET
                   target_name=?, aliases=?, description=?, parish=?, area=?,
                   linked_cases=?, linked_intel=?, modus_operandi=?, threat_level=?,
                   status=?, notes=?, updated_at=?
                   WHERE target_id=?""",
                (
                    target_name, aliases, description, parish, area,
                    linked_cases, linked_intel, modus_operandi, threat_level,
                    status, notes, now, target_id,
                ),
            )
            conn.commit()

            log_audit(
                "intel_targets", target_id, "UPDATE",
                current_user.badge_number, current_user.full_name,
                f"Updated target profile: {target_name}",
            )

            flash("Target profile updated successfully.", "success")
            return redirect(url_for("targets.target_detail", target_id=target_id))

        return render_template(
            "targets/form.html",
            target=target,
            is_edit=True,
            target_id=target_id,
            parishes=PARISHES,
            threat_levels=THREAT_LEVELS,
            statuses=TARGET_STATUSES,
        )
    finally:
        conn.close()


@bp.route("/map")
@login_required
@permission_required("intel", "read")
def target_map():
    """Parish summary showing target counts and threat levels."""
    conn = get_db()
    try:
        parish_data = conn.execute(
            """SELECT parish,
                      COUNT(*) as total,
                      SUM(CASE WHEN threat_level = 'Critical' THEN 1 ELSE 0 END) as critical,
                      SUM(CASE WHEN threat_level = 'High' THEN 1 ELSE 0 END) as high,
                      SUM(CASE WHEN threat_level = 'Medium' THEN 1 ELSE 0 END) as medium,
                      SUM(CASE WHEN threat_level = 'Low' THEN 1 ELSE 0 END) as low,
                      SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active
               FROM intel_targets
               WHERE parish IS NOT NULL AND parish != ''
               GROUP BY parish
               ORDER BY total DESC"""
        ).fetchall()

        return render_template(
            "targets/map.html",
            parish_data=parish_data,
            parishes=PARISHES,
        )
    finally:
        conn.close()
