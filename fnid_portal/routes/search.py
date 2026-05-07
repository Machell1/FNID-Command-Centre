"""
Search Routes

Quick search and advanced search across cases, persons, exhibits, and officers.
"""

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from ..models import get_db

bp = Blueprint("search", __name__, url_prefix="/search")


@bp.route("/")
@login_required
def quick_search():
    """Quick search across all major tables."""
    q = request.args.get("q", "").strip()
    results = {"cases": [], "persons": [], "exhibits": [], "intel": []}

    if not q:
        return render_template("search/results.html", query="", results=results)

    conn = get_db()
    try:
        pattern = f"%{q}%"

        # Search cases
        results["cases"] = conn.execute("""
            SELECT case_id, classification, parish, offence_description,
                   suspect_name, victim_name, case_status, current_stage
            FROM cases
            WHERE case_id LIKE ? OR offence_description LIKE ?
               OR suspect_name LIKE ? OR victim_name LIKE ?
               OR dcrr_number LIKE ? OR diary_number LIKE ?
            ORDER BY id DESC LIMIT 20
        """, (pattern, pattern, pattern, pattern, pattern, pattern)).fetchall()

        # Search persons (suspects, arrestees, witnesses)
        results["persons"] = conn.execute("""
            SELECT 'Suspect' as source, suspect_name as name,
                   suspect_address as address, linked_case_id as case_ref
            FROM arrests WHERE suspect_name LIKE ?
            UNION ALL
            SELECT 'Witness' as source, witness_name as name,
                   witness_address as address, linked_case_id as case_ref
            FROM witness_statements WHERE witness_name LIKE ?
            UNION ALL
            SELECT 'Target' as source, target_name as name,
                   parish as address, linked_cases as case_ref
            FROM intel_targets WHERE target_name LIKE ? OR aliases LIKE ?
            ORDER BY name LIMIT 30
        """, (pattern, pattern, pattern, pattern)).fetchall()

        # Search exhibits
        results["exhibits"] = conn.execute("""
            SELECT exhibit_tag, exhibit_type, description,
                   linked_case_id, current_custodian, storage_location
            FROM chain_of_custody
            WHERE exhibit_tag LIKE ? OR description LIKE ?
               OR linked_case_id LIKE ?
            ORDER BY id DESC LIMIT 20
        """, (pattern, pattern, pattern)).fetchall()

        # Search intel
        if current_user.role in ("admin", "dco", "ddi", "intel_officer"):
            results["intel"] = conn.execute("""
                SELECT intel_id, subject_matter, parish, priority,
                       target_person, triage_decision
                FROM intel_reports
                WHERE intel_id LIKE ? OR subject_matter LIKE ?
                   OR target_person LIKE ? OR target_location LIKE ?
                ORDER BY id DESC LIMIT 20
            """, (pattern, pattern, pattern, pattern)).fetchall()

    finally:
        conn.close()

    return render_template("search/results.html", query=q, results=results)


@bp.route("/advanced")
@login_required
def advanced_search():
    """Advanced search with multiple filters."""
    conn = get_db()
    try:
        filters = {
            "classification": request.args.get("classification", ""),
            "parish": request.args.get("parish", ""),
            "status": request.args.get("status", ""),
            "stage": request.args.get("stage", ""),
            "oic": request.args.get("oic", ""),
            "date_from": request.args.get("date_from", ""),
            "date_to": request.args.get("date_to", ""),
            "crime_type": request.args.get("crime_type", ""),
        }

        has_filters = any(v for v in filters.values())
        cases = []

        if has_filters:
            query = "SELECT * FROM cases WHERE 1=1"
            params = []

            if filters["classification"]:
                query += " AND classification LIKE ?"
                params.append(f"%{filters['classification']}%")
            if filters["parish"]:
                query += " AND parish = ?"
                params.append(filters["parish"])
            if filters["status"]:
                query += " AND case_status LIKE ?"
                params.append(f"%{filters['status']}%")
            if filters["stage"]:
                query += " AND current_stage = ?"
                params.append(filters["stage"])
            if filters["oic"]:
                query += " AND (oic_name LIKE ? OR assigned_io_badge LIKE ?)"
                params.extend([f"%{filters['oic']}%", f"%{filters['oic']}%"])
            if filters["date_from"]:
                query += " AND registration_date >= ?"
                params.append(filters["date_from"])
            if filters["date_to"]:
                query += " AND registration_date <= ?"
                params.append(filters["date_to"])
            if filters["crime_type"]:
                query += " AND crime_type = ?"
                params.append(filters["crime_type"])

            # IO restriction
            if current_user.role == "io":
                query += " AND (assigned_io_badge = ? OR oic_badge = ?)"
                params.extend([current_user.badge_number, current_user.badge_number])

            query += " ORDER BY id DESC LIMIT 100"
            cases = conn.execute(query, params).fetchall()

        return render_template("search/advanced.html",
                             filters=filters, cases=cases,
                             has_filters=has_filters)
    finally:
        conn.close()


@bp.route("/person")
@login_required
def person_search():
    """Dedicated person search."""
    q = request.args.get("q", "").strip()
    results = []

    if q:
        conn = get_db()
        try:
            pattern = f"%{q}%"

            # Search all person-related fields across tables
            results = conn.execute("""
                SELECT 'Case Suspect' as source, suspect_name as name,
                       suspect_address as address, case_id as reference,
                       classification as detail
                FROM cases WHERE suspect_name LIKE ?
                UNION ALL
                SELECT 'Case Victim' as source, victim_name as name,
                       victim_address as address, case_id as reference,
                       classification as detail
                FROM cases WHERE victim_name LIKE ?
                UNION ALL
                SELECT 'Arrestee' as source, suspect_name as name,
                       suspect_address as address, arrest_id as reference,
                       offence_1 as detail
                FROM arrests WHERE suspect_name LIKE ?
                UNION ALL
                SELECT 'Witness' as source, witness_name as name,
                       witness_address as address, linked_case_id as reference,
                       witness_type as detail
                FROM witness_statements WHERE witness_name LIKE ?
                UNION ALL
                SELECT 'Intel Target' as source, target_name as name,
                       parish as address, target_id as reference,
                       threat_level as detail
                FROM intel_targets WHERE target_name LIKE ? OR aliases LIKE ?
                UNION ALL
                SELECT 'Intel Subject' as source, target_person as name,
                       target_location as address, intel_id as reference,
                       subject_matter as detail
                FROM intel_reports WHERE target_person LIKE ?
                ORDER BY name LIMIT 50
            """, (pattern, pattern, pattern, pattern, pattern, pattern, pattern)).fetchall()
        finally:
            conn.close()

    return render_template("search/person.html", query=q, results=results)


@bp.route("/exhibit")
@login_required
def exhibit_search():
    """Dedicated exhibit search."""
    q = request.args.get("q", "").strip()
    results = []

    if q:
        conn = get_db()
        try:
            pattern = f"%{q}%"
            results = conn.execute("""
                SELECT * FROM chain_of_custody
                WHERE exhibit_tag LIKE ? OR description LIKE ?
                   OR linked_case_id LIKE ? OR current_custodian LIKE ?
                   OR storage_location LIKE ?
                ORDER BY id DESC LIMIT 50
            """, (pattern, pattern, pattern, pattern, pattern)).fetchall()
        finally:
            conn.close()

    return render_template("search/exhibit.html", query=q, results=results)
