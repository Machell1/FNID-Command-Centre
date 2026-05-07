
-- ============================================================
-- FNID COMMAND CENTRE v2.0
-- Production Database Schema
-- JCF SOP: JCF/FW/PL/C&S/0001/2024 Compliant
-- FNID Area 3: Manchester, St. Elizabeth, Clarendon
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- ============================================================
-- 1. ORGANIZATIONAL STRUCTURE (SOP Appendix 1 & 2)
-- ============================================================

CREATE TABLE IF NOT EXISTS areas (
    area_id SERIAL PRIMARY KEY,
    area_code VARCHAR(3) NOT NULL UNIQUE,
    area_name VARCHAR(50) NOT NULL,
    acp_reg_number VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS divisions (
    division_id SERIAL PRIMARY KEY,
    area_id INTEGER REFERENCES areas(area_id) ON DELETE RESTRICT,
    division_code VARCHAR(5) NOT NULL UNIQUE,
    division_name VARCHAR(50) NOT NULL,
    division_type VARCHAR(10) CHECK (division_type IN ('SUPER', 'NON_SUPER')),
    commander_reg_number VARCHAR(10) NOT NULL,
    dco_reg_number VARCHAR(10) NOT NULL,
    ddi_reg_number VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stations (
    station_id SERIAL PRIMARY KEY,
    division_id INTEGER REFERENCES divisions(division_id) ON DELETE RESTRICT,
    station_code VARCHAR(5) NOT NULL UNIQUE,
    station_name VARCHAR(50) NOT NULL,
    station_type VARCHAR(15) CHECK (station_type IN ('GEOGRAPHIC', 'SPECIALIST', 'PORTS', 'MARINE')),
    station_manager_reg_number VARCHAR(10),
    srms_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. PERSONNEL & RBAC (SOP Section 7, 8)
-- ============================================================

CREATE TABLE IF NOT EXISTS personnel (
    reg_number VARCHAR(10) PRIMARY KEY,
    rank VARCHAR(20) NOT NULL CHECK (rank IN (
        'CONSTABLE', 'CORPORAL', 'SERGEANT', 'INSPECTOR',
        'SUPERINTENDENT', 'SENIOR_SUPERINTENDENT', 'ASSISTANT_COMMISSIONER',
        'DEPUTY_COMMISSIONER', 'COMMISSIONER'
    )),
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255),
    division_id INTEGER REFERENCES divisions(division_id),
    station_id INTEGER REFERENCES stations(station_id),
    unit VARCHAR(20) CHECK (unit IN (
        'UNIFORMED', 'NON_UNIFORMED', 'INTELLIGENCE', 'OPERATIONS',
        'SEIZURES', 'ARRESTS_COURT', 'FORENSICS', 'CASE_REGISTRY',
        'C_TOC', 'CISOCA', 'PSTEB', 'MARINE', 'PORTS', 'FNID'
    )),
    role VARCHAR(30) CHECK (role IN (
        'INVESTIGATING_OFFICER', 'SENIOR_INVESTIGATION_OFFICER',
        'REGISTRAR', 'REGISTRY_SUPERVISOR', 'VETTING_OFFICER_MAJOR',
        'VETTING_OFFICER_MINOR', 'PROSECUTION_LIAISON_OFFICER',
        'CRIME_ANALYST', 'TYPIST', 'DATA_ENTRY_CLERK', 'READER_INDEXER',
        'STATION_MANAGER', 'DIVISIONAL_CRIME_OFFICER', 'DIVISIONAL_COMMANDER',
        'AREA_CRIME_OFFICER', 'LEGAL_OFFICER'
    )),
    is_active BOOLEAN DEFAULT TRUE,
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret VARCHAR(255),
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. UNIFIED CASE ENTITY (SOP Section 6.3, 9.1)
-- ============================================================

CREATE TABLE IF NOT EXISTS cases (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cr_number VARCHAR(30) NOT NULL UNIQUE,
    cr_format_version INTEGER DEFAULT 1,
    registry_type VARCHAR(10) NOT NULL CHECK (registry_type IN ('DCRR', 'MAJOR', 'MINOR')),
    area_id INTEGER NOT NULL REFERENCES areas(area_id),
    division_id INTEGER NOT NULL REFERENCES divisions(division_id),
    station_id INTEGER NOT NULL REFERENCES stations(station_id),
    crime_category VARCHAR(20) NOT NULL CHECK (crime_category IN (
        'MAJOR', 'MINOR', 'TERRORISM', 'HOMICIDE', 'FIREARMS',
        'NARCOTICS', 'SEXUAL_OFFENCES', 'FRAUD', 'CYBERCRIME',
        'TRAFFIC_FATAL', 'SUDDEN_DEATH', 'MISSING_PERSON', 'CHILD_DIVERSION'
    )),
    offence_code VARCHAR(10) NOT NULL,
    offence_description TEXT NOT NULL,
    investigated_by VARCHAR(15) CHECK (investigated_by IN (
        'UNIFORMED', 'NON_UNIFORMED', 'SPECIALIST_UNIT'
    )),
    specialist_unit VARCHAR(10) CHECK (specialist_unit IN (
        'C_TOC', 'CISOCA', 'MID', 'PSTEB', 'MARINE', 'PORTS', 'FNID'
    )),
    date_reported TIMESTAMPTZ NOT NULL,
    date_of_offence TIMESTAMPTZ,
    time_of_offence TIME,
    date_assigned TIMESTAMPTZ,
    station_diary_entry_number INTEGER,
    crime_diary_entry_number INTEGER,
    diary_used_for_cr VARCHAR(10) CHECK (diary_used_for_cr IN ('STATION', 'CRIME', 'BOTH')),
    location_of_offence TEXT,
    location_gis GEOGRAPHY(POINT,4326),
    location_parish VARCHAR(20),
    status VARCHAR(15) NOT NULL DEFAULT 'OPEN' CHECK (status IN (
        'OPEN', 'ASSIGNED', 'ACTIVE', 'UNDER_REVIEW',
        'SUSPENDED', 'CLEARED', 'CLOSED', 'COLD_CASE', 'REOPENED'
    )),
    status_changed_at TIMESTAMPTZ DEFAULT NOW(),
    status_changed_by VARCHAR(10) REFERENCES personnel(reg_number),
    status_reason TEXT,
    closure_type VARCHAR(30) CHECK (closure_type IN (
        'CHARGES_LAID', 'SUSPECT_DEAD', 'WARRANT_ISSUED_LIFE_SENTENCE',
        'EXTRADITION_DENIED', 'VICTIM_WILL_NOT_PROSECUTE', 'CORONERS_INQUEST',
        'CHILD_DIVERSION', 'CONTrived_REPORT', 'ACP_DISCRETION'
    )),
    closure_approved_by VARCHAR(10) REFERENCES personnel(reg_number),
    closure_approved_at TIMESTAMPTZ,
    suspended_at TIMESTAMPTZ,
    suspended_by VARCHAR(10) REFERENCES personnel(reg_number),
    suspension_review_due TIMESTAMPTZ,
    suspension_reason TEXT,
    declared_cold_at TIMESTAMPTZ,
    declared_cold_by VARCHAR(10) REFERENCES personnel(reg_number),
    court_date TIMESTAMPTZ,
    court_type VARCHAR(20),
    court_status VARCHAR(20),
    mcr_submitted BOOLEAN DEFAULT FALSE,
    mcr_submitted_at TIMESTAMPTZ,
    mcr_submitted_by VARCHAR(10) REFERENCES personnel(reg_number),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by VARCHAR(10) REFERENCES personnel(reg_number),
    version INTEGER DEFAULT 1,
    deleted_at TIMESTAMPTZ,
    deleted_by VARCHAR(10) REFERENCES personnel(reg_number),
    deletion_reason TEXT,
    disposition_scheduled_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cases_cr_number ON cases(cr_number);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_registry_type ON cases(registry_type);
CREATE INDEX IF NOT EXISTS idx_cases_division_station ON cases(division_id, station_id);
CREATE INDEX IF NOT EXISTS idx_cases_date_reported ON cases(date_reported);
CREATE INDEX IF NOT EXISTS idx_cases_mcr_submitted ON cases(mcr_submitted) WHERE mcr_submitted = FALSE;
CREATE INDEX IF NOT EXISTS idx_cases_suspension_review ON cases(suspension_review_due) WHERE status = 'SUSPENDED';

-- ============================================================
-- 4. REGISTRY EXTENSION TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS dcrr_entries (
    dcrr_entry_id SERIAL PRIMARY KEY,
    case_id UUID NOT NULL UNIQUE REFERENCES cases(case_id) ON DELETE CASCADE,
    dcrr_consecutive_number INTEGER NOT NULL,
    dcrr_year INTEGER NOT NULL,
    station_register_ref INTEGER,
    entry_color VARCHAR(10) DEFAULT 'BLUE' CHECK (entry_color IN ('BLUE', 'BLACK', 'RED')),
    color_changed_at TIMESTAMPTZ,
    color_changed_reason TEXT,
    vetting_officer_major_id VARCHAR(10) REFERENCES personnel(reg_number),
    vetting_officer_minor_id VARCHAR(10) REFERENCES personnel(reg_number),
    registry_supervisor_id VARCHAR(10) REFERENCES personnel(reg_number),
    registrar_id VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    monthly_summary_generated BOOLEAN DEFAULT FALSE,
    yearly_summary_generated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS station_registers (
    register_entry_id SERIAL PRIMARY KEY,
    case_id UUID NOT NULL UNIQUE REFERENCES cases(case_id) ON DELETE CASCADE,
    register_type VARCHAR(10) NOT NULL CHECK (register_type IN ('MAJOR', 'MINOR')),
    register_consecutive_number INTEGER NOT NULL,
    station_manager_id VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    handed_over_by VARCHAR(10) REFERENCES personnel(reg_number),
    handed_over_at TIMESTAMPTZ,
    received_by VARCHAR(10) REFERENCES personnel(reg_number),
    received_at TIMESTAMPTZ,
    first_review_due TIMESTAMPTZ,
    first_review_conducted_at TIMESTAMPTZ,
    first_review_conducted_by VARCHAR(10) REFERENCES personnel(reg_number),
    weekly_return_submitted BOOLEAN DEFAULT FALSE,
    weekly_return_submitted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 5. INVESTIGATION MODULE (SOP Section 8.1, 9.3)
-- ============================================================

CREATE TABLE IF NOT EXISTS investigations (
    investigation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    io_reg_number VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    io_assigned_at TIMESTAMPTZ DEFAULT NOW(),
    io_assigned_by VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    sio_reg_number VARCHAR(10) REFERENCES personnel(reg_number),
    supervisor_reg_number VARCHAR(10) REFERENCES personnel(reg_number),
    io_current_case_count INTEGER DEFAULT 0,
    io_capacity_status VARCHAR(10) CHECK (io_capacity_status IN ('AVAILABLE', 'NEAR_CAPACITY', 'AT_CAPACITY')),
    investigation_status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (investigation_status IN (
        'PENDING', 'ACTIVE', 'UNDER_REVIEW', 'AWAITING_EVIDENCE',
        'AWAITING_FORENSICS', 'AWAITING_DPP', 'COMPLETED', 'REASSIGNED'
    )),
    preliminary_vetting_due TIMESTAMPTZ,
    preliminary_vetting_completed_at TIMESTAMPTZ,
    next_review_due TIMESTAMPTZ,
    review_interval_days INTEGER DEFAULT 28,
    court_attendance_required BOOLEAN DEFAULT FALSE,
    next_court_date TIMESTAMPTZ,
    plo_reg_number VARCHAR(10) REFERENCES personnel(reg_number),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS investigation_worksheets (
    worksheet_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(investigation_id),
    worksheet_date DATE NOT NULL,
    narrative TEXT NOT NULL,
    narrative_hash VARCHAR(64) NOT NULL,
    signed_by VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    signed_at TIMESTAMPTZ NOT NULL,
    attachments JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS action_sheets (
    action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(investigation_id),
    action_sequence INTEGER NOT NULL,
    generated_from VARCHAR(20) CHECK (generated_from IN (
        'INITIAL_VETTING', 'CASE_CONFERENCE', 'CONTINUOUS_VETTING',
        'CASE_REVIEW', 'COURT_DIRECTION', 'DPP_ADVICE'
    )),
    action_description TEXT NOT NULL,
    assigned_by VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    assigned_to VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    date_tasked TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    due_date TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    completed_by VARCHAR(10) REFERENCES personnel(reg_number),
    completion_notes TEXT,
    action_status VARCHAR(15) DEFAULT 'PENDING' CHECK (action_status IN (
        'PENDING', 'IN_PROGRESS', 'COMPLETED', 'OVERDUE', 'ESCALATED', 'CANCELLED'
    )),
    escalated_at TIMESTAMPTZ,
    escalated_to VARCHAR(10) REFERENCES personnel(reg_number),
    escalation_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 6. CASE FILE MOVEMENT (SOP 9.1.15, Appendix 14)
-- ============================================================

CREATE TABLE IF NOT EXISTS case_file_movements (
    movement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id),
    moved_from VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    moved_to VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    file_type VARCHAR(15) CHECK (file_type IN ('ORIGINAL', 'WORKING_COPY', 'EXHIBIT')),
    contents_at_handover JSONB NOT NULL,
    contents_at_return JSONB,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expected_return_at TIMESTAMPTZ NOT NULL,
    returned_at TIMESTAMPTZ,
    issued_by VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    received_by VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    returned_by VARCHAR(10) REFERENCES personnel(reg_number),
    return_verified_by VARCHAR(10) REFERENCES personnel(reg_number),
    movement_status VARCHAR(15) DEFAULT 'ISSUED' CHECK (movement_status IN (
        'ISSUED', 'OVERDUE', 'RETURNED', 'LOST', 'DAMAGED'
    )),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 7. EXHIBIT CHAIN OF CUSTODY (CR 5) - SOP Appendix 16
-- ============================================================

CREATE TABLE IF NOT EXISTS exhibits (
    exhibit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES cases(case_id),
    exhibit_number VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    current_holder VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    current_location VARCHAR(50) NOT NULL,
    custody_status VARCHAR(15) CHECK (custody_status IN (
        'SEIZED', 'STORED', 'IN_TRANSIT', 'IN_LAB', 'IN_COURT', 'RETURNED', 'DESTROYED'
    )),
    seized_by VARCHAR(10) NOT NULL REFERENCES personnel(reg_number),
    seized_at TIMESTAMPTZ NOT NULL,
    seized_from_location TEXT,
    custody_chain JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 8. FNID SEIZURES MODULE
-- ============================================================

CREATE TABLE IF NOT EXISTS fnid_seizures (
    seizure_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(case_id),
    seizure_type VARCHAR(20) CHECK (seizure_type IN (
        'FIREARM', 'AMMUNITION', 'NARCOTICS', 'CASH', 'VEHICLE', 'OTHER'
    )),
    firearm_make VARCHAR(50),
    firearm_model VARCHAR(50),
    firearm_serial_number VARCHAR(50),
    firearm_caliber VARCHAR(20),
    ammunition_count INTEGER,
    firearm_condition VARCHAR(20),
    drug_type VARCHAR(30),
    weight_lbs DECIMAL(10,2),
    weight_kg DECIMAL(10,2),
    estimated_purity_percent DECIMAL(5,2),
    street_value_jmd DECIMAL(15,2),
    drug_packaging VARCHAR(50),
    seizure_location GEOGRAPHY(POINT,4326),
    seized_by VARCHAR(10) REFERENCES personnel(reg_number),
    seized_at TIMESTAMPTZ,
    exhibit_number VARCHAR(20),
    intelligence_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 9. INTELLIGENCE MODULE
-- ============================================================

CREATE TABLE IF NOT EXISTS intelligence_reports (
    intel_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(case_id),
    source_type VARCHAR(20) CHECK (source_type IN (
        'HUMAN', 'TECHNICAL', 'OPEN_SOURCE', 'SURVEILLANCE', 'FINANCIAL'
    )),
    source_reliability VARCHAR(10) CHECK (source_reliability IN ('A', 'B', 'C', 'D', 'E')),
    information_validity VARCHAR(10) CHECK (information_validity IN ('1', '2', '3', '4', '5', '6')),
    target_firearm_trafficking BOOLEAN DEFAULT FALSE,
    target_narcotics_cartel BOOLEAN DEFAULT FALSE,
    cross_border_operation BOOLEAN DEFAULT FALSE,
    linked_cases UUID[],
    dim_reg_number VARCHAR(10),
    handler_reg_number VARCHAR(10),
    classification VARCHAR(10) CHECK (classification IN (
        'RESTRICTED', 'CONFIDENTIAL', 'SECRET', 'TOP_SECRET'
    )),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 10. DPP FILE PIPELINE
-- ============================================================

CREATE TABLE IF NOT EXISTS dpp_file_pipeline (
    pipeline_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(case_id),
    file_status VARCHAR(20) CHECK (file_status IN (
        'PREPARATION', 'VETTING', 'SUBMITTED_TO_DPP',
        'RULING_PENDING', 'NO_CASE', 'COMMITTAL', 'TRIAL'
    )),
    prosecution_bundle_hash VARCHAR(64),
    disclosure_bundle_hash VARCHAR(64),
    auto_redaction_applied BOOLEAN DEFAULT FALSE,
    court_date TIMESTAMPTZ,
    court_type VARCHAR(20),
    committal_date TIMESTAMPTZ,
    firearms_expert_cert_attached BOOLEAN DEFAULT FALSE,
    narcotics_certificate_attached BOOLEAN DEFAULT FALSE,
    pocA_restraint_order_attached BOOLEAN DEFAULT FALSE,
    vetted_by_lo VARCHAR(10),
    vetted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 11. AUDIT & COMPLIANCE (WORM - Write Once Read Many)
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    officer_reg_number VARCHAR(10) REFERENCES personnel(reg_number),
    officer_ip INET NOT NULL,
    officer_device_fingerprint VARCHAR(64),
    officer_geolocation GEOGRAPHY(POINT,4326),
    action VARCHAR(30) NOT NULL CHECK (action IN (
        'CREATE', 'READ', 'UPDATE', 'DELETE', 'VIEW', 'PRINT', 'EXPORT',
        'ASSIGN', 'TRANSFER', 'CLOSE', 'REOPEN', 'SUSPEND', 'VET'
    )),
    table_name VARCHAR(30) NOT NULL,
    record_id VARCHAR(50) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    change_reason TEXT,
    action_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    audit_hash VARCHAR(64) NOT NULL,
    previous_audit_hash VARCHAR(64),
    retention_until TIMESTAMPTZ NOT NULL
);

-- Prevent updates/deletes on audit_log (WORM enforcement)
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log is WORM (Write Once Read Many). Modifications are prohibited.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_worm ON audit_log;
CREATE TRIGGER trg_audit_worm
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_modification();

-- ============================================================
-- 12. SOP ENFORCEMENT TRIGGERS
-- ============================================================

-- Trigger: CR# Format Validation (SOP 9.1.13)
CREATE OR REPLACE FUNCTION validate_cr_number()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.registry_type = 'DCRR' THEN
        IF NEW.cr_number !~ '^\d+_\d{4}/\d{2}/\d{2}/[A-Z]+/(SD|CD)\d+/[A-Z]+$' THEN
            RAISE EXCEPTION 'Invalid DCRR CR# format per SOP 9.1.13.1: %', NEW.cr_number;
        END IF;
    ELSIF NEW.registry_type IN ('MAJOR', 'MINOR') THEN
        IF NEW.cr_number !~ '^\d+_/\d+/\d{4}/\d{2}/\d{2}/[A-Z]+$' THEN
            RAISE EXCEPTION 'Invalid Station Register CR# format per SOP 9.1.13.2: %', NEW.cr_number;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_cr_number ON cases;
CREATE TRIGGER trg_validate_cr_number
    BEFORE INSERT OR UPDATE ON cases
    FOR EACH ROW
    EXECUTE FUNCTION validate_cr_number();

-- Trigger: Registry Consistency
CREATE OR REPLACE FUNCTION enforce_registry_consistency()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.registry_type = 'DCRR' THEN
        IF NOT EXISTS (SELECT 1 FROM dcrr_entries WHERE case_id = NEW.case_id) THEN
            RAISE EXCEPTION 'DCRR case must have dcrr_entries record';
        END IF;
    ELSIF NEW.registry_type IN ('MAJOR', 'MINOR') THEN
        IF NOT EXISTS (SELECT 1 FROM station_registers WHERE case_id = NEW.case_id) THEN
            RAISE EXCEPTION 'Station register case must have station_registers record';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_registry_consistency ON cases;
CREATE TRIGGER trg_registry_consistency
    BEFORE UPDATE ON cases
    FOR EACH ROW
    WHEN (NEW.registry_type IS DISTINCT FROM OLD.registry_type)
    EXECUTE FUNCTION enforce_registry_consistency();

-- Trigger: Preliminary Vetting Deadline (SOP 9.1.12)
CREATE OR REPLACE FUNCTION set_vetting_deadline()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.investigated_by = 'NON_UNIFORMED' THEN
        NEW.preliminary_vetting_due := NEW.io_assigned_at + INTERVAL '72 hours';
    ELSE
        NEW.preliminary_vetting_due := NEW.io_assigned_at + INTERVAL '48 hours';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_vetting_deadline ON investigations;
CREATE TRIGGER trg_vetting_deadline
    BEFORE INSERT ON investigations
    FOR EACH ROW
    EXECUTE FUNCTION set_vetting_deadline();

-- Trigger: Suspension Review Date (SOP 9.3.9f)
CREATE OR REPLACE FUNCTION calculate_suspension_review()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'SUSPENDED' AND OLD.status != 'SUSPENDED' THEN
        NEW.suspended_at := NOW();
        NEW.suspension_review_due := NOW() + INTERVAL '90 days';
        NEW.suspension_reason := COALESCE(NEW.suspension_reason, 'All investigative leads exhausted');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_suspension_review ON cases;
CREATE TRIGGER trg_suspension_review
    BEFORE UPDATE ON cases
    FOR EACH ROW
    EXECUTE FUNCTION calculate_suspension_review();

-- Trigger: Auto-calculate Disposition Date (SOP 9.3.11)
CREATE OR REPLACE FUNCTION calculate_disposition_date()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.closure_type IS NOT NULL AND NEW.closure_approved_at IS NOT NULL THEN
        NEW.disposition_scheduled_at := NEW.closure_approved_at + INTERVAL '7 years';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_disposition_date ON cases;
CREATE TRIGGER trg_disposition_date
    BEFORE UPDATE ON cases
    FOR EACH ROW
    EXECUTE FUNCTION calculate_disposition_date();

-- Trigger: Case Status Change Audit
CREATE OR REPLACE FUNCTION log_case_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        NEW.status_changed_at := NOW();
        NEW.version := OLD.version + 1;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_case_status_change ON cases;
CREATE TRIGGER trg_case_status_change
    BEFORE UPDATE ON cases
    FOR EACH ROW
    EXECUTE FUNCTION log_case_status_change();

-- ============================================================
-- 13. SEED DATA (FNID Area 3)
-- ============================================================

INSERT INTO areas (area_code, area_name, acp_reg_number) VALUES
('A3', 'Area 3 (Manchester, St. Elizabeth, Clarendon)', 'ACP001')
ON CONFLICT (area_code) DO NOTHING;

INSERT INTO divisions (area_id, division_code, division_name, division_type, commander_reg_number, dco_reg_number, ddi_reg_number) VALUES
((SELECT area_id FROM areas WHERE area_code = 'A3'), 'M', 'Manchester Division', 'SUPER', 'SP001', 'SP002', 'INSP001'),
((SELECT area_id FROM areas WHERE area_code = 'A3'), 'SE', 'St. Elizabeth Division', 'NON_SUPER', 'SP003', 'SP004', 'INSP002'),
((SELECT area_id FROM areas WHERE area_code = 'A3'), 'C', 'Clarendon Division', 'SUPER', 'SP005', 'SP006', 'INSP003')
ON CONFLICT (division_code) DO NOTHING;

INSERT INTO stations (division_id, station_code, station_name, station_type, station_manager_reg_number) VALUES
((SELECT division_id FROM divisions WHERE division_code = 'M'), 'MT', 'Mandeville Police Station', 'GEOGRAPHIC', 'SGT001'),
((SELECT division_id FROM divisions WHERE division_code = 'M'), 'CHR', 'Christiana Police Station', 'GEOGRAPHIC', 'SGT002'),
((SELECT division_id FROM divisions WHERE division_code = 'SE'), 'BL', 'Black River Police Station', 'GEOGRAPHIC', 'SGT003'),
((SELECT division_id FROM divisions WHERE division_code = 'SE'), 'SA', 'Santa Cruz Police Station', 'GEOGRAPHIC', 'SGT004'),
((SELECT division_id FROM divisions WHERE division_code = 'C'), 'MAY', 'May Pen Police Station', 'GEOGRAPHIC', 'SGT005'),
((SELECT division_id FROM divisions WHERE division_code = 'C'), 'LT', 'Lionel Town Police Station', 'GEOGRAPHIC', 'SGT006'),
((SELECT division_id FROM divisions WHERE division_code = 'C'), 'HWT', 'Half Way Tree CIB', 'SPECIALIST', 'INSP004')
ON CONFLICT (station_code) DO NOTHING;

-- Seed admin user (password: 'changeme' - bcrypt hash)
INSERT INTO personnel (reg_number, rank, full_name, email, password_hash, division_id, station_id, unit, role, is_active) VALUES
('ADMIN001', 'SUPERINTENDENT', 'System Administrator', 'admin@fnid.jcf.gov.jm',
 '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA.qGZvKG6G',
 (SELECT division_id FROM divisions WHERE division_code = 'M'),
 (SELECT station_id FROM stations WHERE station_code = 'MT'),
 'FNID', 'DIVISIONAL_CRIME_OFFICER', TRUE)
ON CONFLICT (reg_number) DO NOTHING;
