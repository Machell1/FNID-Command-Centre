"""Unit portal routes: home, dashboard, CRUD operations."""

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from ..constants import UNIT_PORTALS
from ..deadlines import get_alerts_for_user
from ..models import VALID_TABLES, generate_id, get_db, get_table_columns, log_audit
from . import _cfg_module


def _check_unit_access(unit):
    """Return True if current_user may access this unit, else flash and return False."""
    user_units = current_user.get_assigned_units()
    if unit not in user_units:
        flash("You do not have access to this unit.", "danger")
        return False
    return True

bp = Blueprint("units", __name__)


def _get_table(unit, subtype=None):
    """Map unit/subtype to database table name (validated against whitelist)."""
    tables = {
        "intel": "intel_reports",
        "operations": "operations",
        "seizures": {
            "firearms": "firearm_seizures",
            "narcotics": "narcotics_seizures",
            None: "firearm_seizures",
        },
        "arrests": "arrests",
        "forensics": {
            "custody": "chain_of_custody",
            "lab": "lab_tracking",
            None: "chain_of_custody",
        },
        "registry": {
            "cases": "cases",
            "dpp": "dpp_pipeline",
            "sop": "sop_checklists",
            "witness": "witness_statements",
            "disclosure": "disclosure_log",
            None: "cases",
        },
    }
    mapping = tables.get(unit, "cases")
    if isinstance(mapping, dict):
        table = mapping.get(subtype, mapping.get(None, "cases"))
    else:
        table = mapping

    if table not in VALID_TABLES:
        raise ValueError(f"Invalid table: {table}")
    return table


def _get_id_prefix(unit, subtype=None):
    """Map unit/subtype to ID prefix."""
    prefixes = {
        "intel": "INT",
        "operations": "OP",
        "seizures": {"firearms": "FS", "narcotics": "NS", None: "FS"},
        "arrests": "AR",
        "forensics": {"custody": "EXH", "lab": "LAB", None: "EXH"},
        "registry": {"cases": "CR", "dpp": "DPP", "sop": "SOP",
                      "witness": "WIT", "disclosure": "DISC", None: "CR"},
    }
    mapping = prefixes.get(unit, "REC")
    if isinstance(mapping, dict):
        return mapping.get(subtype, mapping.get(None, "REC"))
    return mapping


def _get_id_column(unit, subtype=None):
    """Map unit/subtype to the ID column name."""
    columns = {
        "intel": "intel_id",
        "operations": "op_id",
        "seizures": "seizure_id",
        "arrests": "arrest_id",
        "forensics": {"custody": "exhibit_tag", "lab": "lab_ref", None: "exhibit_tag"},
        "registry": {"cases": "case_id", "dpp": "linked_case_id",
                      "sop": "linked_case_id", "witness": "statement_id",
                      "disclosure": "disclosure_id", None: "case_id"},
    }
    mapping = columns.get(unit, "id")
    if isinstance(mapping, dict):
        return mapping.get(subtype, mapping.get(None, "id"))
    return mapping


