"""
Mock Face Recognition System for Development/Portfolio
Simulates face recognition without requiring dlib/face-recognition dependencies
"""
import os
import json
import random
import hashlib
from datetime import datetime

class MockFaceRecognitionSystem:
    def __init__(self, encodings_path='static/face_encodings'):
        self.encodings_path = encodings_path
        os.makedirs(encodings_path, exist_ok=True)
        self.mock_database = {}  # In-memory storage for demo
    
    def detect_and_encode(self, image_data):
        """
        Mock face detection - simulates finding a face and creating an encoding
        Returns a fake 128-dim encoding based on image hash
        """
        try:
            # Generate a consistent "encoding" based on file content/hash
            if isinstance(image_data, str) and os.path.exists(image_data):
                with open(image_data, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
            else:
                file_hash = hashlib.md5(str(image_data).encode()).hexdigest()
            
            # Create a deterministic 128-dim vector from the hash
            random.seed(file_hash)
            encoding = [random.gauss(0, 1) for _ in range(128)]
            random.seed()  # Reset seed
            
            return encoding
            
        except Exception as e:
            print(f"Mock face detection error: {e}")
            return None
    
    def save_encoding(self, suspect_id, encoding):
        """Save encoding to JSON file"""
        encoding_path = os.path.join(self.encodings_path, f"{suspect_id}.json")
        with open(encoding_path, 'w') as f:
            json.dump(encoding, f)
        return encoding_path
    
    def load_encoding(self, suspect_id):
        """Load encoding from file"""
        encoding_path = os.path.join(self.encodings_path, f"{suspect_id}.json")
        if os.path.exists(encoding_path):
            with open(encoding_path, 'r') as f:
                return json.load(f)
        return None
    
    def find_similar_faces(self, new_encoding, threshold=0.6):
        """
        Find similar faces by comparing encodings
        Returns list of suspect IDs with similarity scores
        """
        similar = []
        
        for filename in os.listdir(self.encodings_path):
            if filename.endswith('.json'):
                suspect_id = int(filename.split('.')[0])
                stored_encoding = self.load_encoding(suspect_id)
                
                if stored_encoding:
                    # Calculate cosine similarity
                    similarity = self._calculate_similarity(stored_encoding, new_encoding)
                    
                    if similarity > threshold:
                        similar.append({
                            'suspect_id': suspect_id,
                            'similarity': similarity
                        })
        
        # Sort by similarity (highest first)
        similar.sort(key=lambda x: x['similarity'], reverse=True)
        return similar
    
    def _calculate_similarity(self, encoding1, encoding2):
        """Calculate cosine similarity between two encodings"""
        dot_product = sum(a * b for a, b in zip(encoding1, encoding2))
        magnitude1 = sum(a * a for a in encoding1) ** 0.5
        magnitude2 = sum(a * a for a in encoding2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def verify_face(self, suspect_id, image_data):
        """Verify if face matches stored encoding"""
        stored_encoding = self.load_encoding(suspect_id)
        if not stored_encoding:
            return False
        
        new_encoding = self.detect_and_encode(image_data)
        if not new_encoding:
            return False
        
        similarity = self._calculate_similarity(stored_encoding, new_encoding)
        return similarity > 0.6  # 60% threshold

# Singleton instance
face_system = MockFaceRecognitionSystem()