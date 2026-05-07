"""
FNID Command Centre v2.0 - Registry API Routes
SOP Compliant Case Management
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from marshmallow import Schema, fields, validate
from ..services.registry_service import RegistryService
from ..services.audit_service import AuditService
from ..models.base import Case, DCRREntry, StationRegister, Investigation, ActionSheet
from ..models.personnel import Personnel
from .. import db

registry_bp = Blueprint('registry', __name__)

class CaseCreateSchema(Schema):
    area_id = fields.Integer(required=True)
    division_id = fields.Integer(required=True)
    station_id = fields.Integer(required=True)
    offence_code = fields.String(required=True)
    offence_description = fields.String(required=True)
    diary_type = fields.String(validate=validate.OneOf(['SD', 'CD']), load_default='SD')
    diary_entry_number = fields.Integer(load_default=1)
    diary_used_for_cr = fields.String(validate=validate.OneOf(['STATION', 'CRIME', 'BOTH']), load_default='STATION')
    date_of_offence = fields.DateTime(format='%Y-%m-%dT%H:%M:%S', allow_none=True)
    time_of_offence = fields.Time(format='%H:%M', allow_none=True)
    location_of_offence = fields.String(allow_none=True)
    location_parish = fields.String(allow_none=True)
    specialist_unit = fields.String(allow_none=True)

case_schema = CaseCreateSchema()

@registry_bp.route('/cases', methods=['GET'])
@jwt_required()
def list_cases():
    """List cases with filtering."""
    claims = get_jwt()
    division_id = claims.get('division_id')
    station_id = claims.get('station_id')
    role = claims.get('role')

    query = Case.query.filter(Case.deleted_at.is_(None))

    # Filter by access level
    if role not in ['DIVISIONAL_COMMANDER', 'DIVISIONAL_CRIME_OFFICER', 'AREA_CRIME_OFFICER']:
        query = query.filter(
            db.or_(
                Case.division_id == division_id,
                Case.station_id == station_id,
                Case.created_by == claims.get('reg_number')
            )
        )

    # Apply filters
    status = request.args.get('status')
    if status:
        query = query.filter(Case.status == status)

    registry_type = request.args.get('registry_type')
    if registry_type:
        query = query.filter(Case.registry_type == registry_type)

    crime_category = request.args.get('crime_category')
    if crime_category:
        query = query.filter(Case.crime_category == crime_category)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    pagination = query.order_by(Case.date_reported.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    cases = []
    for case in pagination.items:
        cases.append({
            'case_id': str(case.case_id),
            'cr_number': case.cr_number,
            'registry_type': case.registry_type,
            'crime_category': case.crime_category,
            'offence_description': case.offence_description,
            'status': case.status,
            'date_reported': case.date_reported.isoformat() if case.date_reported else None,
            'location_of_offence': case.location_of_offence,
            'created_by': case.created_by
        })

    return jsonify({
        'cases': cases,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    }), 200

@registry_bp.route('/cases', methods=['POST'])
@jwt_required()
def create_case():
    """Create new case with unified registry pipeline."""
    claims = get_jwt()
    reg_number = claims.get('reg_number')
    role = claims.get('role')

    # Only authorized roles can create cases
    if role not in ['REGISTRAR', 'STATION_MANAGER', 'DIVISIONAL_CRIME_OFFICER', 'INVESTIGATING_OFFICER']:
        return jsonify({'message': 'Unauthorized to create cases'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'message': 'No data provided'}), 400

    errors = case_schema.validate(data)
    if errors:
        return jsonify({'message': 'Validation error', 'errors': errors}), 400

    try:
        case = RegistryService.create_case(data, reg_number)

        AuditService.log_action(
            officer=Personnel.query.get(reg_number),
            action='CREATE',
            table_name='cases',
            record_id=case.case_id,
            new_values={'cr_number': case.cr_number, 'status': case.status}
        )

        return jsonify({
            'message': 'Case created successfully',
            'case_id': str(case.case_id),
            'cr_number': case.cr_number,
            'registry_type': case.registry_type
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error creating case: {str(e)}'}), 500

@registry_bp.route('/cases/<case_id>', methods=['GET'])
@jwt_required()
def get_case(case_id):
    """Get case details."""
    case = Case.query.filter(Case.case_id == case_id, Case.deleted_at.is_(None)).first()
    if not case:
        return jsonify({'message': 'Case not found'}), 404

    claims = get_jwt()
    officer = Personnel.query.get(claims.get('reg_number'))
    if not officer.can_access_case(case):
        return jsonify({'message': 'Access denied'}), 403

    result = {
        'case_id': str(case.case_id),
        'cr_number': case.cr_number,
        'registry_type': case.registry_type,
        'crime_category': case.crime_category,
        'offence_code': case.offence_code,
        'offence_description': case.offence_description,
        'investigated_by': case.investigated_by,
        'specialist_unit': case.specialist_unit,
        'status': case.status,
        'date_reported': case.date_reported.isoformat() if case.date_reported else None,
        'date_of_offence': case.date_of_offence.isoformat() if case.date_of_offence else None,
        'location_of_offence': case.location_of_offence,
        'location_parish': case.location_parish,
        'station_diary_entry': case.station_diary_entry_number,
        'crime_diary_entry': case.crime_diary_entry_number,
        'created_by': case.created_by,
        'created_at': case.created_at.isoformat() if case.created_at else None
    }

    # Add registry-specific data
    if case.registry_type == 'DCRR' and case.dcrr_entry:
        result['dcrr'] = {
            'dcrr_consecutive_number': case.dcrr_entry.dcrr_consecutive_number,
            'entry_color': case.dcrr_entry.entry_color,
            'registrar_id': case.dcrr_entry.registrar_id
        }
    elif case.station_register:
        result['station_register'] = {
            'register_type': case.station_register.register_type,
            'register_consecutive_number': case.station_register.register_consecutive_number,
            'station_manager_id': case.station_register.station_manager_id
        }

    # Add investigation data if exists
    if case.investigation:
        result['investigation'] = {
            'investigation_id': str(case.investigation.investigation_id),
            'io_reg_number': case.investigation.io_reg_number,
            'status': case.investigation.investigation_status,
            'preliminary_vetting_due': case.investigation.preliminary_vetting_due.isoformat() if case.investigation.preliminary_vetting_due else None,
            'next_review_due': case.investigation.next_review_due.isoformat() if case.investigation.next_review_due else None
        }

    return jsonify(result), 200

@registry_bp.route('/cases/<case_id>/assign', methods=['POST'])
@jwt_required()
def assign_case(case_id):
    """Assign investigating officer."""
    claims = get_jwt()
    reg_number = claims.get('reg_number')
    role = claims.get('role')

    if role not in ['REGISTRAR', 'STATION_MANAGER', 'DIVISIONAL_CRIME_OFFICER']:
        return jsonify({'message': 'Unauthorized to assign cases'}), 403

    data = request.get_json()
    io_reg_number = data.get('io_reg_number')

    if not io_reg_number:
        return jsonify({'message': 'Investigating officer required'}), 400

    investigation, error = RegistryService.assign_investigation(case_id, io_reg_number, reg_number)
    if error:
        return jsonify({'message': error}), 400

    return jsonify({
        'message': 'Case assigned successfully',
        'investigation_id': str(investigation.investigation_id),
        'io_reg_number': investigation.io_reg_number,
        'preliminary_vetting_due': investigation.preliminary_vetting_due.isoformat() if investigation.preliminary_vetting_due else None
    }), 200

@registry_bp.route('/cases/<case_id>/status', methods=['PUT'])
@jwt_required()
def update_case_status(case_id):
    """Transition case status."""
    claims = get_jwt()
    reg_number = claims.get('reg_number')

    data = request.get_json()
    new_status = data.get('status')
    reason = data.get('reason')

    if not new_status:
        return jsonify({'message': 'New status required'}), 400

    officer = Personnel.query.get(reg_number)
    case, error = RegistryService.transition_status(case_id, new_status, officer, reason)

    if error:
        return jsonify({'message': error}), 400

    return jsonify({
        'message': f'Case status updated to {new_status}',
        'case_id': str(case.case_id),
        'status': case.status,
        'status_changed_at': case.status_changed_at.isoformat() if case.status_changed_at else None
    }), 200

@registry_bp.route('/cases/<case_id>/action-sheets', methods=['GET'])
@jwt_required()
def get_action_sheets(case_id):
    """Get Action Sheets (CR 2) for case."""
    case = Case.query.get(case_id)
    if not case or not case.investigation:
        return jsonify({'message': 'Case or investigation not found'}), 404

    actions = ActionSheet.query.filter_by(investigation_id=case.investigation.investigation_id).order_by(ActionSheet.action_sequence).all()

    result = []
    for action in actions:
        result.append({
            'action_id': str(action.action_id),
            'action_sequence': action.action_sequence,
            'generated_from': action.generated_from,
            'action_description': action.action_description,
            'assigned_to': action.assigned_to,
            'date_tasked': action.date_tasked.isoformat() if action.date_tasked else None,
            'due_date': action.due_date.isoformat() if action.due_date else None,
            'completed_at': action.completed_at.isoformat() if action.completed_at else None,
            'action_status': action.action_status
        })

    return jsonify({'action_sheets': result}), 200
