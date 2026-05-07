"""
DCRR Register Routes

Divisional Crime Report Register — the official JCF register of all
reported crimes at the station level.  Provides browsing, creation,
editing, and summary statistics.
"""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..case_numbers import generate_dcrr_number
from ..models import get_db, log_audit
from ..rbac import role_required

bp = Blueprint("dcrr", __name__, url_prefix="/dcrr")

# Roles allowed to create / edit DCRR entries
DCRR_EDIT_ROLES = ("registrar", "dco", "ddi", "admin", "station_mgr")


# ── Register listing ────────────────────────────────────────────────

@bp.route("/")
@login_required
def dcrr_register():
    """Full DCRR register view with sortable table and filters."""
    conn = get_db()
    try:
        station_filter = request.args.get("station", "")
        status_filter = request.args.get("status", "")
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        sort_col = request.args.get("sort", "id")
        sort_dir = request.args.get("dir", "desc")

        # Whitelist sortable columns
        allowed_sort = {
            "id", "dcrr_number", "report_date", "station",
            "classification", "status", "oic_name",
        }
        if sort_col not in allowed_sort:
            sort_col = "id"
        if sort_dir not in ("asc", "desc"):
            sort_dir = "desc"

        query = "SELECT * FROM dcrr WHERE 1=1"
        params = []

        if station_filter:
            query += " AND station = ?"
            params.append(station_filter)
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        if date_from:
            query += " AND report_date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND report_date <= ?"
            params.append(date_to)

        query += f" ORDER BY {sort_col} {sort_dir}"
        entries = conn.execute(query, params).fetchall()

        # Distinct stations for filter dropdown
        stations = conn.execute(
            "SELECT DISTINCT station FROM dcrr ORDER BY station"
        ).fetchall()

        return render_template(
            "dcrr/register.html",
            entries=entries,
            stations=[s["station"] for s in stations],
            station_filter=station_filter,
            status_filter=status_filter,
            date_from=date_from,
            date_to=date_to,
            sort_col=sort_col,
            sort_dir=sort_dir,
        )
    finally:
        conn.close()


# ── Single entry detail ─────────────────────────────────────────────

@bp.route("/<int:dcrr_id>")
@login_required
def dcrr_entry(dcrr_id):
    """Detailed DCRR entry view with linked case info."""
    conn = get_db()
    try:
        entry = conn.execute(
            "SELECT * FROM dcrr WHERE id = ?", (dcrr_id,)
        ).fetchone()
        if not entry:
            flash("DCRR entry not found.", "danger")
            return redirect(url_for("dcrr.dcrr_register"))

        # Linked case (if any)
        case = None
        if entry["case_id"]:
            case = conn.execute(
                "SELECT * FROM cases WHERE case_id = ?", (entry["case_id"],)
            ).fetchone()

        return render_template("dcrr/entry.html", entry=entry, case=case)
    finally:
        conn.close()


# ── New DCRR entry ──────────────────────────────────────────────────

@bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required(*DCRR_EDIT_ROLES)
def new_dcrr():
    """Create a new DCRR entry."""
    if request.method == "POST":
        conn = get_db()
        try:
            station = request.form.get("station", "FNID")
            dcrr_number = generate_dcrr_number(station_code=station)
            now = datetime.now()
            name = current_user.full_name

            conn.execute("""
                INSERT INTO dcrr (
                    dcrr_number, case_id, report_date, station,
                    diary_number, classification, offence,
                    complainant_name, suspect_name,
                    oic_badge, oic_name, status, created_by,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dcrr_number,
                request.form.get("case_id") or None,
                request.form.get("report_date", now.strftime("%Y-%m-%d")),
                station,
                request.form.get("diary_number"),
                request.form.get("classification", ""),
                request.form.get("offence", ""),
                request.form.get("complainant_name"),
                request.form.get("suspect_name"),
                request.form.get("oic_badge", current_user.badge_number),
                request.form.get("oic_name", name),
                "Open",
                name,
                now.isoformat(),
                now.isoformat(),
            ))
            conn.commit()

            log_audit("dcrr", dcrr_number, "CREATE",
                      current_user.badge_number, name,
                      f"New DCRR entry: {dcrr_number}")

            flash(f"DCRR entry {dcrr_number} created.", "success")
            return redirect(url_for("dcrr.dcrr_register"))

        except Exception as e:
            conn.rollback()
            flash(f"Error creating DCRR entry: {e}", "danger")
        finally:
            conn.close()

    return render_template("dcrr/form.html", entry=None, is_new=True)


# ── Edit DCRR entry ─────────────────────────────────────────────────

@bp.route("/<int:dcrr_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*DCRR_EDIT_ROLES)
def edit_dcrr(dcrr_id):
    """Edit an existing DCRR entry."""
    conn = get_db()
    try:
        entry = conn.execute(
            "SELECT * FROM dcrr WHERE id = ?", (dcrr_id,)
        ).fetchone()
        if not entry:
            flash("DCRR entry not found.", "danger")
            return redirect(url_for("dcrr.dcrr_register"))

        if request.method == "POST":
            now = datetime.now()
            name = current_user.full_name

            conn.execute("""
                UPDATE dcrr SET
                    case_id = ?, report_date = ?, station = ?,
                    diary_number = ?, classification = ?, offence = ?,
                    complainant_name = ?, suspect_name = ?,
                    oic_badge = ?, oic_name = ?, status = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                request.form.get("case_id") or None,
                request.form.get("report_date", entry["report_date"]),
                request.form.get("station", entry["station"]),
                request.form.get("diary_number"),
                request.form.get("classification", ""),
                request.form.get("offence", ""),
                request.form.get("complainant_name"),
                request.form.get("suspect_name"),
                request.form.get("oic_badge"),
                request.form.get("oic_name"),
                request.form.get("status", entry["status"]),
                now.isoformat(),
                dcrr_id,
            ))
            conn.commit()

            log_audit("dcrr", entry["dcrr_number"], "UPDATE",
                      current_user.badge_number, name,
                      f"Updated DCRR entry #{dcrr_id}")

            flash("DCRR entry updated.", "success")
            return redirect(url_for("dcrr.dcrr_entry", dcrr_id=dcrr_id))

        return render_template("dcrr/form.html", entry=entry, is_new=False)

    finally:
        conn.close()


# ── Summary statistics ───────────────────────────────────────────────

@bp.route("/summary")
@login_required
def dcrr_summary():
    """Summary statistics: entries by station, classification, status, month."""
    conn = get_db()
    try:
        by_station = conn.execute("""
            SELECT station, COUNT(*) as cnt
            FROM dcrr GROUP BY station ORDER BY cnt DESC
        """).fetchall()

        by_classification = conn.execute("""
            SELECT classification, COUNT(*) as cnt
            FROM dcrr GROUP BY classification ORDER BY cnt DESC
        """).fetchall()

        by_status = conn.execute("""
            SELECT status, COUNT(*) as cnt
            FROM dcrr GROUP BY status ORDER BY cnt DESC
        """).fetchall()

        by_month = conn.execute("""
            SELECT strftime('%Y-%m', report_date) as month, COUNT(*) as cnt
            FROM dcrr
            WHERE report_date IS NOT NULL
            GROUP BY month ORDER BY month DESC
            LIMIT 12
        """).fetchall()

        total = conn.execute("SELECT COUNT(*) as cnt FROM dcrr").fetchone()["cnt"]

        return render_template(
            "dcrr/summary.html",
            by_station=by_station,
            by_classification=by_classification,
            by_status=by_status,
            by_month=by_month,
            total=total,
        )
    finally:
        conn.close()
