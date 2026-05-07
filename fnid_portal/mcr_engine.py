"""
FNID Morning Crime Report (MCR) Engine

Compiles the daily Morning Crime Report from the 24-hour reporting window
(05:30 previous day to 05:30 current day), filters FNID-relevant matters,
generates CR 7 summaries, and produces leads reports.
"""

import json
from datetime import datetime, timedelta

from .models import get_db, get_setting

# Keywords that flag an entry as FNID-relevant
FNID_KEYWORDS = {
    "firearm", "gun", "pistol", "rifle", "shotgun", "revolver", "ammunition",
    "ammo", "rounds", "magazine", "weapon", "shooting", "shot", "ballistic",
    "narcotics", "drugs", "cocaine", "ganja", "cannabis", "marijuana",
    "heroin", "fentanyl", "mdma", "ecstasy", "methamphetamine",
    "trafficking", "seizure", "smuggling", "contraband",
}


def _get_mcr_window(target_date=None):
    """Calculate the MCR 24-hour window.

    Window: previous day 05:30 → target_date 05:30
    """
    start_time = get_setting("mcr_window_start_time", "05:30")
    end_time = get_setting("mcr_window_end_time", "05:30")

    if target_date is None:
        target_date = datetime.now().date()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()

    h_end, m_end = map(int, end_time.split(":"))
    h_start, m_start = map(int, start_time.split(":"))

    window_end = datetime.combine(target_date, datetime.min.time().replace(
        hour=h_end, minute=m_end))
    window_start = window_end - timedelta(days=1)

    return window_start, window_end


def _is_fnid_relevant(text):
    """Check if text contains FNID-relevant keywords."""
    if not text:
        return False
    lower = text.lower()
    return any(kw in lower for kw in FNID_KEYWORDS)


