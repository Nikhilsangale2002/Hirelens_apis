from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from models.user import User, UserSession
from datetime import datetime

def require_session():
    """
    Hybrid Authentication Decorator
    - Validates JWT token (fast, stateless)
    - Validates session in database (secure, revocable)
    - Updates last activity timestamp
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Step 1: Verify JWT token (fast check)
                verify_jwt_in_request()
                user_id = get_jwt_identity()
                
                # Step 2: Get session token from header
                session_token = request.headers.get('X-Session-Token')
                
                if not session_token:
                    return jsonify({
                        'error': 'Session token required in X-Session-Token header',
                        'authenticated': False
                    }), 401
                
                # Step 3: Validate session in database (security check)
                session = UserSession.query.filter_by(
                    session_token=session_token,
                    user_id=user_id
                ).first()
                
                if not session:
                    return jsonify({
                        'error': 'Invalid session',
                        'authenticated': False
                    }), 401
                
                # Step 4: Check if session is still valid
                if not session.is_valid():
                    return jsonify({
                        'error': 'Session expired or revoked',
                        'authenticated': False
                    }), 401
                
                # Step 5: Update last activity (optional throttle: update every 5 min)
                if not session.last_activity or \
                   (datetime.utcnow() - session.last_activity).seconds > 300:
                    session.last_activity = datetime.utcnow()
                    from extensions import db
                    db.session.commit()
                
                # Step 6: Get user and verify active
                user = User.query.get(user_id)
                if not user or not user.is_active:
                    return jsonify({
                        'error': 'User not found or inactive',
                        'authenticated': False
                    }), 401
                
                # Pass user and session to the route
                request.current_user = user
                request.current_session = session
                
                return f(*args, **kwargs)
                
            except Exception as e:
                return jsonify({
                    'error': f'Authentication failed: {str(e)}',
                    'authenticated': False
                }), 401
        
        return decorated_function
    return decorator


def optional_session():
    """
    Optional authentication - doesn't fail if no token
    Useful for public endpoints that show more data when authenticated
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                verify_jwt_in_request(optional=True)
                user_id = get_jwt_identity()
                
                if user_id:
                    session_token = request.headers.get('X-Session-Token')
                    if session_token:
                        session = UserSession.query.filter_by(
                            session_token=session_token,
                            user_id=user_id
                        ).first()
                        
                        if session and session.is_valid():
                            user = User.query.get(user_id)
                            request.current_user = user
                            request.current_session = session
                        else:
                            request.current_user = None
                            request.current_session = None
                    else:
                        request.current_user = None
                        request.current_session = None
                else:
                    request.current_user = None
                    request.current_session = None
                    
            except:
                request.current_user = None
                request.current_session = None
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator
