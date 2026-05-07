"""
FNID Report Generation

Generates printable reports: monthly statistical return, DCRR summary,
IO caseload report, evidence status report, and PDF exports.
"""

from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, render_template, request
from flask_login import login_required

from ..models import get_db
from ..pdf_export import pdf_base_css, pdf_header_html, render_pdf
from ..rbac import role_required

bp = Blueprint("reports", __name__, url_prefix="/reports")

# Alias for external reference
reports_bp = bp

# Roles permitted to access reports
_REPORT_ROLES = ("admin", "dco", "ddi", "station_mgr")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route("/")
@login_required
@role_required(*_REPORT_ROLES)
def reports_home():
    """Report index page listing all available reports."""
    reports = [
        {
            "id": "monthly",
            "title": "Monthly Statistical Return",
            "description": (
                "Count of new cases, closures, seizures, arrests, "
                "court appearances, and conviction rate for a selected month."
            ),
            "icon": "bi-calendar-month",
            "url": "/reports/monthly",
        },
        {
            "id": "dcrr",
            "title": "DCRR Summary Report",
            "description": (
                "Daily Crime Report Register entries by station, "
                "classification, and status with outstanding entry tracking."
            ),
            "icon": "bi-journal-text",
            "url": "/reports/dcrr-summary",
        },
        {
            "id": "caseload",
            "title": "IO Caseload Report",
            "description": (
                "Investigating Officer workload: assigned cases, "
                "open cases, overdue reviews, and oldest case age."
            ),
            "icon": "bi-people",
            "url": "/reports/caseload",
        },
        {
            "id": "evidence",
            "title": "Evidence Status Report",
            "description": "Exhibits pending lab submission, overdue certificates, and chain-of-custody gaps by case.",
            "icon": "bi-box-seam",
            "url": "/reports/evidence",
        },
    ]
    return render_template("reports/index.html", reports=reports)


@bp.route("/monthly")
@login_required
@role_required(*_REPORT_ROLES)
def monthly_statistical_return():
    """Monthly statistical return for selected month/year."""
    now = datetime.now()
    month = request.args.get("month", now.strftime("%m"))
    year = request.args.get("year", now.strftime("%Y"))

    try:
        month = int(month)
        year = int(year)
    except (ValueError, TypeError):
        month = now.month
        year = now.year

    # Build date range for the month
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    conn = get_db()

    try:
        # New cases
        new_cases = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE created_at >= ? AND created_at < ?",
            (start_date, end_date),
        ).fetchone()[0]

        # Closures
        closures = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE closed_date >= ? AND closed_date < ?",
            (start_date, end_date),
        ).fetchone()[0]

        # Firearm seizures by type
        firearms_by_type = conn.execute(
            "SELECT firearm_type, COUNT(*) AS cnt, SUM(ammo_count) AS ammo "
            "FROM firearm_seizures WHERE seizure_date >= ? AND seizure_date < ? "
            "GROUP BY firearm_type ORDER BY cnt DESC",
            (start_date, end_date),
        ).fetchall()

        total_firearms = sum(r["cnt"] for r in firearms_by_type)

        # Narcotics seizures by type/weight
        narcotics_by_type = conn.execute(
            "SELECT drug_type, SUM(quantity) AS total_qty, unit, COUNT(*) AS cnt "
            "FROM narcotics_seizures WHERE seizure_date >= ? AND seizure_date < ? "
            "GROUP BY drug_type, unit ORDER BY total_qty DESC",
            (start_date, end_date),
        ).fetchall()

        total_narcotics = sum(r["cnt"] for r in narcotics_by_type)

        # Arrests
        arrests = conn.execute(
            "SELECT COUNT(*) FROM arrests WHERE arrest_date >= ? AND arrest_date < ?",
            (start_date, end_date),
        ).fetchone()[0]

        # Court appearances
        court_appearances = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE next_court_date >= ? AND next_court_date < ?",
            (start_date, end_date),
        ).fetchone()[0]

        # Conviction rate
        verdicts_total = conn.execute(
            "SELECT COUNT(*) FROM cases "
            "WHERE verdict IS NOT NULL AND verdict != '' "
            "AND closed_date >= ? AND closed_date < ?",
            (start_date, end_date),
        ).fetchone()[0]

        convictions = conn.execute(
            "SELECT COUNT(*) FROM cases "
            "WHERE verdict LIKE '%Guilty%' OR verdict LIKE '%Convicted%' "
            "AND closed_date >= ? AND closed_date < ?",
            (start_date, end_date),
        ).fetchone()[0]

        conviction_rate = round((convictions / verdicts_total * 100), 1) if verdicts_total else 0.0

    finally:
        conn.close()

    return render_template(
        "reports/monthly.html",
        month=month,
        year=year,
        new_cases=new_cases,
        closures=closures,
        firearms_by_type=firearms_by_type,
        total_firearms=total_firearms,
        narcotics_by_type=narcotics_by_type,
        total_narcotics=total_narcotics,
        arrests=arrests,
        court_appearances=court_appearances,
        conviction_rate=conviction_rate,
        convictions=convictions,
        verdicts_total=verdicts_total,
    )


