from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from extensions import db
from src.models import Case, Suspect, CaseUpdate, Officer, CaseEvidence, Notification, Station
from src.forms import CaseForm, SuspectForm, ClosureRequestForm, ApprovalForm
from src.utils.timezone import get_current_time
from datetime import datetime
import re
import cloudinary
import cloudinary.uploader
import concurrent.futures

cases_bp = Blueprint('cases', __name__)

# ---------- Allowed file extensions ----------
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------- Helper: parse DOB from ID ----------
def parse_dob_from_id(id_number):
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

# ---------- Configure Cloudinary ----------
def init_cloudinary():
    cloud_name = current_app.config.get('CLOUDINARY_CLOUD_NAME')
    api_key = current_app.config.get('CLOUDINARY_API_KEY')
    api_secret = current_app.config.get('CLOUDINARY_API_SECRET')
    if cloud_name and api_key and api_secret:
        cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret)
        return True
    return False

# ---------- Parallel upload helper ----------
def upload_file(file_obj, folder, public_id=None, resource_type='auto', overwrite=False):
    """
    Upload a single file to Cloudinary.
    Returns the secure URL or raises an exception.
    """
    if not file_obj or file_obj.filename == '':
        return None
    options = {
        'folder': folder,
        'resource_type': resource_type,
        'overwrite': overwrite,
    }
    if public_id:
        options['public_id'] = public_id
    result = cloudinary.uploader.upload(file_obj, **options)
    return result.get('secure_url')


# ---------- List cases ----------
@cases_bp.route('/cases')
@login_required
def view_cases():
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


