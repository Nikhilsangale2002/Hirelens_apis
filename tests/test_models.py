"""
Test database models
"""
import pytest
from datetime import datetime, timedelta
from models.user import User, UserSession
from models.job import Job
from models.resume import Resume


class TestUserModel:
    """Test User model"""
    
    def test_create_user(self, db_session):
        """Test user creation"""
        user = User(
            email='model@example.com',
            name='Model Test',
            company='Test Co'
        )
        user.set_password('TestPassword123!')
        
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.email == 'model@example.com'
        assert user.password_hash is not None
        assert user.check_password('TestPassword123!')
    
    def test_password_hashing(self, db_session):
        """Test password is hashed"""
        user = User(email='hash@example.com')
        user.set_password('PlainPassword123!')
        
        assert user.password_hash != 'PlainPassword123!'
        assert user.check_password('PlainPassword123!')
        assert not user.check_password('WrongPassword')
    
    def test_user_to_dict(self, db_session):
        """Test user serialization"""
        user = User(
            email='dict@example.com',
            name='Dict Test',
            plan='pro'
        )
        user.set_password('Test123!')
        db_session.add(user)
        db_session.commit()
        
        user_dict = user.to_dict()
        assert user_dict['email'] == 'dict@example.com'
        assert user_dict['plan'] == 'pro'
        assert 'password_hash' not in user_dict
    
    def test_account_lockout(self, db_session):
        """Test account lockout mechanism"""
        user = User(email='lockout@example.com')
        user.set_password('Test123!')
        
        # Not locked initially
        assert not user.is_locked()
        
        # Increment failed attempts
        for _ in range(5):
            user.increment_failed_login()
        
        # Should be locked now
        assert user.is_locked()
        assert user.locked_until is not None
        
        # Reset should unlock
        user.reset_failed_login()
        assert not user.is_locked()
        assert user.failed_login_attempts == 0


class TestJobModel:
    """Test Job model"""
    
    def test_create_job(self, db_session):
        """Test job creation"""
        user = User(email='jobuser@example.com')
        user.set_password('Test123!')
        db_session.add(user)
        db_session.commit()
        
        job = Job(
            user_id=user.id,
            title='Software Engineer',
            description='Build awesome stuff',
            department='Engineering',
            location='Remote',
            status='active'
        )
        db_session.add(job)
        db_session.commit()
        
        assert job.id is not None
        assert job.title == 'Software Engineer'
        assert job.user_id == user.id
    
    def test_job_to_dict(self, db_session):
        """Test job serialization"""
        user = User(email='jobdict@example.com')
        user.set_password('Test123!')
        db_session.add(user)
        db_session.commit()
        
        job = Job(
            user_id=user.id,
            title='Test Job',
            description='Test',
            status='active'
        )
        db_session.add(job)
        db_session.commit()
        
        job_dict = job.to_dict()
        assert job_dict['title'] == 'Test Job'
        assert 'created_at' in job_dict


class TestUserSession:
    """Test UserSession model"""
    
    def test_create_session(self, db_session):
        """Test session creation"""
        user = User(email='session@example.com')
        user.set_password('Test123!')
        db_session.add(user)
        db_session.commit()
        
        session = UserSession(
            user_id=user.id,
            device_info='Test Device',
            ip_address='127.0.0.1'
        )
        db_session.add(session)
        db_session.commit()
        
        assert session.id is not None
        assert session.session_token is not None
        assert session.is_active
    
    def test_session_expiry(self, db_session):
        """Test session expiration"""
        user = User(email='expiry@example.com')
        user.set_password('Test123!')
        db_session.add(user)
        db_session.commit()
        
        session = UserSession(
            user_id=user.id,
            device_info='Test',
            ip_address='127.0.0.1'
        )
        
        # Set expired date
        session.expires_at = datetime.utcnow() - timedelta(days=1)
        db_session.add(session)
        db_session.commit()
        
        assert not session.is_valid()