@bp.route("/dcrr-summary")
@login_required
@role_required(*_REPORT_ROLES)
def dcrr_summary_report():
    """DCRR summary for date range: entries by station, classification, status."""
    start_date = request.args.get("start_date", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date = request.args.get("end_date", datetime.now().strftime("%Y-%m-%d"))

    conn = get_db()

    try:
        # Entries by station
        by_station = conn.execute(
            "SELECT station, COUNT(*) AS cnt FROM dcrr "
            "WHERE report_date BETWEEN ? AND ? "
            "GROUP BY station ORDER BY cnt DESC",
            (start_date, end_date),
        ).fetchall()

        # Entries by classification
        by_classification = conn.execute(
            "SELECT classification, COUNT(*) AS cnt FROM dcrr "
            "WHERE report_date BETWEEN ? AND ? "
            "GROUP BY classification ORDER BY cnt DESC",
            (start_date, end_date),
        ).fetchall()

        # Entries by status
        by_status = conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM dcrr "
            "WHERE report_date BETWEEN ? AND ? "
            "GROUP BY status ORDER BY cnt DESC",
            (start_date, end_date),
        ).fetchall()

        # Outstanding entries (no case link)
        outstanding = conn.execute(
            "SELECT dcrr_number, report_date, station, classification, offence, "
            "complainant_name, suspect_name, oic_name "
            "FROM dcrr WHERE (case_id IS NULL OR case_id = '') "
            "AND report_date BETWEEN ? AND ? "
            "ORDER BY report_date DESC",
            (start_date, end_date),
        ).fetchall()

        total_entries = conn.execute(
            "SELECT COUNT(*) FROM dcrr WHERE report_date BETWEEN ? AND ?",
            (start_date, end_date),
        ).fetchone()[0]

    finally:
        conn.close()

    return render_template(
        "reports/index.html",
        report_type="dcrr",
        start_date=start_date,
        end_date=end_date,
        by_station=by_station,
        by_classification=by_classification,
        by_status=by_status,
        outstanding=outstanding,
        total_entries=total_entries,
    )


@bp.route("/caseload")
@login_required
@role_required(*_REPORT_ROLES)
def io_caseload_report():
    """IO caseload report: officer workload with overdue review tracking."""
    conn = get_db()

    try:
        officers = conn.execute(
            "SELECT o.badge_number, o.full_name, o.rank "
            "FROM officers o WHERE o.role = 'io' AND o.is_active = 1 "
            "ORDER BY o.full_name"
        ).fetchall()

        caseload = []
        today = datetime.now().strftime("%Y-%m-%d")

        for off in officers:
            badge = off["badge_number"]

            assigned = conn.execute(
                "SELECT COUNT(*) FROM cases WHERE assigned_io_badge = ?",
                (badge,),
            ).fetchone()[0]

            open_cases = conn.execute(
                "SELECT COUNT(*) FROM cases "
                "WHERE assigned_io_badge = ? AND current_stage != 'closed'",
                (badge,),
            ).fetchone()[0]

            overdue_reviews = conn.execute(
                "SELECT COUNT(*) FROM case_reviews cr "
                "JOIN cases c ON cr.case_id = c.case_id "
                "WHERE c.assigned_io_badge = ? "
                "AND cr.status = 'Scheduled' AND cr.scheduled_date < ?",
                (badge, today),
            ).fetchone()[0]

            oldest_row = conn.execute(
                "SELECT MIN(created_at) FROM cases "
                "WHERE assigned_io_badge = ? AND current_stage != 'closed'",
                (badge,),
            ).fetchone()[0]

            oldest_days = 0
            if oldest_row:
                try:
                    oldest_days = (datetime.now() - datetime.strptime(oldest_row[:10], "%Y-%m-%d")).days
                except (ValueError, TypeError):
                    oldest_days = 0

            caseload.append({
                "badge": badge,
                "name": off["full_name"],
                "rank": off["rank"],
                "assigned": assigned,
                "open_cases": open_cases,
                "overdue_reviews": overdue_reviews,
                "oldest_days": oldest_days,
            })

    finally:
        conn.close()

    return render_template("reports/caseload.html", caseload=caseload)


