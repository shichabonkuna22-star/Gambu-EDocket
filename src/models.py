from extensions import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from src.utils.timezone import get_current_time

# ---------- Station ----------
class Station(db.Model):
    __tablename__ = 'stations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('officers.id'), nullable=True)

    supervisor = db.relationship('Officer', foreign_keys=[supervisor_id], backref='supervised_station')
    officers = db.relationship('Officer', foreign_keys='Officer.station_id', backref='station_ref')

    def __repr__(self):
        return f'<Station {self.name}>'


# ---------- Officer ----------
class Officer(UserMixin, db.Model):
    __tablename__ = 'officers'

    id = db.Column(db.Integer, primary_key=True)
    badge_number = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    employee_number = db.Column(db.String(6), unique=True, nullable=False)   # exactly 6 digits
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    rank = db.Column(db.String(50))
    station_id = db.Column(db.Integer, db.ForeignKey('stations.id'), nullable=False)
    role = db.Column(db.String(20), default='officer')  # officer, supervisor, admin
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    cases = db.relationship('Case', foreign_keys='Case.assigned_officer_id', backref='assigned_officer', lazy='dynamic')
    case_updates = db.relationship('CaseUpdate', backref='officer', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    evidence_uploads = db.relationship('CaseEvidence', backref='uploader', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_badge_number(self):
        year = datetime.now().year
        count = Officer.query.filter(
            db.extract('year', Officer.created_at) == year
        ).count() + 1
        self.badge_number = f"SAPS-{year}-{count:03d}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def has_role(self, role_name):
        return self.role == role_name

    def can_access_case(self, case):
        if self.role in ['admin', 'supervisor']:
            return True
        return case.assigned_officer_id == self.id

    def can_approve_closure(self, case):
        if self.role == 'admin':
            return True
        if self.role != 'supervisor':
            return False
        station = Station.query.get(case.station_id)
        return station and station.supervisor_id == self.id

    @property
    def station_name(self):
        return self.station_ref.name if self.station_ref else None

    @property
    def supervisor(self):
        """Return the station commander (supervisor) of this officer's station."""
        if self.station_ref:
            return self.station_ref.supervisor
        return None

    def unread_notification_count(self):
        return self.notifications.filter_by(read=False).count()


# ---------- Suspect ----------
class Suspect(db.Model):
    __tablename__ = 'suspects'

    id = db.Column(db.Integer, primary_key=True)
    id_number = db.Column(db.String(13), unique=True, nullable=False)  # keeps SA ID for suspects
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    address = db.Column(db.Text)
    contact_number = db.Column(db.String(20))
    photo_path = db.Column(db.String(300))
    fingerprint_path = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cases = db.relationship('Case', backref='suspect', lazy='dynamic')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def active_cases(self):
        return self.cases.filter_by(status='open').count()

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'id_number': self.id_number,
            'date_of_birth': str(self.date_of_birth) if self.date_of_birth else None,
            'active_cases': self.active_cases,
            'photo_path': self.photo_path,
            'fingerprint_path': self.fingerprint_path
        }


# ---------- Case ----------
class Case(db.Model):
    __tablename__ = 'cases'

    id = db.Column(db.Integer, primary_key=True)
    case_number = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    severity = db.Column(db.String(20), default='medium')
    status = db.Column(db.String(20), default='open')  # open, investigating, pending_closure, closed, archived
    location = db.Column(db.String(200))
    reported_date = db.Column(db.DateTime, default=datetime.utcnow)
    incident_date = db.Column(db.DateTime)
    assigned_officer_id = db.Column(db.Integer, db.ForeignKey('officers.id'), nullable=False)
    station_id = db.Column(db.Integer, db.ForeignKey('stations.id'), nullable=False)
    suspect_id = db.Column(db.Integer, db.ForeignKey('suspects.id'))
    is_confidential = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Closure workflow fields
    closure_requested_by_id = db.Column(db.Integer, db.ForeignKey('officers.id'), nullable=True)
    closure_requested_at = db.Column(db.DateTime, nullable=True)
    closure_approved_by_id = db.Column(db.Integer, db.ForeignKey('officers.id'), nullable=True)
    closure_approved_at = db.Column(db.DateTime, nullable=True)
    closure_rejection_reason = db.Column(db.Text, nullable=True)
    closure_rejected_at = db.Column(db.DateTime, nullable=True)

    station = db.relationship('Station', foreign_keys=[station_id], backref='cases')
    updates = db.relationship('CaseUpdate', backref='case', lazy='dynamic', order_by='desc(CaseUpdate.created_at)')
    documents = db.relationship('CaseDocument', backref='case', lazy='dynamic')
    evidence = db.relationship('CaseEvidence', backref='case', lazy='dynamic', order_by='CaseEvidence.uploaded_at')

    closure_requested_by = db.relationship('Officer', foreign_keys=[closure_requested_by_id])
    closure_approved_by = db.relationship('Officer', foreign_keys=[closure_approved_by_id])

    def generate_case_number(self):
        now = datetime.now()
        count = Case.query.filter(
            db.extract('year', Case.created_at) == now.year,
            db.extract('month', Case.created_at) == now.month
        ).count() + 1
        self.case_number = f"CAS-{now.year}-{now.month:02d}-{count:04d}"

    def can_be_modified_by(self, officer):
        if officer.role == 'admin':
            return True
        if self.status in ['closed', 'archived']:
            return False
        return officer.id == self.assigned_officer_id

    def can_request_closure(self, officer):
        if officer.role in ['admin', 'supervisor']:
            return True
        return officer.id == self.assigned_officer_id

    def can_approve_closure(self, officer):
        if officer.role == 'admin':
            return True
        if officer.role != 'supervisor':
            return False
        station = Station.query.get(self.station_id)
        return station and station.supervisor_id == officer.id

    @property
    def station_name(self):
        return Station.query.get(self.station_id).name if self.station_id else None


# ---------- Case Evidence ----------
class CaseEvidence(db.Model):
    __tablename__ = 'case_evidence'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    officer_id = db.Column(db.Integer, db.ForeignKey('officers.id'), nullable=False)
    file_url = db.Column(db.String(300), nullable=False)
    caption = db.Column(db.String(200))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_type = db.Column(db.String(20), default='image')


# ---------- Case Update ----------
class CaseUpdate(db.Model):
    __tablename__ = 'case_updates'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    officer_id = db.Column(db.Integer, db.ForeignKey('officers.id'), nullable=False)
    update_type = db.Column(db.String(50))
    previous_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'update_type': self.update_type,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'officer_name': self.officer.full_name if self.officer else None
        }


# ---------- Case Document ----------
class CaseDocument(db.Model):
    __tablename__ = 'case_documents'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    officer_id = db.Column(db.Integer, db.ForeignKey('officers.id'), nullable=False)
    document_type = db.Column(db.String(50))
    filename = db.Column(db.String(200))
    filepath = db.Column(db.String(300))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_confidential = db.Column(db.Boolean, default=False)

    def get_accessible_path(self, officer):
        if self.is_confidential and officer.role not in ['admin', 'supervisor']:
            if officer.id != self.officer_id:
                return None
        return self.filepath


# ---------- Notification ----------
class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('officers.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(300), nullable=True)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def mark_read(self):
        self.read = True
        db.session.commit()