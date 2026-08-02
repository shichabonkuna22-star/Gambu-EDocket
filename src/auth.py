from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from src.models import Officer
from src.forms import RegistrationForm, LoginForm
from src.utils.timezone import get_current_time
import re

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        # Validate SAPS email domain
        if not form.email.data.endswith('@saps.gov.za'):
            flash('Only @saps.gov.za email addresses are allowed', 'danger')
            return render_template('auth/register.html', form=form)
        
        # Validate ID number (13 digits for South Africa)
        if not re.match(r'^\d{13}$', form.id_number.data):
            flash('ID number must be 13 digits', 'danger')
            return render_template('auth/register.html', form=form)
        
        # Check if email or ID already exists
        if Officer.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'danger')
            return render_template('auth/register.html', form=form)
        
        if Officer.query.filter_by(id_number=form.id_number.data).first():
            flash('ID number already registered', 'danger')
            return render_template('auth/register.html', form=form)
        
        # Create new officer
        officer = Officer(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            id_number=form.id_number.data,
            email=form.email.data,
            rank=form.rank.data,
            station=form.station.data,
            role='officer'  # Default role
        )
        
        # Generate badge number
        officer.generate_badge_number()
        
        # Set password
        officer.set_password(form.password.data)
        
        # Save to database
        db.session.add(officer)
        db.session.commit()
        
        flash('Registration successful! Please login with your credentials.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        officer = Officer.query.filter_by(email=form.email.data).first()
        
        if officer and officer.check_password(form.password.data):
            if not officer.is_active:
                flash('Account is deactivated. Please contact administrator.', 'warning')
                return redirect(url_for('auth.login'))
            
            login_user(officer, remember=form.remember.data)
            
            # Update last login – now in SAST
            officer.last_login = get_current_time()
            db.session.commit()
            
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page or url_for('main.dashboard'))
        
        flash('Invalid email or password', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))