"""
Interview Security Log Model
Tracks security events during AI interviews
"""

from extensions import db
from datetime import datetime

class InterviewSecurityLog(db.Model):
    __tablename__ = 'interview_security_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    interview_id = db.Column(db.Integer, db.ForeignKey('interviews.id'), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)  # tab_switch, fullscreen_exit, devtools_opened, etc.
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))  # IPv4 or IPv6
    user_agent = db.Column(db.Text)
    violation_count = db.Column(db.Integer, default=0)
    device_fingerprint = db.Column(db.JSON)  # Browser fingerprint data
    event_metadata = db.Column(db.JSON)  # Additional event data
    auto_submitted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'interview_id': self.interview_id,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'violation_count': self.violation_count,
            'device_fingerprint': self.device_fingerprint,
            'event_metadata': self.event_metadata,
            'auto_submitted': self.auto_submitted,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
