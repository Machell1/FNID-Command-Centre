"""
FNID Command Centre v2.0 - Main Dashboard Routes
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return redirect('/dashboard')

@main_bp.route('/dashboard')
@jwt_required()
def dashboard():
    return render_template('dashboard/main.html')

@main_bp.route('/registry')
@jwt_required()
def registry_portal():
    return render_template('registry/dashboard.html')

@main_bp.route('/investigation')
@jwt_required()
def investigation_portal():
    return render_template('investigation/dashboard.html')

@main_bp.route('/seizures')
@jwt_required()
def seizures_portal():
    return render_template('seizures/dashboard.html')

@main_bp.route('/intelligence')
@jwt_required()
def intelligence_portal():
    return render_template('intelligence/dashboard.html')

@main_bp.route('/court')
@jwt_required()
def court_portal():
    return render_template('court/dashboard.html')

@main_bp.route('/forensics')
@jwt_required()
def forensics_portal():
    return render_template('forensics/dashboard.html')
