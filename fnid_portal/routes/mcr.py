"""
Morning Crime Report (MCR) Routes

Views for MCR compilation, review, briefing, and leads reports.
"""

import json
from datetime import datetime

from flask import Blueprint, current_app, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..mcr_engine import _get_mcr_window, compile_mcr, generate_leads_report
from ..models import get_db, log_audit
from ..official_cr_forms import collect_form_data, get_form_layout
from ..pdf_export import pdf_base_css, pdf_header_html, render_pdf
from ..rbac import permission_required
from . import _cfg_module

bp = Blueprint("mcr", __name__, url_prefix="/mcr")
CR7_FORM_TYPE = "CR7"
CR7_MAX_ROWS = 17


def _cr7_form_id(mcr_date):
    """Stable official CR7 form id for a daily MCR."""
    return f"CR7/MCR/{mcr_date}"


def _json_form_data(row):
    """Decode stored CR7 JSON form data safely."""
    if not row or not row["form_data"]:
        return {}
    try:
        return json.loads(row["form_data"])
    except (TypeError, json.JSONDecodeError):
        return {}


def _cr7_field(base, row_index):
    """Return the generated CR7 field name for a repeated official-template row."""
    return base if row_index == 1 else f"{base}_{row_index}"


def _fetch_mcr_entries(conn, mcr_date):
    """Load MCR matters for a date in official CR7 order."""
    return conn.execute("""
        SELECT * FROM mcr_entries
        WHERE mcr_date = ?
        ORDER BY fnid_relevant DESC, classification, id
    """, (mcr_date,)).fetchall()


def _cr7_prefill_data(mcr_date, entries, current_user_name, existing=None):
    """Map MCR matter rows into the uploaded official CR7 template fields."""
    try:
        window_start, window_end = _get_mcr_window(mcr_date)
        period = (
            f"FNID Area 3 for period "
            f"{window_start.strftime('%Y-%m-%d %H:%M')} to "
            f"{window_end.strftime('%Y-%m-%d %H:%M')}"
        )
    except ValueError:
        period = f"FNID Area 3 for period ending {mcr_date}"

    data = {"cr7_area_division_station_for_period": period}
    sender = current_user_name or "FNID Area 3 Registry"

    for index, entry in enumerate(entries[:CR7_MAX_ROWS], start=1):
        data[_cr7_field("cr7_date_and_time_committed", index)] = (
            (entry["window_start"] or "")[:16]
        )
        data[_cr7_field("cr7_date_and_time_reported", index)] = mcr_date
        data[_cr7_field("cr7_offences_s", index)] = entry["classification"] or ""
        data[_cr7_field("cr7_where_committed", index)] = entry["parish"] or ""
        data[_cr7_field("cr7_particular_of_victim_s", index)] = (
            f"{entry['source_table']}: {entry['source_id']}"
        )
        data[_cr7_field("cr7_name_d_o_b_and_occipation_of_victim_s", index)] = ""
        data[_cr7_field("cr7_drugs_firearm_ammo_etc", index)] = (
            "FNID relevant" if entry["fnid_relevant"] else ""
        )
        data[_cr7_field("cr7_investigator_and_station", index)] = (
            entry["compiled_by"] or sender
        )
        data[_cr7_field("cr7_brief_of_case", index)] = entry["summary"] or ""
        data[_cr7_field("cr7_sender_and_station", index)] = sender

    data["cr7_signature_manager_commander"] = sender
    if existing:
        data.update({key: value for key, value in existing.items() if value not in (None, "")})
    return data


@bp.route("/")
@login_required
@permission_required("mcr", "read")
def mcr_dashboard():
    """MCR dashboard — latest report and history."""
    conn = get_db()
    try:
        # Get distinct MCR dates
        dates = conn.execute("""
            SELECT DISTINCT mcr_date, COUNT(*) as total,
                   SUM(fnid_relevant) as fnid_count,
                   compiled_by
            FROM mcr_entries
            GROUP BY mcr_date
            ORDER BY mcr_date DESC
            LIMIT 30
        """).fetchall()

        # Get today's entries if available
        today = datetime.now().strftime("%Y-%m-%d")
        today_entries = conn.execute("""
            SELECT * FROM mcr_entries WHERE mcr_date = ?
            ORDER BY fnid_relevant DESC, id
        """, (today,)).fetchall()

        return render_template("mcr/dashboard.html",
                             dates=dates, today_entries=today_entries,
                             today=today)
    finally:
        conn.close()


@bp.route("/compile", methods=["POST"])
@login_required
@permission_required("mcr", "compile")
def compile():
    """Manually trigger MCR compilation."""
    target_date = request.form.get("target_date")
    name = current_user.full_name

    try:
        mcr_date, entries = compile_mcr(target_date=target_date, compiled_by=name)
        log_audit("mcr_entries", mcr_date, "COMPILE",
                 current_user.badge_number, name,
                 f"Compiled {len(entries)} entries")
        flash(f"MCR compiled for {mcr_date}: {len(entries)} entries.", "success")
    except Exception as e:
        current_app.logger.exception("MCR compile error"); flash("An error occurred compiling the MCR.", "danger")

    return redirect(url_for("mcr.mcr_dashboard"))


@bp.route("/new")
@login_required
@permission_required("mcr", "create")
def new_mcr_report():
    """Open the official CR7 Morning Crime Report for today's date."""
    today = datetime.now().strftime("%Y-%m-%d")
    return redirect(url_for("mcr.cr7_form", date=today))


@bp.route("/cr7")
@login_required
@permission_required("mcr", "create")
def cr7_today():
    """Open the official CR7 Morning Crime Report for today's date."""
    today = datetime.now().strftime("%Y-%m-%d")
    return redirect(url_for("mcr.cr7_form", date=today))


@bp.route("/<date>/cr7", methods=["GET", "POST"])
@login_required
@permission_required("mcr", "create")
def cr7_form(date):
    """Create, edit, print, and submit the official CR7 MCR form."""
    layout = get_form_layout(CR7_FORM_TYPE)
    conn = get_db()
    try:
        entries = _fetch_mcr_entries(conn, date)
        form_rec = conn.execute(
            "SELECT * FROM mcr_cr7_forms WHERE mcr_date = ?",
            (date,),
        ).fetchone()
        form_id = form_rec["form_id"] if form_rec else _cr7_form_id(date)

        if request.method == "POST":
            form_data = collect_form_data(CR7_FORM_TYPE, request.form)
            status = request.form.get("form_status", "Draft")
            now = datetime.now().isoformat()
            name = current_user.full_name

            if form_rec:
                conn.execute("""
                    UPDATE mcr_cr7_forms
                    SET form_data = ?, status = ?, updated_at = ?
                    WHERE id = ?
                """, (json.dumps(form_data), status, now, form_rec["id"]))
                action = "UPDATE"
            else:
                conn.execute("""
                    INSERT INTO mcr_cr7_forms
                    (form_id, mcr_date, form_type, form_data, status,
                     created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    form_id, date, CR7_FORM_TYPE, json.dumps(form_data),
                    status, name, now, now,
                ))
                action = "CREATE"

            if status == "Submitted":
                conn.execute("""
                    UPDATE mcr_cr7_forms
                    SET submitted_by = COALESCE(submitted_by, ?),
                        submitted_at = COALESCE(submitted_at, ?)
                    WHERE form_id = ?
                """, (name, now, form_id))

            conn.commit()
            log_audit(
                "mcr_cr7_forms", form_id, action,
                current_user.badge_number, name,
                f"Official CR7 for MCR date {date}",
            )
            flash(f"Official CR7 Morning Crime Report saved as {status}.", "success")
            return redirect(url_for("mcr.cr7_form", date=date))

        existing_data = _json_form_data(form_rec)
        form_data = _cr7_prefill_data(date, entries, current_user.full_name, existing_data)
        overflow_count = max(0, len(entries) - CR7_MAX_ROWS)

        return render_template(
            "mcr/cr7_form.html",
            mcr_date=date,
            form_id=form_id,
            form_type=CR7_FORM_TYPE,
            form_def={"name": "Morning Crime Report"},
            form_rec=form_rec,
            form_data=form_data,
            layout=layout,
            mode="edit",
            entries=entries,
            overflow_count=overflow_count,
        )
    finally:
        conn.close()


@bp.route("/entries/new", methods=["GET", "POST"])
@bp.route("/<date>/entries/new", methods=["GET", "POST"])
@login_required
@permission_required("mcr", "create")
def new_entry(date=None):
    """Enter a secondary MCR line item manually."""
    today = datetime.now().strftime("%Y-%m-%d")
    form = {
        "mcr_date": date or request.args.get("date") or today,
        "source_table": "Manual MCR Entry",
        "source_id": "",
        "classification": "",
        "parish": "",
        "summary": "",
        "fnid_relevant": "1",
        "lead_suggestions": "",
    }

    if request.method == "POST":
        form.update({
            "mcr_date": request.form.get("mcr_date", "").strip(),
            "source_table": request.form.get("source_table", "").strip(),
            "source_id": request.form.get("source_id", "").strip(),
            "classification": request.form.get("classification", "").strip(),
            "parish": request.form.get("parish", "").strip(),
            "summary": request.form.get("summary", "").strip(),
            "fnid_relevant": "1" if request.form.get("fnid_relevant") else "0",
            "lead_suggestions": request.form.get("lead_suggestions", "").strip(),
        })

        if not form["mcr_date"] or not form["source_id"] or not form["summary"]:
            flash("Report date, source reference number, and summary are required.", "danger")
        else:
            try:
                window_start, window_end = _get_mcr_window(form["mcr_date"])
            except ValueError:
                flash("Report date must be a valid date.", "danger")
            else:
                leads = [
                    line.strip() for line in form["lead_suggestions"].splitlines()
                    if line.strip()
                ]
                conn = get_db()
                try:
                    conn.execute("""
                        INSERT INTO mcr_entries
                        (mcr_date, window_start, window_end, source_table, source_id,
                         classification, parish, summary, fnid_relevant,
                         lead_suggestions, compiled_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        form["mcr_date"],
                        window_start.strftime("%Y-%m-%d %H:%M:%S"),
                        window_end.strftime("%Y-%m-%d %H:%M:%S"),
                        form["source_table"] or "Manual MCR Entry",
                        form["source_id"],
                        form["classification"],
                        form["parish"],
                        form["summary"],
                        1 if form["fnid_relevant"] == "1" else 0,
                        json.dumps(leads) if leads else None,
                        current_user.full_name,
                    ))
                    conn.commit()
                finally:
                    conn.close()

                log_audit(
                    "mcr_entries", form["mcr_date"], "CREATE",
                    current_user.badge_number, current_user.full_name,
                    f"Entered MCR matter from {form['source_table'] or 'Manual MCR Entry'}: {form['source_id']}",
                )
                flash("MCR matter entered successfully.", "success")
                return redirect(url_for("mcr.view_mcr", date=form["mcr_date"]))

    return render_template(
        "mcr/form.html",
        form=form,
        cfg=_cfg_module(),
        source_options=[
            "Manual MCR Entry",
            "DCRR",
            "Major Crime Register",
            "Station Diary",
            "Case Reference No.",
            "Intelligence Report",
            "Operations Report",
            "Arrest Report",
            "Seizure Report",
            "Other",
        ],
    )


