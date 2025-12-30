from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import User
from models.job import Job
from extensions import db
from config import Config

jobs_bp = Blueprint('jobs', __name__)

@jobs_bp.route('/', methods=['POST'])
@jwt_required()
def create_job():
    try:
        # Get user from JWT
        user_id = get_jwt_identity()
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
    try:
        user_id = get_jwt_identity()
        
        status = request.args.get('status')
        
        query = Job.query.filter_by(user_id=user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        jobs = query.order_by(Job.created_at.desc()).all()
        
        return jsonify({
            'jobs': [job.to_dict() for job in jobs]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/<int:job_id>', methods=['GET'])
@jwt_required()
def get_job(job_id):
    try:
        user_id = get_jwt_identity()
        
        job = Job.query.filter_by(id=job_id, user_id=user_id).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify({'job': job.to_dict(include_resumes=True)}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@jobs_bp.route('/<int:job_id>', methods=['PUT'])
@jwt_required()
def update_job(job_id):
    try:
        user_id = get_jwt_identity()
        
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
        user_id = get_jwt_identity()
        
        job = Job.query.filter_by(id=job_id, user_id=user_id).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        db.session.delete(job)
        db.session.commit()
        
        return jsonify({'message': 'Job deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
