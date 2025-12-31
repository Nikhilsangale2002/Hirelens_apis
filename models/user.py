from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import secrets

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100))
    company = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    profile_image = db.Column(db.String(500))
    role = db.Column(db.String(20), default='recruiter')  # recruiter, admin
    plan = db.Column(db.String(20), default='starter')  # starter, pro, enterprise
    jobs_used = db.Column(db.Integer, default=0)
    resumes_used = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    
    # Token and session fields
    refresh_token = db.Column(db.String(500))  # For JWT refresh token (now hashed)
    token_expires_at = db.Column(db.DateTime)
    last_login = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(50))
    
    # Account security fields (lockout mechanism)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    
    # Email configuration fields
    email_notifications = db.Column(db.Boolean, default=False)
    smtp_configured = db.Column(db.Boolean, default=False)
    smtp_server = db.Column(db.String(255))
    smtp_port = db.Column(db.Integer)
    smtp_username = db.Column(db.String(255))
    smtp_password = db.Column(db.String(255))
    from_email = db.Column(db.String(255))
    from_name = db.Column(db.String(255))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = db.relationship('Job', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    sessions = db.relationship('UserSession', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_refresh_token(self):
        """Generate a secure refresh token"""
        self.refresh_token = secrets.token_urlsafe(64)
        return self.refresh_token
    
    def is_locked(self):
        """Check if account is currently locked"""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False
    
    def increment_failed_login(self):
        """Increment failed login attempts and lock account if threshold reached"""
        self.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts for 15 minutes
        if self.failed_login_attempts >= 5:
            from datetime import timedelta
            self.locked_until = datetime.utcnow() + timedelta(minutes=15)
    
    def reset_failed_login(self):
        """Reset failed login attempts and unlock account"""
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'company': self.company,            'phone': self.phone,            'profile_image': self.profile_image,
            'role': self.role,
            'plan': self.plan,
            'jobs_used': self.jobs_used,
            'resumes_used': self.resumes_used,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    session_token = db.Column(db.String(500), unique=True, nullable=False, index=True)
    device_info = db.Column(db.String(255))  # Browser, OS, device type
    ip_address = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, user_id, device_info=None, ip_address=None, expires_at=None):
        self.user_id = user_id
        self.session_token = secrets.token_urlsafe(64)
        self.device_info = device_info
        self.ip_address = ip_address
        self.expires_at = expires_at
    
    def is_valid(self):
        """Check if session is still valid"""
        return self.is_active and self.expires_at > datetime.utcnow()
    
    def revoke(self):
        """Revoke this session"""
        self.is_active = False
    
    def to_dict(self):
        return {
            'id': self.id,
            'device_info': self.device_info,
            'ip_address': self.ip_address,
            'is_active': self.is_active,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
