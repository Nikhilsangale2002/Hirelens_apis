from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from models.user import User, UserSession
from models.audit_log import AuditLog
from extensions import db, cache_delete
from utils.validators import validate_email, validate_password
from services.supabase_client import get_supabase_auth
from services.email_service import EmailService
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
import secrets
import json

auth_bp = Blueprint('auth', __name__)

# Rate limiter fallback
try:
    import sys
    import os
    # Add middleware to path
    middleware_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'Hirelens_monitoring')
    if os.path.exists(middleware_path):
        sys.path.insert(0, middleware_path)
    from middleware.rate_limiter import rate_limit  # type: ignore
except (ImportError, ModuleNotFoundError):
    # Fallback: no-op decorator if rate_limiter not available
    def rate_limit(limit=None, window=None):
        def decorator(f):
            return f
        return decorator

# Helper function to hash tokens before storing
def hash_token(token):
    """Hash token using werkzeug before storing in database"""
    return generate_password_hash(token)

@auth_bp.route('/signup', methods=['POST'])
@rate_limit(limit=5, window=300)  # 5 signups per 5 minutes per IP
def signup():
    try:
        data = request.get_json()
        
        # Validate input
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        company = data.get('company', '').strip()
        
        if not email or not validate_email(email):
            return jsonify({'error': 'Invalid email address'}), 400
        
        if not password or not validate_password(password):
            return jsonify({'error': 'Password must be at least 8 characters with uppercase, lowercase, digit, and special character'}), 400
        
        # Check if user exists
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 409
        
        # Create user
        user = User(
            email=email,
            name=name,
            company=company,
            plan='starter'
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Create tokens (identity must be string)
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        # Store HASHED refresh token in user record (security improvement)
        user.refresh_token = hash_token(refresh_token)
        user.token_expires_at = datetime.utcnow() + timedelta(days=30)
        user.last_login = datetime.utcnow()
        user.last_login_ip = request.remote_addr
        
        # Create session
        device_info = request.headers.get('User-Agent', 'Unknown')
        session = UserSession(
            user_id=user.id,
            device_info=device_info,
            ip_address=request.remote_addr,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(session)
        db.session.commit()
        
        # Log successful signup
        AuditLog.log_event(user.id, 'signup', 'success', request, 
                          json.dumps({'email': email, 'name': name}))
        
        # Send welcome email (async, don't block signup if it fails)
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Sending welcome email to new signup: {email}")
            
            email_service = EmailService()
            email_service.send_welcome_email(
                user_name=name or email.split('@')[0],
                user_email=email,
                company_name=company
            )
            
            logger.info(f"Welcome email sent successfully to {email}")
            
            # Create welcome notification
            try:
                from routes.notifications import create_notification
                create_notification(
                    user_id=user.id,
                    notification_type='welcome',
                    title='Welcome to HireLens! 🎉',
                    message='Your account has been created successfully. Start by posting your first job!',
                    related_type='user',
                    related_id=user.id,
                    action_url='/dashboard/jobs/create'
                )
            except Exception as notif_error:
                logger.error(f"Failed to create welcome notification: {str(notif_error)}")
                
        except Exception as e:
            # Log the error but don't fail the signup
            logger.error(f"Failed to send welcome email to {email}: {str(e)}")
        
        return jsonify({
            'message': 'User created successfully',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'session_token': session.session_token,
            'expires_at': session.expires_at.isoformat()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        # Log failed signup
        AuditLog.log_event(None, 'signup', 'failure', request, 
                          json.dumps({'error': str(e)}))
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
@rate_limit(limit=5, window=900)  # 5 login attempts per 15 minutes per IP
def login():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        user = User.query.filter_by(email=email).first()
        
        # Check if account is locked
        if user and user.is_locked():
            remaining_time = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
            return jsonify({
                'error': f'Account locked due to multiple failed login attempts. Try again in {remaining_time} minutes.'
            }), 423  # 423 Locked status code
        
        if not user or not user.check_password(password):
            # Increment failed login attempts and log
            if user:
                user.increment_failed_login()
                db.session.commit()
                AuditLog.log_event(user.id, 'login', 'failure', request, 
                                  json.dumps({'reason': 'invalid_password'}))
            else:
                AuditLog.log_event(None, 'login', 'failure', request, 
                                  json.dumps({'reason': 'user_not_found', 'email': email}))
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user.is_active:
            AuditLog.log_event(user.id, 'login', 'failure', request, 
                              json.dumps({'reason': 'account_inactive'}))
            return jsonify({'error': 'Account is inactive'}), 403
        
        # Reset failed login attempts on successful login
        user.reset_failed_login()
        
        # Create tokens (identity must be string)
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        # Update user login info with HASHED refresh token (security improvement)
        user.refresh_token = hash_token(refresh_token)
        user.token_expires_at = datetime.utcnow() + timedelta(days=30)
        user.last_login = datetime.utcnow()
        user.last_login_ip = request.remote_addr
        
        # Revoke old sessions (optional: limit to 5 active sessions)
        active_sessions = UserSession.query.filter_by(user_id=user.id, is_active=True).order_by(UserSession.created_at.desc()).all()
        if len(active_sessions) >= 5:
            # Keep only 4 most recent, revoke oldest
            for old_session in active_sessions[4:]:
                old_session.revoke()
        
        # Create new session
        device_info = request.headers.get('User-Agent', 'Unknown')
        session = UserSession(
            user_id=user.id,
            device_info=device_info,
            ip_address=request.remote_addr,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(session)
        db.session.commit()
        
        # Log successful login
        AuditLog.log_event(user.id, 'login', 'success', request, 
                          json.dumps({'device': device_info}))
        
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'session_token': session.session_token,
            'expires_at': session.expires_at.isoformat()
        }), 200
        
    except Exception as e:
        # Log exception
        AuditLog.log_event(None, 'login', 'error', request, 
                          json.dumps({'error': str(e)}))
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    try:
        # Add detailed logging
        from flask import current_app
        current_app.logger.info('=== /me endpoint called ===')
        current_app.logger.info(f'Headers: {dict(request.headers)}')
        
        user_id = int(get_jwt_identity())  # Convert string back to int
        current_app.logger.info(f'JWT Identity: {user_id}')
        
        user = User.query.get(user_id)
        
        if not user:
            current_app.logger.error(f'User not found for ID: {user_id}')
            return jsonify({'error': 'User not found'}), 404
        
        current_app.logger.info(f'User found: {user.email}')
        return jsonify({'user': user.to_dict()}), 200
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Error in /me endpoint: {str(e)}')
        current_app.logger.error(f'Error type: {type(e).__name__}')
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    try:
        user_id = get_jwt_identity()
        access_token = create_access_token(identity=user_id)
        
        return jsonify({'access_token': access_token}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    try:
        user_id = int(get_jwt_identity())  # Convert string back to int
        
        # Revoke all active sessions for the user
        UserSession.query.filter_by(user_id=user_id, is_active=True).update({'is_active': False})
        
        # Clear refresh token
        user = User.query.get(user_id)
        if user:
            user.refresh_token = None
            user.token_expires_at = None
        
        db.session.commit()
                # Invalidate all user caches
        cache_delete(f"user_profile:{user_id}")
        cache_delete(f"user_plan:{user_id}")
                # Log logout
        AuditLog.log_event(user_id, 'logout', 'success', request, None)
        
        return jsonify({'message': 'Logged out successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/sessions', methods=['GET'])
@jwt_required()
def get_sessions():
    try:
        user_id = int(get_jwt_identity())  # Convert string back to int
        
        sessions = UserSession.query.filter_by(user_id=user_id).order_by(UserSession.created_at.desc()).all()
        
        return jsonify({
            'sessions': [session.to_dict() for session in sessions]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/sessions/<int:session_id>', methods=['DELETE'])
@jwt_required()
def revoke_session(session_id):
    try:
        user_id = int(get_jwt_identity())  # Convert string back to int
        
        session = UserSession.query.filter_by(id=session_id, user_id=user_id).first()
        
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        session.revoke()
        db.session.commit()
        
        return jsonify({'message': 'Session revoked successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/validate', methods=['POST'])
def validate_token():
    """Validate session token from database - HYBRID SECURITY"""
    try:
        data = request.get_json()
        session_token = data.get('session_token')
        
        if not session_token:
            # Check header for session token
            session_token = request.headers.get('X-Session-Token')
        
        if not session_token:
            return jsonify({'error': 'Session token required', 'valid': False}), 401
        
        # Validate session in database
        session = UserSession.query.filter_by(session_token=session_token).first()
        
        if not session:
            return jsonify({'error': 'Invalid session', 'valid': False}), 401
        
        if not session.is_valid():
            return jsonify({'error': 'Session expired or revoked', 'valid': False}), 401
        
        # Update last activity
        session.last_activity = datetime.utcnow()
        db.session.commit()
        
        # Get user info
        user = User.query.get(session.user_id)
        
        if not user or not user.is_active:
            return jsonify({'error': 'User not found or inactive', 'valid': False}), 401
        
        return jsonify({
            'valid': True,
            'user': user.to_dict(),
            'session': session.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e), 'valid': False}), 500

@auth_bp.route('/oauth/callback', methods=['POST'])
def oauth_callback():
    """Handle OAuth callback from Supabase (Google/GitHub)"""
    try:
        data = request.get_json()
        supabase_token = data.get('access_token')
        
        if not supabase_token:
            return jsonify({'error': 'Access token required'}), 400
        
        # Verify token with Supabase
        supabase_auth = get_supabase_auth()
        if not supabase_auth:
            return jsonify({'error': 'OAuth not configured'}), 500
        
        supabase_user = supabase_auth.verify_token(supabase_token)
        
        if not supabase_user:
            return jsonify({'error': 'Invalid OAuth token'}), 401
        
        # Extract user info
        email = supabase_user.get('email', '').strip().lower()
        name = supabase_user.get('user_metadata', {}).get('full_name', '')
        avatar = supabase_user.get('user_metadata', {}).get('avatar_url', '')
        provider = supabase_user.get('app_metadata', {}).get('provider', 'email')
        
        if not email:
            return jsonify({'error': 'Email not provided by OAuth provider'}), 400
        
        # Check if user exists
        user = User.query.filter_by(email=email).first()
        
        is_new_user = False
        if not user:
            # Create new user from OAuth
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Creating new user from {provider} OAuth: {email}")
            
            user = User(
                email=email,
                name=name or email.split('@')[0],
                plan='starter',
                role='recruiter'
            )
            # Set random password (user won't use it for OAuth login)
            user.set_password(secrets.token_urlsafe(32))
            
            db.session.add(user)
            db.session.commit()
            is_new_user = True
            
            logger.info(f"New user created successfully: ID={user.id}, Email={email}")
        
        # Create JWT tokens (identity must be string)
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        # Update user login info with HASHED refresh token
        user.refresh_token = hash_token(refresh_token)
        user.token_expires_at = datetime.utcnow() + timedelta(days=30)
        user.last_login = datetime.utcnow()
        user.last_login_ip = request.remote_addr
        
        # Revoke old sessions if limit exceeded
        active_sessions = UserSession.query.filter_by(user_id=user.id, is_active=True).order_by(UserSession.created_at.desc()).all()
        if len(active_sessions) >= 5:
            for old_session in active_sessions[4:]:
                old_session.revoke()
        
        # Create new session
        device_info = request.headers.get('User-Agent', 'Unknown')
        session = UserSession(
            user_id=user.id,
            device_info=f"{provider.capitalize()} - {device_info}",
            ip_address=request.remote_addr,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(session)
        db.session.commit()
        
        # Send welcome email and create notification for new OAuth users (first time only)
        if is_new_user:
            try:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Sending welcome email to new {provider} user: {email}")
                
                email_service = EmailService()
                email_service.send_welcome_email(
                    user_name=user.name or email.split('@')[0],
                    user_email=email,
                    company_name=user.company
                )
                
                logger.info(f"Welcome email sent successfully to {email}")
                
                # Create welcome notification
                try:
                    from routes.notifications import create_notification
                    create_notification(
                        user_id=user.id,
                        notification_type='welcome',
                        title=f'Welcome to HireLens! 🎉',
                        message=f'Your account has been created successfully via {provider.capitalize()}. Start by posting your first job!',
                        related_type='user',
                        related_id=user.id,
                        action_url='/dashboard/jobs/create'
                    )
                except Exception as notif_error:
                    logger.error(f"Failed to create welcome notification: {str(notif_error)}")
                    
            except Exception as e:
                logger.error(f"Failed to send welcome email to {email}: {str(e)}")
        
        return jsonify({
            'message': f'{provider.capitalize()} login successful',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'session_token': session.session_token,
            'expires_at': session.expires_at.isoformat(),
            'provider': provider
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

