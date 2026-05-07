"""
FNID Command Centre v2.0 - Case & Registry Models
SOP Sections 6.3, 9.1, 9.2, Appendix 11-15
"""
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Numeric, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, INET, GEOGRAPHY
from sqlalchemy.orm import relationship, validates
from uuid import uuid4
from .. import db

class Case(db.Model):
    __tablename__ = 'cases'

    case_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    cr_number = Column(String(30), unique=True, nullable=False)
    cr_format_version = Column(Integer, default=1)
    registry_type = Column(String(10), nullable=False, 
                          CheckConstraint("registry_type IN ('DCRR', 'MAJOR', 'MINOR')"))
    area_id = Column(Integer, ForeignKey('areas.area_id'), nullable=False)
    division_id = Column(Integer, ForeignKey('divisions.division_id'), nullable=False)
    station_id = Column(Integer, ForeignKey('stations.station_id'), nullable=False)
    crime_category = Column(String(20), nullable=False,
                           CheckConstraint("crime_category IN ('MAJOR', 'MINOR', 'TERRORISM', 'HOMICIDE', 'FIREARMS', 'NARCOTICS', 'SEXUAL_OFFENCES', 'FRAUD', 'CYBERCRIME', 'TRAFFIC_FATAL', 'SUDDEN_DEATH', 'MISSING_PERSON', 'CHILD_DIVERSION')"))
    offence_code = Column(String(10), nullable=False)
    offence_description = Column(Text, nullable=False)
    investigated_by = Column(String(15), CheckConstraint("investigated_by IN ('UNIFORMED', 'NON_UNIFORMED', 'SPECIALIST_UNIT')"))
    specialist_unit = Column(String(10), CheckConstraint("specialist_unit IN ('C_TOC', 'CISOCA', 'MID', 'PSTEB', 'MARINE', 'PORTS', 'FNID')"))
    date_reported = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    date_of_offence = Column(DateTime(timezone=True))
    time_of_offence = Column(db.Time)
    date_assigned = Column(DateTime(timezone=True))
    station_diary_entry_number = Column(Integer)
    crime_diary_entry_number = Column(Integer)
    diary_used_for_cr = Column(String(10), CheckConstraint("diary_used_for_cr IN ('STATION', 'CRIME', 'BOTH')"))
    location_of_offence = Column(Text)
    location_gis = Column(GEOGRAPHY('POINT', 4326))
    location_parish = Column(String(20))
    status = Column(String(15), nullable=False, default='OPEN',
                   CheckConstraint("status IN ('OPEN', 'ASSIGNED', 'ACTIVE', 'UNDER_REVIEW', 'SUSPENDED', 'CLEARED', 'CLOSED', 'COLD_CASE', 'REOPENED')"))
    status_changed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    status_changed_by = Column(String(10), ForeignKey('personnel.reg_number'))
    status_reason = Column(Text)
    closure_type = Column(String(30), CheckConstraint("closure_type IN ('CHARGES_LAID', 'SUSPECT_DEAD', 'WARRANT_ISSUED_LIFE_SENTENCE', 'EXTRADITION_DENIED', 'VICTIM_WILL_NOT_PROSECUTE', 'CORONERS_INQUEST', 'CHILD_DIVERSION', 'CONTrived_REPORT', 'ACP_DISCRETION')"))
    closure_approved_by = Column(String(10), ForeignKey('personnel.reg_number'))
    closure_approved_at = Column(DateTime(timezone=True))
    suspended_at = Column(DateTime(timezone=True))
    suspended_by = Column(String(10), ForeignKey('personnel.reg_number'))
    suspension_review_due = Column(DateTime(timezone=True))
    suspension_reason = Column(Text)
    declared_cold_at = Column(DateTime(timezone=True))
    declared_cold_by = Column(String(10), ForeignKey('personnel.reg_number'))
    court_date = Column(DateTime(timezone=True))
    court_type = Column(String(20))
    court_status = Column(String(20))
    mcr_submitted = Column(Boolean, default=False)
    mcr_submitted_at = Column(DateTime(timezone=True))
    mcr_submitted_by = Column(String(10), ForeignKey('personnel.reg_number'))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_by = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_by = Column(String(10), ForeignKey('personnel.reg_number'))
    version = Column(Integer, default=1)
    deleted_at = Column(DateTime(timezone=True))
    deleted_by = Column(String(10), ForeignKey('personnel.reg_number'))
    deletion_reason = Column(Text)
    disposition_scheduled_at = Column(DateTime(timezone=True))

    # Relationships
    dcrr_entry = relationship('DCRREntry', uselist=False, back_populates='case')
    station_register = relationship('StationRegister', uselist=False, back_populates='case')
    investigation = relationship('Investigation', uselist=False, back_populates='case')
    exhibits = relationship('Exhibit', back_populates='case')
    file_movements = relationship('CaseFileMovement', back_populates='case')
    seizures = relationship('FNIDSeizure', back_populates='case')
    intelligence_reports = relationship('IntelligenceReport', back_populates='case')
    dpp_pipeline = relationship('DPPFilePipeline', uselist=False, back_populates='case')

    def is_closed(self):
        return self.status in ['CLOSED', 'COLD_CASE']

    def can_transition_to(self, new_status, officer):
        """Check if case can transition to new status based on SOP rules."""
        transitions = {
            'OPEN': ['ASSIGNED', 'ACTIVE', 'CLOSED'],
            'ASSIGNED': ['ACTIVE', 'UNDER_REVIEW'],
            'ACTIVE': ['UNDER_REVIEW', 'AWAITING_COURT', 'SUSPENDED', 'CLEARED'],
            'UNDER_REVIEW': ['ACTIVE', 'SUSPENDED', 'CLEARED'],
            'AWAITING_COURT': ['CLEARED', 'CLOSED'],
            'SUSPENDED': ['COLD_CASE', 'REOPENED', 'ACTIVE'],
            'CLEARED': ['CLOSED', 'REOPENED'],
            'CLOSED': ['REOPENED'],
            'COLD_CASE': ['REOPENED'],
            'REOPENED': ['OPEN']
        }

        if new_status not in transitions.get(self.status, []):
            return False

        # Authority checks per SOP
        if new_status == 'CLOSED' and officer.role not in ['REGISTRAR', 'DIVISIONAL_CRIME_OFFICER', 'AREA_CRIME_OFFICER', 'ASSISTANT_COMMISSIONER']:
            return False
        if new_status == 'COLD_CASE' and officer.role not in ['DIVISIONAL_CRIME_OFFICER', 'AREA_CRIME_OFFICER', 'ASSISTANT_COMMISSIONER']:
            return False
        if new_status == 'REOPENED' and officer.role not in ['DIVISIONAL_CRIME_OFFICER', 'AREA_CRIME_OFFICER', 'ASSISTANT_COMMISSIONER']:
            return False

        return True

