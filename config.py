import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://') or 'sqlite:///saps.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File upload settings – local fallback (not used if Cloudinary is set)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    UPLOAD_FOLDER = 'static/uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    
    # Email domain validation
    SAPS_EMAIL_DOMAIN = '@saps.gov.za'
    
    # Security
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # ---------- CLOUDINARY CONFIG ----------
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')
    # Optional: upload preset for signed uploads (if you want to use unsigned uploads from client-side)
    # For server-side upload, we'll just use the API key/secret directly.

    @staticmethod
    def init_app(app):
        # Create local directories for any fallback (won't be used if Cloudinary is configured)
        for folder in ['static/uploads/suspects', 'static/uploads/documents']:
            os.makedirs(folder, exist_ok=True)