#!/usr/bin/env python3
"""Fix script for SAPS eDocket - Run this first"""
import os
import shutil
import sys

print("🚀 Starting SAPS eDocket Fix Script...")
print("=" * 50)

# Remove problematic directories
folders_to_remove = [
    'migrations',
    'static/face_encodings',
    '__pycache__',
    'src/__pycache__'
]

print("🗑️  Cleaning up old files...")
for folder in folders_to_remove:
    if os.path.exists(folder):
        try:
            shutil.rmtree(folder)
            print(f"   ✓ Removed: {folder}")
        except Exception as e:
            print(f"   ✗ Could not remove {folder}: {e}")

# Remove old database
if os.path.exists('saps.db'):
    os.remove('saps.db')
    print("   ✓ Removed: saps.db")

# Create necessary directories
folders_to_create = [
    'static/uploads/suspects',
    'static/uploads/documents',
    'templates/errors',
    'static/img'
]

print("\n📁 Creating necessary directories...")
for folder in folders_to_create:
    os.makedirs(folder, exist_ok=True)
    print(f"   ✓ Created: {folder}")

# Create default suspect image
default_img = 'static/img/default_suspect.jpg'
if not os.path.exists(default_img):
    # Create a simple placeholder
    with open(default_img, 'wb') as f:
        f.write(b'')  # Empty file - you should add a real image later
    print("   ✓ Created: default_suspect.jpg (placeholder)")

# Create error templates
error_templates = {
    '404.html': """
<!DOCTYPE html>
<html>
<head>
    <title>404 - Page Not Found</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
        h1 { color: #d9534f; }
    </style>
</head>
<body>
    <h1>404 - Page Not Found</h1>
    <p>The page you are looking for does not exist.</p>
    <a href="/">Go to Homepage</a>
</body>
</html>
    """,
    '403.html': """
<!DOCTYPE html>
<html>
<head>
    <title>403 - Access Denied</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
        h1 { color: #f0ad4e; }
    </style>
</head>
<body>
    <h1>403 - Access Denied</h1>
    <p>You don't have permission to access this page.</p>
    <a href="/">Go to Homepage</a>
</body>
</html>
    """,
    '500.html': """
<!DOCTYPE html>
<html>
<head>
    <title>500 - Server Error</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
        h1 { color: #5bc0de; }
    </style>
</head>
<body>
    <h1>500 - Server Error</h1>
    <p>Something went wrong on our end. Please try again later.</p>
    <a href="/">Go to Homepage</a>
</body>
</html>
    """
}

print("\n📝 Creating error templates...")
for filename, content in error_templates.items():
    filepath = f'templates/errors/{filename}'
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"   ✓ Created: {filename}")

# Install required packages
print("\n📦 Installing required packages...")
os.system(f'"{sys.executable}" -m pip install Flask==3.0.0 Flask-SQLAlchemy==3.1.1 Flask-Login==0.6.3 Flask-WTF==1.2.1 Pillow==10.1.0')

print("\n" + "=" * 50)
print("✅ Setup complete!")
print("\n📋 Next steps:")
print("   1. Run: python app.py")
print("   2. Open: http://localhost:5000")
print("\n🔐 Default login credentials:")
print("   👤 Admin: admin@saps.gov.za / Admin@123")
print("   👤 Supervisor: supervisor@saps.gov.za / Super@123")
print("\n⚠️  Remember to change passwords in production!")
print("=" * 50)