"""
FNID Database Models - SQLite

Central schema designed around Investigations and Case Management.
All tables link back to the Case (investigation) as the core entity.
"""

import os
import sqlite3
from datetime import datetime

# Will be set by the app factory
_db_path = None


def configure(db_path):
    """Set the database path. Called by the app factory."""
    global _db_path
    _db_path = db_path


def get_db():
    """Get database connection with row factory."""
    if _db_path is None:
        raise RuntimeError("Database not configured. Call models.configure(path) first.")
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# Whitelist of valid table names for SQL safety
VALID_TABLES = frozenset({
    "officers", "cases", "intel_reports", "operations",
    "firearm_seizures", "narcotics_seizures", "arrests",
    "chain_of_custody", "lab_tracking", "dpp_pipeline",
    "sop_checklists", "witness_statements", "disclosure_log",
    "audit_log",
    # Phase 1 additions
    "case_lifecycle", "cr_forms", "dcrr", "major_crime_register", "file_movements",
    "correspondence", "investigator_cards", "case_reviews",
    "mcr_entries", "alerts", "system_settings",
    "mcr_cr7_forms",
    "intel_targets", "transport_vehicles", "transport_trips",
    "user_sessions",
    # Phase 5 additions
    "member_documents", "member_kpis",
    # AI assistant harness
    "assistant_agent_profiles", "assistant_runs", "assistant_actions",
})


def get_table_columns(table_name):
    """Return the set of column names for a given table."""
    if table_name not in VALID_TABLES:
        raise ValueError(f"Invalid table name: {table_name}")
    conn = get_db()
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = {row["name"] for row in cursor.fetchall()}
    conn.close()
    return columns


