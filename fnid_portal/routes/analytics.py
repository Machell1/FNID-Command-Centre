"""
FNID Analytics Dashboard

Advanced performance analytics for command staff: case pipeline funnels,
trend lines, parish comparisons, clearance rates, and officer performance.
"""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from ..models import get_db
from ..rbac import role_required

bp = Blueprint("analytics", __name__, url_prefix="/analytics")

# Alias for external reference
analytics_bp = bp

# Roles permitted to access analytics
_ANALYTICS_ROLES = ("admin", "dco", "ddi", "station_mgr", "supervisor")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_range_from_request():
    """Extract start/end date strings from query params with 30-day default."""
    end_date = request.args.get("end_date")
    start_date = request.args.get("start_date")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    return start_date, end_date


def _safe_pct(numerator, denominator):
    """Return percentage rounded to 1 decimal, or 0.0 if denominator is 0."""
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 1)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route("/")
@login_required
@role_required(*_ANALYTICS_ROLES)
def analytics_home():
    """Main analytics page with KPIs, pipeline funnel, trends, and parish comparison."""
    start_date, end_date = _date_range_from_request()
    conn = get_db()

    try:
        # --- Case pipeline funnel ---
        stages = ["intake", "vetting", "assignment", "investigation", "court", "closed"]
        funnel = {}
        for stage in stages:
            row = conn.execute(
                "SELECT COUNT(*) FROM cases WHERE current_stage = ? "
                "AND created_at BETWEEN ? AND ?",
                (stage, start_date, end_date + " 23:59:59"),
            ).fetchone()
            funnel[stage] = row[0] if row else 0

        # --- Monthly trends (new cases, closures, seizures) ---
        trends_new = conn.execute(
            "SELECT strftime('%Y-%m', created_at) AS month, COUNT(*) AS cnt "
            "FROM cases WHERE created_at BETWEEN ? AND ? "
            "GROUP BY month ORDER BY month",
            (start_date, end_date + " 23:59:59"),
        ).fetchall()

        trends_closed = conn.execute(
            "SELECT strftime('%Y-%m', closed_date) AS month, COUNT(*) AS cnt "
            "FROM cases WHERE closed_date IS NOT NULL "
            "AND closed_date BETWEEN ? AND ? "
            "GROUP BY month ORDER BY month",
            (start_date, end_date + " 23:59:59"),
        ).fetchall()

        trends_seizures = conn.execute(
            "SELECT strftime('%Y-%m', seizure_date) AS month, COUNT(*) AS cnt "
            "FROM firearm_seizures WHERE seizure_date BETWEEN ? AND ? "
            "GROUP BY month ORDER BY month",
            (start_date, end_date + " 23:59:59"),
        ).fetchall()

        # Build unified month list
        month_set = set()
        for row in trends_new:
            month_set.add(row["month"])
        for row in trends_closed:
            month_set.add(row["month"])
        for row in trends_seizures:
            month_set.add(row["month"])
        months_sorted = sorted(month_set)

        new_map = {r["month"]: r["cnt"] for r in trends_new}
        closed_map = {r["month"]: r["cnt"] for r in trends_closed}
        seizure_map = {r["month"]: r["cnt"] for r in trends_seizures}

        trends = {
            "labels": months_sorted,
            "new_cases": [new_map.get(m, 0) for m in months_sorted],
            "closures": [closed_map.get(m, 0) for m in months_sorted],
            "seizures": [seizure_map.get(m, 0) for m in months_sorted],
        }

        # --- Parish comparison ---
        parishes = ["Manchester", "St. Elizabeth", "Clarendon"]
        parish_data = {}
        for p in parishes:
            row = conn.execute(
                "SELECT COUNT(*) FROM cases WHERE parish = ? "
                "AND created_at BETWEEN ? AND ?",
                (p, start_date, end_date + " 23:59:59"),
            ).fetchone()
            parish_data[p] = row[0] if row else 0

        # --- Clearance rate ---
        total_cases = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE created_at BETWEEN ? AND ?",
            (start_date, end_date + " 23:59:59"),
        ).fetchone()[0]

        closed_cases = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE current_stage = 'closed' "
            "AND created_at BETWEEN ? AND ?",
            (start_date, end_date + " 23:59:59"),
        ).fetchone()[0]

        clearance_rate = _safe_pct(closed_cases, total_cases)

        # --- Average time-to-close by classification ---
        avg_close = conn.execute(
            "SELECT classification, "
            "ROUND(AVG(julianday(closed_date) - julianday(created_at)), 1) AS avg_days "
            "FROM cases "
            "WHERE closed_date IS NOT NULL AND created_at BETWEEN ? AND ? "
            "GROUP BY classification ORDER BY avg_days DESC",
            (start_date, end_date + " 23:59:59"),
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "analytics/home.html",
        start_date=start_date,
        end_date=end_date,
        funnel=funnel,
        stages=stages,
        trends=trends,
        parish_data=parish_data,
        clearance_rate=clearance_rate,
        total_cases=total_cases,
        closed_cases=closed_cases,
        avg_close=avg_close,
    )


@bp.route("/officers")
@login_required
@role_required(*_ANALYTICS_ROLES)
def io_performance():
    """IO performance metrics: caseloads, clearance rates, review compliance."""
    conn = get_db()

    try:
        # Cases per officer
        officers = conn.execute(
            "SELECT o.badge_number, o.full_name, o.rank, "
            "  COUNT(c.id) AS assigned, "
            "  SUM(CASE WHEN c.current_stage != 'closed' THEN 1 ELSE 0 END) AS active, "
            "  SUM(CASE WHEN c.current_stage = 'closed' THEN 1 ELSE 0 END) AS closed "
            "FROM officers o "
            "LEFT JOIN cases c ON c.assigned_io_badge = o.badge_number "
            "WHERE o.role = 'io' AND o.is_active = 1 "
            "GROUP BY o.badge_number "
            "ORDER BY assigned DESC"
        ).fetchall()

        io_stats = []
        for off in officers:
            assigned = off["assigned"] or 0
            active = off["active"] or 0
            closed = off["closed"] or 0
            clearance = _safe_pct(closed, assigned)

            # Review compliance: scheduled reviews that were completed on time
            total_reviews = conn.execute(
                "SELECT COUNT(*) FROM case_reviews cr "
                "JOIN cases c ON cr.case_id = c.case_id "
                "WHERE c.assigned_io_badge = ?",
                (off["badge_number"],),
            ).fetchone()[0]

            on_time_reviews = conn.execute(
                "SELECT COUNT(*) FROM case_reviews cr "
                "JOIN cases c ON cr.case_id = c.case_id "
                "WHERE c.assigned_io_badge = ? "
                "AND cr.status = 'Completed' "
                "AND cr.actual_date <= cr.scheduled_date",
                (off["badge_number"],),
            ).fetchone()[0]

            review_compliance = _safe_pct(on_time_reviews, total_reviews)

            # Oldest active case age
            oldest = conn.execute(
                "SELECT MIN(created_at) FROM cases "
                "WHERE assigned_io_badge = ? AND current_stage != 'closed'",
                (off["badge_number"],),
            ).fetchone()[0]

            oldest_days = 0
            if oldest:
                try:
                    oldest_days = (datetime.now() - datetime.strptime(oldest[:10], "%Y-%m-%d")).days
                except (ValueError, TypeError):
                    oldest_days = 0

            io_stats.append({
                "badge": off["badge_number"],
                "name": off["full_name"],
                "rank": off["rank"],
                "assigned": assigned,
                "active": active,
                "closed": closed,
                "clearance": clearance,
                "review_compliance": review_compliance,
                "oldest_days": oldest_days,
            })

    finally:
        conn.close()

    return render_template("analytics/officers.html", io_stats=io_stats)


