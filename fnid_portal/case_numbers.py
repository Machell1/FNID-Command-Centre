"""
FNID Case Reference Number Engine

Generates case reference numbers and DCRR numbers per JCF Case Management
Policy (JCF/FW/PL/C&S/0001/2024 Section 9.1.13).

Internal format: {station}/{diary_type}/{division}/{unit}/{YYYY}/{sequence}
Example: MAND/SD/A3/FNID/2026/0042

Policy DCRR format (Section 9.1.13.1):
  {DCRR_seq}_{yyyy/mm/dd}/{station_initial}/{SD or CD}{entry#}/{division_code}
  Example: 32_2014/03/05/LT/SD45/M

Policy Station Manager format (Section 9.1.13.2):
  {register_seq}_/{diary_entry#}/{yyyy/mm/dd}/{station_abbreviation}
  Example: 1_/12/2023/10/03/HWT
"""

from datetime import datetime

from .models import get_db, get_setting

# Default station codes for FNID Area 3 — CONFIGURABLE
STATION_CODES = {
    "mandeville": "MAND",
    "christiana": "CHRS",
    "may_pen": "MAYP",
    "spaldings": "SPAL",
    "santa_cruz": "STCZ",
    "black_river": "BLKR",
    "lacovia": "LACV",
    "junction": "JNCT",
    "lionel_town": "LION",
    "chapelton": "CHAP",
    "frankfield": "FRNK",
    "fnid_hq": "FNID",
}


def _next_sequence(prefix_pattern):
    """Get the next sequential number for a given prefix pattern.

    Queries cases, dcrr, and cr_forms tables to find the highest sequence.
    """
    conn = get_db()
    try:
        # Check cases table
        row = conn.execute("""
            SELECT case_id FROM cases
            WHERE case_id LIKE ?
            ORDER BY id DESC LIMIT 1
        """, (prefix_pattern + "%",)).fetchone()

        max_seq = 0
        if row:
            try:
                max_seq = max(max_seq, int(str(row[0]).rsplit("/", 1)[-1]))
            except (ValueError, IndexError):
                pass

        # Also check DCRR
        row2 = conn.execute("""
            SELECT dcrr_number FROM dcrr
            WHERE dcrr_number LIKE ?
            ORDER BY id DESC LIMIT 1
        """, (prefix_pattern + "%",)).fetchone()

        if row2:
            try:
                max_seq = max(max_seq, int(str(row2[0]).rsplit("/", 1)[-1]))
            except (ValueError, IndexError):
                pass

        return max_seq + 1
    finally:
        conn.close()


def generate_case_reference(station_code=None, diary_type=None,
                            division_code=None, unit_code=None, year=None):
    """Generate the next case reference number.

    Format: {station}/{diary_type}/{division}/{unit}/{year}/{sequence}
    Example: MAND/SD/A3/FNID/2026/0042

    All components are configurable via system_settings or function arguments.
    """
    if station_code is None:
        station_code = get_setting("default_station_code", "FNID")
    if diary_type is None:
        diary_type = get_setting("default_diary_type", "SD")
    if division_code is None:
        division_code = get_setting("default_division_code", "A3")
    if unit_code is None:
        unit_code = get_setting("default_unit_code", "FNID")
    if year is None:
        year = datetime.now().year

    prefix = f"{station_code}/{diary_type}/{division_code}/{unit_code}/{year}"
    seq = _next_sequence(prefix)
    return f"{prefix}/{str(seq).zfill(4)}"


