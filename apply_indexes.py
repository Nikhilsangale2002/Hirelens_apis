"""
Apply performance indexes to database
"""
from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Applying performance indexes...")
    
    # Jobs table indexes
    try:
        db.session.execute(text("CREATE INDEX idx_user_status ON jobs(user_id, status)"))
        print("✓ Created idx_user_status on jobs")
    except Exception as e:
        print(f"  idx_user_status: {str(e)[:50]}...")
    
    try:
        db.session.execute(text("CREATE INDEX idx_status_created ON jobs(status, created_at)"))
        print("✓ Created idx_status_created on jobs")
    except Exception as e:
        print(f"  idx_status_created: {str(e)[:50]}...")
    
    try:
        db.session.execute(text("CREATE INDEX idx_location ON jobs(location)"))
        print("✓ Created idx_location on jobs")
    except Exception as e:
        print(f"  idx_location: {str(e)[:50]}...")
    
    try:
        db.session.execute(text("CREATE INDEX idx_job_type ON jobs(job_type)"))
        print("✓ Created idx_job_type on jobs")
    except Exception as e:
        print(f"  idx_job_type: {str(e)[:50]}...")
    
    # Resumes table indexes
    try:
        db.session.execute(text("CREATE INDEX idx_email ON resumes(email)"))
        print("✓ Created idx_email on resumes")
    except Exception as e:
        print(f"  idx_email: {str(e)[:50]}...")
    
    try:
        db.session.execute(text("CREATE INDEX idx_job_status ON resumes(job_id, status)"))
        print("✓ Created idx_job_status on resumes")
    except Exception as e:
        print(f"  idx_job_status: {str(e)[:50]}...")
    
    try:
        db.session.execute(text("CREATE INDEX idx_job_score ON resumes(job_id, ai_score)"))
        print("✓ Created idx_job_score on resumes")
    except Exception as e:
        print(f"  idx_job_score: {str(e)[:50]}...")
    
    try:
        db.session.execute(text("CREATE INDEX idx_processing ON resumes(processing_status)"))
        print("✓ Created idx_processing on resumes")
    except Exception as e:
        print(f"  idx_processing: {str(e)[:50]}...")
    
    # Interviews table indexes
    try:
        db.session.execute(text("CREATE INDEX idx_access_code ON interviews(access_code)"))
        print("✓ Created idx_access_code on interviews")
    except Exception as e:
        print(f"  idx_access_code: {str(e)[:50]}...")
    
    try:
        db.session.execute(text("CREATE INDEX idx_job_scheduled ON interviews(job_id, scheduled_date)"))
        print("✓ Created idx_job_scheduled on interviews")
    except Exception as e:
        print(f"  idx_job_scheduled: {str(e)[:50]}...")
    
    try:
        db.session.execute(text("CREATE INDEX idx_resume_date ON interviews(resume_id, scheduled_date)"))
        print("✓ Created idx_resume_date on interviews")
    except Exception as e:
        print(f"  idx_resume_date: {str(e)[:50]}...")
    
    try:
        db.session.execute(text("CREATE INDEX idx_status_date ON interviews(status, scheduled_date)"))
        print("✓ Created idx_status_date on interviews")
    except Exception as e:
        print(f"  idx_status_date: {str(e)[:50]}...")
    
    db.session.commit()
    print("\n✅ Index creation complete!")
