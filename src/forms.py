from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, TextAreaField, SelectField, DateField, BooleanField, DateTimeField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
import re

class RegistrationForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=2, max=50)])
    id_number = StringField('ID Number', validators=[DataRequired(), Length(min=13, max=13)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    rank = SelectField('Rank', choices=[
        ('constable', 'Constable'),
        ('sergeant', 'Sergeant'),
        ('captain', 'Captain'),
        ('major', 'Major'),
        ('colonel', 'Colonel')
    ])
    station = StringField('Station', validators=[DataRequired()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8),
        EqualTo('confirm_password', message='Passwords must match')
    ])
    confirm_password = PasswordField('Confirm Password')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')

class CaseForm(FlaskForm):
    title = StringField('Case Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[DataRequired()])
    category = SelectField('Category', choices=[
        # Schedule 1
        ('theft', 'Theft'),
        ('burglary', 'Burglary'),
        ('vandalism', 'Vandalism'),
        ('vehicle_theft', 'Vehicle Theft'),
        ('fraud', 'Fraud'),
        ('corruption', 'Corruption'),
        # Schedule 2
        ('assault', 'Assault'),
        ('robbery', 'Robbery'),
        ('domestic_violence', 'Domestic Violence'),
        ('drugs', 'Drug Related'),
        ('cybercrime', 'Cybercrime'),
        ('arson', 'Arson'),
        # Schedule 3
        ('sexual_assault', 'Sexual Assault'),
        ('homicide', 'Homicide'),
        ('kidnapping', 'Kidnapping'),
        # Other
        ('other', 'Other')
    ])
    severity = SelectField('Severity', choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ])
    location = StringField('Location')
    # Use StringField to accept datetime-local input; we'll parse manually
    incident_date = StringField('Incident Date')

class SuspectForm(FlaskForm):
    id_number = StringField('ID Number', validators=[DataRequired(), Length(min=13, max=13)])
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    gender = SelectField('Gender', choices=[
        ('male', 'Male'),
        ('female', 'Female')
        # removed 'other'
    ])
    address = TextAreaField('Address')
    contact_number = StringField('Contact Number')
    photo = FileField('Suspect Photo', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')
    ])

class SearchForm(FlaskForm):
    search_type = SelectField('Search Type', choices=[
        ('suspect', 'Suspect'),
        ('case', 'Case')
    ])
    query = StringField('Search Query', validators=[DataRequired()])