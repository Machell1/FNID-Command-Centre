"""
FNID Command Centre v2.0 - Case Registry Service
Unified DCRR + Station Register pipeline
SOP JCF/FW/PL/C&S/0001/2024 Compliant
"""
from datetime import datetime, timedelta
from sqlalchemy import func
from ..models.base import Case, DCRREntry, StationRegister, Investigation, ActionSheet
from ..models.personnel import Personnel, Division, Station
from .. import db

class RegistryService:
    OFFENCE_CLASSIFICATION = {
        'FIREARMS': {'category': 'FIREARMS', 'is_major': True, 'registry': 'DCRR'},
        'NARCOTICS_MAJOR': {'category': 'NARCOTICS', 'is_major': True, 'registry': 'DCRR'},
        'NARCOTICS_MINOR': {'category': 'NARCOTICS', 'is_major': False, 'registry': 'MINOR'},
        'MURDER': {'category': 'HOMICIDE', 'is_major': True, 'registry': 'DCRR'},
        'MANSLAUGHTER': {'category': 'HOMICIDE', 'is_major': True, 'registry': 'DCRR'},
        'ROBBERY': {'category': 'MAJOR', 'is_major': True, 'registry': 'DCRR'},
        'BURGLARY': {'category': 'MAJOR', 'is_major': True, 'registry': 'MAJOR'},
        'LARCENY_SIMPLE': {'category': 'MINOR', 'is_major': False, 'registry': 'MINOR'},
        'ASSAULT_COMMON': {'category': 'MINOR', 'is_major': False, 'registry': 'MINOR'},
    }

    @classmethod
    def classify_offence(cls, offence_code):
        """Classify offence and determine registry type."""
        return cls.OFFENCE_CLASSIFICATION.get(offence_code, 
            {'category': 'MAJOR', 'is_major': True, 'registry': 'DCRR'})

    @classmethod
    def generate_cr_number(cls, registry_type, station_id, division_id, diary_type, diary_entry_number, date_reported):
        """Generate SOP-compliant Case Reference Number."""
        station = Station.query.get(station_id)
        division = Division.query.get(division_id)

        date_str = date_reported.strftime('%Y/%m/%d')

        if registry_type == 'DCRR':
            # Get next DCRR consecutive number
            last_entry = DCRREntry.query.join(Case).filter(
                Case.division_id == division_id,
                Case.registry_type == 'DCRR'
            ).order_by(DCRREntry.dcrr_consecutive_number.desc()).first()

            cons_num = (last_entry.dcrr_consecutive_number + 1) if last_entry else 1

            # Format: {cons}_{yyyy/mm/dd}/{station}/SD{entry}/{division}
            cr_number = f"{cons_num}_{date_str}/{station.station_code}/{diary_type}{diary_entry_number}/{division.division_code}"
            return cr_number, cons_num
        else:
            # Station register
            last_reg = StationRegister.query.join(Case).filter(
                Case.station_id == station_id,
                Case.registry_type == registry_type
            ).order_by(StationRegister.register_consecutive_number.desc()).first()

            cons_num = (last_reg.register_consecutive_number + 1) if last_reg else 1

            # Format: {cons}_/{entry}/{yyyy/mm/dd}/{station}
            cr_number = f"{cons_num}_/{diary_entry_number}/{date_str}/{station.station_code}"
            return cr_number, cons_num

    @classmethod
    def create_case(cls, case_data, created_by):
        """Create new case with unified registry pipeline."""
        classification = cls.classify_offence(case_data.get('offence_code', 'FIREARMS'))
        registry_type = classification['registry']

        # Determine investigation unit
        if case_data.get('specialist_unit') == 'FNID':
            investigated_by = 'SPECIALIST_UNIT'
        elif classification['is_major']:
            investigated_by = 'NON_UNIFORMED'
        else:
            investigated_by = 'UNIFORMED'

        # Generate CR number
        cr_number, cons_num = cls.generate_cr_number(
            registry_type=registry_type,
            station_id=case_data['station_id'],
            division_id=case_data['division_id'],
            diary_type=case_data.get('diary_type', 'SD'),
            diary_entry_number=case_data.get('diary_entry_number', 1),
            date_reported=datetime.utcnow()
        )

        # Create case
        case = Case(
            cr_number=cr_number,
            registry_type=registry_type,
            area_id=case_data['area_id'],
            division_id=case_data['division_id'],
            station_id=case_data['station_id'],
            crime_category=classification['category'],
            offence_code=case_data['offence_code'],
            offence_description=case_data['offence_description'],
            investigated_by=investigated_by,
            specialist_unit=case_data.get('specialist_unit'),
            date_reported=datetime.utcnow(),
            date_of_offence=case_data.get('date_of_offence'),
            time_of_offence=case_data.get('time_of_offence'),
            station_diary_entry_number=case_data.get('diary_entry_number'),
            diary_used_for_cr=case_data.get('diary_used_for_cr', 'STATION'),
            location_of_offence=case_data.get('location_of_offence'),
            location_parish=case_data.get('location_parish'),
            status='OPEN',
            created_by=created_by
        )

        db.session.add(case)
        db.session.flush()  # Get case_id

        # Create registry extension
        if registry_type == 'DCRR':
            dcrr_entry = DCRREntry(
                case_id=case.case_id,
                dcrr_consecutive_number=cons_num,
                dcrr_year=datetime.utcnow().year,
                registrar_id=created_by,
                entry_color='BLUE'
            )
            db.session.add(dcrr_entry)
        else:
            station_reg = StationRegister(
                case_id=case.case_id,
                register_type=registry_type,
                register_consecutive_number=cons_num,
                station_manager_id=created_by
            )
            db.session.add(station_reg)

        db.session.commit()
        return case

    @classmethod
    def assign_investigation(cls, case_id, io_reg_number, assigned_by):
        """Assign investigating officer and create initial Action Sheet."""
        case = Case.query.get(case_id)
        if not case:
            return None, 'Case not found'

        io = Personnel.query.get(io_reg_number)
        if not io or not io.is_active:
            return None, 'Investigating officer not found or inactive'

        # Create investigation
        investigation = Investigation(
            case_id=case_id,
            io_reg_number=io_reg_number,
            io_assigned_by=assigned_by,
            investigation_status='PENDING',
            preliminary_vetting_due=datetime.utcnow() + timedelta(hours=72 if case.investigated_by == 'NON_UNIFORMED' else 48),
            next_review_due=datetime.utcnow() + timedelta(days=7)
        )
        db.session.add(investigation)

        # Create initial Action Sheet (CR 2)
        action = ActionSheet(
            investigation_id=investigation.investigation_id,
            action_sequence=1,
            generated_from='INITIAL_VETTING',
            action_description=f"Preliminary vetting of {case.offence_description}",
            assigned_by=assigned_by,
            assigned_to=io_reg_number,
            due_date=investigation.preliminary_vetting_due,
            action_status='PENDING'
        )
        db.session.add(action)

        # Update case status
        case.status = 'ASSIGNED'
        case.date_assigned = datetime.utcnow()
        case.status_changed_at = datetime.utcnow()
        case.status_changed_by = assigned_by

        db.session.commit()
        return investigation, None

    @classmethod
    def transition_status(cls, case_id, new_status, officer, reason=None):
        """Transition case status with SOP compliance checks."""
        case = Case.query.get(case_id)
        if not case:
            return None, 'Case not found'

        if not case.can_transition_to(new_status, officer):
            return None, f'Cannot transition from {case.status} to {new_status} with your authority level'

        old_status = case.status
        case.status = new_status
        case.status_changed_at = datetime.utcnow()
        case.status_changed_by = officer.reg_number
        case.status_reason = reason

        # SOP-specific side effects
        if new_status == 'SUSPENDED':
            case.suspended_at = datetime.utcnow()
            case.suspended_by = officer.reg_number
            case.suspension_review_due = datetime.utcnow() + timedelta(days=90)
            case.suspension_reason = reason or 'All investigative leads exhausted'
        elif new_status == 'CLOSED':
            case.closure_approved_by = officer.reg_number
            case.closure_approved_at = datetime.utcnow()
            case.disposition_scheduled_at = datetime.utcnow() + timedelta(days=365*7)
        elif new_status == 'COLD_CASE':
            case.declared_cold_at = datetime.utcnow()
            case.declared_cold_by = officer.reg_number
        elif new_status == 'REOPENED':
            # Reset review schedule
            if case.investigation:
                case.investigation.next_review_due = datetime.utcnow() + timedelta(days=7)

        db.session.commit()

        # Log audit
        from .audit_service import AuditService
        AuditService.log_action(
            officer=officer,
            action='UPDATE',
            table_name='cases',
            record_id=str(case_id),
            old_values={'status': old_status},
            new_values={'status': new_status},
            change_reason=reason
        )

        return case, None