class DCRREntry(db.Model):
    __tablename__ = 'dcrr_entries'
    dcrr_entry_id = Column(Integer, primary_key=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id'), unique=True, nullable=False)
    dcrr_consecutive_number = Column(Integer, nullable=False)
    dcrr_year = Column(Integer, nullable=False)
    station_register_ref = Column(Integer)
    entry_color = Column(String(10), default='BLUE', CheckConstraint("entry_color IN ('BLUE', 'BLACK', 'RED')"))
    color_changed_at = Column(DateTime(timezone=True))
    color_changed_reason = Column(Text)
    vetting_officer_major_id = Column(String(10), ForeignKey('personnel.reg_number'))
    vetting_officer_minor_id = Column(String(10), ForeignKey('personnel.reg_number'))
    registry_supervisor_id = Column(String(10), ForeignKey('personnel.reg_number'))
    registrar_id = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    monthly_summary_generated = Column(Boolean, default=False)
    yearly_summary_generated = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    case = relationship('Case', back_populates='dcrr_entry')

class StationRegister(db.Model):
    __tablename__ = 'station_registers'
    register_entry_id = Column(Integer, primary_key=True)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id'), unique=True, nullable=False)
    register_type = Column(String(10), nullable=False, CheckConstraint("register_type IN ('MAJOR', 'MINOR')"))
    register_consecutive_number = Column(Integer, nullable=False)
    station_manager_id = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    handed_over_by = Column(String(10), ForeignKey('personnel.reg_number'))
    handed_over_at = Column(DateTime(timezone=True))
    received_by = Column(String(10), ForeignKey('personnel.reg_number'))
    received_at = Column(DateTime(timezone=True))
    first_review_due = Column(DateTime(timezone=True))
    first_review_conducted_at = Column(DateTime(timezone=True))
    first_review_conducted_by = Column(String(10), ForeignKey('personnel.reg_number'))
    weekly_return_submitted = Column(Boolean, default=False)
    weekly_return_submitted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    case = relationship('Case', back_populates='station_register')

class CaseFileMovement(db.Model):
    __tablename__ = 'case_file_movements'
    movement_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id'), nullable=False)
    moved_from = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    moved_to = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    file_type = Column(String(15), CheckConstraint("file_type IN ('ORIGINAL', 'WORKING_COPY', 'EXHIBIT')"))
    contents_at_handover = Column(JSONB, nullable=False)
    contents_at_return = Column(JSONB)
    issued_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expected_return_at = Column(DateTime(timezone=True), nullable=False)
    returned_at = Column(DateTime(timezone=True))
    issued_by = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    received_by = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    returned_by = Column(String(10), ForeignKey('personnel.reg_number'))
    return_verified_by = Column(String(10), ForeignKey('personnel.reg_number'))
    movement_status = Column(String(15), default='ISSUED', CheckConstraint("movement_status IN ('ISSUED', 'OVERDUE', 'RETURNED', 'LOST', 'DAMAGED')"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    case = relationship('Case', back_populates='file_movements')

class Investigation(db.Model):
    __tablename__ = 'investigations'
    investigation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id'), unique=True, nullable=False)
    io_reg_number = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    io_assigned_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    io_assigned_by = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    sio_reg_number = Column(String(10), ForeignKey('personnel.reg_number'))
    supervisor_reg_number = Column(String(10), ForeignKey('personnel.reg_number'))
    io_current_case_count = Column(Integer, default=0)
    io_capacity_status = Column(String(10), CheckConstraint("io_capacity_status IN ('AVAILABLE', 'NEAR_CAPACITY', 'AT_CAPACITY')"))
    investigation_status = Column(String(20), nullable=False, default='PENDING',
                                 CheckConstraint("investigation_status IN ('PENDING', 'ACTIVE', 'UNDER_REVIEW', 'AWAITING_EVIDENCE', 'AWAITING_FORENSICS', 'AWAITING_DPP', 'COMPLETED', 'REASSIGNED')"))
    preliminary_vetting_due = Column(DateTime(timezone=True))
    preliminary_vetting_completed_at = Column(DateTime(timezone=True))
    next_review_due = Column(DateTime(timezone=True))
    review_interval_days = Column(Integer, default=28)
    court_attendance_required = Column(Boolean, default=False)
    next_court_date = Column(DateTime(timezone=True))
    plo_reg_number = Column(String(10), ForeignKey('personnel.reg_number'))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    case = relationship('Case', back_populates='investigation')
    worksheets = relationship('InvestigationWorksheet', back_populates='investigation')
    action_sheets = relationship('ActionSheet', back_populates='investigation')

class InvestigationWorksheet(db.Model):
    __tablename__ = 'investigation_worksheets'
    worksheet_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    investigation_id = Column(UUID(as_uuid=True), ForeignKey('investigations.investigation_id'), nullable=False)
    worksheet_date = Column(db.Date, nullable=False)
    narrative = Column(Text, nullable=False)
    narrative_hash = Column(String(64), nullable=False)
    signed_by = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    signed_at = Column(DateTime(timezone=True), nullable=False)
    attachments = Column(JSONB, default='[]')
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    investigation = relationship('Investigation', back_populates='worksheets')

class ActionSheet(db.Model):
    __tablename__ = 'action_sheets'
    action_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    investigation_id = Column(UUID(as_uuid=True), ForeignKey('investigations.investigation_id'), nullable=False)
    action_sequence = Column(Integer, nullable=False)
    generated_from = Column(String(20), CheckConstraint("generated_from IN ('INITIAL_VETTING', 'CASE_CONFERENCE', 'CONTINUOUS_VETTING', 'CASE_REVIEW', 'COURT_DIRECTION', 'DPP_ADVICE')"))
    action_description = Column(Text, nullable=False)
    assigned_by = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    assigned_to = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    date_tasked = Column(DateTime(timezone=True), default=datetime.utcnow)
    due_date = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    completed_by = Column(String(10), ForeignKey('personnel.reg_number'))
    completion_notes = Column(Text)
    action_status = Column(String(15), default='PENDING',
                          CheckConstraint("action_status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'OVERDUE', 'ESCALATED', 'CANCELLED')"))
    escalated_at = Column(DateTime(timezone=True))
    escalated_to = Column(String(10), ForeignKey('personnel.reg_number'))
    escalation_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    investigation = relationship('Investigation', back_populates='action_sheets')
