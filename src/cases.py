from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from src.models import Case, Suspect, CaseUpdate, Officer
from src.forms import CaseForm, SuspectForm
from src.utils.timezone import get_current_time
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import re
import cloudinary
import cloudinary.uploader
from flask import current_app

cases_bp = Blueprint('cases', __name__)

# ---------- Allowed file extensions for photos ----------
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------- Helper: parse DOB from ID ----------
def parse_dob_from_id(id_number):
    """Extract date of birth from first 6 digits of ID number (YYMMDD)."""
    if not id_number or len(id_number) < 6:
        return None
    try:
        yy = int(id_number[0:2])
        mm = int(id_number[2:4])
        dd = int(id_number[4:6])
        current_yy = get_current_time().year % 100
        year = 1900 + yy if yy > current_yy else 2000 + yy
        return datetime(year, mm, dd).date()
    except ValueError:
        return None

# ---------- Configure Cloudinary (once) ----------
def init_cloudinary():
    cloud_name = current_app.config.get('CLOUDINARY_CLOUD_NAME')
    api_key = current_app.config.get('CLOUDINARY_API_KEY')
    api_secret = current_app.config.get('CLOUDINARY_API_SECRET')
    if cloud_name and api_key and api_secret:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret
        )
        return True
    return False

@cases_bp.route('/cases')
@login_required
def view_cases():
    """View all cases based on role, with filters and search"""
    page = request.args.get('page', 1, type=int)

    query = Case.query.filter(Case.status != 'archived')

    if current_user.role not in ['admin', 'supervisor']:
        query = query.filter_by(assigned_officer_id=current_user.id)

    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)

    severity = request.args.get('severity')
    if severity:
        query = query.filter_by(severity=severity)

    category = request.args.get('category')
    if category:
        query = query.filter_by(category=category)

    search = request.args.get('search', '').strip()
    if search:
        search_term = f"%{search}%"
        query = query.join(Suspect, isouter=True).filter(
            db.or_(
                Case.case_number.ilike(search_term),
                Case.title.ilike(search_term),
                Suspect.first_name.ilike(search_term),
                Suspect.last_name.ilike(search_term),
                Suspect.id_number.ilike(search_term)
            )
        )

    query = query.order_by(Case.created_at.desc())
    cases = query.paginate(page=page, per_page=10, error_out=False)

    base_query = Case.query.filter(Case.status != 'archived')
    if current_user.role not in ['admin', 'supervisor']:
        base_query = base_query.filter_by(assigned_officer_id=current_user.id)

    stats = {
        'total': base_query.count(),
        'open': base_query.filter_by(status='open').count(),
        'investigating': base_query.filter_by(status='investigating').count(),
        'high_priority': base_query.filter_by(severity='high').count(),
    }

    return render_template('cases/index.html', cases=cases, stats=stats)