def compile_mcr(target_date=None, compiled_by=None):
    """Compile Morning Crime Report for the 24-hour window.

    1. Query all new cases, intel, arrests, operations, seizures in window
    2. Classify each as FNID-relevant or general
    3. Generate summary entries
    4. Store in mcr_entries table
    5. Return the compiled entries

    Returns:
        tuple: (mcr_date_str, entries_list)
    """
    window_start, window_end = _get_mcr_window(target_date)
    mcr_date = window_end.strftime("%Y-%m-%d")
    ws = window_start.strftime("%Y-%m-%d %H:%M:%S")
    we = window_end.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    entries = []

    try:
        # Check if already compiled for this date
        existing = conn.execute(
            "SELECT COUNT(*) FROM mcr_entries WHERE mcr_date = ?", (mcr_date,)
        ).fetchone()[0]
        if existing > 0:
            # Return existing entries
            rows = conn.execute(
                "SELECT * FROM mcr_entries WHERE mcr_date = ? ORDER BY fnid_relevant DESC, id",
                (mcr_date,)
            ).fetchall()
            return mcr_date, rows

        # --- Collect from all source tables ---

        # Cases created in window
        cases = conn.execute("""
            SELECT case_id, classification, parish, offence_description,
                   suspect_name, oic_name, created_at
            FROM cases WHERE created_at BETWEEN ? AND ?
        """, (ws, we)).fetchall()

        for c in cases:
            text = f"{c['classification']} {c['offence_description']}".strip()
            relevant = _is_fnid_relevant(text)
            entries.append({
                "source_table": "cases",
                "source_id": c["case_id"],
                "classification": c["classification"],
                "parish": c["parish"],
                "summary": f"Case {c['case_id']}: {c['offence_description'][:200]}",
                "fnid_relevant": 1 if relevant else 0,
            })

        # Intel reports in window
        intel = conn.execute("""
            SELECT intel_id, subject_matter, parish, firearms_related,
                   narcotics_related, priority, created_at
            FROM intel_reports WHERE created_at BETWEEN ? AND ?
        """, (ws, we)).fetchall()

        for i in intel:
            relevant = (
                i["firearms_related"] == "Yes"
                or i["narcotics_related"] == "Yes"
                or _is_fnid_relevant(i["subject_matter"])
            )
            entries.append({
                "source_table": "intel_reports",
                "source_id": i["intel_id"],
                "classification": f"Intel - {i['priority']}",
                "parish": i["parish"],
                "summary": f"Intel {i['intel_id']}: {i['subject_matter'][:200]}",
                "fnid_relevant": 1 if relevant else 0,
            })

        # Arrests in window
        arrests = conn.execute("""
            SELECT arrest_id, suspect_name, parish, offence_1, arrest_date,
                   created_at
            FROM arrests WHERE created_at BETWEEN ? AND ?
        """, (ws, we)).fetchall()

        for a in arrests:
            relevant = _is_fnid_relevant(a["offence_1"])
            entries.append({
                "source_table": "arrests",
                "source_id": a["arrest_id"],
                "classification": a["offence_1"],
                "parish": a["parish"],
                "summary": f"Arrest {a['arrest_id']}: {a['suspect_name']} — {a['offence_1'][:150]}",
                "fnid_relevant": 1 if relevant else 0,
            })

        # Firearm seizures in window
        firearms = conn.execute("""
            SELECT seizure_id, firearm_type, parish, calibre, serial_number,
                   created_at
            FROM firearm_seizures WHERE created_at BETWEEN ? AND ?
        """, (ws, we)).fetchall()

        for f in firearms:
            entries.append({
                "source_table": "firearm_seizures",
                "source_id": f["seizure_id"],
                "classification": f"Firearm Seizure - {f['firearm_type']}",
                "parish": f["parish"],
                "summary": f"Seizure {f['seizure_id']}: {f['firearm_type']} "
                           f"{f['calibre'] or ''} S/N: {f['serial_number'] or 'Unknown'}",
                "fnid_relevant": 1,
            })

        # Narcotics seizures in window
        narcotics = conn.execute("""
            SELECT seizure_id, drug_type, quantity, unit, parish, created_at
            FROM narcotics_seizures WHERE created_at BETWEEN ? AND ?
        """, (ws, we)).fetchall()

        for n in narcotics:
            qty = f"{n['quantity']} {n['unit']}" if n['quantity'] else "quantity unknown"
            entries.append({
                "source_table": "narcotics_seizures",
                "source_id": n["seizure_id"],
                "classification": f"Narcotics Seizure - {n['drug_type']}",
                "parish": n["parish"],
                "summary": f"Seizure {n['seizure_id']}: {n['drug_type']} ({qty})",
                "fnid_relevant": 1,
            })

        # Operations in window
        ops = conn.execute("""
            SELECT op_id, op_name, op_type, parish, outcome, firearms_seized,
                   narcotics_seized, arrests_made, created_at
            FROM operations WHERE created_at BETWEEN ? AND ?
        """, (ws, we)).fetchall()

        for o in ops:
            relevant = (
                (o["firearms_seized"] or 0) > 0
                or (o["narcotics_seized"] or 0) > 0
                or _is_fnid_relevant(o["op_type"])
            )
            entries.append({
                "source_table": "operations",
                "source_id": o["op_id"],
                "classification": o["op_type"],
                "parish": o["parish"],
                "summary": f"Op {o['op_id']} ({o['op_name']}): {o['outcome'] or 'Ongoing'}",
                "fnid_relevant": 1 if relevant else 0,
            })

        # --- Store all entries ---
        for entry in entries:
            leads = _generate_lead_suggestions(entry, entries)
            conn.execute("""
                INSERT INTO mcr_entries
                (mcr_date, window_start, window_end, source_table, source_id,
                 classification, parish, summary, fnid_relevant,
                 lead_suggestions, compiled_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (mcr_date, ws, we, entry["source_table"], entry["source_id"],
                  entry["classification"], entry["parish"], entry["summary"],
                  entry["fnid_relevant"],
                  json.dumps(leads) if leads else None,
                  compiled_by))

        conn.commit()

        # Re-fetch stored entries to get IDs
        stored = conn.execute(
            "SELECT * FROM mcr_entries WHERE mcr_date = ? ORDER BY fnid_relevant DESC, id",
            (mcr_date,)
        ).fetchall()

        return mcr_date, stored

    finally:
        conn.close()


def _generate_lead_suggestions(entry, all_entries):
    """Generate follow-up investigation suggestions for an MCR entry.

    Identifies:
    - Linked incidents (same parish, similar classification)
    - Recurring persons of interest
    - Pattern matches
    """
    suggestions = []

    if not entry.get("fnid_relevant"):
        return suggestions

    # Check for linked parish activity
    same_parish = [
        e for e in all_entries
        if e["parish"] == entry["parish"]
        and e["source_id"] != entry["source_id"]
        and e["fnid_relevant"]
    ]
    if same_parish:
        suggestions.append(
            f"Multiple FNID matters in {entry['parish']} — "
            f"check for linked activity ({len(same_parish)} other entries)"
        )

    # Classification-based suggestions
    classification = (entry.get("classification") or "").lower()
    if "firearm" in classification:
        suggestions.append("Submit for IBIS/eTrace analysis if not already done")
        suggestions.append("Check FNID intelligence database for linked seizures in area")
    if "narcotic" in classification or "drug" in classification:
        suggestions.append("Check for trafficking network links — courier/supplier patterns")
        suggestions.append("Consider POCA referral for financial investigation")
    if "trafficking" in classification:
        suggestions.append("Escalate to intelligence unit for network mapping")

    return suggestions


def generate_leads_report(mcr_date):
    """Generate a comprehensive leads report from MCR data.

    Returns a dict with:
    - follow_up_lines: Suggested investigation lines
    - persons_of_interest: Recurring names
    - linked_incidents: Related entries
    - hotspot_trends: Parish/area concentration
    - briefing_topics: Intel brief topics for supervisors
    """
    conn = get_db()
    try:
        entries = conn.execute(
            "SELECT * FROM mcr_entries WHERE mcr_date = ? AND fnid_relevant = 1",
            (mcr_date,)
        ).fetchall()

        if not entries:
            return {"message": "No FNID-relevant entries for this date."}

        # Hotspot analysis
        parish_counts = {}
        for e in entries:
            p = e["parish"] or "Unknown"
            parish_counts[p] = parish_counts.get(p, 0) + 1

        hotspots = sorted(parish_counts.items(), key=lambda x: x[1], reverse=True)

        # Classification analysis
        class_counts = {}
        for e in entries:
            c = e["classification"] or "Unknown"
            class_counts[c] = class_counts.get(c, 0) + 1

        # Leads from stored suggestions
        all_leads = []
        for e in entries:
            if e["lead_suggestions"]:
                try:
                    leads = json.loads(e["lead_suggestions"])
                    all_leads.extend(leads)
                except (json.JSONDecodeError, TypeError):
                    pass

        # Briefing topics
        briefing_topics = []
        total = len(entries)
        if total > 0:
            briefing_topics.append(
                f"{total} FNID-relevant matters in reporting period"
            )
        for parish, count in hotspots[:3]:
            if count >= 2:
                briefing_topics.append(
                    f"{parish}: {count} FNID matters — increased activity"
                )

        return {
            "mcr_date": mcr_date,
            "total_entries": len(entries),
            "follow_up_lines": list(set(all_leads))[:20],
            "hotspot_trends": hotspots,
            "classification_summary": sorted(
                class_counts.items(), key=lambda x: x[1], reverse=True
            ),
            "briefing_topics": briefing_topics,
        }

    finally:
        conn.close()
