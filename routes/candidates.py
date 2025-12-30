from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.job import Job
from models.resume import Resume
from extensions import db

candidates_bp = Blueprint('candidates', __name__)

@candidates_bp.route('/<int:job_id>', methods=['GET'])
@jwt_required()
def get_candidates(job_id):
    try:
        user_id = get_jwt_identity()
        
        job = Job.query.filter_by(id=job_id, user_id=user_id).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Query parameters
        status = request.args.get('status')
        min_score = request.args.get('min_score', type=float)
        sort_by = request.args.get('sort_by', 'score')  # score, date
        
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
        
        candidates = query.all()
        
        return jsonify({
            'candidates': [c.to_dict() for c in candidates],
            'total': len(candidates)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@candidates_bp.route('/all', methods=['GET'])
@jwt_required()
def get_all_candidates():
    try:
        user_id = get_jwt_identity()
        
        # Get all candidates across all user's jobs
        candidates = Resume.query.join(Job).filter(
            Job.user_id == user_id
        ).order_by(Resume.ai_score.desc()).all()
        
        return jsonify({
            'candidates': [c.to_dict() for c in candidates],
            'total': len(candidates)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
