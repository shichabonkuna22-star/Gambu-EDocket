from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from src.models import Officer, Station
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
        # Check if email or employee number already exists
        if Officer.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'danger')
            return render_template('auth/register.html', form=form)

        if Officer.query.filter_by(employee_number=form.employee_number.data).first():
            flash('Employee number already registered', 'danger')
            return render_template('auth/register.html', form=form)

        # Create officer
        officer = Officer(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            employee_number=form.employee_number.data,
            email=form.email.data,
            rank=form.rank.data,
            station_id=form.station.data,   # station_id from dropdown
            role='officer'
        )
        officer.generate_badge_number()
        officer.set_password(form.password.data)

        db.session.add(officer)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
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
                flash('Account deactivated. Contact admin.', 'warning')
                return redirect(url_for('auth.login'))

            login_user(officer, remember=form.remember.data)
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