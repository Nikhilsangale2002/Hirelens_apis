#!/usr/bin/env python3
"""Initialize database tables from SQLAlchemy models"""
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(__file__))

print("Initializing HireLens database...")
print("-" * 60)

try:
    # Import app
    from app import create_app
    from extensions import db
    
    # Import all models
    from models.user import User
    from models.job import Job
    from models.resume import Resume
    from models.interview import Interview
    from models.notification import Notification
    from models.audit_log import AuditLog
    from models.interview_security_log import InterviewSecurityLog
    
    print("✓ Models imported successfully")
    
    # Create app
    app = create_app()
    print("✓ Flask app created")
    
    # Create tables
    with app.app_context():
        print("\nCreating database tables...")
        db.create_all()
        print("✅ All tables created successfully!")
        
        # List created tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print(f"\nCreated {len(tables)} tables:")
        for table in sorted(tables):
            print(f"  ✓ {table}")
        
        # Test connection
        result = db.session.execute(db.text("SELECT VERSION()")).fetchone()
        print(f"\n✅ MySQL version: {result[0]}")
        
    print("\n" + "=" * 60)
    print("✅ DATABASE INITIALIZATION COMPLETE!")
    print("=" * 60)
    print("\nYour database is ready to use!")
    print("Start the backend with: python app.py")
    
except ImportError as e:
    print(f"\n❌ Import error: {e}")
    print("Make sure all dependencies are installed:")
    print("  pip install -r requirements.txt")
    sys.exit(1)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("-" * 60)
