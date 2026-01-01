from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import User
from models.job import Job
from models.resume import Resume
from extensions import db, cache_get, cache_set, cache_delete, cache_delete_pattern
from routes.notifications import create_notification
from config import Config
from utils.pagination import paginate, paginate_response
import logging

jobs_bp = Blueprint('jobs', __name__)
logger = logging.getLogger(__name__)

# Public endpoint for careers page (no authentication required)
@jobs_bp.route('/public', methods=['GET'])
def get_public_jobs():
    """Get all active jobs for public careers page (no auth required)"""
    try:
        # Check cache first
        cache_key = 'jobs_public_active'
        cached_data = cache_get(cache_key)
        if cached_data:
            logger.info("Returning cached public jobs")
            return jsonify({**cached_data, 'cached': True}), 200
        
        # Query only active jobs
        jobs = Job.query.filter_by(status='active').order_by(Job.created_at.desc()).all()
        
        # Return basic job info (no sensitive data)
        jobs_data = [{
            'id': job.id,
            'title': job.title,
            'description': job.description,
            'department': job.department,
            'location': job.location,
            'job_type': job.job_type,
            'experience_required': job.experience_required,
            'skills_required': job.skills_required,
            'education': job.education,
            'salary_range': job.salary_range,
            'created_at': job.created_at.isoformat() if job.created_at else None
        } for job in jobs]
        
        response_data = {
            'jobs': jobs_data,
            'total': len(jobs_data),
            'cached': False
        }
        
        # Cache for 5 minutes
        cache_set(cache_key, response_data, expire=300)
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching public jobs: {str(e)}")
        return jsonify({'error': 'Failed to load jobs'}), 500

# Public endpoint for single job detail (no authentication required)
@jobs_bp.route('/public/<int:job_id>', methods=['GET'])
def get_public_job(job_id):
    """Get single active job details for public view (no auth required)"""
    try:
        # Check cache first
        cache_key = f'job_public_detail:{job_id}'
        cached_data = cache_get(cache_key)
        if cached_data:
            logger.info(f"Returning cached public job {job_id}")
            return jsonify({**cached_data, 'cached': True}), 200
        
        # Only allow fetching active jobs publicly
        job = Job.query.filter_by(id=job_id, status='active').first()
        
        if not job:
            return jsonify({'error': 'Job not found or not available'}), 404
        
        # Return basic job info (no sensitive data like user_id)
        job_data = {
            'id': job.id,
            'title': job.title,
            'description': job.description,
            'department': job.department,
            'location': job.location,
            'job_type': job.job_type,
            'experience_required': job.experience_required,
            'skills_required': job.skills_required,
            'education': job.education,
            'salary_range': job.salary_range,
            'created_at': job.created_at.isoformat() if job.created_at else None
        }
        
        response_data = {'job': job_data, 'cached': False}
        
        # Cache for 5 minutes
        cache_set(cache_key, response_data, expire=300)
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching public job {job_id}: {str(e)}")
        return jsonify({'error': 'Failed to load job details'}), 500