@bp.route("/evidence")
@login_required
@role_required(*_REPORT_ROLES)
def evidence_status_report():
    """Evidence status: exhibits pending lab, overdue certificates, chain gaps."""
    conn = get_db()

    try:
        # Exhibits pending lab submission
        pending_lab = conn.execute(
            "SELECT lt.lab_ref, lt.exhibit_tag, lt.linked_case_id, "
            "lt.submission_date, lt.exam_type, lt.certificate_status "
            "FROM lab_tracking lt "
            "WHERE lt.certificate_status IN ('Not Yet Submitted to Lab', 'Submitted - Awaiting Results') "
            "ORDER BY lt.submission_date ASC"
        ).fetchall()

        # Overdue certificates (submitted > 8 weeks ago, no result)
        eight_weeks_ago = (datetime.now() - timedelta(weeks=8)).strftime("%Y-%m-%d")
        overdue_certs = conn.execute(
            "SELECT lt.lab_ref, lt.exhibit_tag, lt.linked_case_id, "
            "lt.submission_date, lt.exam_type, lt.expected_date "
            "FROM lab_tracking lt "
            "WHERE lt.completion_date IS NULL "
            "AND lt.submission_date < ? "
            "ORDER BY lt.submission_date ASC",
            (eight_weeks_ago,),
        ).fetchall()

        # Chain-of-custody gaps: exhibits where seal is not intact or condition noted
        chain_gaps = conn.execute(
            "SELECT coc.exhibit_tag, coc.linked_case_id, coc.exhibit_type, "
            "coc.current_custodian, coc.storage_location, coc.seal_intact, coc.condition "
            "FROM chain_of_custody coc "
            "WHERE coc.seal_intact = 'No' OR coc.condition LIKE '%damage%' "
            "OR coc.condition LIKE '%broken%' "
            "ORDER BY coc.linked_case_id"
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "reports/index.html",
        report_type="evidence",
        pending_lab=pending_lab,
        overdue_certs=overdue_certs,
        chain_gaps=chain_gaps,
    )


@bp.route("/export/<report_type>")
@login_required
@role_required(*_REPORT_ROLES)
def export_report_pdf(report_type):
    """PDF export of any report type."""
    supported = ("monthly", "dcrr", "caseload", "evidence")
    if report_type not in supported:
        return jsonify({"error": f"Unsupported report type. Supported: {supported}"}), 400

    # Determine title
    titles = {
        "monthly": "Monthly Statistical Return",
        "dcrr": "DCRR Summary Report",
        "caseload": "IO Caseload Report",
        "evidence": "Evidence Status Report",
    }
    title = titles.get(report_type, "FNID Report")

    # Generate report HTML by calling the appropriate route logic
    if report_type == "monthly":
        html = _monthly_pdf_html(title)
    elif report_type == "dcrr":
        html = _dcrr_pdf_html(title)
    elif report_type == "caseload":
        html = _caseload_pdf_html(title)
    elif report_type == "evidence":
        html = _evidence_pdf_html(title)
    else:
        html = f"<html><body><h1>Report: {report_type}</h1><p>No data.</p></body></html>"

    pdf_buffer = render_pdf(html)

    if pdf_buffer is None:
        # Fallback: return HTML for printing
        return html

    return Response(
        pdf_buffer.read(),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=fnid_{report_type}_{datetime.now().strftime('%Y%m%d')}.pdf"
        },
    )


# ---------------------------------------------------------------------------
# PDF HTML generators
# ---------------------------------------------------------------------------

def _monthly_pdf_html(title):
    """Generate HTML for monthly statistical return PDF."""
    now = datetime.now()
    month = request.args.get("month", now.strftime("%m"))
    year = request.args.get("year", now.strftime("%Y"))

    try:
        month = int(month)
        year = int(year)
    except (ValueError, TypeError):
        month = now.month
        year = now.year

    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    conn = get_db()
    try:
        new_cases = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE created_at >= ? AND created_at < ?",
            (start_date, end_date),
        ).fetchone()[0]
        closures = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE closed_date >= ? AND closed_date < ?",
            (start_date, end_date),
        ).fetchone()[0]
        firearms = conn.execute(
            "SELECT COUNT(*) FROM firearm_seizures WHERE seizure_date >= ? AND seizure_date < ?",
            (start_date, end_date),
        ).fetchone()[0]
        narcotics = conn.execute(
            "SELECT COUNT(*) FROM narcotics_seizures WHERE seizure_date >= ? AND seizure_date < ?",
            (start_date, end_date),
        ).fetchone()[0]
        arrests = conn.execute(
            "SELECT COUNT(*) FROM arrests WHERE arrest_date >= ? AND arrest_date < ?",
            (start_date, end_date),
        ).fetchone()[0]
    finally:
        conn.close()

    header = pdf_header_html(f"{title} - {month:02d}/{year}")
    css = pdf_base_css()

    return f"""<html><head>{css}</head><body>
    {header}
    <table>
        <tr><th>Metric</th><th>Count</th></tr>
        <tr><td>New Cases</td><td>{new_cases}</td></tr>
        <tr><td>Closures</td><td>{closures}</td></tr>
        <tr><td>Firearms Seized</td><td>{firearms}</td></tr>
        <tr><td>Narcotics Seizures</td><td>{narcotics}</td></tr>
        <tr><td>Arrests</td><td>{arrests}</td></tr>
    </table>
    <div class="footer">RESTRICTED - Official Use Only</div>
    </body></html>"""