# ---------- Create case ----------
@cases_bp.route('/cases/create', methods=['GET', 'POST'])
@login_required
def create_case():
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
        # Extract fields
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

        if not case_form.validate_on_submit():
            flash('Please correct the errors in the case form.', 'danger')
            return render_template('cases/create.html', case_form=case_form, suspect_form=suspect_form,
                                   prefill_suspect=prefill_suspect, suspect_id=suspect_id, now=now)

        # ---------- Handle suspect ----------
        suspect = None
        if use_existing_suspect_id and use_existing_suspect_id.isdigit():
            suspect = Suspect.query.get(int(use_existing_suspect_id))
            if not suspect:
                flash('Specified suspect not found.', 'danger')
                return redirect(url_for('cases.create_case'))
            # ---- Existing suspect path – create case without new uploads ----
            case = Case(
                title=case_form.title.data,
                description=case_form.description.data,
                category=category,
                severity=case_form.severity.data,
                location=case_form.location.data,
                incident_date=incident_date,
                assigned_officer_id=current_user.id,
                station_id=current_user.station_id,
                suspect_id=suspect.id
            )
            case.generate_case_number()
            db.session.add(case)
            db.session.flush()

            update = CaseUpdate(
                case_id=case.id,
                officer_id=current_user.id,
                update_type='case_created',
                notes=f'Case created by {current_user.full_name} (existing suspect)'
            )
            db.session.add(update)
            db.session.commit()

            flash(f'Case {case.case_number} created successfully.', 'success')
            return redirect(url_for('cases.view_case', case_id=case.id))

        else:
            # ---- New suspect ----
            existing_suspect = Suspect.query.filter_by(id_number=id_number).first()
            if existing_suspect:
                flash(f'A suspect with ID number {id_number} already exists. Please use the "Use Existing Suspect" option.', 'danger')
                return redirect(url_for('cases.create_case'))

            if not suspect_form.validate():
                for field, errors in suspect_form.errors.items():
                    for error in errors:
                        flash(f'{field}: {error}', 'danger')
                return render_template('cases/create.html', case_form=case_form, suspect_form=suspect_form,
                                       prefill_suspect=prefill_suspect, suspect_id=suspect_id, now=now)

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
                photo_path=None,
                fingerprint_path=None
            )
            db.session.add(suspect)
            db.session.flush()

            # Create case (needed for evidence folder)
            case = Case(
                title=case_form.title.data,
                description=case_form.description.data,
                category=category,
                severity=case_form.severity.data,
                location=case_form.location.data,
                incident_date=incident_date,
                assigned_officer_id=current_user.id,
                station_id=current_user.station_id,
                suspect_id=suspect.id
            )
            case.generate_case_number()
            db.session.add(case)
            db.session.flush()

            # ---------- Prepare parallel upload tasks ----------
            upload_tasks = []

            # Suspect photo
            if 'photo' in request.files:
                photo = request.files['photo']
                if photo.filename != '':
                    if not allowed_file(photo.filename):
                        flash('Photo must be a PNG, JPG, JPEG, or GIF file.', 'danger')
                        return redirect(url_for('cases.create_case'))
                    upload_tasks.append({
                        'file': photo,
                        'folder': 'saps/suspects',
                        'public_id': f"suspect_{suspect.id}",
                        'resource_type': 'image',
                        'overwrite': True,
                        'key': 'photo'
                    })

            # Fingerprint PDF
            fingerprint_file = request.files.get('fingerprint')
            if fingerprint_file and fingerprint_file.filename != '':
                if not fingerprint_file.filename.lower().endswith('.pdf'):
                    flash('Fingerprint file must be a PDF.', 'danger')
                    return redirect(url_for('cases.create_case'))
                upload_tasks.append({
                    'file': fingerprint_file,
                    'folder': 'saps/suspects/fingerprints',
                    'public_id': f"suspect_{suspect.id}_fingerprint",
                    'resource_type': 'raw',
                    'overwrite': True,
                    'key': 'fingerprint'
                })

            # Evidence files
            evidence_files = request.files.getlist('evidence_files')
            for file in evidence_files:
                if file and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    resource_type = 'image' if ext in ['png', 'jpg', 'jpeg', 'gif'] else 'raw'
                    upload_tasks.append({
                        'file': file,
                        'folder': f"saps/evidence/case_{case.id}",
                        'public_id': None,
                        'resource_type': resource_type,
                        'overwrite': False,
                        'key': 'evidence',
                        'filename': file.filename
                    })
                elif file.filename != '':
                    flash(f'File {file.filename} type not allowed. Skipped.', 'warning')

            # ---------- Execute uploads in parallel ----------
            results = {}
            errors = []

            if upload_tasks:
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_index = {
                        executor.submit(
                            upload_file,
                            task['file'],
                            task['folder'],
                            task['public_id'],
                            task['resource_type'],
                            task.get('overwrite', False)
                        ): idx for idx, task in enumerate(upload_tasks)
                    }

                    for future in concurrent.futures.as_completed(future_to_index):
                        idx = future_to_index[future]
                        try:
                            url = future.result()
                            results[idx] = url
                        except Exception as e:
                            errors.append(f"Upload error for {upload_tasks[idx].get('filename', 'file')}: {str(e)}")
                            results[idx] = None

            if errors:
                flash(errors[0], 'danger')
                db.session.rollback()
                return redirect(url_for('cases.create_case'))

            # Assign results
            for idx, task in enumerate(upload_tasks):
                url = results.get(idx)
                if url is None:
                    continue
                if task['key'] == 'photo':
                    suspect.photo_path = url
                elif task['key'] == 'fingerprint':
                    suspect.fingerprint_path = url
                elif task['key'] == 'evidence':
                    evidence = CaseEvidence(
                        case_id=case.id,
                        officer_id=current_user.id,
                        file_url=url,
                        caption='',
                        file_type=task['resource_type']
                    )
                    db.session.add(evidence)

            # Log updates
            update = CaseUpdate(
                case_id=case.id,
                officer_id=current_user.id,
                update_type='case_created',
                notes=f'Case created by {current_user.full_name}'
            )
            db.session.add(update)

            evidence_count = sum(1 for idx, task in enumerate(upload_tasks) if task['key'] == 'evidence' and results.get(idx))
            if evidence_count:
                evidence_update = CaseUpdate(
                    case_id=case.id,
                    officer_id=current_user.id,
                    update_type='evidence_added',
                    notes=f'{evidence_count} evidence file(s) uploaded during case creation'
                )
                db.session.add(evidence_update)

            db.session.commit()
            flash(f'Case {case.case_number} created successfully with {evidence_count} evidence file(s).', 'success')
            return redirect(url_for('cases.view_case', case_id=case.id))

    # GET request – show the form
    return render_template('cases/create.html', case_form=case_form, suspect_form=suspect_form,
                           prefill_suspect=prefill_suspect, suspect_id=suspect_id, now=now)


