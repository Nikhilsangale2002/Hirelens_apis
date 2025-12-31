from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.notification import Notification
from extensions import db, cache_get, cache_set, cache_delete, cache_delete_pattern
from datetime import datetime
import logging

notifications_bp = Blueprint('notifications', __name__)
logger = logging.getLogger(__name__)

@notifications_bp.route('/', methods=['GET'])
@jwt_required()
def get_notifications():
    """Get all notifications for the current user"""
    try:
        user_id = int(get_jwt_identity())
        
        # Query parameters
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Cache key
        cache_key = f"notifications:{user_id}:{'unread' if unread_only else 'all'}:{limit}:{offset}"
        
        # Try cache
        cached_data = cache_get(cache_key)
        if cached_data:
            return jsonify({
                'notifications': cached_data['notifications'],
                'total': cached_data['total'],
                'unread_count': cached_data['unread_count'],
                'cached': True
            }), 200
        
        # Get notifications
        if unread_only:
            notifications = Notification.query.filter_by(user_id=user_id, is_read=False).order_by(Notification.created_at.desc()).limit(limit).offset(offset).all()
            total = len(notifications)
        else:
            notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).limit(limit).offset(offset).all()
            total = len(notifications)
        
        # Get unread count separately
        unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
        
        result = {
            'notifications': [n.to_dict() for n in notifications],
            'total': total,
            'unread_count': unread_count
        }
        
        # Cache for 30 seconds
        cache_set(cache_key, result, expire=30)
        
        return jsonify({
            **result,
            'cached': False
        }), 200
        
    except Exception as e:
        logger.error(f"Get notifications error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@notifications_bp.route('/unread-count', methods=['GET'])
@jwt_required()
def get_unread_count():
    """Get count of unread notifications"""
    try:
        user_id = int(get_jwt_identity())
        
        # Cache key
        cache_key = f"notifications:unread_count:{user_id}"
        
        # Try cache
        cached_count = cache_get(cache_key)
        if cached_count is not None:
            return jsonify({
                'unread_count': cached_count,
                'cached': True
            }), 200
        
        unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
        
        # Cache for 10 seconds
        cache_set(cache_key, unread_count, expire=10)
        
        return jsonify({
            'unread_count': unread_count,
            'cached': False
        }), 200
        
    except Exception as e:
        logger.error(f"Get unread count error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@notifications_bp.route('/<int:notification_id>/read', methods=['PUT'])
@jwt_required()
def mark_as_read(notification_id):
    """Mark a notification as read"""
    try:
        user_id = int(get_jwt_identity())
        
        notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404
        
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            db.session.commit()
            
            # Invalidate cache
            cache_delete_pattern(f"notifications:{user_id}:*")
            cache_delete(f"notifications:unread_count:{user_id}")
        
        return jsonify({
            'message': 'Notification marked as read',
            'notification': notification.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Mark as read error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@notifications_bp.route('/mark-all-read', methods=['PUT'])
@jwt_required()
def mark_all_as_read():
    """Mark all notifications as read"""
    try:
        user_id = int(get_jwt_identity())
        
        Notification.query.filter_by(user_id=user_id, is_read=False).update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })
        
        db.session.commit()
        
        # Invalidate cache
        cache_delete_pattern(f"notifications:{user_id}:*")
        cache_delete(f"notifications:unread_count:{user_id}")
        
        return jsonify({'message': 'All notifications marked as read'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Mark all as read error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@notifications_bp.route('/<int:notification_id>', methods=['DELETE'])
@jwt_required()
def delete_notification(notification_id):
    """Delete a notification"""
    try:
        user_id = int(get_jwt_identity())
        
        notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        
        if not notification:
            return jsonify({'error': 'Notification not found'}), 404
        
        db.session.delete(notification)
        db.session.commit()
        
        # Invalidate cache
        cache_delete_pattern(f"notifications:{user_id}:*")
        cache_delete(f"notifications:unread_count:{user_id}")
        
        return jsonify({'message': 'Notification deleted'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete notification error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@notifications_bp.route('/clear-all', methods=['DELETE'])
@jwt_required()
def clear_all_notifications():
    """Clear all notifications for the user"""
    try:
        user_id = int(get_jwt_identity())
        
        Notification.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        
        # Invalidate cache
        cache_delete_pattern(f"notifications:{user_id}:*")
        cache_delete(f"notifications:unread_count:{user_id}")
        
        return jsonify({'message': 'All notifications cleared'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Clear all notifications error: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Helper function to create notifications (can be called from other routes)
def create_notification(user_id, notification_type, title, message, related_type=None, related_id=None, action_url=None):
    """
    Helper function to create a notification
    
    Types:
    - job_applied: New candidate applied
    - interview_scheduled: Interview has been scheduled
    - interview_reminder: Interview coming up
    - status_changed: Candidate status changed
    - resume_uploaded: New resume uploaded
    - job_created: New job posted
    - job_expired: Job posting expired
    """
    try:
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            related_type=related_type,
            related_id=related_id,
            action_url=action_url
        )
        
        db.session.add(notification)
        db.session.commit()
        
        # Invalidate cache
        cache_delete_pattern(f"notifications:{user_id}:*")
        cache_delete(f"notifications:unread_count:{user_id}")
        
        logger.info(f"Notification created for user {user_id}: {title}")
        return notification
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create notification error: {str(e)}")
        return None
