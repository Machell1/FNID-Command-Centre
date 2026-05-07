"""
FNID Area 3 Sample Data Seeder

Seeds the database with realistic test data for all tables in the
FNID case management system. Called via: flask seed [--force]
"""

import random
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from .models import generate_id, get_db

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rand_date(days_back_max=90, days_back_min=0):
    """Return an ISO date string within the last *days_back_max* days."""
    delta = random.randint(days_back_min, days_back_max)
    return (datetime.now() - timedelta(days=delta)).strftime("%Y-%m-%d")


def _rand_datetime(days_back_max=90, days_back_min=0):
    """Return an ISO datetime string within the last *days_back_max* days."""
    delta = random.randint(days_back_min, days_back_max)
    hrs = random.randint(6, 22)
    mins = random.randint(0, 59)
    dt = datetime.now() - timedelta(days=delta, hours=hrs, minutes=mins)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _rand_time():
    """Return a random time string HH:MM."""
    return f"{random.randint(6,22):02d}:{random.randint(0,59):02d}"


def _future_date(days_ahead_min=7, days_ahead_max=60):
    """Return an ISO date string in the near future."""
    delta = random.randint(days_ahead_min, days_ahead_max)
    return (datetime.now() + timedelta(days=delta)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def seed_database(force=False):
    """Populate every operational table with realistic FNID Area 3 data.

    Args:
        force: If True, delete all existing records first.
    """
    conn = get_db()

    # Check whether data already exists
    case_count = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    if case_count > 0 and not force:
        print("Database already contains data. Use --force to re-seed.")
        conn.close()
        return

    if force:
        print("Force flag set — clearing all tables ...")
        _clear_all(conn)

    _seed_officers(conn)
    _seed_cases(conn)
    _seed_intel_reports(conn)
    _seed_operations(conn)
    _seed_firearm_seizures(conn)
    _seed_narcotics_seizures(conn)
    _seed_arrests(conn)
    _seed_chain_of_custody(conn)
    _seed_lab_tracking(conn)
    _seed_dpp_pipeline(conn)
    _seed_sop_checklists(conn)
    _seed_witness_statements(conn)
    _seed_disclosure_log(conn)
    _seed_case_lifecycle(conn)
    _seed_file_movements(conn)
    _seed_case_reviews(conn)
    _seed_mcr_entries(conn)
    _seed_alerts(conn)
    _seed_intel_targets(conn)
    _seed_dcrr(conn)
    _seed_named_admins(conn)

    conn.commit()
    conn.close()
    print("Seeding complete.")


# ---------------------------------------------------------------------------
# Table clearance (force mode)
# ---------------------------------------------------------------------------

_ALL_SEED_TABLES = [
    "dcrr", "intel_targets", "alerts", "mcr_entries",
    "case_reviews", "file_movements", "case_lifecycle",
    "disclosure_log", "witness_statements", "sop_checklists",
    "dpp_pipeline", "lab_tracking", "chain_of_custody",
    "arrests", "narcotics_seizures", "firearm_seizures",
    "operations", "intel_reports", "cases", "officers",
    "audit_log",
]


def _clear_all(conn):
    """Delete rows from every seedable table (respects FK order)."""
    for table in _ALL_SEED_TABLES:
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    print("  All tables cleared.")


def _seed_named_admins(conn):
    """Seed four named admin officers with tiered access."""
    print("Seeding named admin officers ...")
    pw_hash = generate_password_hash("Fnid@Admin2026!")

    admins = [
        ("JCF-2001", "Cpl. Machell Williams", "Corporal",
         "FNID Headquarters - Area 3", "admin", 1),
        ("JCF-2002", "Insp. Rayon Rodney", "Inspector",
         "FNID Headquarters - Area 3", "dco", 2),
        ("JCF-2003", "Sgt. Robert Barrett", "Sergeant",
         "FNID Headquarters - Area 3", "ddi", 3),
        ("JCF-2004", "Sgt. Danette McPherson", "Sergeant",
         "FNID Headquarters - Area 3", "station_mgr", 4),
    ]
    for badge, name, rank, section, role, tier in admins:
        existing = conn.execute(
            "SELECT badge_number FROM officers WHERE badge_number = ?", (badge,)
        ).fetchone()
        if not existing:
            conn.execute("""
                INSERT INTO officers (badge_number, full_name, rank, section, role,
                    password_hash, unit_access, must_change_password, admin_tier,
                    verification_status)
                VALUES (?, ?, ?, ?, ?, ?, 'all', 1, ?, 'active')
            """, (badge, name, rank, section, role, pw_hash, tier))
            print(f"  Created admin: {badge} ({name}) - Tier {tier}")


# ---------------------------------------------------------------------------
# 1. Officers (10)
# ---------------------------------------------------------------------------

def _seed_officers(conn):
    print("Seeding officers ...")

    pw_hash = generate_password_hash("fnid2026")

    officers = [
        # (badge, full_name, rank, section, role, email, unit_access)
        ("JCF-1001", "Superintendent Althea Morgan",
         "Superintendent of Police",
         "FNID Headquarters - Area 3", "admin",
         "a.morgan@jcf.gov.jm", "all"),
        ("JCF-1002", "DSP Karl Williams",
         "Deputy Superintendent of Police",
         "FNID Headquarters - Area 3", "dco",
         "k.williams@jcf.gov.jm", "all"),
        ("JCF-1003", "Inspector Damion Brown",
         "Inspector",
         "Intelligence Section", "ddi",
         "d.brown@jcf.gov.jm", "all"),
        ("JCF-1004", "Inspector Sandra Clarke",
         "Inspector",
         "Case Management & Registry", "station_mgr",
         "s.clarke@jcf.gov.jm", "all"),
        ("JCF-1005", "Detective Sergeant Michael Campbell",
         "Detective Sergeant",
         "Firearms Investigation Section", "io",
         "m.campbell@jcf.gov.jm", "seizures"),
        ("JCF-1006", "Detective Corporal Keisha Henry",
         "Detective Corporal",
         "Narcotics Investigation Section", "io",
         "k.henry@jcf.gov.jm", "seizures"),
        ("JCF-1007", "Detective Constable Andre Thompson",
         "Detective Constable",
         "Operations Section", "io",
         "a.thompson@jcf.gov.jm", "operations"),
        ("JCF-1008", "Detective Constable Shelly-Ann Reid",
         "Detective Constable",
         "Firearms Investigation Section", "io",
         "s.reid@jcf.gov.jm", "seizures,arrests"),
        ("JCF-1009", "Corporal Patricia Salmon",
         "Corporal",
         "Case Management & Registry", "registrar",
         "p.salmon@jcf.gov.jm", "registry"),
        ("JCF-1010", "Sergeant Rohan Blake",
         "Sergeant",
         "Intelligence Section", "intel_officer",
         "r.blake@jcf.gov.jm", "intel"),
    ]

    for badge, name, rank, section, role, email, unit_access in officers:
        # Skip if this badge already exists (e.g. ADMIN inserted by init_db)
        exists = conn.execute(
            "SELECT 1 FROM officers WHERE badge_number = ?", (badge,)
        ).fetchone()
        if exists:
            continue
        conn.execute("""
            INSERT INTO officers
                (badge_number, full_name, rank, section, role,
                 password_hash, email, unit_access, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (badge, name, rank, section, role, pw_hash, email, unit_access))


# ---------------------------------------------------------------------------
# 2. Cases (25)
# ---------------------------------------------------------------------------

_CLASSIFICATIONS = [
    "Firearms - Possession",
    "Firearms - Trafficking",
    "Firearms - Stockpiling",
    "Firearms - Manufacturing",
    "Narcotics - Possession with Intent",
    "Narcotics - Trafficking (Import/Export)",
    "Narcotics - Cultivation",
    "Narcotics - Distribution/Dealing",
    "Firearms + Narcotics (Combined)",
    "Trafficking - Multi-Commodity",
    "POCA / Financial Investigation",
    "Murder with Firearm",
    "Attempted Murder with Firearm",
    "Shooting with Intent",
    "Robbery with Aggravation (firearm)",
    "Gang / Organised Crime Network",
]

_PARISHES = ["Manchester", "St. Elizabeth", "Clarendon"]

_STATUSES = [
    "Open - Active Investigation",
    "Open - Pending Forensic Results",
    "Open - Pending Witness Statements",
    "Open - Pending DPP File Submission",
    "Referred to DPP - Awaiting Ruling",
    "Before Court - Preliminary Enquiry",
    "Before Court - Trial Pending",
    "Closed - Convicted (sentence imposed)",
    "Closed - Acquitted (verdict of not guilty)",
    "Closed - No Charge (DPP ruling)",
    "Cold Case - Under Periodic Review",
    "Cold Case - Dormant",
]

_STAGES = [
    "intake", "appreciation", "vetting", "assignment",
    "investigation", "follow_up", "review",
    "court_preparation", "before_court", "closed", "suspended",
]

_OFFENCES = [
    ("Illegal Possession of Firearm",
     "s.5 Firearms (Prohibition, Restriction & Regulation) Act, 2022"),
    ("Illegal Possession of Ammunition",
     "s.22 Firearms Act, 2022"),
    ("Shooting with Intent to cause GBH",
     "s.43 Firearms Act, 2022"),
    ("Trafficking in Prohibited Weapon",
     "s.7 Firearms Act, 2022"),
    ("Possession of Cannabis with Intent to Supply",
     "s.7E Dangerous Drugs Act"),
    ("Dealing in Cocaine",
     "s.8 Dangerous Drugs Act"),
    ("Import of Cocaine",
     "s.8 Dangerous Drugs Act"),
    ("Cultivation of Cannabis (>5 plants)",
     "s.7F Dangerous Drugs Act"),
    ("Murder committed with a Firearm",
     "s.42 Firearms Act, 2022 / Offences Against the Person Act"),
    ("Robbery with Aggravation involving Firearm",
     "Offences Against the Person Act / s.42 Firearms Act, 2022"),
    ("Possession of Prohibited Weapon - Stockpiling",
     "s.6 Firearms Act, 2022"),
    ("Manufacturing of Prohibited Weapon",
     "s.9 Firearms Act, 2022"),
    ("Money Laundering (drug proceeds)",
     "s.5 Proceeds of Crime Act (POCA), 2007"),
    ("Conspiracy to Import Controlled Drug",
     "Dangerous Drugs Act / Criminal Justice Act"),
    ("Wounding with Intent",
     "s.20 Offences Against the Person Act"),
]

_IO_BADGES = ["JCF-1005", "JCF-1006", "JCF-1007", "JCF-1008"]
_IO_NAMES = [
    "Detective Sergeant Michael Campbell",
    "Detective Corporal Keisha Henry",
    "Detective Constable Andre Thompson",
    "Detective Constable Shelly-Ann Reid",
]
_IO_RANKS = [
    "Detective Sergeant",
    "Detective Corporal",
    "Detective Constable",
    "Detective Constable",
]

_SUSPECT_NAMES = [
    "Marlon Gayle", "Dwayne Sinclair", "Ricardo Hines",
    "Kemar Powell", "Sanjay Mitchell", "Orville Brown",
    "Damian Stephens", "Christopher Young", "Lloyd Pinnock",
    "Tyrone Marshall", "Everton Bailey", "Omar Francis",
    "Wayne Robinson", "Sheldon Grant", "Jason Miller",
    "Kurt McKenzie", "Leroy Pryce", "Devon Dawkins",
    "Garfield Whyte", "Neville Rowe", "Andre Clarke",
    "Brian Johnson", "Courtney Williams", "Maurice Bennett",
    "Patrick Samuels",
]

_VICTIM_NAMES = [
    "Sonia Edwards", "Michelle Lewis", "Karen Scott",
    "Paulette Green", "Deborah Morgan", "Sharon Wright",
    "Donna Taylor", "Norma James", "Audrey Wallace",
    "Marcia Hamilton", "Angela Davis", "Claudette Bryan",
    "Patricia Rowe", "Beverley Stewart", "Yvonne Thomas",
]

_LOCATIONS_MANCHESTER = [
    "Mandeville Town Centre", "Battersea Road, Mandeville",
    "Newport, Manchester", "Christiana Market Area",
    "Williamsfield, Manchester", "Porus Main Road",
]
_LOCATIONS_ST_ELIZABETH = [
    "Santa Cruz Town Centre", "Black River Bay",
    "Junction Road, St. Elizabeth", "Lacovia Main Road",
    "Treasure Beach, St. Elizabeth", "Maggotty, St. Elizabeth",
]
_LOCATIONS_CLARENDON = [
    "May Pen Town Centre", "Chapelton, Clarendon",
    "Lionel Town, Clarendon", "Frankfield Main Road",
    "Hayes, Clarendon", "Rock River, Clarendon",
]

_PARISH_LOCATIONS = {
    "Manchester": _LOCATIONS_MANCHESTER,
    "St. Elizabeth": _LOCATIONS_ST_ELIZABETH,
    "Clarendon": _LOCATIONS_CLARENDON,
}

_STATION_CODES = {
    "Manchester": "MAND",
    "St. Elizabeth": "STELZ",
    "Clarendon": "CLAR",
}


def _seed_cases(conn):
    print("Seeding cases ...")

    case_ids = []

    for i in range(25):
        case_id = generate_id("CASE", "cases", "case_id")
        case_ids.append(case_id)

        classification = _CLASSIFICATIONS[i % len(_CLASSIFICATIONS)]
        parish = _PARISHES[i % len(_PARISHES)]
        status = _STATUSES[i % len(_STATUSES)]
        stage = _STAGES[i % len(_STAGES)]
        offence_desc, law_section = _OFFENCES[i % len(_OFFENCES)]

        # Assign IO to most cases; leave a few unassigned
        if i < 20:
            io_idx = i % 4
            assigned_io_badge = _IO_BADGES[io_idx]
            oic_badge = assigned_io_badge
            oic_name = _IO_NAMES[io_idx]
            oic_rank = _IO_RANKS[io_idx]
            assigned_date = _rand_date(80, 10)
        else:
            assigned_io_badge = None
            oic_badge = "JCF-1004"
            oic_name = "Inspector Sandra Clarke"
            oic_rank = "Inspector"
            assigned_date = None

        suspect_name = _SUSPECT_NAMES[i]
        victim_name = _VICTIM_NAMES[i % len(_VICTIM_NAMES)] if i < 15 else None

        reg_date = _rand_date(85, 5)
        created_at = reg_date + " 08:00:00"
        location = random.choice(_PARISH_LOCATIONS[parish])

        # Court-related fields for 'Before Court' statuses
        court_type = None
        next_court_date = None
        if "Before Court" in status:
            court_type = random.choice([
                "Gun Court - High Court Division (judge alone, in camera)",
                "Gun Court - Resident Magistrate Division (preliminary enquiry)",
                "Parish Court (summary drug offence)",
            ])
            next_court_date = _future_date(14, 90)

        # Closed fields
        closed_date = None
        closed_reason = None
        if "Closed" in status:
            closed_date = _rand_date(30, 1)
            closed_reason = status.split(" - ", 1)[1] if " - " in status else "Case concluded"

        # Suspended fields
        suspended_date = None
        suspended_reason = None
        if stage == "suspended":
            suspended_date = _rand_date(45, 5)
            suspended_reason = "Insufficient evidence to proceed; witness uncooperative"

        station_code = _STATION_CODES[parish]
        diary_number = f"SD/{station_code}/{datetime.now().year}/{100 + i}"

        conn.execute("""
            INSERT INTO cases
                (case_id, registration_date, classification, oic_badge, oic_name,
                 oic_rank, parish, division, offence_description, law_and_section,
                 suspect_name, suspect_address, victim_name,
                 case_status, current_stage, assigned_io_badge, assigned_date,
                 court_type, next_court_date,
                 closed_date, closed_reason,
                 suspended_date, suspended_reason,
                 station_code, diary_number,
                 crime_type, workflow_type,
                 record_status, created_by, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            case_id, reg_date, classification, oic_badge, oic_name,
            oic_rank, parish, "FNID Area 3", offence_desc, law_section,
            suspect_name, location, victim_name,
            status, stage, assigned_io_badge, assigned_date,
            court_type, next_court_date,
            closed_date, closed_reason,
            suspended_date, suspended_reason,
            station_code, diary_number,
            "major", "non-uniformed",
            "Submitted", oic_badge, created_at, created_at,
        ))

    # Store case_ids on module level for use by other seeders
    _seed_cases._case_ids = case_ids


# ---------------------------------------------------------------------------
# 3. Intel Reports (15)
# ---------------------------------------------------------------------------

_INTEL_SOURCES = [
    "Crime Stop (311)", "Registered Informant", "MOCA (Major Organised Crime & Anti-Corruption Agency)",
    "DEA (US Drug Enforcement Administration)", "ATF (US Bureau of Alcohol, Tobacco, Firearms)",
    "Patrol Intercept", "Anonymous Tip", "Social Media Monitoring",
    "JCA Detection (Jamaica Customs Agency)", "Divisional CIB (Criminal Investigation Branch)",
    "NIB (811)", "FNID Direct (923-6184)", "Walk-In Report",
    "C-TOC (Counter-Terrorism and Organised Crime)", "Station Diary Entry",
]

_INTEL_SUBJECTS = [
    "Suspected firearm cache at residential premises",
    "Illegal firearm trafficking through Clarendon port",
    "Cannabis cultivation site in Manchester hills",
    "Cocaine importation via fishing vessel at Black River",
    "Gang members stockpiling ammunition in May Pen",
    "Handgun sales in Mandeville nightlife district",
    "Suspected drug mule travelling to Kingston",
    "Illegal gun manufacturing workshop discovered",
    "Large cannabis shipment en route from St. Elizabeth",
    "Cocaine distribution network in Christiana",
    "Armed robbery suspects hiding in Porus",
    "Cross-parish firearm supply chain intelligence",
    "Informant reports shooting suspects in Junction",
    "Maritime smuggling operation off Treasure Beach",
    "Organised gang activity in Lionel Town area",
]


def _seed_intel_reports(conn):
    print("Seeding intel reports ...")

    case_ids = _seed_cases._case_ids
    priorities = ["Critical", "High", "Medium", "Low"]
    triage_decisions = [
        "Action - Mount Operation",
        "Action - Surveillance Only",
        "Intel Filed - Active Monitoring",
        "Refer to Divisional CIB",
        "Closed - Insufficient Information",
    ]

    for i in range(15):
        intel_id = generate_id("INTEL", "intel_reports", "intel_id")
        parish = _PARISHES[i % 3]
        date_received = _rand_date(80, 3)
        source = _INTEL_SOURCES[i]
        subject = _INTEL_SUBJECTS[i]
        priority = priorities[i % 4]
        triage = triage_decisions[i % len(triage_decisions)]
        linked_case = case_ids[i] if i < len(case_ids) else None

        firearms_related = "Yes" if i < 8 else "No"
        narcotics_related = "Yes" if i >= 4 and i < 12 else "No"

        conn.execute("""
            INSERT INTO intel_reports
                (intel_id, date_received, time_received, source, priority,
                 subject_matter, firearms_related, narcotics_related,
                 target_person, target_location, parish,
                 substance_of_intel, triage_decision, triage_by, triage_date,
                 linked_case_id, record_status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            intel_id, date_received, _rand_time(), source, priority,
            subject, firearms_related, narcotics_related,
            _SUSPECT_NAMES[i], random.choice(_PARISH_LOCATIONS[parish]), parish,
            f"Detailed intelligence: {subject}. Source assessed as reliable.",
            triage, "JCF-1003", _rand_date(75, 2),
            linked_case, "Submitted", "JCF-1010",
            _rand_datetime(80, 3),
        ))


# ---------------------------------------------------------------------------
# 4. Operations (10)
# ---------------------------------------------------------------------------

_OP_NAMES = [
    "Operation Ironclad", "Operation Blue Harvest", "Operation Nighthawk",
    "Operation Vanguard", "Operation Stonewall", "Operation Trident",
    "Operation Crossfire", "Operation Sentinel", "Operation Thunderbolt",
    "Operation Dragnet",
]

_OP_TYPES = [
    "Search Warrant Execution (s.91 Firearms Act)",
    "Search Warrant Execution (s.21 DDA)",
    "Snap Raid (Exigent Circumstances)",
    "Vehicle Interception / Stop & Search",
    "Joint Operation - JCA",
    "Checkpoint (Authorised)",
    "Surveillance Operation",
    "Coastal/Maritime Operation",
    "Joint Operation - DEA",
    "Fugitive Apprehension",
]

_OP_OUTCOMES = [
    "Successful - Seizure and Arrest",
    "Successful - Seizure Only (no suspect present)",
    "Successful - Arrest Only",
    "Partial Success - Intelligence Developed",
    "Negative - No Finds",
]


def _seed_operations(conn):
    print("Seeding operations ...")

    for i in range(10):
        op_id = generate_id("OP", "operations", "op_id")
        parish = _PARISHES[i % 3]
        op_date = _rand_date(70, 5)

        firearms_seized = random.randint(0, 3) if i < 7 else 0
        narcotics_seized = random.randint(0, 2) if i % 2 == 0 else 0
        ammo_seized = random.randint(0, 50) if firearms_seized > 0 else 0
        arrests_made = random.randint(0, 3)

        conn.execute("""
            INSERT INTO operations
                (op_id, op_name, op_date, op_type, warrant_basis,
                 parish, target_location, target_person,
                 team_lead, team_lead_rank, team_size, joint_agency,
                 linked_intel_id, start_time, end_time, duration_hrs,
                 firearms_seized, narcotics_seized, ammo_seized,
                 arrests_made, outcome, outcome_notes,
                 body_cam, evidence_tagged,
                 record_status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            op_id, _OP_NAMES[i], op_date, _OP_TYPES[i],
            "Section 91 - Firearms (Prohibition, Restriction & Regulation) Act, 2022"
            if i < 5 else "Section 21 - Dangerous Drugs Act",
            parish, random.choice(_PARISH_LOCATIONS[parish]),
            _SUSPECT_NAMES[i],
            "JCF-1005", "Detective Sergeant", random.randint(4, 12),
            "JDF" if i in (4, 7) else None,
            None, _rand_time(), _rand_time(), round(random.uniform(1.5, 8.0), 1),
            firearms_seized, narcotics_seized, ammo_seized,
            arrests_made, _OP_OUTCOMES[i % len(_OP_OUTCOMES)],
            f"Operation {_OP_NAMES[i]} executed in {parish}.",
            "Yes" if i < 6 else "No",
            "Yes" if i < 8 else "No",
            "Submitted", "JCF-1005",
            _rand_datetime(70, 5),
        ))


# ---------------------------------------------------------------------------
# 5. Firearm Seizures (12)
# ---------------------------------------------------------------------------

_FIREARM_TYPES = [
    "Pistol - Semi-Automatic", "Pistol - Revolver",
    "Rifle - Semi-Automatic", "Rifle - Assault / Select Fire",
    "Shotgun - Pump Action", "Shotgun - Semi-Automatic",
    "Submachine Gun", "Improvised / Homemade (Slam Gun)",
    "Component - Frame / Receiver", "Component - Barrel",
    "Pistol - Semi-Automatic", "Pistol - Revolver",
]

_FIREARM_MAKES = [
    "Glock", "Smith & Wesson", "Taurus", "Beretta",
    "Colt", "Ruger", "Mossberg", "Unknown",
    "N/A (component)", "N/A (component)",
    "Hi-Point", "Sig Sauer",
]

_FIREARM_MODELS = [
    "G19 Gen 5", "SD9 VE", "PT111 G2", "92FS",
    "M1911", "SR9c", "500A", "Homemade",
    "Lower Receiver", "Barrel Assembly",
    "C9", "P320",
]

_CALIBRES = [
    "9mm Luger/Parabellum", ".38 Special", "9mm Luger/Parabellum",
    "5.56x45mm NATO / .223 Remington", "12 Gauge", "12 Gauge",
    "9mm Luger/Parabellum", "12 Gauge",
    "N/A", "N/A",
    "9mm Luger/Parabellum", "9mm Luger/Parabellum",
]


def _seed_firearm_seizures(conn):
    print("Seeding firearm seizures ...")

    case_ids = _seed_cases._case_ids

    for i in range(12):
        seizure_id = generate_id("FS", "firearm_seizures", "seizure_id")
        parish = _PARISHES[i % 3]

        serial = f"SN-{random.randint(100000, 999999)}" if i < 8 else "OBLITERATED"

        ibis = random.choice([
            "Submitted to IFSLM - Pending Entry",
            "Entered - No Match",
            "Hit - Confirmed Match (linked to other case)",
            "Not Submitted",
        ])
        etrace = random.choice([
            "Submitted to ATF - Pending",
            "Traced - US Origin (state/dealer identified)",
            "Untraceable - Serial Obliterated",
            "Not Submitted",
        ])

        conn.execute("""
            INSERT INTO firearm_seizures
                (seizure_id, seizure_date, linked_case_id, parish, location,
                 firearm_type, make, model, serial_number, calibre,
                 country_of_origin, ammo_count, magazine_count,
                 ibis_status, etrace_status,
                 exhibit_tag, storage_location,
                 seized_by, witness_officer,
                 record_status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            seizure_id, _rand_date(70, 3),
            case_ids[i] if i < len(case_ids) else None,
            parish, random.choice(_PARISH_LOCATIONS[parish]),
            _FIREARM_TYPES[i], _FIREARM_MAKES[i], _FIREARM_MODELS[i],
            serial, _CALIBRES[i],
            random.choice(["United States", "Unknown", "Brazil", "Turkey"]),
            random.randint(0, 45), random.randint(0, 3),
            ibis, etrace,
            f"EXH-FA-{2026}-{str(i+1).zfill(3)}",
            "FNID Area 3 Armoury - Mandeville",
            _IO_BADGES[i % 4], _IO_BADGES[(i + 1) % 4],
            "Submitted", _IO_BADGES[i % 4],
            _rand_datetime(70, 3),
        ))


# ---------------------------------------------------------------------------
# 6. Narcotics Seizures (8)
# ---------------------------------------------------------------------------

_DRUG_TYPES = [
    "Cannabis / Ganja - Compressed (brick)",
    "Cannabis / Ganja - Loose (cured)",
    "Cocaine Hydrochloride (powder)",
    "Cocaine - Crack / Freebase",
    "Heroin (diamorphine)",
    "Cannabis / Ganja - Compressed (brick)",
    "Cocaine Hydrochloride (powder)",
    "Cannabis / Ganja - Oil / Concentrate",
]


def _seed_narcotics_seizures(conn):
    print("Seeding narcotics seizures ...")

    case_ids = _seed_cases._case_ids
    units = ["kg", "g", "lbs", "kg", "g", "kg", "kg", "ml"]
    quantities = [25.5, 450.0, 10.0, 2.3, 15.0, 55.0, 5.0, 500.0]
    street_values = [
        500000.0, 200000.0, 3500000.0, 800000.0,
        2000000.0, 1100000.0, 7500000.0, 150000.0,
    ]

    for i in range(8):
        seizure_id = generate_id("NS", "narcotics_seizures", "seizure_id")
        parish = _PARISHES[i % 3]

        conn.execute("""
            INSERT INTO narcotics_seizures
                (seizure_id, seizure_date, linked_case_id, parish, location,
                 drug_type, quantity, unit, est_street_value,
                 packaging_method, concealment_method,
                 field_test_result, lab_cert_status,
                 exhibit_tag, storage_location,
                 seized_by, witness_officer,
                 record_status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            seizure_id, _rand_date(65, 3),
            case_ids[i + 4] if (i + 4) < len(case_ids) else None,
            parish, random.choice(_PARISH_LOCATIONS[parish]),
            _DRUG_TYPES[i], quantities[i], units[i], street_values[i],
            random.choice(["Plastic wrapped", "Vacuum sealed", "Loose in bag", "Taped bundles"]),
            random.choice(["Vehicle compartment", "Residential premises", "Underground pit", "Boat hull"]),
            "Positive" if i != 4 else "Inconclusive",
            random.choice([
                "Not Yet Submitted to Lab",
                "Submitted to IFSLM (Institute of Forensic Science & Legal Medicine)",
                "Analysis In Progress",
                "Certificate Issued - Collected",
            ]),
            f"EXH-NA-{2026}-{str(i+1).zfill(3)}",
            "FNID Area 3 Evidence Room - Mandeville",
            _IO_BADGES[i % 4], _IO_BADGES[(i + 1) % 4],
            "Submitted", _IO_BADGES[i % 4],
            _rand_datetime(65, 3),
        ))


# ---------------------------------------------------------------------------
# 7. Arrests (15)
# ---------------------------------------------------------------------------

def _seed_arrests(conn):
    print("Seeding arrests ...")

    case_ids = _seed_cases._case_ids
    bail_statuses = [
        "Bail Granted (conditions set)",
        "Bail Denied (opposed by Crown)",
        "Remanded in Custody (lockup)",
        "Remanded in Custody (correctional centre)",
        "Released - Station Bail",
    ]
    court_types = [
        "Gun Court - High Court Division (judge alone, in camera)",
        "Gun Court - Resident Magistrate Division (preliminary enquiry)",
        "Parish Court (summary drug offence)",
    ]
    remand_locations = [
        "Mandeville Police Lock-Up",
        "Santa Cruz Police Lock-Up",
        "May Pen Police Lock-Up",
        "Tower Street Adult Correctional Centre",
        "St. Catherine Adult Correctional Centre",
    ]

    for i in range(15):
        arrest_id = generate_id("ARR", "arrests", "arrest_id")
        parish = _PARISHES[i % 3]
        arrest_date = _rand_date(75, 5)
        deadline_48hr = (
            datetime.strptime(arrest_date, "%Y-%m-%d") + timedelta(hours=48)
        ).strftime("%Y-%m-%d %H:%M")
        offence_desc, law_section = _OFFENCES[i % len(_OFFENCES)]

        bail = bail_statuses[i % len(bail_statuses)]
        court = court_types[i % len(court_types)]
        first_court = _future_date(7, 30) if "Remanded" in bail or "Bail Granted" in bail else None
        remand = remand_locations[i % len(remand_locations)] if "Remanded" in bail else None

        io_idx = i % 4

        conn.execute("""
            INSERT INTO arrests
                (arrest_id, arrest_date, arrest_time,
                 linked_case_id, suspect_name, suspect_dob,
                 suspect_address, parish, arrest_location,
                 arresting_officer, arresting_officer_rank,
                 offence_1, law_section_1,
                 deadline_48hr, bail_status,
                 court_type, first_court_date, remand_location,
                 statements_taken, witness_count,
                 record_status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            arrest_id, arrest_date, _rand_time(),
            case_ids[i] if i < len(case_ids) else None,
            _SUSPECT_NAMES[i],
            f"{random.randint(1975,2000)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            random.choice(_PARISH_LOCATIONS[parish]),
            parish, random.choice(_PARISH_LOCATIONS[parish]),
            _IO_BADGES[io_idx], _IO_RANKS[io_idx],
            offence_desc, law_section,
            deadline_48hr, bail,
            court, first_court, remand,
            "Yes" if i < 12 else "No", random.randint(0, 4),
            "Submitted", _IO_BADGES[io_idx],
            _rand_datetime(75, 5),
        ))


# ---------------------------------------------------------------------------
# 8. Chain of Custody (20)
# ---------------------------------------------------------------------------

_EXHIBIT_TYPES = [
    "Firearm (complete weapon)", "Ammunition (live rounds)",
    "Magazine (detachable)", "Drug Sample (for lab analysis)",
    "Drug Bulk (for weighing/destruction)", "Cash / Currency (JMD)",
    "Electronic Device (phone/laptop/tablet)", "SIM Card / Memory Card",
    "Clothing / Personal Item", "CCTV / Video Footage",
]


def _seed_chain_of_custody(conn):
    print("Seeding chain of custody ...")

    case_ids = _seed_cases._case_ids

    for i in range(20):
        exhibit_type = _EXHIBIT_TYPES[i % len(_EXHIBIT_TYPES)]
        tag = f"EXH-{str(i+1).zfill(4)}"
        case_id = case_ids[i % len(case_ids)]
        io_idx = i % 4
        seized_date = _rand_date(70, 5)

        transfer_to = random.choice([
            "FNID Area 3 Armoury", "IFSLM Laboratory",
            "Evidence Room - Mandeville", "Court Exhibit Room",
        ])

        conn.execute("""
            INSERT INTO chain_of_custody
                (exhibit_tag, exhibit_type, description,
                 linked_case_id, seized_date, seized_by, seized_location,
                 current_custodian, storage_location,
                 transfer_date, transfer_from, transfer_to, transfer_reason,
                 condition, photos_taken, seal_intact,
                 disposal_status, record_status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            tag, exhibit_type,
            f"{exhibit_type} seized in connection with case {case_id}",
            case_id, seized_date, _IO_BADGES[io_idx],
            random.choice(_PARISH_LOCATIONS[_PARISHES[i % 3]]),
            _IO_NAMES[io_idx],
            "FNID Area 3 Evidence Room - Mandeville",
            _rand_date(60, 2),
            _IO_NAMES[io_idx], transfer_to,
            "Transfer for forensic examination" if i % 3 == 0 else "Secure storage",
            random.choice(["Good", "Good", "Fair", "Sealed"]),
            "Yes", "Yes",
            "Held - Active Case (court proceedings)",
            "Submitted", _IO_BADGES[io_idx],
            _rand_datetime(70, 5),
        ))


# ---------------------------------------------------------------------------
# 9. Lab Tracking (8)
# ---------------------------------------------------------------------------

def _seed_lab_tracking(conn):
    print("Seeding lab tracking ...")

    case_ids = _seed_cases._case_ids
    lab_types = [
        "IFSLM Ballistics", "IFSLM Chemistry", "IFSLM Ballistics",
        "IFSLM Chemistry", "IFSLM DNA", "IFSLM Chemistry",
        "IFSLM Ballistics", "IFSLM Fingerprints",
    ]
    exam_types = [
        "Ballistic comparison", "Drug identification & weight",
        "Firearm functionality test", "Drug purity analysis",
        "DNA extraction & profiling", "Drug identification",
        "Serial number restoration", "Latent print analysis",
    ]
    cert_statuses = [
        "Certificate Issued - Collected",
        "Analysis In Progress",
        "Submitted to IFSLM (Institute of Forensic Science & Legal Medicine)",
        "Certificate Issued - Not Yet Collected",
        "Analysis In Progress",
        "Certificate Overdue (>8 weeks)",
        "Submitted to IFSLM (Institute of Forensic Science & Legal Medicine)",
        "Analysis In Progress",
    ]

    for i in range(8):
        lab_ref = generate_id("LAB", "lab_tracking", "lab_ref")
        sub_date = _rand_date(60, 10)
        expected = (
            datetime.strptime(sub_date, "%Y-%m-%d") + timedelta(weeks=8)
        ).strftime("%Y-%m-%d")

        completion = None
        cert_number = None
        if cert_statuses[i].startswith("Certificate Issued"):
            completion = _rand_date(30, 1)
            cert_number = f"IFSLM-{2026}-{random.randint(1000, 9999)}"

        conn.execute("""
            INSERT INTO lab_tracking
                (lab_ref, exhibit_tag, linked_case_id,
                 submission_date, lab_type, exam_type, analyst,
                 expected_date, completion_date,
                 certificate_number, certificate_status,
                 result, record_status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            lab_ref, f"EXH-{str(i+1).zfill(4)}", case_ids[i],
            sub_date, lab_types[i], exam_types[i],
            random.choice(["Dr. A. Morrison", "Dr. P. Chang", "Dr. R. Samuels"]),
            expected, completion,
            cert_number, cert_statuses[i],
            "Positive match" if completion else "Pending",
            "Submitted", "JCF-1005",
            _rand_datetime(60, 10),
        ))


# ---------------------------------------------------------------------------
# 10. DPP Pipeline (10)
# ---------------------------------------------------------------------------

def _seed_dpp_pipeline(conn):
    print("Seeding DPP pipeline ...")

    case_ids = _seed_cases._case_ids
    dpp_statuses = [
        "File Being Prepared by OIC",
        "File Submitted to DPP",
        "Crown Counsel Reviewing",
        "Additional Investigation Requested",
        "Ruling - Charge Approved",
        "Awaiting Forensic Certificate (Chemistry - IFSLM)",
        "Awaiting Ballistic Certificate (IFSLM)",
        "Ruling - No Charge (Insufficient Evidence)",
        "Voluntary Bill of Indictment Filed",
        "File Under Review by Unit Commander",
    ]
    crown_counsels = [
        "Ms. D. Thompson, Crown Counsel",
        "Mr. R. Sinclair, Senior Crown Counsel",
        "Ms. P. Williams, Crown Counsel",
        None, None,
    ]

    for i in range(10):
        case_id = case_ids[i]
        classification = _CLASSIFICATIONS[i % len(_CLASSIFICATIONS)]
        offence_desc = _OFFENCES[i % len(_OFFENCES)][0]
        io_idx = i % 4

        ruling_date = None
        ruling_outcome = None
        if "Ruling" in dpp_statuses[i]:
            ruling_date = _rand_date(20, 1)
            ruling_outcome = dpp_statuses[i].split(" - ", 1)[1]

        conn.execute("""
            INSERT INTO dpp_pipeline
                (linked_case_id, classification, oic_name, suspect_name,
                 offence_summary, dpp_file_date, crown_counsel, dpp_status,
                 evidential_sufficiency, public_interest_met,
                 ruling_date, ruling_outcome,
                 record_status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            case_id, classification, _IO_NAMES[io_idx], _SUSPECT_NAMES[i],
            offence_desc, _rand_date(50, 5),
            crown_counsels[i % len(crown_counsels)],
            dpp_statuses[i],
            "Yes" if i in (4, 8) else "No",
            "Yes" if i in (4, 8) else "No",
            ruling_date, ruling_outcome,
            "Submitted", _IO_BADGES[io_idx],
            _rand_datetime(50, 5),
        ))


# ---------------------------------------------------------------------------
# 11. SOP Checklists (8)
# ---------------------------------------------------------------------------

def _seed_sop_checklists(conn):
    print("Seeding SOP checklists ...")

    case_ids = _seed_cases._case_ids
    compliance_levels = [
        "Fully Compliant",
        "Substantially Compliant (minor deficiencies)",
        "Non-Compliant - Missing Statements",
        "Non-Compliant - Missing Forensic Certificates",
        "Under Review",
        "Fully Compliant",
        "Non-Compliant - Multiple Deficiencies",
        "Substantially Compliant (minor deficiencies)",
    ]

    for i in range(8):
        io_idx = i % 4
        is_compliant = "Fully Compliant" in compliance_levels[i]
        is_partial = "Substantially" in compliance_levels[i]

        def _yn(prob_yes):
            return "Yes" if random.random() < prob_yes else "No"

        # Higher probability of 'Yes' for compliant cases
        p = 1.0 if is_compliant else (0.8 if is_partial else 0.4)

        conn.execute("""
            INSERT INTO sop_checklists
                (linked_case_id, oic_name, checklist_date,
                 station_diary_entry, crime_report_filed,
                 offence_register_updated, occurrence_book_entry,
                 scene_log_started, suspect_cautioned,
                 rights_advised, attorney_access,
                 detainee_book_entry, property_book_entry,
                 lockup_time_recorded, forty_eight_hr_compliance,
                 charge_sheet_prepared, exhibit_register_updated,
                 exhibits_photographed, exhibits_sealed_tagged,
                 chain_of_custody_started, forensic_submissions_made,
                 victim_statement, witness_statements,
                 suspect_statement_cautioned, officer_statements,
                 scene_photographed, cctv_canvass,
                 neighbourhood_enquiry,
                 forensic_certs_received, all_statements_compiled,
                 exhibit_list_complete, case_summary_prepared,
                 evidential_sufficiency_met, dpp_file_complete,
                 overall_compliance, compliance_notes,
                 record_status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            case_ids[i], _IO_NAMES[io_idx], _rand_date(60, 5),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            _yn(p),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            _yn(p), _yn(p),
            compliance_levels[i],
            f"SOP review completed for {case_ids[i]}.",
            "Submitted", _IO_BADGES[io_idx],
            _rand_datetime(60, 5),
        ))


# ---------------------------------------------------------------------------
# 12. Witness Statements (12)
# ---------------------------------------------------------------------------

_WITNESS_TYPES = [
    "Eyewitness", "Expert witness", "Character witness",
    "Victim", "Police officer", "Civilian informant",
]


def _seed_witness_statements(conn):
    print("Seeding witness statements ...")

    case_ids = _seed_cases._case_ids
    witness_names = [
        "Pauline Baker", "Winston Chambers", "Denise Forbes",
        "Raymond Grant", "Marcia Hylton", "Trevor Irving",
        "Norma Jackson", "Kevin Lawrence", "Andrea McFarlane",
        "Byron Nelson", "Sheila Oakley", "Philip Reid",
    ]

    for i in range(12):
        stmt_id = generate_id("WS", "witness_statements", "statement_id")
        io_idx = i % 4
        parish = _PARISHES[i % 3]

        conn.execute("""
            INSERT INTO witness_statements
                (statement_id, linked_case_id, witness_name, witness_type,
                 witness_address, witness_phone, relation_to_case,
                 statement_date, statement_taken_by,
                 statement_pages, statement_signed,
                 witness_willing, special_measures_needed,
                 available_for_court,
                 record_status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            stmt_id, case_ids[i % len(case_ids)],
            witness_names[i], _WITNESS_TYPES[i % len(_WITNESS_TYPES)],
            random.choice(_PARISH_LOCATIONS[parish]),
            f"876-{random.randint(200,999)}-{random.randint(1000,9999)}",
            random.choice([
                "Eyewitness at scene", "Neighbour heard gunshots",
                "Forensic analyst", "Arresting officer",
                "Victim of robbery", "Bystander",
            ]),
            _rand_date(60, 3), _IO_BADGES[io_idx],
            random.randint(1, 5),
            "Yes" if i < 10 else "No",
            "Yes" if i < 11 else "No",
            "No" if i == 5 else "No" if i == 9 else "No",
            "Yes" if i < 10 else "No",
            "Submitted", _IO_BADGES[io_idx],
            _rand_datetime(60, 3),
        ))


# ---------------------------------------------------------------------------
# 13. Disclosure Log (5)
# ---------------------------------------------------------------------------

def _seed_disclosure_log(conn):
    print("Seeding disclosure log ...")

    case_ids = _seed_cases._case_ids
    disc_types = [
        "Primary prosecution disclosure",
        "Unused material schedule",
        "Expert evidence disclosure",
        "CCTV/digital evidence disclosure",
        "Supplementary disclosure",
    ]
    disc_statuses = [
        "Primary Disclosure Served on Defence",
        "Disclosure Schedule Being Prepared",
        "Primary Disclosure Package Prepared",
        "All Disclosure Complete",
        "Supplementary Disclosure Pending",
    ]

    for i in range(5):
        disc_id = generate_id("DISC", "disclosure_log", "disclosure_id")
        io_idx = i % 4

        conn.execute("""
            INSERT INTO disclosure_log
                (disclosure_id, linked_case_id, disclosure_date,
                 disclosure_type, material_disclosed,
                 served_on_defence, defence_solicitor,
                 service_method, service_date,
                 disclosure_status, prepared_by,
                 record_status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            disc_id, case_ids[i],
            _rand_date(40, 3),
            disc_types[i],
            f"Prosecution evidence bundle for {case_ids[i]}",
            "Yes" if i in (0, 3) else "No",
            random.choice([
                "Henlin Gibson Henlin", "Livingston Alexander & Levy",
                "Knight Junor & Samuels", None,
            ]),
            random.choice(["Hand delivery", "Registered post", "Court filing"]),
            _rand_date(35, 1) if i in (0, 3) else None,
            disc_statuses[i],
            _IO_NAMES[io_idx],
            "Submitted", _IO_BADGES[io_idx],
            _rand_datetime(40, 3),
        ))


# ---------------------------------------------------------------------------
# 14. Case Lifecycle (entries for several cases)
# ---------------------------------------------------------------------------

def _seed_case_lifecycle(conn):
    print("Seeding case lifecycle ...")

    case_ids = _seed_cases._case_ids
    # Create lifecycle entries for the first 8 cases showing progression
    stage_progression = [
        ["intake", "appreciation", "vetting", "assignment", "investigation"],
        ["intake", "appreciation", "vetting", "assignment", "investigation", "follow_up"],
        ["intake", "appreciation", "vetting", "assignment", "investigation", "review", "court_preparation"],
        ["intake", "appreciation", "vetting", "assignment",
         "investigation", "review", "court_preparation", "before_court"],
        ["intake", "appreciation", "vetting", "assignment", "investigation"],
        ["intake", "appreciation", "vetting"],
        ["intake", "appreciation", "vetting", "assignment",
         "investigation", "review", "court_preparation", "before_court",
         "closed"],
        ["intake", "appreciation", "suspended"],
    ]

    for case_idx, stages in enumerate(stage_progression):
        case_id = case_ids[case_idx]
        base_date = datetime.now() - timedelta(days=80 - case_idx * 5)

        for stage_idx, stage in enumerate(stages):
            entered = base_date + timedelta(days=stage_idx * 3)
            exited = entered + timedelta(days=2, hours=12) if stage_idx < len(stages) - 1 else None
            outcome = "Completed" if exited else None

            conn.execute("""
                INSERT INTO case_lifecycle
                    (case_id, stage, entered_at, entered_by,
                     exited_at, exited_by, outcome, notes)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                case_id, stage,
                entered.strftime("%Y-%m-%d %H:%M:%S"),
                "JCF-1004",
                exited.strftime("%Y-%m-%d %H:%M:%S") if exited else None,
                "JCF-1004" if exited else None,
                outcome,
                f"Case {case_id} entered {stage} stage.",
            ))


