from extensions import db
from datetime import datetime

class Job(db.Model):
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    department = db.Column(db.String(100))
    location = db.Column(db.String(100))
    job_type = db.Column(db.String(50))  # Full-time, Part-time, Contract
    experience_required = db.Column(db.String(50))
    skills_required = db.Column(db.JSON)  # List of required skills
    education = db.Column(db.String(100))
    salary_range = db.Column(db.String(100))
    status = db.Column(db.String(20), default='active')  # active, closed, draft
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    resumes = db.relationship('Resume', backref='job', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self, include_resumes=False):
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
        
        if include_resumes:
            data['resumes'] = [r.to_dict() for r in self.resumes.all()]
        
        return data