@bp.route("/<date>")
@login_required
@permission_required("mcr", "read")
def view_mcr(date):
    """View MCR for a specific date."""
    conn = get_db()
    try:
        entries = conn.execute("""
            SELECT * FROM mcr_entries WHERE mcr_date = ?
            ORDER BY fnid_relevant DESC, classification, id
        """, (date,)).fetchall()

        fnid_entries = [e for e in entries if e["fnid_relevant"]]
        general_entries = [e for e in entries if not e["fnid_relevant"]]

        return render_template("mcr/report.html",
                             mcr_date=date, entries=entries,
                             fnid_entries=fnid_entries,
                             general_entries=general_entries)
    finally:
        conn.close()


@bp.route("/<date>/briefing")
@login_required
@permission_required("mcr", "read")
def briefing(date):
    """Operational briefing view from MCR data."""
    conn = get_db()
    try:
        entries = conn.execute("""
            SELECT * FROM mcr_entries WHERE mcr_date = ? AND fnid_relevant = 1
            ORDER BY classification, id
        """, (date,)).fetchall()

        # Group by parish
        parish_groups = {}
        for e in entries:
            p = e["parish"] or "Unknown"
            parish_groups.setdefault(p, []).append(e)

        # Group by classification
        class_groups = {}
        for e in entries:
            c = e["classification"] or "Unknown"
            class_groups.setdefault(c, []).append(e)

        return render_template("mcr/briefing.html",
                             mcr_date=date, entries=entries,
                             parish_groups=parish_groups,
                             class_groups=class_groups)
    finally:
        conn.close()


@bp.route("/<date>/leads")
@login_required
@permission_required("mcr", "read")
def leads(date):
    """Leads report from MCR data."""
    report = generate_leads_report(date)
    return render_template("mcr/leads.html", mcr_date=date, report=report)


@bp.route("/<date>/pdf")
@login_required
@permission_required("mcr", "read")
def mcr_pdf(date):
    """Export MCR as PDF."""
    conn = get_db()
    try:
        entries = conn.execute("""
            SELECT * FROM mcr_entries WHERE mcr_date = ?
            ORDER BY fnid_relevant DESC, id
        """, (date,)).fetchall()

        html = f"""<!DOCTYPE html><html><head>{pdf_base_css()}</head><body>
        {pdf_header_html(f'Morning Crime Report — {date}')}
        <p><strong>FNID-Relevant Matters: {sum(1 for e in entries if e['fnid_relevant'])}</strong>
         | Total Matters: {len(entries)}</p>
        <table>
            <thead>
                <tr><th>Source</th><th>Classification</th><th>Parish</th><th>Summary</th><th>FNID</th></tr>
            </thead>
            <tbody>
        """
        for e in entries:
            fnid = "YES" if e["fnid_relevant"] else ""
            html += f"""<tr>
                <td>{e['source_table']}</td>
                <td>{e['classification'] or ''}</td>
                <td>{e['parish'] or ''}</td>
                <td>{e['summary'] or ''}</td>
                <td style="font-weight:bold; color:{'red' if e['fnid_relevant'] else '#999'}">{fnid}</td>
            </tr>"""

        html += """</tbody></table>
        <div class="footer">RESTRICTED — Morning Crime Report — FNID Area 3</div>
        </body></html>"""

        pdf_buffer = render_pdf(html)
        if pdf_buffer:
            log_audit("mcr_entries", date, "EXPORT_PDF",
                     current_user.badge_number, current_user.full_name)
            return Response(
                pdf_buffer.read(),
                mimetype="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=MCR_{date}.pdf"}
            )
        else:
            flash("PDF generation unavailable.", "warning")
            return redirect(url_for("mcr.view_mcr", date=date))
    finally:
        conn.close()
