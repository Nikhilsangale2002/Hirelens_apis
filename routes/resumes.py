from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from models.user import User
from models.job import Job
from models.resume import Resume
from routes.notifications import create_notification
from extensions import db, cache_delete_pattern
from config import Config
from services.resume_parser import ResumeParser
from services.ai_scorer import AIScorer
import os
import logging

resumes_bp = Blueprint('resumes', __name__)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

# Public endpoint for candidate applications (no authentication required)
@resumes_bp.route('/<int:job_id>/upload', methods=['POST'])
def public_upload_resume(job_id):
    """Public endpoint for candidates to apply to jobs"""
    try:
        # Check if job exists and is active
        job = Job.query.filter_by(id=job_id, status='active').first()
        if not job:
            return jsonify({'error': 'Job not found or not accepting applications'}), 404
        
        # Check if file is present
        if 'resume' not in request.files:
            return jsonify({'error': 'No resume file provided'}), 400
        
        file = request.files['resume']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed. Please upload PDF or Word document'}), 400
        
        # Get candidate info from form
        candidate_name = request.form.get('candidate_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        location = request.form.get('location', '').strip()
        linkedin = request.form.get('linkedin', '').strip()
        portfolio = request.form.get('portfolio', '').strip()
        cover_letter = request.form.get('cover_letter', '').strip()
        
        # Validate required fields
        if not candidate_name or not email or not phone:
            return jsonify({'error': 'Name, email, and phone are required'}), 400
        
        # Save file
        filename = secure_filename(file.filename)
        upload_path = os.path.join(Config.UPLOAD_FOLDER, 'public', str(job_id))
        os.makedirs(upload_path, exist_ok=True)
        
        # Generate unique filename to avoid conflicts
        import time
        unique_filename = f"{int(time.time())}_{filename}"
        file_path = os.path.join(upload_path, unique_filename)
        file.save(file_path)
        
        # Create resume record
        resume = Resume(
            job_id=job_id,
            filename=unique_filename,
            file_path=file_path,
            candidate_name=candidate_name,
            email=email,
            phone=phone,
            location=location,
            status='new',
            processing_status='pending'
        )
        
        db.session.add(resume)
        db.session.commit()
        
        # Process resume (parse and AI score)
        try:
            process_resume_public(resume.id, job_id, {
                'linkedin': linkedin,
                'portfolio': portfolio,
                'cover_letter': cover_letter
            })
        except Exception as e:
            logger.error(f"Error processing resume: {e}")
        
        # Invalidate candidate caches
        cache_delete_pattern(f"candidates_job:*:{job_id}:*")
        cache_delete_pattern(f"candidates_all:*")
        
        return jsonify({
            'message': 'Application submitted successfully! We will review your resume and get back to you soon.',
            'resume_id': resume.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error uploading public resume: {str(e)}")
        return jsonify({'error': 'Failed to submit application. Please try again.'}), 500

def process_resume_public(resume_id, job_id, additional_info):
    """Process public resume - parse and score"""
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
        
        print(f"\n{'='*60}")
        print(f"RESUME PARSING RESULTS for Resume #{resume_id}")
        print(f"{'='*60}")
        print(f"Job Title: {job.title}")
        print(f"Job Required Skills: {job.skills_required}")
        print(f"Extracted Skills: {parsed_data.get('skills', [])}")
        print(f"Experience: {parsed_data.get('experience_years', 0)} years")
        print(f"Education: {parsed_data.get('education_level', 'Unknown')}")
        print(f"{'='*60}\n")
        
        # Update resume with parsed data
        if not resume.candidate_name and parsed_data.get('name'):
            resume.candidate_name = parsed_data.get('name')
        if not resume.email and parsed_data.get('email'):
            resume.email = parsed_data.get('email')
        if not resume.phone and parsed_data.get('phone'):
            resume.phone = parsed_data.get('phone')
        if not resume.location and parsed_data.get('location'):
            resume.location = parsed_data.get('location')
            
        resume.experience_years = parsed_data.get('experience_years', 0)
        resume.education_level = parsed_data.get('education_level')
        resume.parsed_data = {**parsed_data, **additional_info}
        
        # Score resume with AI
        scorer = AIScorer()
        score_result = scorer.score_resume(parsed_data, job)
        
        print(f"\n{'='*60}")
        print(f"AI SCORING RESULTS for Resume #{resume_id}")
        print(f"{'='*60}")
        print(f"AI Score: {score_result['score']}")
        print(f"Matched Skills: {score_result['matched_skills']}")
        print(f"Missing Skills: {score_result['missing_skills']}")
        print(f"Explanation: {score_result['explanation']}")
        print(f"{'='*60}\n")
        
        resume.ai_score = score_result['score']
        resume.matched_skills = score_result['matched_skills']
        resume.missing_skills = score_result['missing_skills']
        resume.ai_explanation = score_result['explanation']
        
        resume.processing_status = 'completed'
        db.session.commit()
        
        logger.info(f"Resume {resume_id} processed successfully with AI score: {resume.ai_score}")
        
    except Exception as e:
        logger.error(f"Error processing public resume {resume_id}: {e}")
        if resume:
            resume.processing_status = 'failed'
            db.session.commit()

# Admin endpoint for manual resume upload (requires authentication)
@resumes_bp.route('/admin/upload/<int:job_id>', methods=['POST'])
@jwt_required()
def admin_upload_resume(job_id):
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
        
        # Create notification for job owner
        create_notification(
            user_id=job.user_id,
            notification_type='resume_uploaded',
            title='New Resume Received',
            message=f'A new candidate has applied for {job.title}',
            related_type='candidate',
            related_id=resume.id,
            action_url=f'/dashboard/candidates/{resume.id}'
        )
        
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
