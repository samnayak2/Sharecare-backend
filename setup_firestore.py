"""
Setup script for Firestore collections and indexes
Run this script once to set up the database structure
"""

from google.cloud import firestore
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_firestore():
    """Initialize Firestore collections and indexes"""
    try:
        db = firestore.Client()
        logger.info("Connected to Firestore")
        
        collections_to_create = [
            "users",
            "user_preferences",
            "donations",
            "reservations",
            "messages",
            "notifications"
        ]
        
        for collection_name in collections_to_create:
            temp_doc_ref = db.collection(collection_name).document("temp_init")
            temp_doc_ref.set({"initialized": True, "temp": True})
            
            temp_doc_ref.delete()
            
            logger.info(f"Collection '{collection_name}' initialized")
        
        logger.info("Firestore setup completed successfully")
        
        print("\n=== Firestore Collection Structure ===")
        print("users/")
        print("  - uid (string)")
        print("  - email (string)")
        print("  - full_name (string)")
        print("  - phone_number (string, optional)")
        print("  - address (string, optional)")
        print("  - photo_url (string, optional)")
        print("  - bio (string, optional)")
        print("  - email_verified (boolean)")
        print("  - created_at (timestamp)")
        print("  - updated_at (timestamp)")
        print()
        print("user_preferences/")
        print("  - uid (string)")
        print("  - theme (string: 'light' | 'dark')")
        print("  - language (string: 'en' | 'ga' | 'hi' | 'te')")
        print("  - notifications (map)")
        print("    - email (boolean)")
        print("    - push (boolean)")
        print("    - donations (boolean)")
        print("    - reservations (boolean)")
        print("    - messages (boolean)")
        print("  - created_at (timestamp)")
        print("  - updated_at (timestamp)")
        print()
        print("Future collections:")
        print("- donations/ (for donation items)")
        print("- reservations/ (for item reservations)")
        print("- messages/ (for user communications)")
        print("- notifications/ (for push notifications)")
        
    except Exception as e:
        logger.error(f"Error setting up Firestore: {e}")
        raise

if __name__ == "__main__":
    setup_firestore()
