"""
FNID Command Centre v2.0 - FNID Domain Models
Firearms, Narcotics, Intelligence, DPP Pipeline, Exhibits
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, GEOGRAPHY
from sqlalchemy.orm import relationship
from uuid import uuid4
from .. import db

class FNIDSeizure(db.Model):
    __tablename__ = 'fnid_seizures'
    seizure_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id'))
    seizure_type = Column(String(20), CheckConstraint("seizure_type IN ('FIREARM', 'AMMUNITION', 'NARCOTICS', 'CASH', 'VEHICLE', 'OTHER')"))
    firearm_make = Column(String(50))
    firearm_model = Column(String(50))
    firearm_serial_number = Column(String(50))
    firearm_caliber = Column(String(20))
    ammunition_count = Column(Integer)
    firearm_condition = Column(String(20))
    drug_type = Column(String(30))
    weight_lbs = Column(Numeric(10, 2))
    weight_kg = Column(Numeric(10, 2))
    estimated_purity_percent = Column(Numeric(5, 2))
    street_value_jmd = Column(Numeric(15, 2))
    drug_packaging = Column(String(50))
    seizure_location = Column(GEOGRAPHY('POINT', 4326))
    seized_by = Column(String(10), ForeignKey('personnel.reg_number'))
    seized_at = Column(DateTime(timezone=True))
    exhibit_number = Column(String(20))
    intelligence_id = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    case = relationship('Case', back_populates='seizures')

class IntelligenceReport(db.Model):
    __tablename__ = 'intelligence_reports'
    intel_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id'))
    source_type = Column(String(20), CheckConstraint("source_type IN ('HUMAN', 'TECHNICAL', 'OPEN_SOURCE', 'SURVEILLANCE', 'FINANCIAL')"))
    source_reliability = Column(String(10), CheckConstraint("source_reliability IN ('A', 'B', 'C', 'D', 'E')"))
    information_validity = Column(String(10), CheckConstraint("information_validity IN ('1', '2', '3', '4', '5', '6')"))
    target_firearm_trafficking = Column(Boolean, default=False)
    target_narcotics_cartel = Column(Boolean, default=False)
    cross_border_operation = Column(Boolean, default=False)
    linked_cases = Column(ARRAY(UUID(as_uuid=True)))
    dim_reg_number = Column(String(10))
    handler_reg_number = Column(String(10))
    classification = Column(String(10), CheckConstraint("classification IN ('RESTRICTED', 'CONFIDENTIAL', 'SECRET', 'TOP_SECRET')"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    case = relationship('Case', back_populates='intelligence_reports')

class DPPFilePipeline(db.Model):
    __tablename__ = 'dpp_file_pipeline'
    pipeline_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id'))
    file_status = Column(String(20), CheckConstraint("file_status IN ('PREPARATION', 'VETTING', 'SUBMITTED_TO_DPP', 'RULING_PENDING', 'NO_CASE', 'COMMITTAL', 'TRIAL')"))
    prosecution_bundle_hash = Column(String(64))
    disclosure_bundle_hash = Column(String(64))
    auto_redaction_applied = Column(Boolean, default=False)
    court_date = Column(DateTime(timezone=True))
    court_type = Column(String(20))
    committal_date = Column(DateTime(timezone=True))
    firearms_expert_cert_attached = Column(Boolean, default=False)
    narcotics_certificate_attached = Column(Boolean, default=False)
    pocA_restraint_order_attached = Column(Boolean, default=False)
    vetted_by_lo = Column(String(10))
    vetted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    case = relationship('Case', back_populates='dpp_pipeline')

class Exhibit(db.Model):
    __tablename__ = 'exhibits'
    exhibit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey('cases.case_id'), nullable=False)
    exhibit_number = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    current_holder = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    current_location = Column(String(50), nullable=False)
    custody_status = Column(String(15), CheckConstraint("custody_status IN ('SEIZED', 'STORED', 'IN_TRANSIT', 'IN_LAB', 'IN_COURT', 'RETURNED', 'DESTROYED')"))
    seized_by = Column(String(10), ForeignKey('personnel.reg_number'), nullable=False)
    seized_at = Column(DateTime(timezone=True), nullable=False)
    seized_from_location = Column(Text)
    custody_chain = Column(JSONB, nullable=False, default='[]')
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    case = relationship('Case', back_populates='exhibits')
