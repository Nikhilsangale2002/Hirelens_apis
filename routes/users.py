from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from PIL import Image
import io
from models.user import User
from extensions import db, cache_get, cache_set, cache_delete
from datetime import datetime
import os
import uuid

users_bp = Blueprint('users', __name__)

@users_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user's profile"""
    try:
        user_id = int(get_jwt_identity())
        
        # Try to get from cache first
        cache_key = f"user_profile:{user_id}"
        cached_profile = cache_get(cache_key)
        
        if cached_profile:
            return jsonify({'profile': cached_profile, 'cached': True}), 200
        
        # If not in cache, get from database
        user = User.query.get(user_id)
        
        if not user:
            current_app.logger.error(f"User not found: ID={user_id}")
            return jsonify({'error': 'User not found'}), 404
        
        profile_data = {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'company': user.company,
            'phone': user.phone,
            'profile_image': user.profile_image,
            'role': user.role,
            'plan': user.plan,
            'jobs_used': user.jobs_used,
            'resumes_used': user.resumes_used,
            'created_at': user.created_at.isoformat() if user.created_at else None
        }
        
        # Cache for 5 minutes
        cache_set(cache_key, profile_data, expire=300)
        
        return jsonify({'profile': profile_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error in get_profile: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@users_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update current user's profile"""
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if request contains file upload
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename:
                # Validate file type
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                
                if file_ext not in allowed_extensions:
                    return jsonify({'error': 'Invalid file type. Allowed: png, jpg, jpeg, gif, webp'}), 400
                
                try:
                    # Open and process image with PIL
                    img = Image.open(file.stream)
                    
                    # Convert RGBA to RGB if necessary (for JPEG)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    
                    # Resize image while maintaining aspect ratio (max 1024x1024 for high quality)
                    max_size = (1024, 1024)
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    
                    # Generate unique filename
                    filename = f"{uuid.uuid4().hex}.jpg"  # Always save as JPG for consistency
                    
                    # Create uploads directory if it doesn't exist
                    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles')
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    # Save with high quality
                    file_path = os.path.join(upload_folder, filename)
                    img.save(file_path, 'JPEG', quality=95, optimize=True, subsampling=0)
                    
                    # Delete old profile image if exists
                    if user.profile_image:
                        old_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles', user.profile_image)
                        if os.path.exists(old_file_path):
                            try:
                                os.remove(old_file_path)
                            except:
                                pass
                    
                    # Update user profile image
                    user.profile_image = filename
                    
                except Exception as img_error:
                    return jsonify({'error': f'Failed to process image: {str(img_error)}'}), 400
        
        # Handle JSON or form data
        if request.form:
            data = request.form.to_dict()
        else:
            data = request.get_json() or {}
        
        # Update allowed fields
        if 'name' in data:
            user.name = data['name']
        if 'company' in data:
            user.company = data['company']
        if 'phone' in data:
            user.phone = data['phone']
        if 'email' in data:
            # Check if email is already taken by another user
            existing_user = User.query.filter(User.email == data['email'], User.id != user_id).first()
            if existing_user:
                return jsonify({'error': 'Email already in use'}), 409
            user.email = data['email']
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Invalidate cache
        cache_delete(f"user_profile:{user_id}")
        cache_delete(f"user_plan:{user_id}")
        
        return jsonify({
            'message': 'Profile updated successfully',
            'profile': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'company': user.company,
                'phone': user.phone,
                'profile_image': user.profile_image,
                'role': user.role,
                'plan': user.plan
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@users_bp.route('/password', methods=['PUT'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Validate required fields
        if not data.get('current_password'):
            return jsonify({'error': 'Current password is required'}), 400
        if not data.get('new_password'):
            return jsonify({'error': 'New password is required'}), 400
        
        # Verify current password
        if not user.check_password(data['current_password']):
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        # Validate new password strength
        new_password = data['new_password']
        if len(new_password) < 8:
            return jsonify({'error': 'New password must be at least 8 characters long'}), 400
        
        # Set new password
        user.set_password(new_password)
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@users_bp.route('/plan', methods=['GET'])
@jwt_required()
def get_plan():
    """Get user's current plan details"""
    try:
        user_id = int(get_jwt_identity())
        
        # Try to get from cache first
        cache_key = f"user_plan:{user_id}"
        cached_plan = cache_get(cache_key)
        
        if cached_plan:
            return jsonify({'plan': cached_plan, 'cached': True}), 200
        
        user = User.query.get(user_id)
        
        if not user:
            current_app.logger.error(f"User not found for plan: ID={user_id}")
            return jsonify({'error': 'User not found'}), 404
        
        # Plan limits
        plan_limits = {
            'starter': {'jobs': 3, 'resumes': 500, 'price': 1999},
            'pro': {'jobs': 10, 'resumes': 2000, 'price': 4999},
            'enterprise': {'jobs': -1, 'resumes': -1, 'price': 9999}
        }
        
        limits = plan_limits.get(user.plan, plan_limits['starter'])
        
        plan_data = {
            'name': user.plan,
            'price': limits['price'],
            'jobs_limit': limits['jobs'],
            'resumes_limit': limits['resumes'],
            'jobs_used': user.jobs_used,
            'resumes_used': user.resumes_used
        }
        
        # Cache for 5 minutes
        cache_set(cache_key, plan_data, expire=300)
        
        return jsonify({'plan': plan_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error in get_plan: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@users_bp.route('/uploads/profiles/<filename>', methods=['GET'])
def serve_profile_image(filename):
    """Serve profile images"""
    try:
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profiles')
        return send_from_directory(upload_folder, filename)
    except Exception as e:
        return jsonify({'error': 'Image not found'}), 404


@users_bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    """Get user notification preferences"""
    try:
        user_id = int(get_jwt_identity())
        
        # For now, return default preferences
        # In production, you'd have a separate UserPreferences table
        return jsonify({
            'notifications': {
                'resume_processed': True,
                'new_candidates': True,
                'plan_limits': True,
                'weekly_summary': True
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@users_bp.route('/notifications', methods=['PUT'])
@jwt_required()
def update_notifications():
    """Update user notification preferences"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        
        # In production, save to UserPreferences table
        # For now, just return success
        
        return jsonify({
            'message': 'Notification preferences updated successfully',
            'notifications': data.get('notifications', {})
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@users_bp.route('/email-config', methods=['GET'])
@jwt_required()
def get_email_config():
    """Get user's email configuration"""
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'email_config': {
                'smtp_server': user.smtp_server or '',
                'smtp_port': user.smtp_port or 587,
                'smtp_username': user.smtp_username or '',
                'smtp_password': user.smtp_password or '',
                'from_email': user.from_email or '',
                'from_name': user.from_name or ''
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@users_bp.route('/email-config', methods=['PUT'])
@jwt_required()
def update_email_config():
    """Update user's email configuration"""
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        # Update email configuration
        if 'smtp_server' in data:
            user.smtp_server = data['smtp_server']
        if 'smtp_port' in data:
            user.smtp_port = data['smtp_port']
        if 'smtp_username' in data:
            user.smtp_username = data['smtp_username']
        if 'smtp_password' in data:
            user.smtp_password = data['smtp_password']
        if 'from_email' in data:
            user.from_email = data['from_email']
        if 'from_name' in data:
            user.from_name = data['from_name']
        
        user.email_notifications = True
        user.smtp_configured = True
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Invalidate cache
        cache_delete(f"user_profile:{user_id}")
        
        return jsonify({
            'message': 'Email configuration updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@users_bp.route('/test-email', methods=['POST'])
@jwt_required()
def send_test_email():
    """Send a test email to verify SMTP configuration"""
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        test_email = data.get('email')
        
        if not test_email:
            return jsonify({'error': 'Email address required'}), 400
        
        # Import EmailService
        from services.email_service import EmailService
        
        # Create email service with user's SMTP config
        email_service = EmailService(
            smtp_server=user.smtp_server,
            smtp_port=user.smtp_port,
            smtp_username=user.smtp_username,
            smtp_password=user.smtp_password,
            from_email=user.from_email or user.email,
            from_name=user.from_name or user.company or 'HireLens'
        )
        
        # Send test email
        subject = "HireLens - Test Email"
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #004E89 0%, #FF6B35 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">Test Email Successful!</h1>
            </div>
            <div style="padding: 30px; background-color: #f5f5f5;">
                <p style="font-size: 16px; color: #333;">
                    Congratulations! Your SMTP configuration is working correctly.
                </p>
                <p style="font-size: 14px; color: #666;">
                    This test email confirms that HireLens can successfully send emails using your SMTP settings.
                </p>
                <div style="background-color: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #004E89; margin-top: 0;">Configuration Details</h3>
                    <p style="margin: 5px 0; color: #666;"><strong>SMTP Server:</strong> {user.smtp_server}</p>
                    <p style="margin: 5px 0; color: #666;"><strong>Port:</strong> {user.smtp_port}</p>
                    <p style="margin: 5px 0; color: #666;"><strong>From Email:</strong> {user.from_email or user.email}</p>
                </div>
                <p style="font-size: 14px; color: #666;">
                    You can now send interview invitations and status notifications to candidates.
                </p>
            </div>
            <div style="background-color: #004E89; padding: 20px; text-align: center;">
                <p style="color: white; margin: 0; font-size: 12px;">
                    Sent from HireLens - AI-Powered Recruitment Platform
                </p>
            </div>
        </div>
        """
        
        success = email_service.send_email(
            to_email=test_email,
            subject=subject,
            html_content=body
        )
        
        if success:
            return jsonify({
                'message': 'Test email sent successfully! Check your inbox.'
            }), 200
        else:
            return jsonify({'error': 'Failed to send test email. Please check your SMTP configuration.'}), 500
        
    except Exception as e:
        return jsonify({'error': f'Failed to send test email: {str(e)}'}), 500