# ---------------------------------------------------------------------------
# 15. File Movements (8)
# ---------------------------------------------------------------------------

def _seed_file_movements(conn):
    print("Seeding file movements ...")

    case_ids = _seed_cases._case_ids
    movement_types = [
        "Checkout", "Checkout", "Transfer", "Checkout",
        "Transfer", "Checkout", "Return", "Checkout",
    ]
    destinations = [
        "DCO Office", "Court Liaison Officer", "DPP Office - Kingston",
        "IO Desk - JCF-1005", "Forensic Liaison Section",
        "Inspector Clarke Office", "Registry - Filing Room",
        "IO Desk - JCF-1007",
    ]
    reasons = [
        "DCO review of case progress",
        "Preparation for court appearance",
        "DPP file submission",
        "Investigation officer review",
        "Forensic certificate attachment",
        "Station Manager review",
        "Re-filing after court appearance",
        "Follow-up investigation actions",
    ]
    statuses = [
        "Out", "Out", "Out", "Out",
        "Out", "Out", "Returned", "Out",
    ]

    for i in range(8):
        case_id = case_ids[i]

        conn.execute("""
            INSERT INTO file_movements
                (case_id, file_type, movement_type,
                 moved_from, moved_to, moved_by, moved_at,
                 reason, expected_return, actual_return,
                 status, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            case_id, "Case File",
            movement_types[i],
            "Registry - Filing Room",
            destinations[i],
            "JCF-1009",
            _rand_datetime(30, 1),
            reasons[i],
            _future_date(2, 7) if statuses[i] == "Out" else None,
            _rand_date(5, 1) if statuses[i] == "Returned" else None,
            statuses[i],
            f"File movement for {case_id}: {reasons[i]}.",
        ))


# ---------------------------------------------------------------------------
# 16. Case Reviews (10)
# ---------------------------------------------------------------------------

def _seed_case_reviews(conn):
    print("Seeding case reviews ...")

    case_ids = _seed_cases._case_ids
    review_types = [
        "14-day initial review", "28-day follow-up review",
        "DCO case conference", "Station Manager audit",
        "DPP file readiness review", "Quarterly cold-case review",
    ]
    reviewer_badges = ["JCF-1001", "JCF-1002", "JCF-1004"]
    reviewer_names = [
        "Superintendent Althea Morgan",
        "DSP Karl Williams",
        "Inspector Sandra Clarke",
    ]
    outcomes = [
        "Satisfactory progress - continue investigation",
        "Additional witness statements required",
        "File nearly complete - schedule DPP submission",
        "IO to follow up forensic lab within 7 days",
        "Escalate to DCO for resource allocation",
        "Case to be suspended - insufficient leads",
    ]

    for i in range(10):
        case_id = case_ids[i % len(case_ids)]
        rev_type = review_types[i % len(review_types)]
        rev_idx = i % 3
        is_completed = i < 6

        scheduled = _rand_date(40, 5) if is_completed else _future_date(7, 30)
        actual = scheduled if is_completed else None
        status = "Completed" if is_completed else "Scheduled"

        conn.execute("""
            INSERT INTO case_reviews
                (case_id, review_type, scheduled_date, actual_date,
                 reviewer_badge, reviewer_name,
                 outcome, findings, directives,
                 next_review_date, status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            case_id, rev_type, scheduled, actual,
            reviewer_badges[rev_idx], reviewer_names[rev_idx],
            outcomes[i % len(outcomes)] if is_completed else None,
            f"Review findings for {case_id}." if is_completed else None,
            f"IO to action review directives for {case_id}." if is_completed else None,
            _future_date(14, 42),
            status,
            reviewer_badges[rev_idx],
            _rand_datetime(40, 5),
        ))


# ---------------------------------------------------------------------------
# 17. MCR Entries (5)
# ---------------------------------------------------------------------------

def _seed_mcr_entries(conn):
    print("Seeding MCR entries ...")

    case_ids = _seed_cases._case_ids
    source_tables = ["cases", "arrests", "firearm_seizures", "operations", "intel_reports"]
    summaries = [
        "New firearms case registered in Manchester - suspect Marlon Gayle detained with 9mm pistol.",
        "Arrest made in St. Elizabeth - suspect Dwayne Sinclair charged with trafficking.",
        "Firearm seizure in Clarendon - Glock 19 recovered during search warrant execution.",
        "Operation Ironclad concluded in Manchester - 2 firearms and ammunition seized.",
        "Critical intelligence received regarding suspected gun cache in Porus area.",
    ]

    for i in range(5):
        mcr_date = _rand_date(10, 1)
        conn.execute("""
            INSERT INTO mcr_entries
                (mcr_date, window_start, window_end,
                 source_table, source_id,
                 classification, parish, summary,
                 fnid_relevant, lead_suggestions,
                 compiled_by, compiled_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            mcr_date, "05:30", "05:30",
            source_tables[i], case_ids[i],
            _CLASSIFICATIONS[i], _PARISHES[i % 3],
            summaries[i],
            1, "Follow up with assigned IO for status update.",
            "JCF-1002",
            _rand_datetime(10, 1),
        ))


# ---------------------------------------------------------------------------
# 18. Alerts (8)
# ---------------------------------------------------------------------------

def _seed_alerts(conn):
    print("Seeding alerts ...")

    case_ids = _seed_cases._case_ids
    alerts_data = [
        ("deadline", "case", case_ids[0],
         "48-Hour Deadline Approaching",
         f"Case {case_ids[0]}: suspect detention approaching 48-hour limit.",
         "critical", "io", "JCF-1005"),
        ("deadline", "case", case_ids[1],
         "DPP Submission Overdue",
         f"Case {case_ids[1]}: DPP file submission is 5 days overdue.",
         "warning", "io", "JCF-1006"),
        ("review", "case", case_ids[2],
         "14-Day Review Due",
         f"Case {case_ids[2]}: initial 14-day review is scheduled for today.",
         "info", "dco", "JCF-1002"),
        ("forensic", "case", case_ids[3],
         "Forensic Certificate Overdue",
         f"Case {case_ids[3]}: IFSLM certificate overdue (>8 weeks).",
         "warning", "io", "JCF-1007"),
        ("file_movement", "case", case_ids[4],
         "File Not Returned",
         f"Case {case_ids[4]}: case file checked out 5 days ago, not yet returned.",
         "warning", "registrar", "JCF-1009"),
        ("court", "case", case_ids[5],
         "Court Date in 7 Days",
         f"Case {case_ids[5]}: next court appearance is in 7 days.",
         "info", "io", "JCF-1005"),
        ("intel", "case", case_ids[6],
         "New Intelligence Linked",
         f"New critical intel report linked to case {case_ids[6]}.",
         "info", "intel_officer", "JCF-1010"),
        ("system", "system", "SYS",
         "Weekly Database Backup Completed",
         "Automated weekly backup completed successfully.",
         "info", "admin", "JCF-1001"),
    ]

    for (alert_type, target_type, target_id, title, message,
         severity, target_role, target_badge) in alerts_data:
        conn.execute("""
            INSERT INTO alerts
                (alert_type, target_type, target_id,
                 title, message, severity,
                 target_role, target_badge,
                 is_read, is_dismissed, due_date, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            alert_type, target_type, target_id,
            title, message, severity,
            target_role, target_badge,
            0, 0,
            _future_date(1, 14) if severity in ("critical", "warning") else None,
            _rand_datetime(5, 0),
        ))


