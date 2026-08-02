from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from extensions import db  # <-- changed
from src.models import Suspect, Case
import json

suspects_bp = Blueprint('suspects', __name__)

@suspects_bp.route('/suspects/search', methods=['GET', 'POST'])
@login_required
def search_suspects():
    """Search for suspects"""
    query = request.args.get('q', '')
    
    if query:
        # Search by ID number or name
        suspects = Suspect.query.filter(
            db.or_(
                Suspect.id_number.ilike(f'%{query}%'),
                Suspect.first_name.ilike(f'%{query}%'),
                Suspect.last_name.ilike(f'%{query}%'),
                db.func.concat(Suspect.first_name, ' ', Suspect.last_name).ilike(f'%{query}%')
            )
        ).all()
    else:
        suspects = []
    
    return render_template('suspects/search.html', suspects=suspects, query=query)

@suspects_bp.route('/suspects/<int:suspect_id>')
@login_required
def view_suspect(suspect_id):
    """View suspect profile and cases"""
    suspect = Suspect.query.get_or_404(suspect_id)
    
    # Get cases for this suspect
    if current_user.role in ['admin', 'supervisor']:
        cases = Case.query.filter_by(suspect_id=suspect_id)\
                         .order_by(Case.created_at.desc())\
                         .all()
    else:
        cases = Case.query.filter_by(
            suspect_id=suspect_id,
            assigned_officer_id=current_user.id
        ).order_by(Case.created_at.desc()).all()
    
    return render_template('suspects/profile.html', suspect=suspect, cases=cases)

@suspects_bp.route('/api/suspects/<int:suspect_id>', methods=['GET'])
@login_required
def get_suspect_details(suspect_id):
    """Get detailed suspect information by ID"""
    try:
        suspect = Suspect.query.get_or_404(suspect_id)
        
        return jsonify({
            'success': True,
            'suspect': {
                'id': suspect.id,
                'first_name': suspect.first_name,
                'last_name': suspect.last_name,
                'full_name': suspect.full_name,
                'id_number': suspect.id_number,
                'date_of_birth': suspect.date_of_birth.strftime('%Y-%m-%d') if suspect.date_of_birth else None,
                'gender': suspect.gender,
                'address': suspect.address,
                'contact_number': suspect.contact_number,
                'photo_path': suspect.photo_path,
                'active_cases': suspect.active_cases,
                'created_at': suspect.created_at.strftime('%Y-%m-%d') if suspect.created_at else None
            }
        })
        
    except Exception as e:
        print(f"Error getting suspect details: {str(e)}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500