"""
FNID Command Centre v2.0 - REST API v1
Production-grade endpoints with RBAC
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from ..models.base import Case, Investigation, ActionSheet, InvestigationWorksheet
from ..models.personnel import Personnel, Area, Division, Station
from ..models.fnid import FNIDSeizure, IntelligenceReport, DPPFilePipeline, Exhibit
from ..services.registry_service import RegistryService
from ..services.audit_service import AuditService
from .. import db

api_bp = Blueprint('api', __name__)

def get_current_officer():
    claims = get_jwt()
    return Personnel.query.get(claims.get('reg_number'))

# ── CASES ─────────────────────────────────────────────────

@api_bp.route('/cases', methods=['GET'])
@jwt_required()
def api_list_cases():
    claims = get_jwt()
    division_id = claims.get('division_id')
    station_id = claims.get('station_id')
    role = claims.get('role')
    reg_number = claims.get('reg_number')

    query = Case.query.filter(Case.deleted_at.is_(None))

    if role not in ['DIVISIONAL_COMMANDER', 'DIVISIONAL_CRIME_OFFICER', 'AREA_CRIME_OFFICER', 'ASSISTANT_COMMISSIONER']:
        query = query.filter(
            or_(
                Case.division_id == division_id,
                Case.station_id == station_id,
                Case.created_by == reg_number
            )
        )

    if request.args.get('status'):
        query = query.filter(Case.status == request.args.get('status'))
    if request.args.get('registry_type'):
        query = query.filter(Case.registry_type == request.args.get('registry_type'))
    if request.args.get('crime_category'):
        query = query.filter(Case.crime_category == request.args.get('crime_category'))
    if request.args.get('division_id'):
        query = query.filter(Case.division_id == request.args.get('division_id'))
    if request.args.get('date_from'):
        query = query.filter(Case.date_reported >= request.args.get('date_from'))
    if request.args.get('date_to'):
        query = query.filter(Case.date_reported <= request.args.get('date_to'))

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    pagination = query.order_by(Case.date_reported.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'cases': [{
            'case_id': str(c.case_id),
            'cr_number': c.cr_number,
            'registry_type': c.registry_type,
            'crime_category': c.crime_category,
            'offence_description': c.offence_description,
            'status': c.status,
            'date_reported': c.date_reported.isoformat() if c.date_reported else None,
            'location_of_offence': c.location_of_offence,
            'created_by': c.created_by,
            'has_investigation': c.investigation is not None
        } for c in pagination.items],
        'meta': {
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page
        }
    }), 200

@api_bp.route('/cases/<case_id>', methods=['GET'])
@jwt_required()
def api_get_case(case_id):
    case = Case.query.filter(Case.case_id == case_id, Case.deleted_at.is_(None)).first()
    if not case:
        return jsonify({'message': 'Case not found'}), 404

    officer = get_current_officer()
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
        'status_reason': case.status_reason,
        'date_reported': case.date_reported.isoformat() if case.date_reported else None,
        'date_of_offence': case.date_of_offence.isoformat() if case.date_of_offence else None,
        'location_of_offence': case.location_of_offence,
        'location_parish': case.location_parish,
        'created_by': case.created_by,
        'created_at': case.created_at.isoformat() if case.created_at else None,
        'version': case.version
    }

    if case.dcrr_entry:
        result['dcrr'] = {
            'dcrr_consecutive_number': case.dcrr_entry.dcrr_consecutive_number,
            'entry_color': case.dcrr_entry.entry_color,
            'registrar_id': case.dcrr_entry.registrar_id,
            'vetting_officer_major_id': case.dcrr_entry.vetting_officer_major_id,
            'vetting_officer_minor_id': case.dcrr_entry.vetting_officer_minor_id
        }

    if case.station_register:
        result['station_register'] = {
            'register_type': case.station_register.register_type,
            'register_consecutive_number': case.station_register.register_consecutive_number,
            'station_manager_id': case.station_register.station_manager_id,
            'first_review_due': case.station_register.first_review_due.isoformat() if case.station_register.first_review_due else None
        }

    if case.investigation:
        result['investigation'] = {
            'investigation_id': str(case.investigation.investigation_id),
            'io_reg_number': case.investigation.io_reg_number,
            'sio_reg_number': case.investigation.sio_reg_number,
            'supervisor_reg_number': case.investigation.supervisor_reg_number,
            'investigation_status': case.investigation.investigation_status,
            'preliminary_vetting_due': case.investigation.preliminary_vetting_due.isoformat() if case.investigation.preliminary_vetting_due else None,
            'next_review_due': case.investigation.next_review_due.isoformat() if case.investigation.next_review_due else None,
            'review_interval_days': case.investigation.review_interval_days,
            'court_attendance_required': case.investigation.court_attendance_required,
            'next_court_date': case.investigation.next_court_date.isoformat() if case.investigation.next_court_date else None
        }

    return jsonify(result), 200

@api_bp.route('/cases/<case_id>/investigation', methods=['GET'])
@jwt_required()
def api_get_investigation(case_id):
    case = Case.query.get(case_id)
    if not case or not case.investigation:
        return jsonify({'message': 'Investigation not found'}), 404

    inv = case.investigation
    actions = ActionSheet.query.filter_by(investigation_id=inv.investigation_id).order_by(ActionSheet.action_sequence).all()
    worksheets = InvestigationWorksheet.query.filter_by(investigation_id=inv.investigation_id).order_by(InvestigationWorksheet.worksheet_date.desc()).all()

    return jsonify({
        'investigation_id': str(inv.investigation_id),
        'io_reg_number': inv.io_reg_number,
        'io_assigned_at': inv.io_assigned_at.isoformat() if inv.io_assigned_at else None,
        'supervisor_reg_number': inv.supervisor_reg_number,
        'investigation_status': inv.investigation_status,
        'preliminary_vetting_due': inv.preliminary_vetting_due.isoformat() if inv.preliminary_vetting_due else None,
        'preliminary_vetting_completed_at': inv.preliminary_vetting_completed_at.isoformat() if inv.preliminary_vetting_completed_at else None,
        'next_review_due': inv.next_review_due.isoformat() if inv.next_review_due else None,
        'action_sheets': [{
            'action_id': str(a.action_id),
            'action_sequence': a.action_sequence,
            'generated_from': a.generated_from,
            'action_description': a.action_description,
            'assigned_to': a.assigned_to,
            'due_date': a.due_date.isoformat() if a.due_date else None,
            'completed_at': a.completed_at.isoformat() if a.completed_at else None,
            'action_status': a.action_status,
            'escalated_at': a.escalated_at.isoformat() if a.escalated_at else None
        } for a in actions],
        'worksheets': [{
            'worksheet_id': str(w.worksheet_id),
            'worksheet_date': w.worksheet_date.isoformat() if w.worksheet_date else None,
            'signed_by': w.signed_by,
            'signed_at': w.signed_at.isoformat() if w.signed_at else None,
            'narrative_hash': w.narrative_hash
        } for w in worksheets]
    }), 200

# ── DASHBOARD STATS ───────────────────────────────────────

@api_bp.route('/dashboard/stats', methods=['GET'])
@jwt_required()
def api_dashboard_stats():
    claims = get_jwt()
    division_id = claims.get('division_id')
    station_id = claims.get('station_id')
    role = claims.get('role')

    base_filter = [Case.deleted_at.is_(None)]
    if role not in ['DIVISIONAL_COMMANDER', 'DIVISIONAL_CRIME_OFFICER', 'AREA_CRIME_OFFICER']:
        base_filter.append(or_(Case.division_id == division_id, Case.station_id == station_id))

    status_counts = db.session.query(Case.status, func.count(Case.case_id)).filter(*base_filter).group_by(Case.status).all()
    counts = {status: 0 for status in ['OPEN', 'ASSIGNED', 'ACTIVE', 'UNDER_REVIEW', 'SUSPENDED', 'CLEARED', 'CLOSED', 'COLD_CASE']}
    for status, count in status_counts:
        counts[status] = count

    overdue = ActionSheet.query.filter(
        ActionSheet.due_date < datetime.utcnow(),
        ActionSheet.action_status.in_(['PENDING', 'IN_PROGRESS'])
    ).count()

    category_counts = db.session.query(Case.crime_category, func.count(Case.case_id)).filter(*base_filter).group_by(Case.crime_category).all()

    return jsonify({
        'status_counts': counts,
        'overdue_actions': overdue,
        'category_counts': {cat: count for cat, count in category_counts},
        'total_cases': sum(counts.values())
    }), 200

# ── REFERENCE DATA ────────────────────────────────────────

@api_bp.route('/divisions', methods=['GET'])
@jwt_required()
def api_list_divisions():
    divisions = Division.query.all()
    return jsonify([{
        'division_id': d.division_id,
        'division_code': d.division_code,
        'division_name': d.division_name,
        'division_type': d.division_type,
        'area_id': d.area_id
    } for d in divisions]), 200

@api_bp.route('/stations', methods=['GET'])
@jwt_required()
def api_list_stations():
    division_id = request.args.get('division_id')
    query = Station.query
    if division_id:
        query = query.filter_by(division_id=division_id)
    stations = query.all()
    return jsonify([{
        'station_id': s.station_id,
        'station_code': s.station_code,
        'station_name': s.station_name,
        'station_type': s.station_type,
        'division_id': s.division_id
    } for s in stations]), 200

@api_bp.route('/officers', methods=['GET'])
@jwt_required()
def api_list_officers():
    division_id = request.args.get('division_id')
    station_id = request.args.get('station_id')
    role_filter = request.args.get('role')

    query = Personnel.query.filter_by(is_active=True)
    if division_id:
        query = query.filter_by(division_id=division_id)
    if station_id:
        query = query.filter_by(station_id=station_id)
    if role_filter:
        query = query.filter_by(role=role_filter)

    officers = query.all()
    return jsonify([{
        'reg_number': o.reg_number,
        'full_name': o.full_name,
        'rank': o.rank,
        'role': o.role,
        'unit': o.unit,
        'division_id': o.division_id,
        'station_id': o.station_id
    } for o in officers]), 200
