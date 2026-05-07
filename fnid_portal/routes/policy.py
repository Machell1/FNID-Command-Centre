"""
Case Management Policy & Forms Routes

Provides access to JCF Case Management Policy information and
downloadable/editable Case Reference (CR) forms per
JCF/FW/PL/C&S/0001/2024.

NB: All related forms must be referred to as Case Reference Form
(not Crime Reference Form) per policy.
"""

import os

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    send_from_directory,
    url_for,
)
from flask_login import login_required

from ..constants import (
    CASE_LIFECYCLE_STAGES,
    CASE_STATUS,
    CR_FORM_TYPES,
    JCF_ABBREVIATIONS,
    REVIEW_TIMELINES,
    VETTING_TIMELINES,
)
from ..official_cr_forms import (
    OFFICIAL_CR_FORM_DEFINITIONS,
    OFFICIAL_FORM_DIR,
    get_form_layout,
    is_official_form,
    source_filename,
)

bp = Blueprint("policy", __name__, url_prefix="/policy")
REGISTRY_REGISTER_DIR = OFFICIAL_FORM_DIR.parent / "registers"
REGISTRY_REGISTER_WORKBOOK = "fnid_registry_registers_workbook.xlsx"


# ── Policy Overview Page ─────────────────────────────────────────────

@bp.route("/")
@login_required
def policy_home():
    """Case Management Policy overview page."""
    return render_template(
        "policy/home.html",
        abbreviations=JCF_ABBREVIATIONS,
        case_statuses=CASE_STATUS,
        lifecycle_stages=CASE_LIFECYCLE_STAGES,
        review_timelines=REVIEW_TIMELINES,
        vetting_timelines=VETTING_TIMELINES,
    )


# ── Definitions Page ─────────────────────────────────────────────────

@bp.route("/definitions")
@login_required
def definitions():
    """Policy definitions per Section 6.0."""
    return render_template("policy/definitions.html")


# ── Roles & Responsibilities ─────────────────────────────────────────

@bp.route("/responsibilities")
@login_required
def responsibilities():
    """Roles and responsibilities per Sections 7.0-8.0."""
    return render_template("policy/responsibilities.html")


# ── SOPs Page ────────────────────────────────────────────────────────

@bp.route("/sops")
@login_required
def sops():
    """Standard Operating Procedures per Section 9.0."""
    return render_template(
        "policy/sops.html",
        review_timelines=REVIEW_TIMELINES,
        vetting_timelines=VETTING_TIMELINES,
    )


# ── Forms Library ────────────────────────────────────────────────────

@bp.route("/forms")
@login_required
def forms_library():
    """Case Reference Forms library - browse, download, or fill online."""
    return render_template(
        "policy/forms_library.html",
        cr_form_types=CR_FORM_TYPES,
        form_definitions=OFFICIAL_CR_FORM_DEFINITIONS,
    )


# ── Blank Form View (editable in browser) ───────────────────────────

@bp.route("/registers/workbook/download")
@login_required
def download_registry_workbook():
    """Download the editable Excel registry register workbook."""
    workbook_path = REGISTRY_REGISTER_DIR / REGISTRY_REGISTER_WORKBOOK
    if not workbook_path.exists():
        flash("Registry register workbook is not available.", "danger")
        return redirect(url_for("policy.forms_library"))

    return send_from_directory(
        str(REGISTRY_REGISTER_DIR),
        REGISTRY_REGISTER_WORKBOOK,
        as_attachment=True,
        download_name="FNID Official Registry Register Workbook.xlsx",
    )


@bp.route("/forms/<form_type>/blank")
@login_required
def blank_form(form_type):
    """Open the exact uploaded official Word template."""
    form_type = form_type.upper()
    if not is_official_form(form_type):
        flash(f"Unknown form type: {form_type}", "danger")
        return redirect(url_for("policy.forms_library"))

    return redirect(url_for("policy.download_form", form_type=form_type))


@bp.route("/forms/<form_type>/browser")
@login_required
def browser_form(form_type):
    """Render the browser workflow-capture version of an official CR form."""
    form_type = form_type.upper()
    form_def = OFFICIAL_CR_FORM_DEFINITIONS.get(form_type)
    if not form_def or not is_official_form(form_type):
        flash(f"Unknown form type: {form_type}", "danger")
        return redirect(url_for("policy.forms_library"))

    return render_template(
        "policy/blank_form.html",
        form_type=form_type,
        form_def=form_def,
        layout=get_form_layout(form_type),
        form_data={},
        mode="blank",
        print_only=False,
        cr_form_types=CR_FORM_TYPES,
    )


# ── Download blank form as printable HTML ────────────────────────────

@bp.route("/forms/<form_type>/download")
@login_required
def download_form(form_type):
    """Download the original official Word template for a CR form."""
    form_type = form_type.upper()
    if not is_official_form(form_type):
        flash(f"Unknown form type: {form_type}", "danger")
        return redirect(url_for("policy.forms_library"))

    return send_from_directory(
        str(OFFICIAL_FORM_DIR),
        source_filename(form_type),
        as_attachment=True,
    )


