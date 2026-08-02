import face_recognition
import cv2
import numpy as np
import os
import pickle
from PIL import Image
import io

class FaceRecognitionSystem:
    def __init__(self, encodings_path='static/face_encodings'):
        self.encodings_path = encodings_path
        os.makedirs(encodings_path, exist_ok=True)
    
    def detect_and_encode(self, image_data):
        """
        Detect face in image and return encoding
        Args:
            image_data: Bytes or file path
        Returns:
            encoding (list) or None if no face detected
        """
        try:
            # Load image
            if isinstance(image_data, bytes):
                image = face_recognition.load_image_file(io.BytesIO(image_data))
            else:
                image = face_recognition.load_image_file(image_data)
            
            # Find all face locations
            face_locations = face_recognition.face_locations(image)
            
            if not face_locations:
                return None
            
            # Get encoding for the first face found
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if face_encodings:
                return face_encodings[0].tolist()
            
            return None
            
        except Exception as e:
            print(f"Face detection error: {e}")
            return None
    
    def save_encoding(self, suspect_id, encoding):
        """Save face encoding to file"""
        encoding_path = os.path.join(self.encodings_path, f"{suspect_id}.pkl")
        with open(encoding_path, 'wb') as f:
            pickle.dump(encoding, f)
        return encoding_path
    
    def load_encoding(self, suspect_id):
        """Load face encoding from file"""
        encoding_path = os.path.join(self.encodings_path, f"{suspect_id}.pkl")
        if os.path.exists(encoding_path):
            with open(encoding_path, 'rb') as f:
                return pickle.load(f)
        return None
    
    def find_similar_faces(self, new_encoding, threshold=0.6):
        """
        Find similar faces in database
        Returns list of suspect IDs with similarity score
        """
        similar = []
        
        # Load all encodings
        for filename in os.listdir(self.encodings_path):
            if filename.endswith('.pkl'):
                suspect_id = int(filename.split('.')[0])
                stored_encoding = self.load_encoding(suspect_id)
                
                if stored_encoding:
                    # Calculate face distance
                    distance = face_recognition.face_distance([stored_encoding], new_encoding)[0]
                    similarity = 1 - distance  # Convert to similarity score
                    
                    if similarity > threshold:
                        similar.append({
                            'suspect_id': suspect_id,
                            'similarity': similarity
                        })
        
        # Sort by similarity
        similar.sort(key=lambda x: x['similarity'], reverse=True)
        return similar
    
    def verify_face(self, suspect_id, image_data):
        """Verify if face matches stored encoding"""
        stored_encoding = self.load_encoding(suspect_id)
        if not stored_encoding:
            return False
        
        new_encoding = self.detect_and_encode(image_data)
        if not new_encoding:
            return False
        
        # Compare faces
        results = face_recognition.compare_faces([stored_encoding], new_encoding)
        return results[0] if results else False

face_system = FaceRecognitionSystem()