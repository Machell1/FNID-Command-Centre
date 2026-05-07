"""
FNID Command Centre v2.0 - Personnel & Organizational Models
SOP Sections 7, 8 - Appendix 1 & 2
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, INET, GEOGRAPHY
from sqlalchemy.orm import relationship
from uuid import uuid4
from .. import db

class Area(db.Model):
    __tablename__ = 'areas'
    area_id = Column(Integer, primary_key=True)
    area_code = Column(String(3), unique=True, nullable=False)
    area_name = Column(String(50), nullable=False)
    acp_reg_number = Column(String(10), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    divisions = relationship('Division', back_populates='area')

class Division(db.Model):
    __tablename__ = 'divisions'
    division_id = Column(Integer, primary_key=True)
    area_id = Column(Integer, ForeignKey('areas.area_id'), nullable=False)
    division_code = Column(String(5), unique=True, nullable=False)
    division_name = Column(String(50), nullable=False)
    division_type = Column(String(10), CheckConstraint("division_type IN ('SUPER', 'NON_SUPER')"))
    commander_reg_number = Column(String(10), nullable=False)
    dco_reg_number = Column(String(10), nullable=False)
    ddi_reg_number = Column(String(10))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    area = relationship('Area', back_populates='divisions')
    stations = relationship('Station', back_populates='division')
    personnel = relationship('Personnel', back_populates='division')

class Station(db.Model):
    __tablename__ = 'stations'
    station_id = Column(Integer, primary_key=True)
    division_id = Column(Integer, ForeignKey('divisions.division_id'), nullable=False)
    station_code = Column(String(5), unique=True, nullable=False)
    station_name = Column(String(50), nullable=False)
    station_type = Column(String(15), CheckConstraint("station_type IN ('GEOGRAPHIC', 'SPECIALIST', 'PORTS', 'MARINE')"))
    station_manager_reg_number = Column(String(10))
    srms_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    division = relationship('Division', back_populates='stations')
    personnel = relationship('Personnel', back_populates='station')

class Personnel(db.Model):
    __tablename__ = 'personnel'
    reg_number = Column(String(10), primary_key=True)
    rank = Column(String(20), nullable=False, 
                  CheckConstraint("rank IN ('CONSTABLE', 'CORPORAL', 'SERGEANT', 'INSPECTOR', 'SUPERINTENDENT', 'SENIOR_SUPERINTENDENT', 'ASSISTANT_COMMISSIONER', 'DEPUTY_COMMISSIONER', 'COMMISSIONER')"))
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True)
    password_hash = Column(String(255))
    division_id = Column(Integer, ForeignKey('divisions.division_id'))
    station_id = Column(Integer, ForeignKey('stations.station_id'))
    unit = Column(String(20), CheckConstraint("unit IN ('UNIFORMED', 'NON_UNIFORMED', 'INTELLIGENCE', 'OPERATIONS', 'SEIZURES', 'ARRESTS_COURT', 'FORENSICS', 'CASE_REGISTRY', 'C_TOC', 'CISOCA', 'PSTEB', 'MARINE', 'PORTS', 'FNID')"))
    role = Column(String(30), CheckConstraint("role IN ('INVESTIGATING_OFFICER', 'SENIOR_INVESTIGATION_OFFICER', 'REGISTRAR', 'REGISTRY_SUPERVISOR', 'VETTING_OFFICER_MAJOR', 'VETTING_OFFICER_MINOR', 'PROSECUTION_LIAISON_OFFICER', 'CRIME_ANALYST', 'TYPIST', 'DATA_ENTRY_CLERK', 'READER_INDEXER', 'STATION_MANAGER', 'DIVISIONAL_CRIME_OFFICER', 'DIVISIONAL_COMMANDER', 'AREA_CRIME_OFFICER', 'LEGAL_OFFICER')"))
    is_active = Column(Boolean, default=True)
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255))
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    division = relationship('Division', back_populates='personnel')
    station = relationship('Station', back_populates='personnel')

    def has_role(self, required_roles):
        if isinstance(required_roles, str):
            required_roles = [required_roles]
        return self.role in required_roles

    def can_access_case(self, case):
        """Check if officer can access case based on unit, division, station."""
        if self.role in ['DIVISIONAL_COMMANDER', 'DIVISIONAL_CRIME_OFFICER', 'AREA_CRIME_OFFICER']:
            return True
        if case.division_id == self.division_id:
            return True
        if case.station_id == self.station_id:
            return True
        if case.created_by == self.reg_number:
            return True
        return False