@bp.route("/forms/<form_type>/print")
@login_required
def print_blank_form(form_type):
    """Open the exact uploaded official Word template for printing in Word."""
    form_type = form_type.upper()
    if not is_official_form(form_type):
        flash(f"Unknown form type: {form_type}", "danger")
        return redirect(url_for("policy.forms_library"))

    return redirect(url_for("policy.download_form", form_type=form_type))


# ── Uploaded form files (PDF/DOCX) ──────────────────────────────────

@bp.route("/forms/uploads/<filename>")
@login_required
def serve_form_upload(filename):
    """Serve uploaded form files from the forms directory."""
    from werkzeug.utils import secure_filename as _secure
    safe_name = _secure(filename)
    if not safe_name:
        from flask import abort
        abort(400)
    forms_dir = os.path.join(current_app.config.get("UPLOAD_DIR", "data/uploads"), "forms")
    if not os.path.isdir(forms_dir):
        os.makedirs(forms_dir, exist_ok=True)
    return send_from_directory(forms_dir, safe_name)


def _generate_printable_form_html(form_type, form_def, form_name):
    """Generate a standalone printable HTML form."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>JCF {form_type} - {form_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; font-size: 12px; }}
        .header {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }}
        .header h2 {{ margin: 5px 0; }}
        .header h3 {{ margin: 5px 0; color: #333; }}
        .header small {{ color: #666; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; }}
        th, td {{ border: 1px solid #333; padding: 6px 8px; text-align: left; vertical-align: top; }}
        th {{ background-color: #f0f0f0; font-weight: bold; width: 35%; }}
        td {{ min-height: 25px; }}
        .section-title {{ background-color: #1a3a5c; color: white; padding: 6px 10px;
                         font-weight: bold; margin-top: 15px; margin-bottom: 5px; }}
        .form-field {{ height: 30px; border-bottom: 1px solid #999; }}
        .form-field-large {{ height: 80px; border: 1px solid #999; }}
        .footer {{ margin-top: 30px; border-top: 1px solid #000;
                  padding-top: 10px; font-size: 10px; text-align: center; }}
        .signature-line {{ margin-top: 40px; }}
        .signature-line span {{ display: inline-block; width: 45%; border-top: 1px solid #000;
                               text-align: center; padding-top: 5px; margin: 0 2%; }}
        @media print {{
            body {{ margin: 10mm; }}
            .no-print {{ display: none; }}
        }}
        input, textarea, select {{
            width: 100%; border: none; border-bottom: 1px dotted #999;
            padding: 3px; font-size: 12px; font-family: Arial, sans-serif;
        }}
        textarea {{ min-height: 60px; resize: vertical; }}
    </style>
</head>
<body>
    <div class="no-print" style="background: #fffbcc; padding: 10px; margin-bottom: 15px; border: 1px solid #e6d800;">
        <strong>Instructions:</strong> Fill in the fields below, then print (Ctrl+P) or save.
        <button onclick="window.print()"
                style="margin-left: 10px; padding: 5px 15px; cursor: pointer;">Print Form</button>
    </div>

    <div class="header">
        <h2>JAMAICA CONSTABULARY FORCE</h2>
        <h3>{form_type} - {form_name}</h3>
        <small>JCF/FW/PL/C&S/0001/2024 | Case Reference Form</small>
    </div>

    <table>
        <tr>
            <th>Case Reference No.:</th>
            <td><input type="text" placeholder="Enter CR#"></td>
            <th>Date:</th>
            <td><input type="date"></td>
        </tr>
    </table>
"""

    for section in form_def.get("sections", []):
        html += f'    <div class="section-title">{section["title"]}</div>\n'
        html += '    <table>\n'
        for field in section.get("fields", []):
            label = field["label"]
            required = " *" if field.get("required") else ""
            ftype = field.get("type", "text")

            html += f'        <tr><th>{label}{required}</th><td>'
            if ftype == "textarea":
                html += '<textarea placeholder=""></textarea>'
            elif ftype == "select":
                options = field.get("options_list", [])
                html += '<select><option value="">-- Select --</option>'
                for opt in options:
                    html += f'<option value="{opt}">{opt}</option>'
                html += '</select>'
            elif ftype == "date":
                html += '<input type="date">'
            elif ftype == "time":
                html += '<input type="time">'
            elif ftype == "number":
                html += '<input type="number">'
            else:
                html += '<input type="text" placeholder="">'
            html += '</td></tr>\n'
        html += '    </table>\n'

    html += """
    <div class="signature-line">
        <span>Signature of Officer</span>
        <span>Date</span>
    </div>

    <div class="footer">
        <p>Jamaica Constabulary Force | Case Management Policy & Standard Operating Procedures</p>
        <p>JCF/FW/PL/C&S/0001/2024 | NB: This is a Case Reference Form (not Crime Reference Form)</p>
    </div>
</body>
</html>"""

    return html
