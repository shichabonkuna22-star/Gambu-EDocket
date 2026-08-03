from app import app
from extensions import db
from src.models import Suspect

with app.app_context():
    suspect = Suspect.query.first()  # or filter by ID
    if suspect:
        print(f"ID: {suspect.id}, Photo Path: '{suspect.photo_path}'")
    else:
        print("No suspects.")