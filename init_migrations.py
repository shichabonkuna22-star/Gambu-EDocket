#!/usr/bin/env python3
"""Initialize Flask-Migrate properly"""
import sys
import os
from flask_migrate import Migrate

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

# Initialize migrate
migrate = Migrate(app, db)

if __name__ == '__main__':
    with app.app_context():
        # Initialize migrations if they don't exist
        migrations_dir = 'migrations'
        if not os.path.exists(migrations_dir):
            print("📁 Creating migrations directory...")
            os.system('flask db init')
            print("✅ Migrations initialized")
        
        # Create initial migration
        print("📝 Creating initial migration...")
        os.system('flask db migrate -m "Initial migration after face recognition removal"')
        
        print("🔄 Applying migration...")
        os.system('flask db upgrade')
        
        print("\n✅ Database migrations set up successfully!")
        print("📊 Database structure is now up to date with the models")