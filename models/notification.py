from extensions import db
from datetime import datetime

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Notification details
    type = db.Column(db.String(50), nullable=False)  # 'job_applied', 'interview_scheduled', 'status_changed', 'resume_uploaded'
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # Related entities
    related_type = db.Column(db.String(50))  # 'job', 'candidate', 'interview'
    related_id = db.Column(db.Integer)
    
    # Metadata
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    read_at = db.Column(db.DateTime)
    
    # Action URL
    action_url = db.Column(db.String(500))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'related_type': self.related_type,
            'related_id': self.related_id,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'action_url': self.action_url
        }
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.title}>'