# ---------- View single case ----------
@cases_bp.route('/cases/<int:case_id>')
@login_required
def view_case(case_id):
    case = Case.query.get_or_404(case_id)
    if not current_user.can_access_case(case):
        flash('You do not have permission to view this case.', 'danger')
        return redirect(url_for('main.dashboard'))

    closure_form = ClosureRequestForm()
    approval_form = ApprovalForm()

    can_request = case.can_request_closure(current_user) and case.status not in ['closed', 'archived', 'pending_closure']
    can_approve = case.can_approve_closure(current_user) and case.status == 'pending_closure'

    return render_template('cases/view.html', case=case, closure_form=closure_form,
                           approval_form=approval_form, can_request=can_request, can_approve=can_approve)


# ---------- Update case status (general) ----------
@cases_bp.route('/cases/<int:case_id>/update-status', methods=['POST'])
@login_required
def update_case_status(case_id):
    case = Case.query.get_or_404(case_id)

    if not case.can_be_modified_by(current_user):
        flash('You do not have permission to update this case.', 'danger')
        return redirect(url_for('cases.view_case', case_id=case_id))

    new_status = request.form.get('status')
    notes = request.form.get('notes', '')

    allowed_statuses = ['open', 'investigating', 'in_court']
    if new_status and new_status in allowed_statuses:
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
    else:
        flash('Invalid status or closure must be requested through the closure workflow.', 'danger')

    return redirect(url_for('cases.view_case', case_id=case_id))


# ---------- Request Closure ----------
@cases_bp.route('/cases/<int:case_id>/request-closure', methods=['POST'])
@login_required
def request_closure(case_id):
    case = Case.query.get_or_404(case_id)

    if not case.can_request_closure(current_user):
        flash('You are not authorized to request closure for this case.', 'danger')
        return redirect(url_for('cases.view_case', case_id=case.id))

    if case.status in ['closed', 'archived', 'pending_closure']:
        flash('This case cannot be closed.', 'warning')
        return redirect(url_for('cases.view_case', case_id=case.id))

    notes = request.form.get('notes', '')

    case.status = 'pending_closure'
    case.closure_requested_by_id = current_user.id
    case.closure_requested_at = get_current_time()
    case.updated_at = get_current_time()

    update = CaseUpdate(
        case_id=case.id,
        officer_id=current_user.id,
        update_type='closure_requested',
        previous_status=case.status,
        new_status='pending_closure',
        notes=notes
    )
    db.session.add(update)

    station = Station.query.get(case.station_id)
    commander = Officer.query.get(station.supervisor_id) if station else None

    if commander:
        notif = Notification(
            user_id=commander.id,
            message=f'Closure requested for case {case.case_number} by {current_user.full_name}',
            link=url_for('cases.view_case', case_id=case.id),
            read=False
        )
        db.session.add(notif)

    admins = Officer.query.filter_by(role='admin').all()
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            message=f'Closure requested for case {case.case_number} by {current_user.full_name}',
            link=url_for('cases.view_case', case_id=case.id),
            read=False
        )
        db.session.add(notif)

    db.session.commit()
    flash('Closure request submitted for station commander approval.', 'success')
    return redirect(url_for('cases.view_case', case_id=case.id))


# ---------- Approve Closure ----------
@cases_bp.route('/cases/<int:case_id>/approve-closure', methods=['POST'])
@login_required
def approve_closure(case_id):
    case = Case.query.get_or_404(case_id)

    if not case.can_approve_closure(current_user):
        flash('You are not authorized to approve closure for this case.', 'danger')
        return redirect(url_for('cases.view_case', case_id=case.id))

    if case.status != 'pending_closure':
        flash('This case is not pending closure.', 'warning')
        return redirect(url_for('cases.view_case', case_id=case.id))

    form = ApprovalForm()
    if form.validate_on_submit():
        if form.action.data == 'approve':
            case.status = 'closed'
            case.closure_approved_by_id = current_user.id
            case.closure_approved_at = get_current_time()
            case.updated_at = get_current_time()

            update = CaseUpdate(
                case_id=case.id,
                officer_id=current_user.id,
                update_type='closure_approved',
                previous_status='pending_closure',
                new_status='closed',
                notes=form.reason.data or 'Approved by station commander'
            )
            db.session.add(update)

            officer = Officer.query.get(case.assigned_officer_id)
            if officer:
                notif = Notification(
                    user_id=officer.id,
                    message=f'Case {case.case_number} has been closed by {current_user.full_name}',
                    link=url_for('cases.view_case', case_id=case.id),
                    read=False
                )
                db.session.add(notif)

            db.session.commit()
            flash('Case has been closed successfully.', 'success')

        elif form.action.data == 'reject':
            if not form.reason.data:
                flash('Please provide a reason for rejection.', 'danger')
                return redirect(url_for('cases.view_case', case_id=case.id))

            case.status = 'investigating'
            case.closure_rejection_reason = form.reason.data
            case.closure_rejected_at = get_current_time()
            case.updated_at = get_current_time()

            update = CaseUpdate(
                case_id=case.id,
                officer_id=current_user.id,
                update_type='closure_rejected',
                previous_status='pending_closure',
                new_status='investigating',
                notes=f'Rejected: {form.reason.data}'
            )
            db.session.add(update)

            officer = Officer.query.get(case.assigned_officer_id)
            if officer:
                notif = Notification(
                    user_id=officer.id,
                    message=f'Closure request for case {case.case_number} was rejected by {current_user.full_name}. Reason: {form.reason.data}',
                    link=url_for('cases.view_case', case_id=case.id),
                    read=False
                )
                db.session.add(notif)

            db.session.commit()
            flash('Closure request rejected.', 'warning')

        return redirect(url_for('cases.view_case', case_id=case.id))

    flash('Invalid form submission.', 'danger')
    return redirect(url_for('cases.view_case', case_id=case.id))


# ---------- Pending Approvals ----------
@cases_bp.route('/cases/pending-approvals')
@login_required
def pending_approvals():
    if current_user.role not in ['admin', 'supervisor']:
        flash('You do not have permission to view pending approvals.', 'danger')
        return redirect(url_for('main.dashboard'))

    query = Case.query.filter_by(status='pending_closure')

    if current_user.role == 'supervisor':
        station = Station.query.filter_by(supervisor_id=current_user.id).first()
        if station:
            query = query.filter_by(station_id=station.id)
        else:
            query = query.filter(False)

    cases = query.order_by(Case.closure_requested_at.desc()).all()
    return render_template('cases/pending_approvals.html', cases=cases)


