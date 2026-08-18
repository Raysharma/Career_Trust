"""
MongoDB database helper logic. Connects to the database and provides functions
to save scans and fetch history, with a graceful fallback if connection fails.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Fix Windows console encoding if needed
if sys.stdout and getattr(sys.stdout, 'encoding', None) and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Load env variables from the project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(project_root, '.env'))

MONGO_URI = os.getenv("MONGO_URI")

client = None
db = None
scans_col = None
db_active = False

if MONGO_URI:
    try:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
        import urllib.parse
        import re

        # Clean brackets and url-encode username/password to avoid RFC 3986 escape errors
        match = re.match(r'(mongodb(?:\+srv)?://)([^:]+):([^@]+)@(.+)', MONGO_URI)
        if match:
            prefix, user, password, rest = match.groups()
            if user.startswith('<') and user.endswith('>'):
                user = user[1:-1]
            if password.startswith('<') and password.endswith('>'):
                password = password[1:-1]
            
            user_quoted = urllib.parse.quote_plus(user)
            password_quoted = urllib.parse.quote_plus(password)
            MONGO_URI = f"{prefix}{user_quoted}:{password_quoted}@{rest}"

        print(f"Connecting to MongoDB...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        
        # Access database and collection
        db = client.get_database("careertrust")
        scans_col = db.get_collection("scans")
        
        # Test connection
        client.admin.command('ping')
        db_active = True
        print("✅ MongoDB connection established successfully!")
    except Exception as e:
        print(f"⚠️ MongoDB connection failed: {e}")
        print("   Running in Database-Disabled Mode. Scans will not be logged.")
        db_active = False
else:
    print("⚠️ MONGO_URI not found in environment variables.")
    print("   Running in Database-Disabled Mode. Scans will not be logged.")

def is_db_active():
    """Returns True if MongoDB connection is active, False otherwise."""
    return db_active

def save_scan(scan_input, scan_result):
    """
    Saves a scan's input and result output to MongoDB scans collection.
    Fails gracefully if the database is offline.
    """
    if not db_active or scans_col is None:
        return False
        
    try:
        # Build the document
        document = {
            "timestamp": datetime.utcnow(),
            "input": {
                "text": scan_input.get("text", "")[:1000],  # truncate text to save space
                "company_url": scan_input.get("company_url", ""),
                "company_domain": scan_input.get("company_domain", ""),
                "url": scan_input.get("url", "")
            },
            "results": {
                "hybrid_trust_score": scan_result.get("hybrid_trust_score", 0),
                "risk_level": scan_result.get("risk_level", "UNKNOWN"),
                "bert_fraud_probability": scan_result.get("bert_fraud_probability", 0),
                "_bert_trust": scan_result.get("_bert_trust", 0),
                "_text_trust": scan_result.get("_text_trust", 0),
                "_domain_trust": scan_result.get("_domain_trust", 0),
                "_contact_trust": scan_result.get("_contact_trust", 0),
                "explanation": scan_result.get("explanation", [])
            }
        }
        scans_col.insert_one(document)
        return True
    except Exception as e:
        print(f"⚠️ Failed to save scan to MongoDB: {e}")
        return False

def get_recent_scans(limit=10):
    """
    Fetches the most recent N scans from MongoDB.
    Fails gracefully if the database is offline.
    """
    if not db_active or scans_col is None:
        return []
        
    try:
        limit = max(1, min(int(limit), 100))
        projection = {
            "timestamp": 1,
            "input.text": 1,
            "input.company_url": 1,
            "input.company_domain": 1,
            "input.url": 1,
            "results": 1,
        }
        cursor = scans_col.find({}, projection).sort("timestamp", -1).limit(limit)
        results = []
        for doc in cursor:
            # Map MongoDB ObjectId to string for JSON serialization
            doc["_id"] = str(doc["_id"])
            # Format datetime as ISO string
            if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
                doc["timestamp"] = doc["timestamp"].isoformat()
            results.append(doc)
        return results
    except Exception as e:
        print(f"⚠️ Failed to fetch scans from MongoDB: {e}")
        return []