@jobs_bp.route('/', methods=['POST'])
@jwt_required()
def create_job():
    try:
        # Get user from JWT
        user_id = int(get_jwt_identity())  # Convert to int for DB queries
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check plan limits
        plan_config = Config.PLANS.get(user.plan, Config.PLANS['starter'])
        jobs_limit = plan_config['jobs_limit']
        
        if jobs_limit != -1 and user.jobs_used >= jobs_limit:
            return jsonify({'error': f'Job limit reached for {user.plan} plan'}), 403
        
        data = request.get_json()
        
        job = Job(
            user_id=user_id,
            title=data.get('title'),
            description=data.get('description'),
            department=data.get('department'),
            location=data.get('location'),
            job_type=data.get('job_type', 'Full-time'),
            experience_required=data.get('experience_required'),
            skills_required=data.get('skills_required', []),
            education=data.get('education'),
            salary_range=data.get('salary_range'),
            status='active'
        )
        
        db.session.add(job)
        user.jobs_used += 1
        db.session.commit()
        
        # Invalidate cache
        cache_delete(f"jobs_list:{user_id}")
        cache_delete_pattern(f"dashboard_*:{user_id}")
        cache_delete(f"user_plan:{user_id}")
        # Invalidate public cache when new job is created
        cache_delete('jobs_public_active')
        
        # Create notification for job creation
        try:
            create_notification(
                user_id=user_id,
                notification_type='job_created',
                title='New Job Posted',
                message=f'Successfully posted job: {job.title}',
                related_type='job',
                related_id=job.id,
                action_url=f'/dashboard/jobs/{job.id}'
            )
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
        
        return jsonify({
            'message': 'Job created successfully',
            'job': job.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/', methods=['GET'])
@jwt_required()
def get_jobs():
    """Get paginated list of user's jobs"""
    try:
        user_id = int(get_jwt_identity())
        status = request.args.get('status')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Create cache key based on filters
        cache_key = f"jobs_list:{user_id}:{status or 'all'}:p{page}:pp{per_page}"
        
        # Try to get from cache
        cached_data = cache_get(cache_key)
        if cached_data:
            return jsonify({**cached_data, 'cached': True}), 200
        
        # Build query
        query = Job.query.filter_by(user_id=user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        query = query.order_by(Job.created_at.desc())
        
        # Paginate
        paginated = paginate(query, page=page, per_page=per_page)
        response_data = paginate_response(paginated)
        
        # Restructure response to match frontend expectations (jobs instead of data)
        frontend_response = {
            'jobs': response_data['data'],
            'pagination': response_data['pagination'],
            'cached': False
        }
        
        # Cache for 3 minutes (cache without the 'cached' flag)
        cache_set(cache_key, {
            'jobs': response_data['data'],
            'pagination': response_data['pagination']
        }, expire=180)
        
        return jsonify(frontend_response), 200
        
    except Exception as e:
        logger.error(f"Get jobs error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/<int:job_id>', methods=['GET'])
@jwt_required()
def get_job(job_id):
    try:
        user_id = int(get_jwt_identity())  # Convert to int for DB queries
        
        # Cache key for individual job
        cache_key = f"job_detail:{user_id}:{job_id}"
        
        # Try to get from cache
        cached_data = cache_get(cache_key)
        if cached_data:
            return jsonify({
                'job': cached_data,
                'cached': True
            }), 200
        
        job = Job.query.filter_by(id=job_id, user_id=user_id).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # to_dict will calculate counts internally
        job_data = job.to_dict(include_resumes=False, include_counts=True)
        
        # Cache for 2 minutes
        cache_set(cache_key, job_data, expire=120)
        
        return jsonify({
            'job': job_data,
            'cached': False
        }), 200
        
    except Exception as e:
        logger.error(f"Get job error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/<int:job_id>', methods=['PUT'])
@jwt_required()
def update_job(job_id):
    try:
        user_id = int(get_jwt_identity())  # Convert to int for DB queries
        
        job = Job.query.filter_by(id=job_id, user_id=user_id).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        data = request.get_json()
        
        if 'title' in data:
            job.title = data['title']
        if 'description' in data:
            job.description = data['description']
        if 'department' in data:
            job.department = data['department']
        if 'location' in data:
            job.location = data['location']
        if 'job_type' in data:
            job.job_type = data['job_type']
        if 'experience_required' in data:
            job.experience_required = data['experience_required']
        if 'skills_required' in data:
            job.skills_required = data['skills_required']
        if 'education' in data:
            job.education = data['education']
        if 'salary_range' in data:
            job.salary_range = data['salary_range']
        if 'status' in data:
            job.status = data['status']
        
        db.session.commit()
        
        # Invalidate cache
        cache_delete(f"job_detail:{user_id}:{job_id}")
        cache_delete_pattern(f"jobs_list:{user_id}:*")
        cache_delete_pattern(f"dashboard_*:{user_id}")
        # Invalidate public cache when job is updated
        cache_delete('jobs_public_active')
        cache_delete(f'job_public_detail:{job_id}')
        
        return jsonify({
            'message': 'Job updated successfully',
            'job': job.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/<int:job_id>', methods=['DELETE'])
@jwt_required()
def delete_job(job_id):
    try:
        user_id = int(get_jwt_identity())  # Convert to int for DB queries
        
        job = Job.query.filter_by(id=job_id, user_id=user_id).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        db.session.delete(job)
        db.session.commit()
        
        # Invalidate cache
        cache_delete(f"job_detail:{user_id}:{job_id}")
        cache_delete_pattern(f"jobs_list:{user_id}:*")
        cache_delete_pattern(f"dashboard_*:{user_id}")
        # Invalidate public cache when job is deleted
        cache_delete('jobs_public_active')
        cache_delete(f'job_public_detail:{job_id}')
        
        return jsonify({'message': 'Job deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
