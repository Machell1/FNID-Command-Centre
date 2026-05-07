"""Data import and export routes."""

import os
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for

from ..constants import UNIT_PORTALS
from ..models import get_db

bp = Blueprint("data", __name__)


def _get_table(unit):
    """Get default table for a unit."""
    tables = {
        "intel": "intel_reports",
        "operations": "operations",
        "seizures": "firearm_seizures",
        "arrests": "arrests",
        "forensics": "chain_of_custody",
        "registry": "cases",
    }
    return tables.get(unit, "cases")


@bp.route("/import", methods=["GET", "POST"])
def import_data():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file selected.", "danger")
            return redirect(url_for("data.import_data"))

        file = request.files["file"]
        if file.filename == "":
            flash("No file selected.", "danger")
            return redirect(url_for("data.import_data"))

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in (".docx", ".xlsx"):
            flash("Only .docx and .xlsx files are supported.", "danger")
            return redirect(url_for("data.import_data"))

        from werkzeug.utils import secure_filename
        upload_dir = current_app.config.get("UPLOAD_DIR", "data/uploads")
        os.makedirs(upload_dir, exist_ok=True)
        safe_name = secure_filename(file.filename)
        filepath = os.path.join(upload_dir, safe_name)
        file.save(filepath)

        flash(f"File '{safe_name}' uploaded successfully.", "info")
        return redirect(url_for("data.import_data"))

    return render_template("import.html")


@bp.route("/export/<unit>")
def export_unit(unit):
    if unit not in UNIT_PORTALS:
        flash("Invalid unit.", "danger")
        return redirect(url_for("main.home"))

    try:
        from openpyxl import Workbook as XlWorkbook
    except ImportError:
        flash("openpyxl required for export.", "danger")
        return redirect(url_for("units.unit_home", unit=unit))

    table = _get_table(unit)
    conn = get_db()
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    columns = [desc[0] for desc in conn.execute(f"SELECT * FROM {table} LIMIT 0").description]
    conn.close()

    wb = XlWorkbook()
    ws = wb.active
    ws.title = unit.title()
    ws.append(columns)
    for row in rows:
        ws.append(list(row))

    export_dir = current_app.config.get("EXPORT_DIR", "data/exports")
    os.makedirs(export_dir, exist_ok=True)
    filename = f"FNID_{unit}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    filepath = os.path.join(export_dir, filename)
    wb.save(filepath)

    return send_file(filepath, as_attachment=True, download_name=filename)


@bp.route("/export/workbook")
def export_workbook():
    """Export the full JCF FO 4032 Operational Workbook (all 10 sheets)."""
    from ..workbook import generate_operational_workbook

    conn = get_db()
    try:
        wb = generate_operational_workbook(conn)
    finally:
        conn.close()

    export_dir = current_app.config.get("EXPORT_DIR", "data/exports")
    os.makedirs(export_dir, exist_ok=True)
    filename = f"FNID_Operational_Workbook_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    filepath = os.path.join(export_dir, filename)
    wb.save(filepath)

    return send_file(filepath, as_attachment=True, download_name=filename)
