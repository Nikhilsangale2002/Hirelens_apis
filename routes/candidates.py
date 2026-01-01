from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.job import Job
from models.resume import Resume
from models.user import User
from extensions import db, cache_get, cache_set, cache_delete, cache_delete_pattern
from services.email_service import EmailService
from routes.notifications import create_notification
from utils.pagination import paginate, paginate_response
import logging
import os

candidates_bp = Blueprint('candidates', __name__)
logger = logging.getLogger(__name__)

@candidates_bp.route('/job/<int:job_id>', methods=['GET'])
@jwt_required()
def get_candidates(job_id):
    """Get paginated candidates for a specific job"""
    try:
        user_id = int(get_jwt_identity())
        
        # Query parameters
        status = request.args.get('status')
        min_score = request.args.get('min_score', type=float)
        sort_by = request.args.get('sort_by', 'score')  # score, date
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        # Verify job ownership
        job = Job.query.filter_by(id=job_id, user_id=user_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Build query with optimizations
        query = Resume.query.filter_by(job_id=job_id)
        
        if status:
            query = query.filter_by(status=status)
        
        if min_score:
            query = query.filter(Resume.ai_score >= min_score)
        
        # Sort
        if sort_by == 'score':
            query = query.order_by(Resume.ai_score.desc())
        else:
            query = query.order_by(Resume.created_at.desc())
        
        # Paginate
        paginated = paginate(query, page=page, per_page=per_page, max_per_page=100)
        response_data = paginate_response(paginated)
        
        # Restructure response to match frontend expectations (candidates instead of data)
        frontend_response = {
            'candidates': response_data['data'],
            'pagination': response_data['pagination']
        }
        
        return jsonify(frontend_response), 200
        
    except Exception as e:
        logger.error(f"Get candidates error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@candidates_bp.route('/all', methods=['GET'])
@jwt_required()
def get_all_candidates():
    try:
        user_id = int(get_jwt_identity())  # Convert to int for DB queries
        
        # Query parameters
        status = request.args.get('status')
        search = request.args.get('search', '').lower()
        
        # Create cache key
        cache_key = f"candidates_all:{user_id}:{status or 'all'}:{search or 'none'}"
        
        # Try to get from cache
        cached_data = cache_get(cache_key)
        if cached_data:
            return jsonify({
                'candidates': cached_data,
                'cached': True
            }), 200
        
        # Get all candidates across all user's jobs
        query = Resume.query.join(Job).filter(Job.user_id == user_id)
        
        if status:
            query = query.filter(Resume.status == status)
        
        candidates = query.order_by(Resume.ai_score.desc()).all()
        candidates_data = [c.to_dict(include_job=True) for c in candidates]
        
        # Apply search filter
        if search:
            candidates_data = [
                c for c in candidates_data 
                if search in c.get('name', '').lower() or 
                   search in c.get('email', '').lower() or
                   search in c.get('job_title', '').lower()
            ]
        
        # Cache for 2 minutes
        cache_set(cache_key, candidates_data, expire=120)
        
        return jsonify({
            'candidates': candidates_data,
            'cached': False
        }), 200
        
    except Exception as e:
        logger.error(f"Get all candidates error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@candidates_bp.route('/detail/<int:candidate_id>', methods=['GET'])
@jwt_required()
def get_candidate(candidate_id):
    try:
        user_id = int(get_jwt_identity())  # Convert to int to ensure consistency
        
        # Cache key for single candidate
        cache_key = f"candidate_detail:{user_id}:{candidate_id}"
        
        # Try to get from cache
        cached_data = cache_get(cache_key)
        if cached_data:
            return jsonify({
                'candidate': cached_data,
                'cached': True
            }), 200
        
        # First, check if candidate exists at all
        candidate = Resume.query.get(candidate_id)
        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404
        
        # Then check if it belongs to user's job
        job = Job.query.filter_by(id=candidate.job_id, user_id=user_id).first()
        if not job:
            return jsonify({'error': 'Unauthorized access to this candidate'}), 403
        
        candidate_data = candidate.to_dict(include_job=True)
        
        # Cache for 5 minutes
        cache_set(cache_key, candidate_data, expire=300)
        
        return jsonify({
            'candidate': candidate_data,
            'cached': False
        }), 200
        
    except Exception as e:
        logger.error(f"Get candidate error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@candidates_bp.route('/detail/<int:candidate_id>/status', methods=['PUT'])
@jwt_required()
def update_candidate_status(candidate_id):
    try:
        user_id = int(get_jwt_identity())  # Convert to int for DB queries
        
        # Get candidate first
        candidate = Resume.query.get(candidate_id)
        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404
        
        # Check if job belongs to user
        job = Job.query.filter_by(id=candidate.job_id, user_id=user_id).first()
        if not job:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['new', 'shortlisted', 'rejected', 'hired']:
            return jsonify({'error': 'Invalid status'}), 400
        
        old_status = candidate.status
        candidate.status = new_status
        db.session.commit()
        
        # Send email notification if status changed to shortlisted, rejected, or hired
        if new_status in ['shortlisted', 'rejected', 'hired'] and old_status != new_status:
            try:
                user = User.query.get(job.user_id)
                company_name = user.company or 'HireLens'
                
                email_service = EmailService()
                email_service.send_status_change_email(
                    candidate_name=candidate.candidate_name,
                    candidate_email=candidate.email,
                    job_title=job.title,
                    old_status=old_status,
                    new_status=new_status,
                    company_name=company_name
                )
                logger.info(f"Status change email sent to {candidate.email} for status: {new_status}")
            except Exception as e:
                logger.error(f"Failed to send status change email: {str(e)}")
                # Don't fail the status update if email fails
        
        # Invalidate cache
        cache_delete(f"candidate_detail:{user_id}:{candidate_id}")
        cache_delete_pattern(f"candidates_job:{user_id}:{candidate.job_id}:*")
        cache_delete_pattern(f"candidates_all:{user_id}:*")
        cache_delete_pattern(f"dashboard_*:{user_id}")
        cache_delete(f"job_detail:{user_id}:{candidate.job_id}")
        
        # Create notification for status change
        if new_status != old_status:
            status_messages = {
                'shortlisted': f'{candidate.candidate_name} has been shortlisted',
                'rejected': f'{candidate.candidate_name} has been rejected',
                'hired': f'{candidate.candidate_name} has been hired! 🎉',
                'new': f'{candidate.candidate_name} status changed to new'
            }
            
            try:
                create_notification(
                    user_id=user_id,
                    notification_type='status_changed',
                    title='Candidate Status Updated',
                    message=status_messages.get(new_status, f'{candidate.candidate_name} status updated'),
                    related_type='candidate',
                    related_id=candidate_id,
                    action_url=f'/dashboard/candidates/{candidate_id}'
                )
            except Exception as e:
                logger.error(f"Failed to create notification: {str(e)}")
        
        return jsonify({
            'message': 'Status updated successfully',
            'candidate': candidate.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update candidate status error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@candidates_bp.route('/detail/<int:candidate_id>', methods=['DELETE'])
@jwt_required()
def delete_candidate(candidate_id):
    try:
        user_id = get_jwt_identity()
        
        candidate = Resume.query.join(Job).filter(
            Resume.id == candidate_id,
            Job.user_id == user_id
        ).first()
        
        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404
        
        job_id = candidate.job_id
        
        # Delete the candidate
        db.session.delete(candidate)
        db.session.commit()
        
        # Invalidate cache
        cache_delete(f"candidate_detail:{user_id}:{candidate_id}")
        cache_delete_pattern(f"candidates_job:{user_id}:{job_id}:*")
        cache_delete_pattern(f"candidates_all:{user_id}:*")
        cache_delete_pattern(f"dashboard_*:{user_id}")
        cache_delete(f"job_detail:{user_id}:{job_id}")
        
        return jsonify({'message': 'Candidate deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete candidate error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@candidates_bp.route('/detail/<int:candidate_id>/download', methods=['GET'])
@jwt_required()
def download_resume(candidate_id):
    try:
        user_id = int(get_jwt_identity())  # Convert to int for DB queries
        
        # Get candidate first
        candidate = Resume.query.get(candidate_id)
        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404
        
        # Check if job belongs to user
        job = Job.query.filter_by(id=candidate.job_id, user_id=user_id).first()
        if not job:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        if not os.path.exists(candidate.file_path):
            return jsonify({'error': 'Resume file not found'}), 404
        
        return send_file(
            candidate.file_path,
            as_attachment=False,  # Open in browser instead of downloading
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Download resume error: {str(e)}")
        return jsonify({'error': str(e)}), 500
