from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from models.user import User
from models.job import Job
from models.resume import Resume
from extensions import db
from config import Config
from services.resume_parser import ResumeParser
from services.ai_scorer import AIScorer
import os

resumes_bp = Blueprint('resumes', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

@resumes_bp.route('/upload/<int:job_id>', methods=['POST'])
@jwt_required()
def upload_resume(job_id):
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check plan limits
        plan_config = Config.PLANS.get(user.plan, Config.PLANS['starter'])
        resumes_limit = plan_config['resumes_limit']
        
        if resumes_limit != -1 and user.resumes_used >= resumes_limit:
            return jsonify({'error': f'Resume limit reached for {user.plan} plan'}), 403
        
        # Check job exists
        job = Job.query.filter_by(id=job_id, user_id=user_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed. Use PDF or DOCX'}), 400
        
        # Save file
        filename = secure_filename(file.filename)
        upload_path = os.path.join(Config.UPLOAD_FOLDER, str(user_id), str(job_id))
        os.makedirs(upload_path, exist_ok=True)
        
        file_path = os.path.join(upload_path, filename)
        file.save(file_path)
        
        # Create resume record
        resume = Resume(
            job_id=job_id,
            filename=filename,
            file_path=file_path,
            processing_status='pending'
        )
        
        db.session.add(resume)
        user.resumes_used += 1
        db.session.commit()
        
        # Start async processing (in production, use Celery or background task)
        try:
            process_resume(resume.id, job_id)
        except Exception as e:
            print(f"Error processing resume: {e}")
        
        return jsonify({
            'message': 'Resume uploaded successfully',
            'resume': resume.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def process_resume(resume_id, job_id):
    """Process resume - parse and score"""
    try:
        resume = Resume.query.get(resume_id)
        job = Job.query.get(job_id)
        
        if not resume or not job:
            return
        
        resume.processing_status = 'processing'
        db.session.commit()
        
        # Parse resume
        parser = ResumeParser()
        parsed_data = parser.parse(resume.file_path)
        
        # Update resume with parsed data
        resume.candidate_name = parsed_data.get('name')
        resume.email = parsed_data.get('email')
        resume.phone = parsed_data.get('phone')
        resume.location = parsed_data.get('location')
        resume.experience_years = parsed_data.get('experience_years', 0)
        resume.education_level = parsed_data.get('education_level')
        resume.parsed_data = parsed_data
        
        # Score resume
        scorer = AIScorer()
        score_result = scorer.score_resume(parsed_data, job)
        
        resume.ai_score = score_result['score']
        resume.matched_skills = score_result['matched_skills']
        resume.missing_skills = score_result['missing_skills']
        resume.ai_explanation = score_result['explanation']
        
        resume.processing_status = 'completed'
        db.session.commit()
        
    except Exception as e:
        print(f"Error processing resume {resume_id}: {e}")
        if resume:
            resume.processing_status = 'failed'
            db.session.commit()

@resumes_bp.route('/<int:resume_id>', methods=['GET'])
@jwt_required()
def get_resume(resume_id):
    try:
        user_id = get_jwt_identity()
        
        resume = Resume.query.join(Job).filter(
            Resume.id == resume_id,
            Job.user_id == user_id
        ).first()
        
        if not resume:
            return jsonify({'error': 'Resume not found'}), 404
        
        return jsonify({'resume': resume.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@resumes_bp.route('/<int:resume_id>/status', methods=['PUT'])
@jwt_required()
def update_resume_status(resume_id):
    try:
        user_id = get_jwt_identity()
        
        resume = Resume.query.join(Job).filter(
            Resume.id == resume_id,
            Job.user_id == user_id
        ).first()
        
        if not resume:
            return jsonify({'error': 'Resume not found'}), 404
        
        data = request.get_json()
        status = data.get('status')
        
        if status not in ['new', 'shortlisted', 'rejected']:
            return jsonify({'error': 'Invalid status'}), 400
        
        resume.status = status
        db.session.commit()
        
        return jsonify({
            'message': 'Status updated successfully',
            'resume': resume.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@resumes_bp.route('/<int:resume_id>', methods=['DELETE'])
@jwt_required()
def delete_resume(resume_id):
    try:
        user_id = get_jwt_identity()
        
        resume = Resume.query.join(Job).filter(
            Resume.id == resume_id,
            Job.user_id == user_id
        ).first()
        
        if not resume:
            return jsonify({'error': 'Resume not found'}), 404
        
        # Delete file
        if resume.file_path and os.path.exists(resume.file_path):
            os.remove(resume.file_path)
        
        db.session.delete(resume)
        db.session.commit()
        
        return jsonify({'message': 'Resume deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