def _save_record(unit, subtype, is_new, record_id=None):
    """Save a new or edited record from form data."""
    table = _get_table(unit, subtype)
    form = request.form.to_dict()

    # Validate column names against the actual table schema
    valid_columns = get_table_columns(table)
    form = {k: v for k, v in form.items() if k in valid_columns}

    officer_badge = session.get("officer_badge", "")
    officer_name = session.get("officer_name", "")

    if is_new:
        id_col = _get_id_column(unit, subtype)
        prefix = _get_id_prefix(unit, subtype)
        new_id = generate_id(prefix, table, id_col)
        form[id_col] = new_id
        form["created_by"] = officer_name
        form["record_status"] = form.get("record_status", "Draft")
        if form.get("record_status") == "Submitted":
            form["submitted_by"] = officer_name
            form["submitted_date"] = datetime.now().strftime("%Y-%m-%d")
    else:
        form["updated_at"] = datetime.now().isoformat()
        if form.get("record_status") == "Submitted" and not form.get("submitted_by"):
            form["submitted_by"] = officer_name
            form["submitted_date"] = datetime.now().strftime("%Y-%m-%d")

    # Replace empty strings with None
    form = {k: (v if v != "" else None) for k, v in form.items()}

    conn = get_db()
    try:
        if is_new:
            cols = ", ".join(form.keys())
            placeholders = ", ".join(["?"] * len(form))
            conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                         list(form.values()))
            log_audit(table, form.get(_get_id_column(unit, subtype), ""),
                      "CREATE", officer_badge, officer_name)
            flash(f"Record {form.get(_get_id_column(unit, subtype), '')} created successfully.", "success")
        else:
            set_clause = ", ".join([f"{k} = ?" for k in form.keys()])
            conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?",
                         list(form.values()) + [record_id])
            log_audit(table, str(record_id), "UPDATE", officer_badge, officer_name)
            flash("Record updated successfully.", "success")
        conn.commit()
    except Exception:
        conn.rollback()
        flash("An error occurred while saving. Please contact your administrator.", "danger")
    finally:
        conn.close()

    return redirect(url_for("units.unit_home", unit=unit))


@bp.route("/unit/<unit>")
@login_required
def unit_home(unit):
    if unit not in UNIT_PORTALS:
        flash("Invalid unit.", "danger")
        return redirect(url_for("main.home"))
    if not _check_unit_access(unit):
        return redirect(url_for("main.home"))
    session["unit"] = unit
    portal = UNIT_PORTALS[unit]

    # Fetch alerts for single-unit users (they skip the home page)
    alerts = []
    is_unit_workspace = current_user.get_single_unit() == unit
    if is_unit_workspace:
        try:
            badge = getattr(current_user, "badge_number", None)
            role = getattr(current_user, "role", "viewer")
            alerts = get_alerts_for_user(badge=badge, role=role)
        except Exception:
            pass

    conn = get_db()
    data = {}

    if unit == "intel":
        data["records"] = conn.execute(
            "SELECT * FROM intel_reports ORDER BY id DESC"
        ).fetchall()
    elif unit == "operations":
        data["records"] = conn.execute(
            "SELECT * FROM operations ORDER BY id DESC"
        ).fetchall()
    elif unit == "seizures":
        data["firearms"] = conn.execute(
            "SELECT * FROM firearm_seizures ORDER BY id DESC"
        ).fetchall()
        data["narcotics"] = conn.execute(
            "SELECT * FROM narcotics_seizures ORDER BY id DESC"
        ).fetchall()
    elif unit == "arrests":
        data["records"] = conn.execute(
            "SELECT * FROM arrests ORDER BY id DESC"
        ).fetchall()
    elif unit == "forensics":
        data["custody"] = conn.execute(
            "SELECT * FROM chain_of_custody ORDER BY id DESC"
        ).fetchall()
        data["lab"] = conn.execute(
            "SELECT * FROM lab_tracking ORDER BY id DESC"
        ).fetchall()
    elif unit == "registry":
        cases = conn.execute(
            "SELECT * FROM cases ORDER BY id DESC"
        ).fetchall()
        data["cases"] = cases
        data["dpp"] = conn.execute(
            "SELECT * FROM dpp_pipeline ORDER BY id DESC"
        ).fetchall()
        data["sop"] = conn.execute(
            "SELECT * FROM sop_checklists ORDER BY id DESC"
        ).fetchall()
        data["major_crime_register"] = conn.execute(
            "SELECT * FROM major_crime_register ORDER BY id DESC"
        ).fetchall()
        data["registry_kpis"] = {
            "sop_compliant": sum(
                1 for case in cases
                if any(marker in (case["sop_compliance"] or "")
                       for marker in ("Fully", "Substantially"))
            ),
            "dcrr_cases": sum(
                1 for case in cases
                if (case["primary_register_type"] if "primary_register_type" in case.keys() else "dcrr") == "dcrr"
            ),
            "major_register_cases": sum(
                1 for case in cases
                if (case["primary_register_type"] if "primary_register_type" in case.keys() else "") == "major_crime_register"
            ),
            "at_dpp": sum(
                1 for case in cases
                if "Referred to DPP" in (case["case_status"] or "")
            ),
            "non_compliant": sum(
                1 for case in cases
                if "Non-Compliant" in (case["sop_compliance"] or "")
            ),
        }

    conn.close()
    return render_template(f"{unit}/home.html", portal=portal, data=data, unit=unit,
                           alerts=alerts, is_unit_workspace=is_unit_workspace)