@bp.route("/seizures")
@login_required
@role_required(*_ANALYTICS_ROLES)
def seizure_analytics():
    """Seizure trends: firearms by month, narcotics by month, calibres, drug types."""
    start_date, end_date = _date_range_from_request()
    conn = get_db()

    try:
        # Firearms by month
        firearms_monthly = conn.execute(
            "SELECT strftime('%Y-%m', seizure_date) AS month, COUNT(*) AS cnt "
            "FROM firearm_seizures WHERE seizure_date BETWEEN ? AND ? "
            "GROUP BY month ORDER BY month",
            (start_date, end_date + " 23:59:59"),
        ).fetchall()

        # Narcotics by month
        narcotics_monthly = conn.execute(
            "SELECT strftime('%Y-%m', seizure_date) AS month, COUNT(*) AS cnt "
            "FROM narcotics_seizures WHERE seizure_date BETWEEN ? AND ? "
            "GROUP BY month ORDER BY month",
            (start_date, end_date + " 23:59:59"),
        ).fetchall()

        # Top calibres
        top_calibres = conn.execute(
            "SELECT calibre, COUNT(*) AS cnt FROM firearm_seizures "
            "WHERE calibre IS NOT NULL AND seizure_date BETWEEN ? AND ? "
            "GROUP BY calibre ORDER BY cnt DESC LIMIT 10",
            (start_date, end_date + " 23:59:59"),
        ).fetchall()

        # Drug types by quantity
        drug_types = conn.execute(
            "SELECT drug_type, SUM(quantity) AS total_qty, unit "
            "FROM narcotics_seizures "
            "WHERE seizure_date BETWEEN ? AND ? "
            "GROUP BY drug_type, unit ORDER BY total_qty DESC",
            (start_date, end_date + " 23:59:59"),
        ).fetchall()

        # Parish breakdown (firearms + narcotics)
        parish_firearms = conn.execute(
            "SELECT parish, COUNT(*) AS cnt FROM firearm_seizures "
            "WHERE seizure_date BETWEEN ? AND ? "
            "GROUP BY parish ORDER BY cnt DESC",
            (start_date, end_date + " 23:59:59"),
        ).fetchall()

        parish_narcotics = conn.execute(
            "SELECT parish, COUNT(*) AS cnt FROM narcotics_seizures "
            "WHERE seizure_date BETWEEN ? AND ? "
            "GROUP BY parish ORDER BY cnt DESC",
            (start_date, end_date + " 23:59:59"),
        ).fetchall()

        # IBIS / eTrace hit rates
        total_firearms = conn.execute(
            "SELECT COUNT(*) FROM firearm_seizures WHERE seizure_date BETWEEN ? AND ?",
            (start_date, end_date + " 23:59:59"),
        ).fetchone()[0]

        ibis_hits = conn.execute(
            "SELECT COUNT(*) FROM firearm_seizures "
            "WHERE ibis_status = 'Hit' AND seizure_date BETWEEN ? AND ?",
            (start_date, end_date + " 23:59:59"),
        ).fetchone()[0]

        etrace_hits = conn.execute(
            "SELECT COUNT(*) FROM firearm_seizures "
            "WHERE etrace_status = 'Hit' AND seizure_date BETWEEN ? AND ?",
            (start_date, end_date + " 23:59:59"),
        ).fetchone()[0]

        ibis_rate = _safe_pct(ibis_hits, total_firearms)
        etrace_rate = _safe_pct(etrace_hits, total_firearms)

    finally:
        conn.close()

    return render_template(
        "analytics/seizures.html",
        start_date=start_date,
        end_date=end_date,
        firearms_monthly=firearms_monthly,
        narcotics_monthly=narcotics_monthly,
        top_calibres=top_calibres,
        drug_types=drug_types,
        parish_firearms=parish_firearms,
        parish_narcotics=parish_narcotics,
        total_firearms=total_firearms,
        ibis_rate=ibis_rate,
        etrace_rate=etrace_rate,
    )


@bp.route("/court")
@login_required
@role_required(*_ANALYTICS_ROLES)
def court_pipeline():
    """Court and DPP pipeline analytics."""
    conn = get_db()

    try:
        # Cases at each DPP stage
        dpp_stages = conn.execute(
            "SELECT dpp_status, COUNT(*) AS cnt FROM dpp_pipeline "
            "GROUP BY dpp_status ORDER BY cnt DESC"
        ).fetchall()

        # Average time from arrest to charge
        avg_arrest_to_charge = conn.execute(
            "SELECT ROUND(AVG(julianday(charge_date) - julianday(arrest_date)), 1) "
            "FROM arrests WHERE charge_date IS NOT NULL"
        ).fetchone()[0] or 0

        # Average time from charge to DPP submission
        avg_charge_to_dpp = conn.execute(
            "SELECT ROUND(AVG(julianday(dp.dpp_file_date) - julianday(a.charge_date)), 1) "
            "FROM dpp_pipeline dp "
            "JOIN arrests a ON dp.linked_case_id = a.linked_case_id "
            "WHERE dp.dpp_file_date IS NOT NULL AND a.charge_date IS NOT NULL"
        ).fetchone()[0] or 0

        # Conviction / acquittal breakdown
        verdicts = conn.execute(
            "SELECT verdict, COUNT(*) AS cnt FROM cases "
            "WHERE verdict IS NOT NULL AND verdict != '' "
            "GROUP BY verdict ORDER BY cnt DESC"
        ).fetchall()

        # Upcoming court dates (next 30 days)
        today = datetime.now().strftime("%Y-%m-%d")
        thirty_days = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        upcoming_court = conn.execute(
            "SELECT case_id, suspect_name, classification, court_type, "
            "next_court_date, oic_name "
            "FROM cases WHERE next_court_date BETWEEN ? AND ? "
            "ORDER BY next_court_date ASC",
            (today, thirty_days),
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "analytics/court.html",
        dpp_stages=dpp_stages,
        avg_arrest_to_charge=avg_arrest_to_charge,
        avg_charge_to_dpp=avg_charge_to_dpp,
        verdicts=verdicts,
        upcoming_court=upcoming_court,
    )


