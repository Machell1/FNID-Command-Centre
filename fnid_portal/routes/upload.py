"""Report upload routes: upload, bot processing, review, and confirm."""

import os
import uuid
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ..bot import process_report
from ..constants import UNIT_PORTALS
from ..models import generate_id, get_db, get_table_columns, log_audit

bp = Blueprint("upload", __name__, url_prefix="/upload")

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "jpg", "jpeg", "png"}


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route("/", methods=["GET", "POST"])
@login_required
def submit_report():
    """Upload a report for bot processing."""
    # Determine user's unit context
    single_unit = current_user.get_single_unit()

    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("Please select a file to upload.", "warning")
            return redirect(url_for("upload.submit_report"))

        if not _allowed(file.filename):
            flash("File type not allowed. Use PDF, DOCX, TXT, JPG, or PNG.", "danger")
            return redirect(url_for("upload.submit_report"))

        # Save the uploaded file
        upload_dir = os.path.join(current_app.config["UPLOAD_DIR"], "reports")
        os.makedirs(upload_dir, exist_ok=True)

        ext = file.filename.rsplit(".", 1)[1].lower()
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(upload_dir, stored_name)
        file.save(filepath)

        # Log the upload
        officer_badge = session.get("officer_badge", "")
        officer_name = session.get("officer_name", "")
        log_audit("report_uploads", stored_name, "UPLOAD",
                  officer_badge, officer_name,
                  f"Report uploaded: {secure_filename(file.filename)}")

        # Process with bot
        result = process_report(filepath, user_unit=single_unit)

        # Store result in session for the review page
        session["bot_result"] = {
            "filepath": filepath,
            "original_filename": secure_filename(file.filename),
            "stored_name": stored_name,
            "target_unit": result["target_unit"],
            "unit_scores": result["unit_scores"],
            "fields": result["fields"],
            "meta": result["meta"],
            "guidance": result["guidance"],
            "subtype": result["subtype"],
            "text_preview": result["text"][:2000],
        }

        return redirect(url_for("upload.review"))

    return render_template("upload/submit.html",
                           single_unit=single_unit,
                           portals=UNIT_PORTALS)


@bp.route("/review", methods=["GET", "POST"])
@login_required
def review():
    """Review bot-extracted data and guidance before saving."""
    bot_result = session.get("bot_result")
    if not bot_result:
        flash("No report to review. Please upload a report first.", "warning")
        return redirect(url_for("upload.submit_report"))

    target_unit = bot_result["target_unit"]
    subtype = bot_result.get("subtype")
    fields = bot_result["fields"]
    guidance = bot_result["guidance"]

    if request.method == "POST":
        # User confirmed - save the record
        action = request.form.get("action", "save")

        if action == "discard":
            session.pop("bot_result", None)
            flash("Report discarded.", "info")
            single_unit = current_user.get_single_unit()
            if single_unit:
                return redirect(url_for("units.unit_home", unit=single_unit))
            return redirect(url_for("main.home"))

        # Get the confirmed unit and subtype
        confirmed_unit = request.form.get("target_unit", target_unit)
        confirmed_subtype = request.form.get("subtype", subtype)

        # Validate unit
        if confirmed_unit not in UNIT_PORTALS:
            flash("Invalid unit selected.", "danger")
            return redirect(url_for("upload.review"))

        # Check unit access
        user_units = current_user.get_assigned_units()
        if confirmed_unit not in user_units:
            flash("You do not have access to this unit.", "danger")
            return redirect(url_for("upload.review"))

        # Build form data from the review form fields
        form_data = {}
        for key in request.form:
            if key not in ("csrf_token", "action", "target_unit", "subtype",
                           "record_status"):
                val = request.form[key]
                if val:
                    form_data[key] = val

        # Determine table and save
        from .units import _get_id_column, _get_id_prefix, _get_table
        table = _get_table(confirmed_unit, confirmed_subtype)
        valid_columns = get_table_columns(table)
        form_data = {k: v for k, v in form_data.items() if k in valid_columns}

        # Set metadata
        officer_badge = session.get("officer_badge", "")
        officer_name = session.get("officer_name", "")
        id_col = _get_id_column(confirmed_unit, confirmed_subtype)
        prefix = _get_id_prefix(confirmed_unit, confirmed_subtype)
        new_id = generate_id(prefix, table, id_col)

        form_data[id_col] = new_id
        form_data["created_by"] = officer_name

        record_status = request.form.get("record_status", "Draft")
        form_data["record_status"] = record_status
        if record_status == "Submitted":
            form_data["submitted_by"] = officer_name
            form_data["submitted_date"] = datetime.now().strftime("%Y-%m-%d")

        # Link to uploaded report file
        if "notes" in valid_columns:
            existing_notes = form_data.get("notes", "") or ""
            source_note = f"[Bot-extracted from: {bot_result['original_filename']}]"
            form_data["notes"] = f"{source_note}\n{existing_notes}".strip()

        # Replace empty strings with None
        form_data = {k: (v if v != "" else None) for k, v in form_data.items()}

        conn = get_db()
        try:
            cols = ", ".join(form_data.keys())
            placeholders = ", ".join(["?"] * len(form_data))
            conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                         list(form_data.values()))
            log_audit(table, new_id, "CREATE_FROM_REPORT",
                      officer_badge, officer_name,
                      f"Created from uploaded report: {bot_result['original_filename']}")
            conn.commit()
            flash(f"Record {new_id} created successfully from your report.", "success")
        except Exception:
            conn.rollback()
            flash("Error saving record. Please contact your administrator.", "danger")
        finally:
            conn.close()

        session.pop("bot_result", None)
        return redirect(url_for("units.unit_home", unit=confirmed_unit))

    # GET - render the review page
    # Build form field definitions for the target unit
    from .units import _get_table
    table = _get_table(target_unit, subtype)
    table_columns = get_table_columns(table)

    # Load constants for dropdowns
    from . import _cfg_module
    cfg = _cfg_module()

    return render_template("upload/review.html",
                           bot_result=bot_result,
                           target_unit=target_unit,
                           subtype=subtype,
                           fields=fields,
                           guidance=guidance,
                           table_columns=table_columns,
                           portal=UNIT_PORTALS.get(target_unit, {}),
                           portals=UNIT_PORTALS,
                           cfg=cfg)
