from extensions import db
from datetime import datetime

class Resume(db.Model):
    __tablename__ = 'resumes'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500))
    
    # Parsed Data
    candidate_name = db.Column(db.String(200))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    location = db.Column(db.String(100))
    parsed_data = db.Column(db.JSON)  # Full parsed resume data
    
    # AI Scoring
    ai_score = db.Column(db.Float, default=0.0)  # 0-100
    matched_skills = db.Column(db.JSON)  # Skills that match JD
    missing_skills = db.Column(db.JSON)  # Skills missing from JD
    experience_years = db.Column(db.Float)
    education_level = db.Column(db.String(100))
    ai_explanation = db.Column(db.Text)  # Why this score
    
    # Status
    status = db.Column(db.String(20), default='new')  # new, shortlisted, rejected
    processing_status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    processing_time_seconds = db.Column(db.Float, default=0.0)  # Time taken to process
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self, include_job=False):
        data = {
            'id': self.id,
            'job_id': self.job_id,
            'filename': self.filename,
            'candidate_name': self.candidate_name,
            'email': self.email,
            'phone': self.phone,
            'location': self.location,
            'ai_score': round(self.ai_score, 2) if self.ai_score else 0,
            'matched_skills': self.matched_skills or [],
            'missing_skills': self.missing_skills or [],
            'experience_years': self.experience_years,
            'education_level': self.education_level,
            'status': self.status,
            'processing_status': self.processing_status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_job and self.job:
            data['job_title'] = self.job.title
            data['job_department'] = self.job.department
            data['job_location'] = self.job.location
        
        return data