def _migrate_add_column(cursor, table, column, col_type):
    """Add a column to an existing table if it doesn't already exist."""
    cols = [row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_db():
    """Initialize database schema."""
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS officers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        badge_number TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        rank TEXT NOT NULL,
        section TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'io',
        password_hash TEXT,
        email TEXT,
        unit_access TEXT NOT NULL DEFAULT 'all',
        is_active INTEGER DEFAULT 1,
        must_change_password INTEGER DEFAULT 0,
        last_login TEXT,
        failed_attempts INTEGER DEFAULT 0,
        locked_until TEXT,
        admin_tier INTEGER DEFAULT NULL,
        verification_status TEXT DEFAULT 'active',
        registered_at TEXT,
        locked_at TEXT,
        duty_assignment TEXT,
        regulation_no TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT UNIQUE NOT NULL,
        registration_date TEXT NOT NULL,
        classification TEXT NOT NULL,
        oic_badge TEXT NOT NULL,
        oic_name TEXT NOT NULL,
        oic_rank TEXT NOT NULL,
        parish TEXT NOT NULL,
        division TEXT DEFAULT 'FNID Area 3',
        offence_description TEXT NOT NULL,
        law_and_section TEXT NOT NULL,
        suspect_name TEXT,
        suspect_dob TEXT,
        suspect_address TEXT,
        suspect_occupation TEXT,
        victim_name TEXT,
        victim_address TEXT,
        linked_intel_id TEXT,
        linked_op_id TEXT,
        linked_arrest_id TEXT,
        case_status TEXT NOT NULL DEFAULT 'Open - Active Investigation',
        file_completeness TEXT DEFAULT 'Not Started',
        sop_compliance TEXT DEFAULT 'Under Review',
        dpp_submission_date TEXT,
        dpp_status TEXT,
        dpp_ruling TEXT,
        court_type TEXT,
        next_court_date TEXT,
        trial_date TEXT,
        verdict TEXT,
        sentence TEXT,
        poca_referred TEXT DEFAULT 'No',
        poca_status TEXT DEFAULT 'Not Applicable',
        dcrr_number TEXT,
        primary_register_type TEXT DEFAULT 'dcrr',
        primary_register_number TEXT,
        station_code TEXT,
        diary_number TEXT,
        assigned_io_badge TEXT,
        assigned_date TEXT,
        crime_type TEXT DEFAULT 'major',
        workflow_type TEXT DEFAULT 'non-uniformed',
        current_stage TEXT DEFAULT 'intake',
        last_review_date TEXT,
        next_review_date TEXT,
        suspended_date TEXT,
        suspended_reason TEXT,
        reopened_date TEXT,
        closed_date TEXT,
        closed_reason TEXT,
        record_status TEXT DEFAULT 'Draft',
        submitted_by TEXT,
        submitted_date TEXT,
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS intel_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        intel_id TEXT UNIQUE NOT NULL,
        date_received TEXT NOT NULL,
        time_received TEXT,
        source TEXT NOT NULL,
        source_ref TEXT,
        priority TEXT NOT NULL,
        subject_matter TEXT NOT NULL,
        firearms_related TEXT DEFAULT 'No',
        narcotics_related TEXT DEFAULT 'No',
        trafficking_related TEXT DEFAULT 'No',
        target_person TEXT,
        target_location TEXT,
        parish TEXT NOT NULL,
        substance_of_intel TEXT,
        triage_decision TEXT,
        triage_by TEXT,
        triage_date TEXT,
        linked_op_id TEXT,
        linked_case_id TEXT,
        outcome TEXT,
        outcome_notes TEXT,
        record_status TEXT DEFAULT 'Draft',
        submitted_by TEXT,
        submitted_date TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        op_id TEXT UNIQUE NOT NULL,
        op_name TEXT NOT NULL,
        op_date TEXT NOT NULL,
        op_type TEXT NOT NULL,
        warrant_basis TEXT,
        warrant_number TEXT,
        issuing_jp TEXT,
        parish TEXT NOT NULL,
        target_location TEXT,
        target_person TEXT,
        team_lead TEXT NOT NULL,
        team_lead_rank TEXT,
        team_size INTEGER,
        joint_agency TEXT,
        linked_intel_id TEXT,
        start_time TEXT,
        end_time TEXT,
        duration_hrs REAL,
        firearms_seized INTEGER DEFAULT 0,
        narcotics_seized INTEGER DEFAULT 0,
        ammo_seized INTEGER DEFAULT 0,
        cash_seized REAL DEFAULT 0,
        arrests_made INTEGER DEFAULT 0,
        outcome TEXT,
        outcome_notes TEXT,
        risk_assessment TEXT,
        body_cam TEXT DEFAULT 'No',
        evidence_tagged TEXT DEFAULT 'No',
        record_status TEXT DEFAULT 'Draft',
        submitted_by TEXT,
        submitted_date TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS firearm_seizures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seizure_id TEXT UNIQUE NOT NULL,
        seizure_date TEXT NOT NULL,
        linked_op_id TEXT,
        linked_case_id TEXT,
        parish TEXT NOT NULL,
        location TEXT,
        firearm_type TEXT NOT NULL,
        make TEXT,
        model TEXT,
        serial_number TEXT,
        calibre TEXT,
        country_of_origin TEXT,
        ammo_count INTEGER DEFAULT 0,
        magazine_count INTEGER DEFAULT 0,
        ibis_status TEXT DEFAULT 'Not Submitted',
        etrace_status TEXT DEFAULT 'Not Submitted',
        exhibit_tag TEXT,
        storage_location TEXT,
        seized_by TEXT NOT NULL,
        witness_officer TEXT,
        record_status TEXT DEFAULT 'Draft',
        submitted_by TEXT,
        submitted_date TEXT,
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS narcotics_seizures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seizure_id TEXT UNIQUE NOT NULL,
        seizure_date TEXT NOT NULL,
        linked_op_id TEXT,
        linked_case_id TEXT,
        parish TEXT NOT NULL,
        location TEXT,
        drug_type TEXT NOT NULL,
        quantity REAL,
        unit TEXT,
        est_street_value REAL,
        packaging_method TEXT,
        concealment_method TEXT,
        field_test_result TEXT,
        lab_cert_status TEXT DEFAULT 'Not Yet Submitted to Lab',
        exhibit_tag TEXT,
        storage_location TEXT,
        seized_by TEXT NOT NULL,
        witness_officer TEXT,
        record_status TEXT DEFAULT 'Draft',
        submitted_by TEXT,
        submitted_date TEXT,
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS arrests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arrest_id TEXT UNIQUE NOT NULL,
        arrest_date TEXT NOT NULL,
        arrest_time TEXT,
        linked_op_id TEXT,
        linked_case_id TEXT,
        suspect_name TEXT NOT NULL,
        suspect_dob TEXT,
        suspect_address TEXT,
        suspect_occupation TEXT,
        parish TEXT NOT NULL,
        arrest_location TEXT,
        arresting_officer TEXT NOT NULL,
        arresting_officer_rank TEXT,
        offence_1 TEXT NOT NULL,
        law_section_1 TEXT,
        offence_2 TEXT,
        law_section_2 TEXT,
        deadline_48hr TEXT,
        charge_date TEXT,
        charge_within_48hr TEXT,
        bail_status TEXT,
        court_type TEXT,
        first_court_date TEXT,
        remand_location TEXT,
        legal_representation TEXT,
        statements_taken TEXT DEFAULT 'No',
        witness_count INTEGER DEFAULT 0,
        record_status TEXT DEFAULT 'Draft',
        submitted_by TEXT,
        submitted_date TEXT,
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS chain_of_custody (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exhibit_tag TEXT NOT NULL,
        exhibit_type TEXT NOT NULL,
        description TEXT,
        linked_case_id TEXT,
        linked_seizure_id TEXT,
        seized_date TEXT,
        seized_by TEXT,
        seized_location TEXT,
        current_custodian TEXT,
        storage_location TEXT,
        transfer_date TEXT,
        transfer_from TEXT,
        transfer_to TEXT,
        transfer_reason TEXT,
        condition TEXT,
        photos_taken TEXT DEFAULT 'No',
        seal_intact TEXT DEFAULT 'Yes',
        disposal_status TEXT DEFAULT 'Held - Active Case (court proceedings)',
        record_status TEXT DEFAULT 'Draft',
        submitted_by TEXT,
        submitted_date TEXT,
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS lab_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lab_ref TEXT UNIQUE NOT NULL,
        exhibit_tag TEXT NOT NULL,
        linked_case_id TEXT,
        submission_date TEXT NOT NULL,
        lab_type TEXT,
        exam_type TEXT,
        analyst TEXT,
        expected_date TEXT,
        completion_date TEXT,
        certificate_number TEXT,
        certificate_status TEXT DEFAULT 'Not Yet Submitted to Lab',
        result TEXT,
        collected_by TEXT,
        collection_date TEXT,
        ibis_status TEXT,
        etrace_status TEXT,
        record_status TEXT DEFAULT 'Draft',
        submitted_by TEXT,
        submitted_date TEXT,
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS dpp_pipeline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        linked_case_id TEXT NOT NULL,
        classification TEXT,
        oic_name TEXT,
        suspect_name TEXT,
        offence_summary TEXT,
        dpp_file_date TEXT,
        crown_counsel TEXT,
        dpp_status TEXT NOT NULL,
        evidential_sufficiency TEXT DEFAULT 'No',
        public_interest_met TEXT DEFAULT 'No',
        ruling_date TEXT,
        ruling_outcome TEXT,
        ruling_notes TEXT,
        voluntary_bill TEXT DEFAULT 'No',
        prelim_exam TEXT DEFAULT 'No',
        returned_for_investigation TEXT DEFAULT 'No',
        return_reason TEXT,
        resubmission_date TEXT,
        record_status TEXT DEFAULT 'Draft',
        submitted_by TEXT,
        submitted_date TEXT,
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS sop_checklists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        linked_case_id TEXT NOT NULL,
        oic_name TEXT,
        checklist_date TEXT,
        station_diary_entry TEXT DEFAULT 'No',
        crime_report_filed TEXT DEFAULT 'No',
        offence_register_updated TEXT DEFAULT 'No',
        occurrence_book_entry TEXT DEFAULT 'No',
        scene_log_started TEXT DEFAULT 'No',
        suspect_cautioned TEXT DEFAULT 'No',
        rights_advised TEXT DEFAULT 'No',
        attorney_access TEXT DEFAULT 'No',
        detainee_book_entry TEXT DEFAULT 'No',
        property_book_entry TEXT DEFAULT 'No',
        lockup_time_recorded TEXT DEFAULT 'No',
        forty_eight_hr_compliance TEXT DEFAULT 'No',
        charge_sheet_prepared TEXT DEFAULT 'No',
        exhibit_register_updated TEXT DEFAULT 'No',
        exhibits_photographed TEXT DEFAULT 'No',
        exhibits_sealed_tagged TEXT DEFAULT 'No',
        chain_of_custody_started TEXT DEFAULT 'No',
        forensic_submissions_made TEXT DEFAULT 'No',
        ballistic_submission TEXT DEFAULT 'No',
        drug_field_test TEXT DEFAULT 'No',
        ibis_etrace_submitted TEXT DEFAULT 'No',
        victim_statement TEXT DEFAULT 'No',
        witness_statements TEXT DEFAULT 'No',
        suspect_statement_cautioned TEXT DEFAULT 'No',
        officer_statements TEXT DEFAULT 'No',
        expert_statements TEXT DEFAULT 'No',
        scene_photographed TEXT DEFAULT 'No',
        scene_sketch TEXT DEFAULT 'No',
        scene_video TEXT DEFAULT 'No',
        id_parade_required TEXT DEFAULT 'N/A',
        id_parade_conducted TEXT DEFAULT 'N/A',
        cctv_canvass TEXT DEFAULT 'No',
        neighbourhood_enquiry TEXT DEFAULT 'No',
        forensic_certs_received TEXT DEFAULT 'No',
        ballistic_cert_received TEXT DEFAULT 'No',
        post_mortem_received TEXT DEFAULT 'N/A',
        all_statements_compiled TEXT DEFAULT 'No',
        exhibit_list_complete TEXT DEFAULT 'No',
        case_summary_prepared TEXT DEFAULT 'No',
        evidential_sufficiency_met TEXT DEFAULT 'No',
        public_interest_assessed TEXT DEFAULT 'No',
        dpp_file_complete TEXT DEFAULT 'No',
        disclosure_schedule TEXT DEFAULT 'No',
        unused_material_listed TEXT DEFAULT 'No',
        disclosure_served TEXT DEFAULT 'No',
        pii_application TEXT DEFAULT 'N/A',
        supplementary_disclosure TEXT DEFAULT 'N/A',
        overall_compliance TEXT DEFAULT 'Under Review',
        compliance_notes TEXT,
        record_status TEXT DEFAULT 'Draft',
        submitted_by TEXT,
        submitted_date TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS witness_statements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        statement_id TEXT UNIQUE NOT NULL,
        linked_case_id TEXT NOT NULL,
        witness_name TEXT NOT NULL,
        witness_type TEXT,
        witness_address TEXT,
        witness_phone TEXT,
        relation_to_case TEXT,
        statement_date TEXT,
        statement_taken_by TEXT,
        statement_pages INTEGER,
        statement_signed TEXT DEFAULT 'No',
        witness_willing TEXT DEFAULT 'Yes',
        special_measures_needed TEXT DEFAULT 'No',
        special_measures_type TEXT,
        available_for_court TEXT DEFAULT 'Yes',
        record_status TEXT DEFAULT 'Draft',
        submitted_by TEXT,
        submitted_date TEXT,
        notes TEXT,
        statement_text TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS disclosure_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        disclosure_id TEXT UNIQUE NOT NULL,
        linked_case_id TEXT NOT NULL,
        disclosure_date TEXT,
        disclosure_type TEXT,
        material_disclosed TEXT,
        served_on_defence TEXT DEFAULT 'No',
        defence_solicitor TEXT,
        service_method TEXT,
        service_date TEXT,
        acknowledgement_received TEXT DEFAULT 'No',
        pii_application TEXT DEFAULT 'No',
        pii_outcome TEXT,
        supplementary_needed TEXT DEFAULT 'No',
        supplementary_date TEXT,
        disclosure_status TEXT DEFAULT 'Not Required Yet (pre-charge)',
        prepared_by TEXT,
        record_status TEXT DEFAULT 'Draft',
        submitted_by TEXT,
        submitted_date TEXT,
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        record_id TEXT NOT NULL,
        action TEXT NOT NULL,
        officer_badge TEXT,
        officer_name TEXT,
        details TEXT,
        timestamp TEXT DEFAULT (datetime('now'))
    )""")

    # --- Phase 1 new tables ---

    c.execute("""
    CREATE TABLE IF NOT EXISTS case_lifecycle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT NOT NULL,
        stage TEXT NOT NULL,
        entered_at TEXT NOT NULL,
        entered_by TEXT NOT NULL,
        exited_at TEXT,
        exited_by TEXT,
        outcome TEXT,
        notes TEXT,
        FOREIGN KEY (case_id) REFERENCES cases(case_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS cr_forms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        form_id TEXT UNIQUE NOT NULL,
        case_id TEXT NOT NULL,
        form_type TEXT NOT NULL,
        form_data TEXT NOT NULL DEFAULT '{}',
        status TEXT DEFAULT 'Draft',
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        submitted_by TEXT,
        submitted_at TEXT,
        approved_by TEXT,
        approved_at TEXT,
        FOREIGN KEY (case_id) REFERENCES cases(case_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS dcrr (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dcrr_number TEXT UNIQUE NOT NULL,
        case_id TEXT,
        report_date TEXT NOT NULL,
        station TEXT NOT NULL,
        diary_number TEXT,
        classification TEXT NOT NULL,
        offence TEXT NOT NULL,
        complainant_name TEXT,
        suspect_name TEXT,
        oic_badge TEXT,
        oic_name TEXT,
        status TEXT DEFAULT 'Open',
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (case_id) REFERENCES cases(case_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS file_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT NOT NULL,
        file_type TEXT NOT NULL,
        movement_type TEXT NOT NULL,
        moved_from TEXT,
        moved_to TEXT NOT NULL,
        moved_by TEXT NOT NULL,
        moved_at TEXT DEFAULT (datetime('now')),
        reason TEXT NOT NULL,
        expected_return TEXT,
        actual_return TEXT,
        return_logged_by TEXT,
        status TEXT DEFAULT 'Out',
        notes TEXT,
        FOREIGN KEY (case_id) REFERENCES cases(case_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS correspondence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT,
        direction TEXT NOT NULL,
        date TEXT NOT NULL,
        reference_number TEXT,
        from_entity TEXT,
        to_entity TEXT,
        subject TEXT NOT NULL,
        document_type TEXT,
        logged_by TEXT NOT NULL,
        logged_at TEXT DEFAULT (datetime('now')),
        action_required TEXT,
        action_deadline TEXT,
        action_status TEXT DEFAULT 'Pending',
        notes TEXT,
        body TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS investigator_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        officer_badge TEXT NOT NULL,
        case_id TEXT NOT NULL,
        assigned_date TEXT NOT NULL,
        assignment_type TEXT DEFAULT 'primary',
        tasks_assigned TEXT,
        tasks_completed TEXT,
        next_action TEXT,
        next_action_date TEXT,
        supervisor_badge TEXT,
        supervisor_notes TEXT,
        status TEXT DEFAULT 'Active',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (case_id) REFERENCES cases(case_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS case_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT NOT NULL,
        review_type TEXT NOT NULL,
        scheduled_date TEXT NOT NULL,
        actual_date TEXT,
        reviewer_badge TEXT,
        reviewer_name TEXT,
        outcome TEXT,
        findings TEXT,
        directives TEXT,
        next_review_date TEXT,
        status TEXT DEFAULT 'Scheduled',
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (case_id) REFERENCES cases(case_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS mcr_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mcr_date TEXT NOT NULL,
        window_start TEXT NOT NULL,
        window_end TEXT NOT NULL,
        source_table TEXT NOT NULL,
        source_id TEXT NOT NULL,
        classification TEXT,
        parish TEXT,
        summary TEXT,
        fnid_relevant INTEGER DEFAULT 0,
        lead_suggestions TEXT,
        compiled_by TEXT,
        compiled_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS mcr_cr7_forms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        form_id TEXT UNIQUE NOT NULL,
        mcr_date TEXT UNIQUE NOT NULL,
        form_type TEXT NOT NULL DEFAULT 'CR7',
        form_data TEXT NOT NULL DEFAULT '{}',
        status TEXT DEFAULT 'Draft',
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        submitted_by TEXT,
        submitted_at TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT,
        severity TEXT DEFAULT 'warning',
        target_role TEXT,
        target_badge TEXT,
        is_read INTEGER DEFAULT 0,
        is_dismissed INTEGER DEFAULT 0,
        due_date TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        updated_by TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS intel_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_id TEXT UNIQUE NOT NULL,
        target_name TEXT NOT NULL,
        aliases TEXT,
        description TEXT,
        parish TEXT,
        area TEXT,
        linked_cases TEXT,
        linked_intel TEXT,
        modus_operandi TEXT,
        threat_level TEXT DEFAULT 'Medium',
        status TEXT DEFAULT 'Active',
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS transport_vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id TEXT UNIQUE NOT NULL,
        registration TEXT NOT NULL,
        make TEXT,
        model TEXT,
        year INTEGER,
        vehicle_type TEXT,
        assigned_unit TEXT,
        assigned_officer TEXT,
        status TEXT DEFAULT 'Available',
        current_mileage INTEGER DEFAULT 0,
        last_service_date TEXT,
        next_service_due TEXT,
        defects TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS transport_trips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id TEXT UNIQUE NOT NULL,
        vehicle_id TEXT NOT NULL,
        driver_badge TEXT NOT NULL,
        driver_name TEXT,
        trip_date TEXT NOT NULL,
        purpose TEXT NOT NULL,
        linked_case_id TEXT,
        linked_op_id TEXT,
        departure_location TEXT,
        destination TEXT,
        departure_time TEXT,
        return_time TEXT,
        start_mileage INTEGER,
        end_mileage INTEGER,
        fuel_added_litres REAL DEFAULT 0,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (vehicle_id) REFERENCES transport_vehicles(vehicle_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        badge_number TEXT NOT NULL,
        login_at TEXT DEFAULT (datetime('now')),
        logout_at TEXT,
        ip_address TEXT,
        user_agent TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS major_crime_register (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        register_number TEXT UNIQUE NOT NULL,
        case_id TEXT,
        report_date TEXT NOT NULL,
        station TEXT NOT NULL,
        diary_number TEXT,
        classification TEXT NOT NULL,
        offence TEXT NOT NULL,
        complainant_name TEXT,
        suspect_name TEXT,
        oic_badge TEXT,
        oic_name TEXT,
        status TEXT DEFAULT 'Open',
        created_by TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (case_id) REFERENCES cases(case_id)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS assistant_agent_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_key TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        role_scope TEXT NOT NULL,
        enabled INTEGER DEFAULT 0,
        automation_mode TEXT DEFAULT 'assistive',
        max_runs_per_day INTEGER DEFAULT 10,
        max_actions_per_run INTEGER DEFAULT 6,
        max_prompt_chars INTEGER DEFAULT 6000,
        max_tokens INTEGER DEFAULT 1200,
        requires_human_approval INTEGER DEFAULT 1,
        allow_sensitive_context INTEGER DEFAULT 0,
        created_by TEXT,
        updated_by TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS assistant_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT UNIQUE NOT NULL,
        agent_key TEXT NOT NULL,
        case_id TEXT,
        trigger_type TEXT DEFAULT 'manual',
        status TEXT DEFAULT 'queued',
        mode TEXT DEFAULT 'assistive',
        started_by TEXT NOT NULL,
        human_guidance TEXT,
        input_summary TEXT,
        output_summary TEXT,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        request_count INTEGER DEFAULT 0,
        blocked_reason TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS assistant_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        action_key TEXT NOT NULL,
        action_type TEXT NOT NULL,
        case_id TEXT,
        title TEXT NOT NULL,
        description TEXT,
        target_role TEXT,
        target_badge TEXT,
        payload_json TEXT,
        status TEXT DEFAULT 'proposed',
        risk_level TEXT DEFAULT 'low',
        requires_approval INTEGER DEFAULT 1,
        created_object_table TEXT,
        created_object_id TEXT,
        created_by_agent TEXT,
        approved_by TEXT,
        applied_by TEXT,
        rolled_back_by TEXT,
        rollback_notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(run_id, action_key)
    )""")

    # Phase 5: Member documents table
    c.execute("""
    CREATE TABLE IF NOT EXISTS member_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        stored_filename TEXT NOT NULL,
        file_size INTEGER,
        file_type TEXT,
        category TEXT DEFAULT 'General',
        description TEXT,
        uploaded_by TEXT NOT NULL,
        uploaded_at TEXT DEFAULT (datetime('now'))
    )""")

    # Phase 5: Member KPIs table
    c.execute("""
    CREATE TABLE IF NOT EXISTS member_kpis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        officer_badge TEXT NOT NULL,
        period TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        metric_value TEXT,
        target_value TEXT,
        notes TEXT,
        entered_by TEXT NOT NULL,
        entered_at TEXT DEFAULT (datetime('now'))
    )""")

    conn.commit()

    # --- Schema migrations for existing databases ---
    # Add columns that may be missing from older schema versions.
    _migrate_add_column(c, "officers", "admin_tier", "INTEGER DEFAULT NULL")
    _migrate_add_column(c, "officers", "verification_status", "TEXT DEFAULT 'active'")
    _migrate_add_column(c, "officers", "registered_at", "TEXT")
    _migrate_add_column(c, "officers", "locked_at", "TEXT")
    _migrate_add_column(c, "officers", "duty_assignment", "TEXT")
    _migrate_add_column(c, "officers", "regulation_no", "TEXT")
    _migrate_add_column(c, "cases", "primary_register_type", "TEXT DEFAULT 'dcrr'")
    _migrate_add_column(c, "cases", "primary_register_number", "TEXT")

    # In-app statement / memo composition (closes the "must use Word" gap).
    _migrate_add_column(c, "witness_statements", "statement_text", "TEXT")
    _migrate_add_column(c, "correspondence", "body", "TEXT")
    c.execute("""
        UPDATE cases
        SET primary_register_type = COALESCE(primary_register_type, 'dcrr'),
            primary_register_number = COALESCE(primary_register_number, dcrr_number)
        WHERE primary_register_number IS NULL OR primary_register_type IS NULL
    """)
    conn.commit()

    # Insert default admin officer if none exist
    existing = c.execute("SELECT COUNT(*) FROM officers").fetchone()[0]
    if existing == 0:
        import secrets

        from werkzeug.security import generate_password_hash
        default_pw = secrets.token_urlsafe(16)
        c.execute("""
            INSERT INTO officers (badge_number, full_name, rank, section,
                                  role, password_hash, unit_access,
                                  must_change_password, admin_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("ADMIN", "System Administrator", "Superintendent of Police",
              "FNID Headquarters - Area 3", "admin",
              generate_password_hash(default_pw), "all", 1, 1))
        conn.commit()
        _write_initial_credentials([{
            "badge": "ADMIN",
            "name": "System Administrator",
            "role": "admin",
            "password": default_pw,
        }])

    # Auto-seed the 28-officer roster only when explicitly requested.
    # On a single-PC install, each user creates their own account via /register.
    if os.environ.get("FNID_SEED_ROSTER") == "1":
        _seed_named_accounts(c, conn)

    # Seed any missing default system settings without overriding local changes.
    _seed_default_settings(c)
    conn.commit()

    conn.close()


def _write_initial_credentials(accounts):
    """Write first-run credentials to a single-readable file beside the DB.

    accounts: list of {"badge", "name", "role", "password"} dicts.
    Path: <db_dir>/_initial_credentials.txt
    The file is created with restrictive perms where the OS supports it.
    """
    if not _db_path or not accounts:
        return
    out_dir = os.path.dirname(_db_path)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "_initial_credentials.txt")
    lines = [
        "FNID Command Centre - Initial Credentials",
        "=" * 50,
        "This file was generated on first run and contains the initial",
        "passwords for the seeded accounts. After signing in and changing",
        "your password, DELETE this file.",
        "",
    ]
    for acc in accounts:
        lines.append(
            f"  [{acc['role'].upper():>10}] Badge: {acc['badge']:<18} "
            f"Name: {acc['name']:<22} Password: {acc['password']}"
        )
    lines.append("")
    lines.append("Press Ctrl+L at the login page to copy a badge to clipboard.")
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        try:
            # Best-effort restrictive perms (no-op on Windows for most cases)
            os.chmod(out_path, 0o600)
        except OSError:
            pass
    except OSError:
        # Fall back to logger if we cannot write the file
        import logging
        logging.getLogger("fnid_portal").warning(
            "Could not write initial credentials to %s", out_path
        )


def _seed_named_accounts(cursor, conn):
    """Seed the authorised FNID Area 3 roster (28 officers).

    Only officers on this roster may use the system.
    - Insp. Rodney & Cpl. Williams: full command access (admin tier 2)
    - Sgt. Barrett, Det. Sgt. McPherson, Det. Sgt. Henry: supervisor access
    - All others: regular user access
    Each officer's JCF regulation number is stored for reference.
    """
    import secrets

    from werkzeug.security import generate_password_hash

    # (badge, full_name, rank, role, admin_tier, duty_assignment, email, reg_no)
    # email uses firstname.lastname@jcf.gov.jm
    # reg_no = JCF Regulation Number
    ROSTER = [
        # --- Command ---
        ("INSP-RODNEY", "Rayon Rodney", "Inspector",
         "admin", 2, "Command", "rayon.rodney@jcf.gov.jm", None),
        # --- 8am-6pm Shift ---
        ("SGT-ANDERSON", "Tamecka Anderson", "Sergeant",
         "user", None, "8am-6pm Shift", "tamecka.anderson@jcf.gov.jm", "12431"),
        ("CPL-HINES", "Natoya Hines", "Corporal",
         "user", None, "8am-6pm Shift", "natoya.hines@jcf.gov.jm", "19721"),
        ("CPL-WILLIAMS", "Machell Williams", "Corporal",
         "admin", 2, "8am-6pm Shift", "machell.williams@jcf.gov.jm", "13432"),
        ("CONS-BROWN", "Vinnette Brown", "Constable",
         "user", None, "8am-6pm Shift", "vinnette.brown@jcf.gov.jm", "14658"),
        ("DCONS-FOSTER", "Rodney Foster", "Detective Constable",
         "user", None, "8am-6pm Shift", "rodney.foster@jcf.gov.jm", "17558"),
        # --- Court ---
        ("DS-MCPHERSON", "Danet McPherson", "Detective Sergeant",
         "supervisor", None, "Court", "danet.mcpherson@jcf.gov.jm", "10940"),
        # --- Fraud Desk ---
        ("DCONS-GAYLE", "Chavoun Gayle", "Detective Constable",
         "user", None, "Fraud Desk", "chavoun.gayle@jcf.gov.jm", "19250"),
        # --- Special Assignment / FS Branch ---
        ("CPL-BBARRETT", "Bonthanie Barrett", "Corporal",
         "user", None, "FS Branch - Special Assignment", "bonthanie.barrett@jcf.gov.jm", "20918"),
        # --- 6pm-8am Shift ---
        ("DCPL-SWABY", "Zeato Swaby", "Detective Corporal",
         "user", None, "6pm-8am Shift", "zeato.swaby@jcf.gov.jm", "7871"),
        ("DCONS-ENNIS", "Ochane Ennis", "Detective Constable",
         "user", None, "6pm-8am Shift", "ochane.ennis@jcf.gov.jm", "13306"),
        ("CONS-RUSSELL", "Desmond Russell", "Constable",
         "user", None, "6pm-8am Shift", "desmond.russell@jcf.gov.jm", "25221"),
        ("CONS-CAMPBELL", "Evergay Campbell", "Constable",
         "user", None, "6pm-8am Shift", "evergay.campbell@jcf.gov.jm", "24561"),
        # --- Rest Period ---
        ("DCPL-MORGAN", "Dwight Morgan", "Detective Corporal",
         "user", None, "Rest Period", "dwight.morgan@jcf.gov.jm", "1345"),
        ("CPL-BAKER", "Ricardo Baker", "Corporal",
         "user", None, "Rest Period", "ricardo.baker@jcf.gov.jm", "15766"),
        ("CONS-JONES", "Ashlee Jones", "Constable",
         "user", None, "Rest Period", "ashlee.jones@jcf.gov.jm", "24991"),
        # --- Day Off ---
        ("SGT-BARRETT", "Robert Barrett", "Sergeant",
         "supervisor", None, "Day Off", "robert.barrett@jcf.gov.jm", "7549"),
        ("DCPL-JOHNSON", "Nickesha Johnson", "Detective Corporal",
         "user", None, "Day Off", "nickesha.johnson@jcf.gov.jm", "14816"),
        ("DCONS-SMITH", "Cassandra Smith", "Detective Constable",
         "user", None, "Day Off", "cassandra.smith@jcf.gov.jm", "13647"),
        ("CONS-WITTER", "Shawn Witter", "Constable",
         "user", None, "Day Off", "shawn.witter@jcf.gov.jm", "24635"),
        ("CONS-MALCOLM", "Ramoy Malcolm", "Constable",
         "user", None, "Day Off", "ramoy.malcolm@jcf.gov.jm", "19703"),
        ("CONS-WALLACE", "Jermaine Wallace", "Constable",
         "user", None, "Day Off", "jermaine.wallace@jcf.gov.jm", "13658"),
        # --- FIC ---
        ("DS-HENRY", "Daven Henry", "Detective Sergeant",
         "supervisor", None, "FIC", "daven.henry@jcf.gov.jm", "13623"),
        ("DCPL-SPENCER", "Indira Spencer", "Detective Corporal",
         "user", None, "FIC", "indira.spencer@jcf.gov.jm", "14569"),
        # --- Sick Leave ---
        ("CONS-RWALLACE", "Rasheed Wallace", "Constable",
         "user", None, "Sick Leave", "rasheed.wallace@jcf.gov.jm", "25241"),
        ("DCONS-MCLAREN", "Marlon McLaren", "Detective Constable",
         "user", None, "Sick Leave", "marlon.mclaren@jcf.gov.jm", "13631"),
        ("CONS-EWILLIAMS", "Emadulu Williams", "Constable",
         "user", None, "Sick Leave", "emadulu.williams@jcf.gov.jm", "25002"),
        ("CONS-REID", "Shakary Reid", "Constable",
         "user", None, "Sick Leave", "shakary.reid@jcf.gov.jm", "24934"),
    ]

    section = "FNID Headquarters - Area 3"
    created = []
    for badge, name, rank, role, tier, duty, email, reg_no in ROSTER:
        existing = cursor.execute(
            "SELECT badge_number FROM officers WHERE badge_number = ?", (badge,)
        ).fetchone()
        if not existing:
            pw = secrets.token_urlsafe(16)
            cursor.execute("""
                INSERT INTO officers (badge_number, full_name, rank, section,
                                      role, password_hash, email, unit_access,
                                      must_change_password, admin_tier,
                                      verification_status, duty_assignment,
                                      regulation_no)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'all', 1, ?, 'active', ?, ?)
            """, (badge, name, rank, section, role,
                  generate_password_hash(pw), email, tier, duty, reg_no))
            created.append((badge, name, role, pw, email))

    if created:
        conn.commit()
        _write_initial_credentials([
            {"badge": badge, "name": name, "role": role, "password": pw}
            for badge, name, role, pw, _email in created
        ])
        import logging
        logging.getLogger("fnid_portal").info(
            "Seeded %d roster accounts; passwords written to "
            "_initial_credentials.txt beside the database.",
            len(created),
        )


def _seed_default_settings(cursor):
    """Insert default configurable system settings."""
    defaults = [
        # Case number format — CONFIGURABLE per JCF policy
        ("case_number_format", "{station}/{diary}/{division}/{unit}/{year}/{seq}",
         "case_numbers", "Case reference number format template"),
        ("default_division_code", "A3", "case_numbers", "Division code for FNID Area 3"),
        ("default_unit_code", "FNID", "case_numbers", "Unit code for case numbers"),
        ("default_diary_type", "SD", "case_numbers", "Default station diary type"),
        # Deadline periods — CONFIGURABLE per policy
        ("preliminary_vetting_hours", "24", "deadlines",
         "Hours allowed for preliminary vetting"),
        ("case_submission_days", "7", "deadlines",
         "Days to submit case file after assignment"),
        ("first_review_days", "14", "deadlines",
         "Days after assignment for first review"),
        ("followup_review_days", "28", "deadlines",
         "Days between follow-up reviews"),
        ("suspended_review_days", "90", "deadlines",
         "Days between reviews for suspended cases"),
        ("court_doc_days", "14", "deadlines",
         "Days before court to prepare documents"),
        ("file_return_hours", "48", "deadlines",
         "Hours for file return after checkout"),
        ("forensic_cert_overdue_weeks", "8", "deadlines",
         "Weeks after which forensic cert is overdue"),
        # MCR settings
        ("mcr_window_start_time", "05:30", "mcr",
         "Morning Crime Report window start time (HH:MM)"),
        ("mcr_window_end_time", "05:30", "mcr",
         "Morning Crime Report window end time (HH:MM)"),
        # General
        ("division_name", "FNID Area 3", "general",
         "Full division name"),
        ("division_parishes", "Manchester,St. Elizabeth,Clarendon", "general",
         "Parishes covered by this division"),
        ("session_timeout_hours", "8", "general",
         "User session timeout in hours"),
        ("allow_legacy_login", "false", "general",
         "Allow badge-only login without password (for migration period)"),
        # Data Protection Act 2020 compliance
        ("data_retention_years", "7", "data_protection",
         "Years to retain records before flagging for review"),
        ("dsar_enabled", "true", "data_protection",
         "Enable Data Subject Access Request tracking"),
        ("bulk_export_requires_approval", "true", "data_protection",
         "Require Tier1 approval for bulk data exports"),
        # AI assistant harness
        ("ai_assistants_global_enabled", "false", "ai_assistants",
         "Master switch for all internal work assistants"),
        ("ai_assistants_deepseek_base_url", "https://api.deepseek.com", "ai_assistants",
         "DeepSeek OpenAI-compatible API base URL"),
        ("ai_assistants_deepseek_model", "deepseek-v4-flash", "ai_assistants",
         "DeepSeek model used for assistant planning"),
        ("ai_assistants_daily_run_limit", "25", "ai_assistants",
         "Maximum AI assistant runs per user per day"),
        ("ai_assistants_monthly_token_budget", "500000", "ai_assistants",
         "Soft monthly token budget for AI assistant calls"),
        ("ai_assistants_default_dry_run", "true", "ai_assistants",
         "Keep generated actions as proposals unless explicitly approved"),
        ("ai_assistants_send_human_guidance_externally", "false", "ai_assistants",
         "Keep free-text human guidance inside FNID unless explicitly enabled"),
        ("ai_assistants_tavily_public_lookup_enabled", "true", "ai_assistants",
         "Allow Tavily only for public policy/reference lookup, never case facts"),
        ("ai_assistants_tavily_base_url", "https://api.tavily.com/search", "ai_assistants",
         "Tavily search API endpoint"),
        ("ai_assistants_tavily_max_results", "3", "ai_assistants",
         "Maximum public Tavily results attached to an assistant run"),
        ("ai_assistants_tavily_allowed_domains", "jcf.gov.jm,moj.gov.jm,dpp.gov.jm,japarliament.gov.jm",
         "ai_assistants", "Comma-separated public domains allowed for Tavily lookup"),
        ("registry_default_register_type", "dcrr", "registry",
         "Default case intake register: dcrr or major_crime_register"),
    ]
    for key, value, category, description in defaults:
        cursor.execute("""
            INSERT OR IGNORE INTO system_settings (key, value, category, description)
            VALUES (?, ?, ?, ?)
        """, (key, value, category, description))


def get_setting(key, default=None):
    """Get a system setting value by key."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT value FROM system_settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key, value, category="general", description=None, updated_by=None):
    """Set a system setting value."""
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO system_settings (key, value, category, description, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_by = excluded.updated_by,
                updated_at = datetime('now')
        """, (key, value, category, description, updated_by))
        conn.commit()
    finally:
        conn.close()


def log_audit(table_name, record_id, action, officer_badge=None,
              officer_name=None, details=None):
    """Log an action to the audit trail."""
    conn = get_db()
    conn.execute("""
        INSERT INTO audit_log (table_name, record_id, action,
                               officer_badge, officer_name, details)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (table_name, record_id, action, officer_badge, officer_name, details))
    conn.commit()
    conn.close()


def generate_id(prefix, table, id_column, conn=None):
    """Generate the next sequential ID for a table.

    When the caller is inside an uncommitted transaction (e.g. seeding), pass
    its connection so that uncommitted rows are visible — otherwise a fresh
    connection sees the pre-batch state and returns the same ID repeatedly.
    """
    if table not in VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    own_conn = conn is None
    if own_conn:
        conn = get_db()
    try:
        year = datetime.now().year
        pattern = f"{prefix}-{year}-%"
        row = conn.execute(
            f"SELECT {id_column} FROM {table} WHERE {id_column} LIKE ? "
            f"ORDER BY id DESC LIMIT 1",
            (pattern,),
        ).fetchone()
    finally:
        if own_conn:
            conn.close()

    if row:
        try:
            num = int(str(row[0]).split("-")[-1]) + 1
        except (ValueError, IndexError):
            num = 1
    else:
        num = 1
    return f"{prefix}-{year}-{str(num).zfill(3)}"
