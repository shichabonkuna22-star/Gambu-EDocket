#!/usr/bin/env python3
"""Initialize database tables on Render"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from src.models import Officer
from werkzeug.security import generate_password_hash

def init_db():
    app = create_app()
    with app.app_context():
        print("Creating tables...")
        db.create_all()
        
        # Seed admin if not exists
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
            db.session.commit()
            print("✅ Admin user created")
        
        print("✅ Database initialized!")

if __name__ == '__main__':
    init_db()