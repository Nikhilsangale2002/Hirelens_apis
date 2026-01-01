"""
Test authentication endpoints
"""
import pytest
import json
from models.user import User


class TestAuth:
    """Test authentication routes"""
    
    def test_signup_success(self, client, db_session):
        """Test successful user registration"""
        response = client.post('/api/auth/signup', json={
            'email': 'newuser@example.com',
            'password': 'SecurePass123!',
            'name': 'New User',
            'company': 'Test Company'
        })
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'access_token' in data
        assert 'refresh_token' in data
        assert 'session_token' in data
        assert data['user']['email'] == 'newuser@example.com'
    
    def test_signup_duplicate_email(self, client, db_session):
        """Test signup with duplicate email"""
        # Create first user
        client.post('/api/auth/signup', json={
            'email': 'duplicate@example.com',
            'password': 'SecurePass123!',
            'name': 'First User'
        })
        
        # Try to create second user with same email
        response = client.post('/api/auth/signup', json={
            'email': 'duplicate@example.com',
            'password': 'AnotherPass123!',
            'name': 'Second User'
        })
        
        assert response.status_code == 409
        data = json.loads(response.data)
        assert 'already registered' in data['error'].lower()
    
    def test_signup_invalid_email(self, client):
        """Test signup with invalid email"""
        response = client.post('/api/auth/signup', json={
            'email': 'notanemail',
            'password': 'SecurePass123!',
            'name': 'Test User'
        })
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'email' in data['error'].lower()
    
    def test_signup_weak_password(self, client):
        """Test signup with weak password"""
        response = client.post('/api/auth/signup', json={
            'email': 'test@example.com',
            'password': 'weak',
            'name': 'Test User'
        })
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'password' in data['error'].lower()
    
    def test_login_success(self, client, db_session):
        """Test successful login"""
        # Create user first
        client.post('/api/auth/signup', json={
            'email': 'login@example.com',
            'password': 'SecurePass123!',
            'name': 'Login User'
        })
        
        # Login
        response = client.post('/api/auth/login', json={
            'email': 'login@example.com',
            'password': 'SecurePass123!'
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'access_token' in data
        assert data['user']['email'] == 'login@example.com'
    
    def test_login_invalid_credentials(self, client, db_session):
        """Test login with invalid credentials"""
        response = client.post('/api/auth/login', json={
            'email': 'nonexistent@example.com',
            'password': 'WrongPassword123!'
        })
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'invalid' in data['error'].lower()
    
    def test_login_missing_fields(self, client):
        """Test login with missing fields"""
        response = client.post('/api/auth/login', json={
            'email': 'test@example.com'
        })
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'required' in data['error'].lower()


class TestPasswordValidation:
    """Test password validation rules"""
    
    @pytest.mark.parametrize('password,should_pass', [
        ('SecurePass123!', True),
        ('Another@Valid1', True),
        ('weak', False),
        ('NoNumber!', False),
        ('nonumber123', False),
        ('NoSpecialChar1', False),
        ('nouppercase123!', False),
    ])
    def test_password_validation(self, client, password, should_pass):
        """Test various password patterns"""
        response = client.post('/api/auth/signup', json={
            'email': f'test_{password}@example.com',
            'password': password,
            'name': 'Test User'
        })
        
        if should_pass:
            assert response.status_code in [201, 409]  # 409 if email exists
        else:
            assert response.status_code == 400