@bp.route("/api/data")
@login_required
@role_required(*_ANALYTICS_ROLES)
def api_chart_data():
    """JSON API for chart data. Accepts chart_type and period params."""
    chart_type = request.args.get("chart_type", "pipeline")
    period = request.args.get("period", "30")

    try:
        period_days = int(period)
    except (ValueError, TypeError):
        period_days = 30

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

    conn = get_db()

    try:
        if chart_type == "pipeline":
            stages = ["intake", "vetting", "assignment", "investigation", "court", "closed"]
            counts = []
            for stage in stages:
                row = conn.execute(
                    "SELECT COUNT(*) FROM cases WHERE current_stage = ?", (stage,)
                ).fetchone()
                counts.append(row[0] if row else 0)
            return jsonify({
                "labels": stages,
                "datasets": [{
                    "label": "Cases",
                    "data": counts,
                    "backgroundColor": [
                        "#6c757d", "#17a2b8", "#ffc107",
                        "#0d6efd", "#fd7e14", "#198754",
                    ],
                }],
            })

        elif chart_type == "trends":
            rows = conn.execute(
                "SELECT strftime('%Y-%m', created_at) AS month, COUNT(*) AS cnt "
                "FROM cases WHERE created_at BETWEEN ? AND ? "
                "GROUP BY month ORDER BY month",
                (start_date, end_date + " 23:59:59"),
            ).fetchall()
            return jsonify({
                "labels": [r["month"] for r in rows],
                "datasets": [{
                    "label": "New Cases",
                    "data": [r["cnt"] for r in rows],
                    "borderColor": "#1F3864",
                    "fill": False,
                }],
            })

        elif chart_type == "parish":
            parishes = ["Manchester", "St. Elizabeth", "Clarendon"]
            counts = []
            for p in parishes:
                row = conn.execute(
                    "SELECT COUNT(*) FROM cases WHERE parish = ? "
                    "AND created_at BETWEEN ? AND ?",
                    (p, start_date, end_date + " 23:59:59"),
                ).fetchone()
                counts.append(row[0] if row else 0)
            return jsonify({
                "labels": parishes,
                "datasets": [{
                    "label": "Cases by Parish",
                    "data": counts,
                    "backgroundColor": ["#1F3864", "#C5A23C", "#28a745"],
                }],
            })

        elif chart_type == "firearms":
            rows = conn.execute(
                "SELECT strftime('%Y-%m', seizure_date) AS month, COUNT(*) AS cnt "
                "FROM firearm_seizures WHERE seizure_date BETWEEN ? AND ? "
                "GROUP BY month ORDER BY month",
                (start_date, end_date + " 23:59:59"),
            ).fetchall()
            return jsonify({
                "labels": [r["month"] for r in rows],
                "datasets": [{
                    "label": "Firearms Seized",
                    "data": [r["cnt"] for r in rows],
                    "backgroundColor": "#dc3545",
                }],
            })

        elif chart_type == "narcotics":
            rows = conn.execute(
                "SELECT strftime('%Y-%m', seizure_date) AS month, COUNT(*) AS cnt "
                "FROM narcotics_seizures WHERE seizure_date BETWEEN ? AND ? "
                "GROUP BY month ORDER BY month",
                (start_date, end_date + " 23:59:59"),
            ).fetchall()
            return jsonify({
                "labels": [r["month"] for r in rows],
                "datasets": [{
                    "label": "Narcotics Seizures",
                    "data": [r["cnt"] for r in rows],
                    "backgroundColor": "#6f42c1",
                }],
            })

        elif chart_type == "dpp":
            rows = conn.execute(
                "SELECT dpp_status, COUNT(*) AS cnt FROM dpp_pipeline "
                "GROUP BY dpp_status ORDER BY cnt DESC"
            ).fetchall()
            return jsonify({
                "labels": [r["dpp_status"] for r in rows],
                "datasets": [{
                    "label": "DPP Pipeline",
                    "data": [r["cnt"] for r in rows],
                    "backgroundColor": [
                        "#1F3864", "#C5A23C", "#28a745", "#dc3545",
                        "#17a2b8", "#fd7e14", "#6f42c1", "#20c997",
                    ],
                }],
            })

        else:
            return jsonify({"error": "Unknown chart_type", "labels": [], "datasets": []}), 400

    finally:
        conn.close()
