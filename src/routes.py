from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db  # <-- changed
from src.models import Officer, Case, Suspect
from src.forms import SearchForm

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Get officer's cases
    if current_user.role in ['admin', 'supervisor']:
        cases = Case.query.filter(Case.status != 'archived').order_by(Case.created_at.desc()).limit(10).all()
    else:
        cases = Case.query.filter_by(assigned_officer_id=current_user.id, status='open').order_by(Case.created_at.desc()).limit(10).all()
    
    # Get statistics
    stats = {
        'total_cases': Case.query.filter_by(assigned_officer_id=current_user.id).count() if current_user.role == 'officer' else Case.query.count(),
        'open_cases': Case.query.filter_by(assigned_officer_id=current_user.id, status='open').count() if current_user.role == 'officer' else Case.query.filter_by(status='open').count(),
        'closed_cases': Case.query.filter_by(assigned_officer_id=current_user.id, status='closed').count() if current_user.role == 'officer' else Case.query.filter_by(status='closed').count(),
        'total_suspects': Suspect.query.count()
    }
    
    return render_template('officers/dashboard.html', cases=cases, stats=stats)

@main_bp.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    form = SearchForm()
    results = []
    
    if form.validate_on_submit():
        search_type = form.search_type.data
        query = form.query.data
        
        if search_type == 'suspect':
            # Search suspects by name or ID
            results = Suspect.query.filter(
                db.or_(
                    Suspect.id_number.ilike(f'%{query}%'),
                    Suspect.first_name.ilike(f'%{query}%'),
                    Suspect.last_name.ilike(f'%{query}%')
                )
            ).all()
        elif search_type == 'case':
            # Search cases
            results = Case.query.filter(
                db.or_(
                    Case.case_number.ilike(f'%{query}%'),
                    Case.title.ilike(f'%{query}%')
                )
            ).all()
            # Filter by access rights
            if current_user.role == 'officer':
                results = [case for case in results if case.assigned_officer_id == current_user.id]
    
    return render_template('search.html', form=form, results=results, search_type=form.search_type.data if form.is_submitted() else None)

@main_bp.route('/api/suspects/check-duplicate', methods=['POST'])
@login_required
def check_duplicate_suspect():
    data = request.get_json()
    id_number = data.get('id_number')
    
    if not id_number:
        return jsonify({'error': 'ID number required'}), 400
    
    suspect = Suspect.query.filter_by(id_number=id_number).first()
    
    if suspect:
        return jsonify({
            'exists': True,
            'suspect': suspect.to_dict()
        })
    
    return jsonify({'exists': False})