# ---------------------------------------------------------------------------
# 19. Intel Targets (3)
# ---------------------------------------------------------------------------

def _seed_intel_targets(conn):
    print("Seeding intel targets ...")

    case_ids = _seed_cases._case_ids
    targets = [
        {
            "name": "Orville 'Bucky' Brown",
            "aliases": "Bucky, O-Brown",
            "description": (
                "Suspected leader of firearms trafficking network "
                "operating across Manchester and Clarendon parishes."
            ),
            "parish": "Manchester",
            "area": "Mandeville / Porus corridor",
            "linked_cases": f"{case_ids[0]},{case_ids[1]}",
            "modus_operandi": "Uses modified vehicles with hidden compartments; firearms sourced from Kingston docks.",
            "threat_level": "High",
        },
        {
            "name": "Sanjay 'Chemist' Mitchell",
            "aliases": "Chemist, Sanj",
            "description": (
                "Major cocaine distributor in St. Elizabeth; "
                "linked to transnational supply chain via fishing vessels."
            ),
            "parish": "St. Elizabeth",
            "area": "Black River / Treasure Beach coast",
            "linked_cases": f"{case_ids[5]},{case_ids[6]}",
            "modus_operandi": "Uses fishing vessels for coastal drops; distribution via rural taxi network.",
            "threat_level": "Critical",
        },
        {
            "name": "Tyrone 'Trigger' Marshall",
            "aliases": "Trigger, T-Marsh",
            "description": (
                "Suspected enforcer linked to multiple shooting incidents "
                "in Clarendon; known associate of gang network."
            ),
            "parish": "Clarendon",
            "area": "May Pen / Lionel Town",
            "linked_cases": f"{case_ids[11]},{case_ids[13]}",
            "modus_operandi": "Operates at night; uses stolen motorcycles; multiple illegal firearms suspected.",
            "threat_level": "High",
        },
    ]

    for t in targets:
        target_id = generate_id("TGT", "intel_targets", "target_id")
        conn.execute("""
            INSERT INTO intel_targets
                (target_id, target_name, aliases, description,
                 parish, area, linked_cases, linked_intel,
                 modus_operandi, threat_level, status,
                 notes, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            target_id, t["name"], t["aliases"], t["description"],
            t["parish"], t["area"], t["linked_cases"], None,
            t["modus_operandi"], t["threat_level"], "Active",
            f"Target profile created. Linked to ongoing investigations in {t['parish']}.",
            "JCF-1003",
            _rand_datetime(60, 10),
        ))


# ---------------------------------------------------------------------------
# 20. DCRR (10)
# ---------------------------------------------------------------------------

def _seed_dcrr(conn):
    print("Seeding DCRR entries ...")

    case_ids = _seed_cases._case_ids
    stations = [
        "Mandeville Police Station", "Santa Cruz Police Station",
        "May Pen Police Station", "Christiana Police Station",
        "Black River Police Station", "Porus Police Station",
        "Chapelton Police Station", "Lionel Town Police Station",
        "Mandeville Police Station", "May Pen Police Station",
    ]

    for i in range(10):
        dcrr_number = generate_id("DCRR", "dcrr", "dcrr_number")
        case_id = case_ids[i]
        classification = _CLASSIFICATIONS[i % len(_CLASSIFICATIONS)]
        offence_desc = _OFFENCES[i % len(_OFFENCES)][0]
        io_idx = i % 4
        report_date = _rand_date(70, 5)

        conn.execute("""
            INSERT INTO dcrr
                (dcrr_number, case_id, report_date, station,
                 diary_number, classification, offence,
                 complainant_name, suspect_name,
                 oic_badge, oic_name,
                 status, created_by, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            dcrr_number, case_id, report_date, stations[i],
            f"SD/{_STATION_CODES[_PARISHES[i % 3]]}/{datetime.now().year}/{200 + i}",
            classification, offence_desc,
            _VICTIM_NAMES[i % len(_VICTIM_NAMES)],
            _SUSPECT_NAMES[i],
            _IO_BADGES[io_idx], _IO_NAMES[io_idx],
            random.choice(["Open", "Open", "Closed", "Under Investigation"]),
            _IO_BADGES[io_idx],
            _rand_datetime(70, 5),
        ))
