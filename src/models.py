from extensions import db  # <-- changed
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Officer(UserMixin, db.Model):
    __tablename__ = 'officers'
    
    id = db.Column(db.Integer, primary_key=True)
    badge_number = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    id_number = db.Column(db.String(13), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    rank = db.Column(db.String(50))
    station = db.Column(db.String(100))
    role = db.Column(db.String(20), default='officer')  # officer, supervisor, admin
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    cases = db.relationship('Case', backref='assigned_officer', lazy='dynamic')
    case_updates = db.relationship('CaseUpdate', backref='officer', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_badge_number(self):
        """Generate unique badge number: SAPS-YYYY-XXX"""
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
        """Check if officer can access this case"""
        if self.role in ['admin', 'supervisor']:
            return True
        return case.assigned_officer_id == self.id

class Suspect(db.Model):
    __tablename__ = 'suspects'
    
    id = db.Column(db.Integer, primary_key=True)
    id_number = db.Column(db.String(13), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    address = db.Column(db.Text)
    contact_number = db.Column(db.String(20))
    photo_path = db.Column(db.String(200))  # Just photo path, no face encoding
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
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
            'photo_path': self.photo_path
        }

class Case(db.Model):
    __tablename__ = 'cases'
    
    id = db.Column(db.Integer, primary_key=True)
    case_number = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))  # Theft, Assault, etc.
    severity = db.Column(db.String(20), default='medium')  # low, medium, high
    status = db.Column(db.String(20), default='open')  # open, investigating, in_court, closed, archived
    location = db.Column(db.String(200))
    reported_date = db.Column(db.DateTime, default=datetime.utcnow)
    incident_date = db.Column(db.DateTime)
    assigned_officer_id = db.Column(db.Integer, db.ForeignKey('officers.id'), nullable=False)
    suspect_id = db.Column(db.Integer, db.ForeignKey('suspects.id'))
    is_confidential = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    updates = db.relationship('CaseUpdate', backref='case', lazy='dynamic', order_by='desc(CaseUpdate.created_at)')
    documents = db.relationship('CaseDocument', backref='case', lazy='dynamic')
    
    def generate_case_number(self):
        """Generate unique case number: CAS-YYYY-MM-XXXX"""
        now = datetime.now()
        count = Case.query.filter(
            db.extract('year', Case.created_at) == now.year,
            db.extract('month', Case.created_at) == now.month
        ).count() + 1
        self.case_number = f"CAS-{now.year}-{now.month:02d}-{count:04d}"
    
    def can_be_modified_by(self, officer):
        """Check if officer can modify this case"""
        if officer.role == 'admin':
            return True
        if self.status in ['closed', 'archived']:
            return False
        return officer.id == self.assigned_officer_id

class CaseUpdate(db.Model):
    __tablename__ = 'case_updates'
    
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    officer_id = db.Column(db.Integer, db.ForeignKey('officers.id'), nullable=False)
    update_type = db.Column(db.String(50))  # status_change, note, evidence_added, etc.
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

class CaseDocument(db.Model):
    __tablename__ = 'case_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    officer_id = db.Column(db.Integer, db.ForeignKey('officers.id'), nullable=False)
    document_type = db.Column(db.String(50))  # statement, evidence, warrant, etc.
    filename = db.Column(db.String(200))
    filepath = db.Column(db.String(300))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_confidential = db.Column(db.Boolean, default=False)
    
    def get_accessible_path(self, officer):
        """Return file path only if officer has access"""
        if self.is_confidential and officer.role not in ['admin', 'supervisor']:
            if officer.id != self.officer_id:
                return None
        return self.filepath