from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, url_for
from flask_login import current_user
import os
from config import Config
from extensions import db, login_manager
from src.utils.timezone import get_current_time


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # ----- Context processor: current time (SAST) -----
    @app.context_processor
    def inject_now():
        now = get_current_time()
        return {'now': now, 'today': now.date()}

    # ----- Context processor: navbar badge counts -----
    @app.context_processor
    def inject_nav_counts():
        from src.models import Case, Station
        pending_count = 0
        unread_count = 0
        if current_user.is_authenticated:
            # Only Station Commanders and Admins see pending approvals
            if current_user.role in ['admin', 'supervisor']:
                query = Case.query.filter_by(status='pending_closure')
                if current_user.role == 'supervisor':
                    # Station Commander: only show cases from their station
                    station = Station.query.filter_by(supervisor_id=current_user.id).first()
                    if station:
                        query = query.filter_by(station_id=station.id)
                    else:
                        query = query.filter(False)
                pending_count = query.count()
            unread_count = current_user.unread_notification_count()
        return {
            'pending_count': pending_count,
            'unread_count': unread_count
        }

    # ----- Custom template filter for suspect photos -----
    @app.template_filter('suspect_photo')
    def suspect_photo_filter(photo_path):
        if not photo_path:
            return url_for('static', filename='img/default_suspect.jpg')
        if photo_path.startswith('http'):
            return photo_path
        filename = photo_path.split('/')[-1].split('\\')[-1]
        return url_for('static', filename=f'uploads/suspects/{filename}')

    # ----- Import and register blueprints -----
    from src.auth import auth_bp
    from src.routes import main_bp
    from src.cases import cases_bp
    from src.suspects import suspects_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(cases_bp)
    app.register_blueprint(suspects_bp)

    # ----- Error handlers -----
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # ----- Database initialization and seeding -----
    with app.app_context():
        try:
            os.makedirs(os.path.join(app.root_path, 'static', 'uploads', 'suspects'), exist_ok=True)
            os.makedirs(os.path.join(app.root_path, 'static', 'uploads', 'documents'), exist_ok=True)

            db.create_all()
            print("✅ Database tables verified/created")

            seed_database()
        except Exception as e:
            print(f"⚠️  Database initialization warning: {e}")

    return app


def seed_database():
    from src.models import Officer, Station
    from werkzeug.security import generate_password_hash

    try:
        # ---------- 1. Create Stations ----------
        station_data = [
            {'name': 'Johannesburg Central', 'commander_email': 'GambuN@saps.gov.za'},
            {'name': 'Pretoria', 'commander_email': 'NcaneC@saps.gov.za'},
            {'name': 'Durban', 'commander_email': 'ButheleziK@saps.gov.za'},
            {'name': 'Cape Town', 'commander_email': 'NdlanziT@saps.gov.za'},
            {'name': 'Bloemfontein', 'commander_email': 'KhumaloS@saps.gov.za'},
            {'name': 'Port Elizabeth', 'commander_email': 'SibiyaS@saps.gov.za'},
            {'name': 'East London', 'commander_email': 'NtshangaseT@saps.gov.za'},
            # ----- NEW STATIONS & COMMANDERS -----
            {'name': 'Polokwane', 'commander_email': 'TholeS@saps.gov.za'},
            {'name': 'Kimberley', 'commander_email': 'MbuthoS@saps.gov.za'},
            {'name': 'Nelspruit', 'commander_email': 'MalopeT@saps.gov.za'},
        ]

        station_objects = {}
        for station_info in station_data:
            station = Station.query.filter_by(name=station_info['name']).first()
            if not station:
                station = Station(name=station_info['name'])
                db.session.add(station)
                db.session.flush()
            station_objects[station_info['commander_email']] = station

        db.session.commit()
        print("✅ Stations created.")

        # ---------- 2. Create Station Commanders ----------
        commander_credentials = {
            'GambuN@saps.gov.za': ('Njabulo', 'Gambu', '22309145@dut'),
            'NcaneC@saps.gov.za': ('C', 'Ncane', '22139739@dut'),
            'ButheleziK@saps.gov.za': ('K', 'Buthelezi', '22309590@dut'),
            'NdlanziT@saps.gov.za': ('T', 'Ndlanzi', '22306484@dut'),
            'KhumaloS@saps.gov.za': ('S', 'Khumalo', '22233182@dut'),
            'SibiyaS@saps.gov.za': ('S', 'Sibiya', '21724659@dut'),
            'NtshangaseT@saps.gov.za': ('Thobani', 'Ntshangase', '22318985@dut'),
            # ----- NEW COMMANDERS -----
            'TholeS@saps.gov.za': ('Sphesihle', 'Thole', '22346497@dut'),
            'MbuthoS@saps.gov.za': ('Syabonga', 'Mbutho', '22055757@dut'),
            'MalopeT@saps.gov.za': ('Thembelihle', 'Malope', '22203220@dut'),
        }

        # Generate sequential 6-digit employee numbers
        # We need to know how many existing officers there are to continue the sequence
        existing_count = Officer.query.count()
        emp_counter = existing_count + 1  # start after existing

        for email, (first, last, password) in commander_credentials.items():
            officer = Officer.query.filter_by(email=email).first()
            station = station_objects.get(email)

            if not officer and station:
                employee_number = str(emp_counter).zfill(6)  # exactly 6 digits
                officer = Officer(
                    first_name=first,
                    last_name=last,
                    employee_number=employee_number,
                    email=email,
                    rank='Captain',
                    station_id=station.id,
                    role='supervisor',
                    is_active=True
                )
                officer.set_password(password)
                officer.generate_badge_number()
                db.session.add(officer)
                db.session.flush()

                station.supervisor_id = officer.id
                emp_counter += 1

        db.session.commit()
        print("✅ Station Commanders created and assigned to stations.")

        # ---------- 3. Create Admin ----------
        if not Officer.query.filter_by(email='admin@saps.gov.za').first():
            first_station = Station.query.first()
            if first_station:
                admin = Officer(
                    first_name="System",
                    last_name="Administrator",
                    employee_number="00000001",   # 6 digits
                    email="admin@saps.gov.za",
                    badge_number="SAPS-ADMIN-001",
                    rank="Commissioner",
                    station_id=first_station.id,
                    role="admin"
                )
                admin.set_password("Admin@123")
                db.session.add(admin)
                db.session.commit()
                print("✅ Admin user created.")

        print("✅ Stations and Station Commanders seeded successfully.")

    except Exception as e:
        db.session.rollback()
        print(f"ℹ️  Seeding skipped: {e}")


# Create app instance
app = create_app()


@login_manager.user_loader
def load_user(user_id):
    from src.models import Officer
    return Officer.query.get(int(user_id))


if __name__ == '__main__':
    app.run(debug=True, port=5000)