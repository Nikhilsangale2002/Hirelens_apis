from extensions import db
from datetime import datetime

class Job(db.Model):
    __tablename__ = 'jobs'
    __table_args__ = (
        db.Index('idx_user_status', 'user_id', 'status'),  # Composite index for user's jobs by status
        db.Index('idx_status_created', 'status', 'created_at'),  # For public job listings
        db.Index('idx_location', 'location'),  # For location-based searches
        db.Index('idx_job_type', 'job_type'),  # For filtering by job type
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text)
    department = db.Column(db.String(100), index=True)
    location = db.Column(db.String(100))
    job_type = db.Column(db.String(50))  # Full-time, Part-time, Contract
    experience_required = db.Column(db.String(50))
    skills_required = db.Column(db.JSON)  # List of required skills
    education = db.Column(db.String(100))
    salary_range = db.Column(db.String(100))
    status = db.Column(db.String(20), default='active')  # active, closed, draft
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    resumes = db.relationship('Resume', backref='job', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self, include_resumes=False, include_counts=True):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'department': self.department,
            'location': self.location,
            'job_type': self.job_type,
            'experience_required': self.experience_required,
            'skills_required': self.skills_required or [],
            'education': self.education,
            'salary_range': self.salary_range,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        
        # Add candidate counts only if requested and session is available
        if include_counts:
            try:
                from models.resume import Resume
                all_candidates = Resume.query.filter_by(job_id=self.id).all()
                data['candidates_count'] = len(all_candidates)
                data['shortlisted_count'] = len([c for c in all_candidates if c.status == 'shortlisted'])
                data['rejected_count'] = len([c for c in all_candidates if c.status == 'rejected'])
            except Exception:
                # If query fails (e.g., no session), set default counts
                data['candidates_count'] = 0
                data['shortlisted_count'] = 0
                data['rejected_count'] = 0
        
        if include_resumes:
            from models.resume import Resume
            all_candidates = Resume.query.filter_by(job_id=self.id).all()
            data['resumes'] = [r.to_dict() for r in all_candidates]
        
        return data
