from extensions import db
from datetime import datetime

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)  # login, logout, signup, password_change, etc.
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    status = db.Column(db.String(20))  # success, failure, warning
    details = db.Column(db.Text)  # JSON string with additional details
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __init__(self, user_id, event_type, ip_address, user_agent, status, details=None):
        self.user_id = user_id
        self.event_type = event_type
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.status = status
        self.details = details
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'event_type': self.event_type,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'status': self.status,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def log_event(user_id, event_type, status, request, details=None):
        """Helper method to quickly log an event"""
        log = AuditLog(
            user_id=user_id,
            event_type=event_type,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', 'Unknown'),
            status=status,
            details=details
        )
        db.session.add(log)
        try:
            db.session.commit()
        except Exception as e:
            # Don't fail the main operation if logging fails
            db.session.rollback()
            print(f"Audit log failed: {e}")