@cases_bp.route('/cases/create', methods=['GET', 'POST'])
@login_required
def create_case():
    """Create a new case - with suspect autofill from profile"""
    # Initialize Cloudinary (do it once per request or globally)
    init_cloudinary()

    case_form = CaseForm()
    suspect_form = SuspectForm()

    prefill_suspect = None
    suspect_id = request.args.get('suspect_id', type=int)

    if suspect_id:
        prefill_suspect = Suspect.query.get(suspect_id)
        if prefill_suspect:
            suspect_form.id_number.data = prefill_suspect.id_number
            suspect_form.first_name.data = prefill_suspect.first_name
            suspect_form.last_name.data = prefill_suspect.last_name
            suspect_form.date_of_birth.data = prefill_suspect.date_of_birth
            suspect_form.gender.data = prefill_suspect.gender
            suspect_form.address.data = prefill_suspect.address
            suspect_form.contact_number.data = prefill_suspect.contact_number

    now = get_current_time()

    if request.method == 'POST':
        # ---------- 1. Extract and validate common fields ----------
        use_existing_suspect_id = request.form.get('use_existing_suspect', '').strip()

        id_number = request.form.get('id_number', '').strip()
        if not id_number or not re.match(r'^\d{13}$', id_number):
            flash('ID number must be exactly 13 digits.', 'danger')
            return redirect(url_for('cases.create_case'))

        contact_number = request.form.get('contact_number', '').strip()
        if contact_number and not re.match(r'^\d{10}$', contact_number):
            flash('Contact number must be exactly 10 digits (if provided).', 'danger')
            return redirect(url_for('cases.create_case'))

        incident_date_str = request.form.get('incident_date', '').strip()
        incident_date = None
        if incident_date_str:
            try:
                incident_date = datetime.strptime(incident_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                try:
                    incident_date = datetime.strptime(incident_date_str, '%Y-%m-%d')
                except ValueError:
                    flash('Invalid incident date format. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM.', 'danger')
                    return redirect(url_for('cases.create_case'))
            if incident_date > get_current_time():
                flash('Incident date cannot be in the future.', 'danger')
                return redirect(url_for('cases.create_case'))

        gender = request.form.get('gender', '')
        if gender not in ['male', 'female']:
            flash('Gender must be either Male or Female.', 'danger')
            return redirect(url_for('cases.create_case'))

        category = request.form.get('category', '')
        allowed_categories = [choice[0] for choice in case_form.category.choices]
        if category not in allowed_categories:
            flash('Invalid category selected.', 'danger')
            return redirect(url_for('cases.create_case'))

        # ---------- 2. Validate the main case form ----------
        if not case_form.validate_on_submit():
            flash('Please correct the errors in the case form.', 'danger')
            return render_template('cases/create.html',
                                   case_form=case_form,
                                   suspect_form=suspect_form,
                                   prefill_suspect=prefill_suspect,
                                   suspect_id=suspect_id,
                                   now=now)

        # ---------- 3. Handle suspect ----------
        suspect = None

        if use_existing_suspect_id and use_existing_suspect_id.isdigit():
            suspect = Suspect.query.get(int(use_existing_suspect_id))
            if not suspect:
                flash('Specified suspect not found.', 'danger')
                return redirect(url_for('cases.create_case'))
        else:
            existing_suspect = Suspect.query.filter_by(id_number=id_number).first()
            if existing_suspect:
                flash(f'A suspect with ID number {id_number} already exists. Please use the "Use Existing Suspect" option.', 'danger')
                return redirect(url_for('cases.create_case'))

            if not suspect_form.validate():
                for field, errors in suspect_form.errors.items():
                    for error in errors:
                        flash(f'{field}: {error}', 'danger')
                return render_template('cases/create.html',
                                       case_form=case_form,
                                       suspect_form=suspect_form,
                                       prefill_suspect=prefill_suspect,
                                       suspect_id=suspect_id,
                                       now=now)

            # Create new suspect
            dob = None
            if suspect_form.date_of_birth.data:
                try:
                    if isinstance(suspect_form.date_of_birth.data, str):
                        dob = datetime.strptime(suspect_form.date_of_birth.data, '%Y-%m-%d').date()
                    else:
                        dob = suspect_form.date_of_birth.data
                except:
                    dob = None
            if not dob:
                dob = parse_dob_from_id(id_number)

            suspect = Suspect(
                id_number=id_number,
                first_name=suspect_form.first_name.data,
                last_name=suspect_form.last_name.data,
                date_of_birth=dob,
                gender=gender,
                address=suspect_form.address.data,
                contact_number=contact_number,
                photo_path=None  # will be set after upload
            )
            db.session.add(suspect)
            db.session.flush()

        # ---------- 4. Handle photo upload (only for new suspect) ----------
        if not use_existing_suspect_id and 'photo' in request.files:
            photo = request.files['photo']
            if photo.filename != '':
                if not allowed_file(photo.filename):
                    flash('Photo must be a PNG, JPG, JPEG, or GIF file.', 'danger')
                    return redirect(url_for('cases.create_case'))

                # Upload to Cloudinary
                try:
                    upload_result = cloudinary.uploader.upload(
                        photo,
                        folder="saps/suspects",        # optional folder in Cloudinary
                        public_id=f"suspect_{suspect.id}",
                        overwrite=True,
                        resource_type="image"
                    )
                    # Get the secure URL
                    photo_url = upload_result.get('secure_url')
                    if photo_url:
                        suspect.photo_path = photo_url
                    else:
                        flash('Failed to upload photo to Cloudinary.', 'danger')
                        return redirect(url_for('cases.create_case'))
                except Exception as e:
                    flash(f'Cloudinary upload error: {str(e)}', 'danger')
                    return redirect(url_for('cases.create_case'))

        # ---------- 5. Create the case ----------
        case = Case(
            title=case_form.title.data,
            description=case_form.description.data,
            category=category,
            severity=case_form.severity.data,
            location=case_form.location.data,
            incident_date=incident_date,
            assigned_officer_id=current_user.id,
            suspect_id=suspect.id
        )
        case.generate_case_number()

        db.session.add(case)
        db.session.flush()

        update = CaseUpdate(
            case_id=case.id,
            officer_id=current_user.id,
            update_type='case_created',
            notes=f'Case created by {current_user.full_name}'
        )
        db.session.add(update)

        db.session.commit()

        flash(f'Case {case.case_number} created successfully!', 'success')
        return redirect(url_for('cases.view_case', case_id=case.id))

    return render_template('cases/create.html',
                           case_form=case_form,
                           suspect_form=suspect_form,
                           prefill_suspect=prefill_suspect,
                           suspect_id=suspect_id,
                           now=now)


@cases_bp.route('/cases/<int:case_id>')
@login_required
def view_case(case_id):
    """View a specific case"""
    case = Case.query.get_or_404(case_id)

    if not current_user.can_access_case(case):
        flash('You do not have permission to view this case.', 'danger')
        return redirect(url_for('main.dashboard'))

    return render_template('cases/view.html', case=case)


@cases_bp.route('/cases/<int:case_id>/update-status', methods=['POST'])
@login_required
def update_case_status(case_id):
    """Update case status"""
    case = Case.query.get_or_404(case_id)

    if not case.can_be_modified_by(current_user):
        flash('You do not have permission to update this case.', 'danger')
        return redirect(url_for('cases.view_case', case_id=case_id))

    new_status = request.form.get('status')
    notes = request.form.get('notes', '')

    if new_status and new_status in ['open', 'investigating', 'in_court', 'closed', 'archived']:
        update = CaseUpdate(
            case_id=case.id,
            officer_id=current_user.id,
            update_type='status_change',
            previous_status=case.status,
            new_status=new_status,
            notes=notes
        )

        case.status = new_status
        case.updated_at = get_current_time()

        db.session.add(update)
        db.session.commit()

        flash(f'Case status updated to {new_status}.', 'success')

    return redirect(url_for('cases.view_case', case_id=case_id))


@cases_bp.route('/api/check-suspect', methods=['POST'])
@login_required
def check_suspect():
    """Check if suspect already exists by ID number and return full details"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        id_number = data.get('id_number')
        if not id_number:
            return jsonify({'error': 'ID number is required'}), 400

        id_number = id_number.strip()
        suspect = Suspect.query.filter_by(id_number=id_number).first()

        if suspect:
            return jsonify({
                'exists': True,
                'suspect': {
                    'id': suspect.id,
                    'full_name': suspect.full_name,
                    'first_name': suspect.first_name,
                    'last_name': suspect.last_name,
                    'id_number': suspect.id_number,
                    'date_of_birth': suspect.date_of_birth.strftime('%Y-%m-%d') if suspect.date_of_birth else None,
                    'gender': suspect.gender,
                    'address': suspect.address,
                    'contact_number': suspect.contact_number,
                    'photo_path': suspect.photo_path,
                    'active_cases': suspect.active_cases
                }
            })

        return jsonify({'exists': False})

    except Exception as e:
        print(f"Error checking suspect: {str(e)}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500


@cases_bp.route('/api/get-suspect/<int:suspect_id>', methods=['GET'])
@login_required
def get_suspect(suspect_id):
    """Get suspect details by ID"""
    try:
        suspect = Suspect.query.get(suspect_id)
        if not suspect:
            return jsonify({'error': 'Suspect not found'}), 404

        return jsonify({
            'success': True,
            'suspect': {
                'id': suspect.id,
                'full_name': suspect.full_name,
                'first_name': suspect.first_name,
                'last_name': suspect.last_name,
                'id_number': suspect.id_number,
                'date_of_birth': suspect.date_of_birth.strftime('%Y-%m-%d') if suspect.date_of_birth else None,
                'gender': suspect.gender,
                'address': suspect.address,
                'contact_number': suspect.contact_number,
                'photo_path': suspect.photo_path,
                'active_cases': suspect.active_cases
            }
        })

    except Exception as e:
        print(f"Error getting suspect: {str(e)}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500