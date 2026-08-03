from dotenv import load_dotenv
load_dotenv()  # Load .env file BEFORE creating app

from flask import Flask, render_template, url_for   # <-- added url_for
import os
from config import Config
from extensions import db, login_manager
from src.utils.timezone import get_current_time

def create_app():
    app = Flask(__name__)
    
    # Load configuration from Config class (handles DATABASE_URL for Render)
    app.config.from_object(Config)
    
    # Ensure upload folders are properly set for Render's ephemeral storage
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'
    
    # Add context processor for global template variables – now in SAST
    @app.context_processor
    def inject_now():
        now = get_current_time()
        return {
            'now': now,
            'today': now.date()
        }
    
    # Add custom template filter for suspect photos
    @app.template_filter('suspect_photo')
    def suspect_photo_filter(photo_path):
        # Debug: print what we get
        print(f"🔍 suspect_photo filter called with: {photo_path}")
        if not photo_path:
            return url_for('static', filename='img/default_suspect.jpg')
        # If it's a full URL (Cloudinary), return it directly
        if photo_path.startswith('http'):
            return photo_path
        # Otherwise, treat as local path
        filename = photo_path.split('/')[-1].split('\\')[-1]
        return url_for('static', filename=f'uploads/suspects/{filename}')
    
    # Import and register blueprints
    from src.auth import auth_bp
    from src.routes import main_bp
    from src.cases import cases_bp
    from src.suspects import suspects_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(cases_bp)
    app.register_blueprint(suspects_bp)
    
    # Error handlers
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
    
    # Auto-initialize database on startup (Free Tier Compatible)
    with app.app_context():
        try:
            # Create upload directories
            os.makedirs(os.path.join(app.root_path, 'static', 'uploads', 'suspects'), exist_ok=True)
            os.makedirs(os.path.join(app.root_path, 'static', 'uploads', 'documents'), exist_ok=True)
            
            # Create all tables (idempotent - safe to run multiple times)
            db.create_all()
            print("✅ Database tables verified/created")
            
            # Seed initial data
            seed_database()
            
        except Exception as e:
            print(f"⚠️  Database initialization warning (may already exist): {e}")
    
    return app

def seed_database():
    """Seed the database with initial admin and supervisor accounts"""
    from src.models import Officer
    from werkzeug.security import generate_password_hash
    
    try:
        # Check if admin already exists
        if not Officer.query.filter_by(email='admin@saps.gov.za').first():
            admin = Officer(
                first_name="System",
                last_name="Administrator",
                id_number="0000000000001",
                email="admin@saps.gov.za",
                badge_number="SAPS-ADMIN-001",
                rank="Commissioner",
                station="Headquarters",
                role="admin"
            )
            admin.password_hash = generate_password_hash("Admin@123")
            db.session.add(admin)
            print("✅ Admin user created")
        
        # Check if supervisor already exists
        if not Officer.query.filter_by(email='supervisor@saps.gov.za').first():
            supervisor = Officer(
                first_name="Station",
                last_name="Supervisor",
                id_number="0000000000002",
                email="supervisor@saps.gov.za",
                badge_number="SAPS-SUP-001",
                rank="Captain",
                station="Central Station",
                role="supervisor"
            )
            supervisor.password_hash = generate_password_hash("Super@123")
            db.session.add(supervisor)
            print("✅ Supervisor user created")
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"ℹ️  Seeding skipped: {e}")

# Create the Flask application instance
app = create_app()

@login_manager.user_loader
def load_user(user_id):
    from src.models import Officer
    return Officer.query.get(int(user_id))

if __name__ == '__main__':
    app.run(debug=True, port=5000)