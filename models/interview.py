from extensions import db
from datetime import datetime

class Interview(db.Model):
    __tablename__ = 'interviews'
    __table_args__ = (
        db.Index('idx_job_scheduled', 'job_id', 'scheduled_date'),  # For job interview schedule
        db.Index('idx_resume_date', 'resume_id', 'scheduled_date'),  # For candidate interviews
        db.Index('idx_status_date', 'status', 'scheduled_date'),  # For filtering by status
        db.Index('idx_access_code', 'access_code'),  # For quick access code lookup
    )
    
    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey('resumes.id'), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, index=True)
    interview_type = db.Column(db.String(50), nullable=False, default='screening')  # screening, technical, hr, final
    scheduled_date = db.Column(db.DateTime, nullable=False, index=True)
    duration_minutes = db.Column(db.Integer, default=60)
    interview_mode = db.Column(db.String(50), default='video')  # video, phone, in-person, ai
    meeting_link = db.Column(db.String(500))
    location = db.Column(db.String(255))
    interviewer_name = db.Column(db.String(200))
    interviewer_email = db.Column(db.String(200))
    status = db.Column(db.String(50), default='scheduled', index=True)  # scheduled, completed, cancelled, no-show
    notes = db.Column(db.Text)
    feedback = db.Column(db.Text)
    ai_questions = db.Column(db.Text)  # For AI interviews (stored as JSON string)
    ai_responses = db.Column(db.Text)  # For AI interviews (stored as JSON string)
    ai_score = db.Column(db.Float)
    ai_feedback = db.Column(db.Text)
    ai_analysis = db.Column(db.Text)  # Complete AI analysis (stored as JSON string)
    video_responses = db.Column(db.Text)  # Video URLs (stored as JSON string)
    interview_status = db.Column(db.String(20))  # pending, in_progress, completed
    completed_at = db.Column(db.DateTime)
    access_code = db.Column(db.String(6))  # 6-character access code for candidate authentication
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'resume_id': self.resume_id,
            'job_id': self.job_id,
            'interview_type': self.interview_type,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'duration_minutes': self.duration_minutes,
            'interview_mode': self.interview_mode,
            'meeting_link': self.meeting_link,
            'location': self.location,
            'interviewer_name': self.interviewer_name,
            'interviewer_email': self.interviewer_email,
            'status': self.status,
            'notes': self.notes,
            'feedback': self.feedback,
            'ai_questions': self.ai_questions,
            'ai_responses': self.ai_responses,
            'ai_score': self.ai_score,
            'ai_feedback': self.ai_feedback,
            'ai_analysis': self.ai_analysis,
            'video_responses': self.video_responses,
            'interview_status': self.interview_status,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class EmailLog(db.Model):
    __tablename__ = 'email_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    to_email = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    email_type = db.Column(db.String(50))  # status_change, interview_invite, reminder, rejection, offer
    related_id = db.Column(db.Integer)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='sent')  # sent, failed, pending
    error_message = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'to_email': self.to_email,
            'subject': self.subject,
            'email_type': self.email_type,
            'related_id': self.related_id,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'status': self.status,
            'error_message': self.error_message
        }
