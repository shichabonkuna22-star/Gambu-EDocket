from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from src.models import Officer, Case, Suspect, Notification
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
    # ---- Recent cases ----
    if current_user.role in ['admin', 'supervisor']:
        # Supervisors/admins see all non-archived cases
        cases = Case.query.filter(Case.status != 'archived')\
                          .order_by(Case.created_at.desc())\
                          .limit(10)\
                          .all()
    else:
        # Officers see all cases they are assigned to, except closed/archived
        cases = Case.query.filter_by(assigned_officer_id=current_user.id)\
                          .filter(Case.status.notin_(['closed', 'archived']))\
                          .order_by(Case.created_at.desc())\
                          .limit(10)\
                          .all()

    # ---- Statistics ----
    if current_user.role == 'officer':
        # All cases assigned to this officer (including closed/archived) for totals
        all_assigned = Case.query.filter_by(assigned_officer_id=current_user.id)
        total_cases = all_assigned.count()
        open_cases = all_assigned.filter_by(status='open').count()
        closed_cases = all_assigned.filter_by(status='closed').count()
    else:
        # For admin/supervisor, count all cases (excluding archived? we'll include all for stats)
        total_cases = Case.query.count()
        open_cases = Case.query.filter_by(status='open').count()
        closed_cases = Case.query.filter_by(status='closed').count()

    stats = {
        'total_cases': total_cases,
        'open_cases': open_cases,
        'closed_cases': closed_cases,
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
            results = Suspect.query.filter(
                db.or_(
                    Suspect.id_number.ilike(f'%{query}%'),
                    Suspect.first_name.ilike(f'%{query}%'),
                    Suspect.last_name.ilike(f'%{query}%')
                )
            ).all()
        elif search_type == 'case':
            results = Case.query.filter(
                db.or_(
                    Case.case_number.ilike(f'%{query}%'),
                    Case.title.ilike(f'%{query}%')
                )
            ).all()
            if current_user.role == 'officer':
                results = [case for case in results if case.assigned_officer_id == current_user.id]
    return render_template('search.html', form=form, results=results, search_type=form.search_type.data if form.is_submitted() else None)


# ---------- Notifications ----------
@main_bp.route('/notifications')
@login_required
def notifications():
    notifications = current_user.notifications.order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)


@main_bp.route('/notifications/mark-read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('main.notifications'))
    notif.mark_read()
    flash('Notification marked as read.', 'success')
    return redirect(url_for('main.notifications'))


@main_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    current_user.notifications.update({Notification.read: True})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('main.notifications'))


# ---------- API ----------
@main_bp.route('/api/suspects/check-duplicate', methods=['POST'])
@login_required
def check_duplicate_suspect():
    data = request.get_json()
    id_number = data.get('id_number')
    if not id_number:
        return jsonify({'error': 'ID number required'}), 400
    suspect = Suspect.query.filter_by(id_number=id_number).first()
    if suspect:
        return jsonify({'exists': True, 'suspect': suspect.to_dict()})
    return jsonify({'exists': False})