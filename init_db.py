#!/usr/bin/env python3
"""Initialize the database and seed initial data"""
import os
import sys

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, seed_database

def init_database():
    """Initialize the database"""
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✅ Database tables created.")
        
        # Seed initial data
        seed_database()
        print("✅ Database seeded with admin and supervisor accounts.")
        
        print("\n✅ Initial accounts created:")
        print("   👤 Admin: admin@saps.gov.za / Admin@123")
        print("   👤 Supervisor: supervisor@saps.gov.za / Super@123")
        print("\n⚠️  CHANGE THESE PASSWORDS IN PRODUCTION!")

if __name__ == '__main__':
    init_database()