@bp.route("/unit/<unit>/dashboard")
@login_required
def unit_dashboard(unit):
    if unit not in UNIT_PORTALS:
        return redirect(url_for("main.home"))
    if not _check_unit_access(unit):
        return redirect(url_for("main.home"))

    conn = get_db()
    charts = {}

    if unit == "intel":
        charts["by_source"] = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM intel_reports GROUP BY source ORDER BY cnt DESC"
        ).fetchall()
        charts["by_priority"] = conn.execute(
            "SELECT priority, COUNT(*) as cnt FROM intel_reports GROUP BY priority"
        ).fetchall()
        charts["by_parish"] = conn.execute(
            "SELECT parish, COUNT(*) as cnt FROM intel_reports GROUP BY parish"
        ).fetchall()
        charts["total"] = conn.execute("SELECT COUNT(*) FROM intel_reports").fetchone()[0]
        charts["critical"] = conn.execute(
            "SELECT COUNT(*) FROM intel_reports WHERE priority='Critical'"
        ).fetchone()[0]
        charts["actioned"] = conn.execute(
            "SELECT COUNT(*) FROM intel_reports WHERE triage_decision LIKE 'Action%'"
        ).fetchone()[0]

    elif unit == "operations":
        charts["by_type"] = conn.execute(
            "SELECT op_type, COUNT(*) as cnt FROM operations GROUP BY op_type ORDER BY cnt DESC"
        ).fetchall()
        charts["by_outcome"] = conn.execute(
            "SELECT outcome, COUNT(*) as cnt FROM operations GROUP BY outcome"
        ).fetchall()
        charts["total"] = conn.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
        charts["successful"] = conn.execute(
            "SELECT COUNT(*) FROM operations WHERE outcome LIKE 'Successful%'"
        ).fetchone()[0]
        charts["firearms_total"] = conn.execute(
            "SELECT COALESCE(SUM(firearms_seized),0) FROM operations"
        ).fetchone()[0]

    elif unit == "seizures":
        charts["fa_by_type"] = conn.execute(
            "SELECT firearm_type, COUNT(*) as cnt FROM firearm_seizures GROUP BY firearm_type ORDER BY cnt DESC"
        ).fetchall()
        charts["na_by_type"] = conn.execute(
            "SELECT drug_type, COUNT(*) as cnt FROM narcotics_seizures GROUP BY drug_type ORDER BY cnt DESC"
        ).fetchall()
        charts["fa_total"] = conn.execute("SELECT COUNT(*) FROM firearm_seizures").fetchone()[0]
        charts["na_total"] = conn.execute("SELECT COUNT(*) FROM narcotics_seizures").fetchone()[0]
        charts["ibis_hits"] = conn.execute(
            "SELECT COUNT(*) FROM firearm_seizures WHERE ibis_status LIKE 'Hit%'"
        ).fetchone()[0]

    elif unit == "arrests":
        charts["by_bail"] = conn.execute(
            "SELECT bail_status, COUNT(*) as cnt FROM arrests GROUP BY bail_status"
        ).fetchall()
        charts["total"] = conn.execute("SELECT COUNT(*) FROM arrests").fetchone()[0]
        charts["compliant_48"] = conn.execute(
            "SELECT COUNT(*) FROM arrests WHERE charge_within_48hr='Yes'"
        ).fetchone()[0]

    elif unit == "forensics":
        charts["by_type"] = conn.execute(
            "SELECT exhibit_type, COUNT(*) as cnt FROM chain_of_custody GROUP BY exhibit_type ORDER BY cnt DESC"
        ).fetchall()
        charts["by_cert"] = conn.execute(
            "SELECT certificate_status, COUNT(*) as cnt FROM lab_tracking GROUP BY certificate_status"
        ).fetchall()
        charts["total_exhibits"] = conn.execute("SELECT COUNT(*) FROM chain_of_custody").fetchone()[0]
        charts["certs_issued"] = conn.execute(
            "SELECT COUNT(*) FROM lab_tracking WHERE certificate_status LIKE '%Issued%'"
        ).fetchone()[0]

    elif unit == "registry":
        charts["by_status"] = conn.execute(
            "SELECT case_status, COUNT(*) as cnt FROM cases GROUP BY case_status ORDER BY cnt DESC"
        ).fetchall()
        charts["by_classification"] = conn.execute(
            "SELECT classification, COUNT(*) as cnt FROM cases GROUP BY classification ORDER BY cnt DESC"
        ).fetchall()
        charts["by_compliance"] = conn.execute(
            "SELECT sop_compliance, COUNT(*) as cnt FROM cases GROUP BY sop_compliance"
        ).fetchall()
        charts["by_dpp"] = conn.execute(
            "SELECT dpp_status, COUNT(*) as cnt FROM cases WHERE dpp_status IS NOT NULL GROUP BY dpp_status"
        ).fetchall()
        charts["total"] = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        charts["compliant"] = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE sop_compliance LIKE 'Fully%' OR sop_compliance LIKE 'Substantially%'"
        ).fetchone()[0]
        charts["at_dpp"] = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE case_status LIKE 'Referred to DPP%'"
        ).fetchone()[0]

    conn.close()
    return render_template(f"{unit}/dashboard.html",
                           portal=UNIT_PORTALS[unit],
                           charts=charts, unit=unit)