# ---------- Upload Evidence (for existing cases) ----------
@cases_bp.route('/cases/<int:case_id>/evidence', methods=['POST'])
@login_required
def upload_evidence(case_id):
    case = Case.query.get_or_404(case_id)

    if not current_user.can_access_case(case):
        flash('You do not have permission to add evidence to this case.', 'danger')
        return redirect(url_for('cases.view_case', case_id=case.id))

    if case.status in ['closed', 'archived']:
        flash('Cannot add evidence to a closed/archived case.', 'warning')
        return redirect(url_for('cases.view_case', case_id=case.id))

    init_cloudinary()

    files = request.files.getlist('evidence_files')
    if not files or files[0].filename == '':
        flash('No files selected.', 'warning')
        return redirect(url_for('cases.view_case', case_id=case.id))

    upload_tasks = []
    for file in files:
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            resource_type = 'image' if ext in ['png', 'jpg', 'jpeg', 'gif'] else 'raw'
            upload_tasks.append({
                'file': file,
                'folder': f"saps/evidence/case_{case.id}",
                'public_id': None,
                'resource_type': resource_type,
                'overwrite': False,
                'filename': file.filename
            })
        elif file.filename != '':
            flash(f'File {file.filename} type not allowed.', 'danger')

    if not upload_tasks:
        flash('No valid files to upload.', 'warning')
        return redirect(url_for('cases.view_case', case_id=case.id))

    uploaded_count = 0
    errors = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_task = {executor.submit(upload_file, t['file'], t['folder'], t['public_id'], t['resource_type'], t.get('overwrite', False)): t for t in upload_tasks}
        for future in concurrent.futures.as_completed(future_to_task):
            task = future_to_task[future]
            try:
                url = future.result()
                if url:
                    evidence = CaseEvidence(
                        case_id=case.id,
                        officer_id=current_user.id,
                        file_url=url,
                        caption=request.form.get('caption', ''),
                        file_type=task['resource_type']
                    )
                    db.session.add(evidence)
                    uploaded_count += 1
            except Exception as e:
                errors.append(f"Upload error for {task.get('filename', 'file')}: {str(e)}")

    if errors:
        flash('Some files failed to upload: ' + '; '.join(errors[:3]), 'danger')

    if uploaded_count:
        update = CaseUpdate(
            case_id=case.id,
            officer_id=current_user.id,
            update_type='evidence_added',
            notes=f'{uploaded_count} evidence file(s) uploaded by {current_user.full_name}'
        )
        db.session.add(update)
        db.session.commit()
        flash(f'{uploaded_count} evidence file(s) uploaded successfully.', 'success')
    else:
        flash('No files were uploaded successfully.', 'warning')

    return redirect(url_for('cases.view_case', case_id=case.id))


# ---------- API endpoints ----------
@cases_bp.route('/api/check-suspect', methods=['POST'])
@login_required
def check_suspect():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        id_number = data.get('id_number')
        if not id_number:
            return jsonify({'error': 'ID number is required'}), 400
        suspect = Suspect.query.filter_by(id_number=id_number.strip()).first()
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
                    'fingerprint_path': suspect.fingerprint_path,
                    'active_cases': suspect.active_cases
                }
            })
        return jsonify({'exists': False})
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500