def generate_dcrr_number(station_code=None, year=None):
    """Generate the next DCRR (Divisional Case Report Register) number.

    Format: DCRR/{station}/{year}/{sequence}
    Example: DCRR/MAND/2026/0015
    """
    if station_code is None:
        station_code = get_setting("default_station_code", "FNID")
    if year is None:
        year = datetime.now().year

    prefix = f"DCRR/{station_code}/{year}"
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT dcrr_number FROM dcrr
            WHERE dcrr_number LIKE ?
            ORDER BY id DESC LIMIT 1
        """, (prefix + "%",)).fetchone()

        seq = 1
        if row:
            try:
                seq = int(str(row[0]).rsplit("/", 1)[-1]) + 1
            except (ValueError, IndexError):
                pass

        return f"{prefix}/{str(seq).zfill(4)}"
    finally:
        conn.close()


def generate_major_crime_register_number(station_code=None, year=None):
    """Generate the next Major Crime Register number.

    Format: MCRG/{station}/{year}/{sequence}. The MCRG prefix avoids confusion
    with the existing MCR Morning Crime Report engine.
    """
    if station_code is None:
        station_code = get_setting("default_station_code", "FNID")
    if year is None:
        year = datetime.now().year

    prefix = f"MCRG/{station_code}/{year}"
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT register_number FROM major_crime_register
            WHERE register_number LIKE ?
            ORDER BY id DESC LIMIT 1
        """, (prefix + "%",)).fetchone()

        seq = 1
        if row:
            try:
                seq = int(str(row[0]).rsplit("/", 1)[-1]) + 1
            except (ValueError, IndexError):
                pass

        return f"{prefix}/{str(seq).zfill(4)}"
    finally:
        conn.close()


def generate_form_id(form_type, case_id):
    """Generate a unique form ID for a CR form.

    Format: {form_type}/{case_id}/{sequence}
    Example: CR1/MAND/SD/A3/FNID/2026/0042/001
    """
    conn = get_db()
    try:
        prefix = f"{form_type}/{case_id}"
        row = conn.execute("""
            SELECT form_id FROM cr_forms
            WHERE form_id LIKE ?
            ORDER BY id DESC LIMIT 1
        """, (prefix + "%",)).fetchone()

        seq = 1
        if row:
            try:
                seq = int(str(row[0]).rsplit("/", 1)[-1]) + 1
            except (ValueError, IndexError):
                pass

        return f"{prefix}/{str(seq).zfill(3)}"
    finally:
        conn.close()


def parse_case_reference(case_ref):
    """Parse a case reference number into its components.

    Returns dict with: station, diary_type, division, unit, year, sequence
    """
    parts = case_ref.split("/")
    if len(parts) >= 6:
        return {
            "station": parts[0],
            "diary_type": parts[1],
            "division": parts[2],
            "unit": parts[3],
            "year": parts[4],
            "sequence": parts[5],
        }
    return {"raw": case_ref}


def generate_policy_dcrr_reference(dcrr_seq, report_date, station_initial,
                                    diary_type, diary_entry, division_code,
                                    unit_code=None):
    """Generate a Case Reference Number per JCF Policy Section 9.1.13.1.

    Format: {DCRR_seq}_{yyyy/mm/dd}/{station}/{diary_type}{entry#}/{division}
    Optionally append /{unit} for specialist units.

    Example: 32_2014/03/05/LT/SD45/M
    Example: 43_2017/06/10/HWT/CD52/SAC
    """
    # Format date as yyyy/mm/dd
    if isinstance(report_date, str):
        date_str = report_date.replace("-", "/")
    else:
        date_str = report_date.strftime("%Y/%m/%d")

    cr_num = f"{dcrr_seq}_{date_str}/{station_initial}/{diary_type}{diary_entry}/{division_code}"
    if unit_code:
        cr_num += f"/{unit_code}"
    return cr_num


def generate_station_manager_reference(register_seq, diary_entry, report_date,
                                        station_abbreviation):
    """Generate a Case Reference Number per JCF Policy Section 9.1.13.2.

    Format: {register_seq}_/{diary_entry}/{yyyy/mm/dd}/{station}

    Example: 1_/12/2023/10/03/HWT
    """
    if isinstance(report_date, str):
        date_str = report_date.replace("-", "/")
    else:
        date_str = report_date.strftime("%Y/%m/%d")

    return f"{register_seq}_/{diary_entry}/{date_str}/{station_abbreviation}"