def _dcrr_pdf_html(title):
    """Generate HTML for DCRR summary PDF."""
    start_date = request.args.get("start_date", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date = request.args.get("end_date", datetime.now().strftime("%Y-%m-%d"))

    conn = get_db()
    try:
        by_station = conn.execute(
            "SELECT station, COUNT(*) AS cnt FROM dcrr "
            "WHERE report_date BETWEEN ? AND ? GROUP BY station ORDER BY cnt DESC",
            (start_date, end_date),
        ).fetchall()
        outstanding = conn.execute(
            "SELECT COUNT(*) FROM dcrr WHERE (case_id IS NULL OR case_id = '') "
            "AND report_date BETWEEN ? AND ?",
            (start_date, end_date),
        ).fetchone()[0]
    finally:
        conn.close()

    header = pdf_header_html(f"{title} ({start_date} to {end_date})")
    css = pdf_base_css()

    station_rows = "".join(
        f"<tr><td>{r['station']}</td><td>{r['cnt']}</td></tr>" for r in by_station
    )

    return f"""<html><head>{css}</head><body>
    {header}
    <h4>Entries by Station</h4>
    <table><tr><th>Station</th><th>Count</th></tr>{station_rows}</table>
    <p><strong>Outstanding (no case link):</strong> {outstanding}</p>
    <div class="footer">RESTRICTED - Official Use Only</div>
    </body></html>"""


def _caseload_pdf_html(title):
    """Generate HTML for IO caseload PDF."""
    conn = get_db()
    try:
        officers = conn.execute(
            "SELECT o.badge_number, o.full_name, "
            "  COUNT(c.id) AS assigned, "
            "  SUM(CASE WHEN c.current_stage != 'closed' THEN 1 ELSE 0 END) AS open_cases "
            "FROM officers o "
            "LEFT JOIN cases c ON c.assigned_io_badge = o.badge_number "
            "WHERE o.role = 'io' AND o.is_active = 1 "
            "GROUP BY o.badge_number ORDER BY assigned DESC"
        ).fetchall()
    finally:
        conn.close()

    header = pdf_header_html(title)
    css = pdf_base_css()

    rows = "".join(
        f"<tr><td>{r['full_name']}</td><td>{r['badge_number']}</td>"
        f"<td>{r['assigned']}</td><td>{r['open_cases']}</td></tr>"
        for r in officers
    )

    return f"""<html><head>{css}</head><body>
    {header}
    <table>
        <tr><th>Officer</th><th>Badge</th><th>Assigned</th><th>Open</th></tr>
        {rows}
    </table>
    <div class="footer">RESTRICTED - Official Use Only</div>
    </body></html>"""


def _evidence_pdf_html(title):
    """Generate HTML for evidence status PDF."""
    conn = get_db()
    try:
        pending = conn.execute(
            "SELECT COUNT(*) FROM lab_tracking "
            "WHERE certificate_status IN ('Not Yet Submitted to Lab', 'Submitted - Awaiting Results')"
        ).fetchone()[0]
        eight_weeks_ago = (datetime.now() - timedelta(weeks=8)).strftime("%Y-%m-%d")
        overdue = conn.execute(
            "SELECT COUNT(*) FROM lab_tracking "
            "WHERE completion_date IS NULL AND submission_date < ?",
            (eight_weeks_ago,),
        ).fetchone()[0]
        gaps = conn.execute(
            "SELECT COUNT(*) FROM chain_of_custody "
            "WHERE seal_intact = 'No' OR condition LIKE '%damage%' OR condition LIKE '%broken%'"
        ).fetchone()[0]
    finally:
        conn.close()

    header = pdf_header_html(title)
    css = pdf_base_css()

    return f"""<html><head>{css}</head><body>
    {header}
    <table>
        <tr><th>Category</th><th>Count</th></tr>
        <tr><td>Exhibits Pending Lab</td><td>{pending}</td></tr>
        <tr><td>Overdue Certificates (8+ weeks)</td><td>{overdue}</td></tr>
        <tr><td>Chain-of-Custody Gaps</td><td>{gaps}</td></tr>
    </table>
    <div class="footer">RESTRICTED - Official Use Only</div>
    </body></html>"""