@cases_bp.route('/api/get-suspect/<int:suspect_id>', methods=['GET'])
@login_required
def get_suspect(suspect_id):
    try:
        suspect = Suspect.query.get_or_404(suspect_id)
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
                'fingerprint_path': suspect.fingerprint_path,
                'active_cases': suspect.active_cases
            }
        })
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500
    
    
# ==================== ADD THIS BLOCK AT THE END OF YOUR EXISTING cases.py ====================
# ---------- NEW: Offline Sync API Endpoints ----------
@cases_bp.route('/api/cases', methods=['POST'])
@login_required
def api_create_case():
    """
    JSON endpoint for offline sync to create a case.
    Expects JSON payload with all case & suspect data.
    Returns the real case number and ID.
    """
    init_cloudinary()
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    # --- Extract fields (same as create_case) ---
    id_number = data.get('id_number', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    category = data.get('category', '')
    severity = data.get('severity', 'medium')
    location = data.get('location', '')
    gender = data.get('gender', '')
    address = data.get('address', '')
    contact_number = data.get('contact_number', '').strip()
    incident_date_str = data.get('incident_date', '').strip()
    # photo and fingerprint will be uploaded separately via /api/upload later

    # --- Validations ---
    if not id_number or not re.match(r'^\d{13}$', id_number):
        return jsonify({'success': False, 'error': 'Invalid ID number'}), 400
    if contact_number and not re.match(r'^\d{10}$', contact_number):
        return jsonify({'success': False, 'error': 'Contact number must be 10 digits'}), 400

    incident_date = None
    if incident_date_str:
        try:
            incident_date = datetime.fromisoformat(incident_date_str)
        except:
            return jsonify({'success': False, 'error': 'Invalid incident date format'}), 400
        if incident_date > get_current_time():
            return jsonify({'success': False, 'error': 'Incident date cannot be in future'}), 400

    if gender not in ['male', 'female']:
        return jsonify({'success': False, 'error': 'Gender must be male/female'}), 400

    # --- Handle Suspect (create or reuse) ---
    suspect = Suspect.query.filter_by(id_number=id_number).first()
    if not suspect:
        # Parse DOB from ID if not provided
        dob = data.get('date_of_birth')
        if dob:
            try:
                dob = datetime.strptime(dob, '%Y-%m-%d').date()
            except:
                dob = parse_dob_from_id(id_number)
        else:
            dob = parse_dob_from_id(id_number)

        suspect = Suspect(
            id_number=id_number,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            gender=gender,
            address=address,
            contact_number=contact_number,
            photo_path=None,
            fingerprint_path=None
        )
        db.session.add(suspect)
        db.session.flush()

    # --- Create Case ---
    case = Case(
        title=title,
        description=description,
        category=category,
        severity=severity,
        location=location,
        incident_date=incident_date,
        assigned_officer_id=current_user.id,
        station_id=current_user.station_id,
        suspect_id=suspect.id
    )
    case.generate_case_number()
    db.session.add(case)
    db.session.flush()

    # Log update
    update = CaseUpdate(
        case_id=case.id,
        officer_id=current_user.id,
        update_type='case_created',
        notes=f'Case created via offline sync by {current_user.full_name}'
    )
    db.session.add(update)
    db.session.commit()

    return jsonify({
        'success': True,
        'case_id': case.id,
        'case_number': case.case_number,
        'suspect_id': suspect.id
    })


@cases_bp.route('/api/upload', methods=['POST'])
@login_required
def api_upload_file():
    """
    Upload a file (photo, fingerprint, evidence) to Cloudinary.
    Expects form-data with 'file', 'type' (photo/fingerprint/evidence), and optional 'case_id' and 'suspect_id'.
    Returns the secure URL.
    """
    init_cloudinary()
    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file_type = request.form.get('type', 'evidence')
    case_id = request.form.get('case_id')
    suspect_id = request.form.get('suspect_id')

    # Determine folder and resource type
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    resource_type = 'image' if ext in ['png', 'jpg', 'jpeg', 'gif'] else 'raw'

    if file_type == 'photo':
        folder = 'saps/suspects'
        public_id = f"suspect_{suspect_id}" if suspect_id else None
        overwrite = True
    elif file_type == 'fingerprint':
        folder = 'saps/suspects/fingerprints'
        public_id = f"suspect_{suspect_id}_fingerprint" if suspect_id else None
        overwrite = True
    else:  # evidence
        folder = f"saps/evidence/case_{case_id}" if case_id else 'saps/evidence'
        public_id = None
        overwrite = False

    try:
        url = upload_file(file, folder, public_id, resource_type, overwrite)
        if url:
            # If evidence, we might want to create CaseEvidence record here
            if file_type == 'evidence' and case_id:
                evidence = CaseEvidence(
                    case_id=int(case_id),
                    officer_id=current_user.id,
                    file_url=url,
                    caption=request.form.get('caption', ''),
                    file_type=resource_type
                )
                db.session.add(evidence)
                db.session.commit()
            return jsonify({'success': True, 'url': url})
        else:
            return jsonify({'success': False, 'error': 'Upload failed'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@cases_bp.route('/api/sync', methods=['POST'])
@login_required
def api_sync():
    """
    Bulk sync endpoint.
    Expects a JSON array of operations: { 'method': 'POST', 'endpoint': '/api/cases', 'payload': {...} }
    Processes each and returns results.
    """
    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({'success': False, 'error': 'Expected array of operations'}), 400

    results = []
    for op in data:
        method = op.get('method', 'POST')
        endpoint = op.get('endpoint')
        payload = op.get('payload', {})
        if endpoint == '/api/cases':
            # Forward to our create endpoint
            with current_app.test_request_context(json=payload):
                resp = api_create_case()
                results.append({
                    'endpoint': endpoint,
                    'status': resp.status_code,
                    'data': resp.get_json() if resp.is_json else None
                })
        else:
            results.append({'endpoint': endpoint, 'error': 'Unknown endpoint'})
    return jsonify({'results': results})