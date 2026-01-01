"""
Pytest configuration and fixtures
"""
import pytest
from app import create_app
from extensions import db
from config import Config


class TestConfig(Config):
    """Test configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}  # Override pool settings for SQLite
    JWT_SECRET_KEY = 'test-secret-key-for-testing-only'
    REDIS_HOST = 'localhost'
    WTF_CSRF_ENABLED = False
    DEBUG = False


@pytest.fixture(scope='session')
def app():
    """Create application for testing"""
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture(scope='function')
def db_session(app):
    """Create a new database session for a test"""
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()
        
        # Bind session to connection
        session = db.create_scoped_session(
            options={'bind': connection, 'binds': {}}
        )
        db.session = session
        
        yield session
        
        # Rollback and cleanup
        transaction.rollback()
        connection.close()
        session.remove()


@pytest.fixture
def auth_headers(client):
    """Get authentication headers for testing"""
    from models.user import User
    from flask_jwt_extended import create_access_token
    
    # Create test user
    user = User(
        email='test@example.com',
        name='Test User',
        company='Test Company',
        plan='starter'
    )
    user.set_password('TestPassword123!')
    db.session.add(user)
    db.session.commit()
    
    # Create tokens
    access_token = create_access_token(identity=str(user.id))
    
    # Create session
    from models.user import UserSession
    session = UserSession(
        user_id=user.id,
        device_info='pytest',
        ip_address='127.0.0.1'
    )
    db.session.add(session)
    db.session.commit()
    
    return {
        'Authorization': f'Bearer {access_token}',
        'X-Session-Token': session.session_token,
        'Content-Type': 'application/json'
    }