@bp.route("/unit/<unit>/new", methods=["GET", "POST"])
@bp.route("/unit/<unit>/new/<subtype>", methods=["GET", "POST"])
@login_required
def new_record(unit, subtype=None):
    if unit not in UNIT_PORTALS:
        return redirect(url_for("main.home"))
    if not _check_unit_access(unit):
        return redirect(url_for("main.home"))

    if unit == "registry" and subtype in (None, "cases"):
        flash("Use the registry intake workflow to choose DCRR or Major Crime Register.", "info")
        return redirect(url_for("cases.intake"))

    # Basic users must use the report upload flow instead of manual entry
    if current_user.get_single_unit():
        flash("Please upload a report. The bot will extract the information.", "info")
        return redirect(url_for("upload.submit_report"))

    if request.method == "POST":
        return _save_record(unit, subtype, is_new=True)

    cfg = _cfg_module()
    return render_template(f"{unit}/form.html",
                           portal=UNIT_PORTALS[unit],
                           unit=unit, subtype=subtype,
                           record=None, cfg=cfg, is_new=True)


@bp.route("/unit/<unit>/edit/<int:record_id>", methods=["GET", "POST"])
@bp.route("/unit/<unit>/edit/<int:record_id>/<subtype>", methods=["GET", "POST"])
@login_required
def edit_record(unit, record_id, subtype=None):
    if unit not in UNIT_PORTALS:
        return redirect(url_for("main.home"))
    if not _check_unit_access(unit):
        return redirect(url_for("main.home"))

    conn = get_db()
    table = _get_table(unit, subtype)
    record = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
    conn.close()

    if not record:
        flash("Record not found.", "danger")
        return redirect(url_for("units.unit_home", unit=unit))

    if request.method == "POST":
        return _save_record(unit, subtype, is_new=False, record_id=record_id)

    cfg = _cfg_module()
    return render_template(f"{unit}/form.html",
                           portal=UNIT_PORTALS[unit],
                           unit=unit, subtype=subtype,
                           record=record, cfg=cfg, is_new=False)
