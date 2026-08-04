from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, TextAreaField, SelectField, DateField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, ValidationError, Regexp
from src.models import Station
import re

class RegistrationForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=2, max=50)])
    employee_number = StringField('Employee Number', validators=[
        DataRequired(),
        Length(min=6, max=6),   # exactly 6 digits
        Regexp(r'^\d{6}$', message='Employee number must be exactly 6 digits (0-9).')
    ])
    email = StringField('Email', validators=[DataRequired(), Email()])
    rank = SelectField('Rank', choices=[
        ('constable', 'Constable'),
        ('sergeant', 'Sergeant'),
        ('captain', 'Captain'),
        ('major', 'Major'),
        ('colonel', 'Colonel')
    ])
    station = SelectField('Station', coerce=int, validators=[DataRequired()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8),
        EqualTo('confirm_password', message='Passwords must match')
    ])
    confirm_password = PasswordField('Confirm Password')

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        self.station.choices = [(s.id, s.name) for s in Station.query.order_by(Station.name).all()]

    def validate_email(self, field):
        if not field.data.endswith('@saps.gov.za'):
            raise ValidationError('Only @saps.gov.za email addresses are allowed.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')


class CaseForm(FlaskForm):
    title = StringField('Case Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('theft', 'Theft'),
        ('burglary', 'Burglary'),
        ('vandalism', 'Vandalism'),
        ('vehicle_theft', 'Vehicle Theft'),
        ('fraud', 'Fraud'),
        ('corruption', 'Corruption'),
        ('assault', 'Assault'),
        ('robbery', 'Robbery'),
        ('domestic_violence', 'Domestic Violence'),
        ('drugs', 'Drug Related'),
        ('cybercrime', 'Cybercrime'),
        ('arson', 'Arson'),
        ('sexual_assault', 'Sexual Assault'),
        ('homicide', 'Homicide'),
        ('kidnapping', 'Kidnapping'),
        ('other', 'Other')
    ])
    severity = SelectField('Severity', choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ])
    location = StringField('Location')
    incident_date = StringField('Incident Date')


class SuspectForm(FlaskForm):
    id_number = StringField('ID Number', validators=[DataRequired(), Length(min=13, max=13)])
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female')])
    address = TextAreaField('Address')
    contact_number = StringField('Contact Number')
    photo = FileField('Suspect Photo', validators=[FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')])
    fingerprint = FileField('Fingerprint PDF', validators=[FileAllowed(['pdf'], 'PDF only!')])

    def validate_id_number(self, field):
        if not re.match(r'^\d{13}$', field.data):
            raise ValidationError('ID number must be exactly 13 digits.')


class SearchForm(FlaskForm):
    search_type = SelectField('Search Type', choices=[
        ('suspect', 'Suspect'),
        ('case', 'Case')
    ])
    query = StringField('Search Query', validators=[DataRequired()])


class ClosureRequestForm(FlaskForm):
    notes = TextAreaField('Closure Notes', validators=[Optional()])


class ApprovalForm(FlaskForm):
    action = SelectField('Action', choices=[('approve', 'Approve'), ('reject', 'Reject')], validators=[DataRequired()])
    reason = TextAreaField('Reason', validators=[Optional()])