from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.job import Job
from models.resume import Resume
from models.interview import Interview
from models.user import User
from extensions import db, cache_delete_pattern
from services.email_service import EmailService
from routes.notifications import create_notification
from datetime import datetime
import logging

interviews_bp = Blueprint('interviews', __name__)
logger = logging.getLogger(__name__)

@interviews_bp.route('/', methods=['POST'])
@jwt_required()
def schedule_interview():
    """Schedule an interview for a candidate"""
    try:
        user_id = int(get_jwt_identity())  # Convert to int for DB queries
        data = request.get_json()
        
        resume_id = data.get('resume_id')
        job_id = data.get('job_id')
        interview_type = data.get('interview_type', 'screening')
        scheduled_date = data.get('scheduled_date')  # ISO format string
        duration_minutes = data.get('duration_minutes', 60)
        interview_mode = data.get('interview_mode', 'video')
        meeting_link = data.get('meeting_link', '')
        location = data.get('location', '')
        interviewer_name = data.get('interviewer_name', '')
        interviewer_email = data.get('interviewer_email', '')
        notes = data.get('notes', '')
        
        # Validate required fields
        if not resume_id or not job_id or not scheduled_date:
            return jsonify({'error': 'resume_id, job_id, and scheduled_date are required'}), 400
        
        # Verify job belongs to user
        job = Job.query.filter_by(id=job_id, user_id=user_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Verify candidate exists
        candidate = Resume.query.filter_by(id=resume_id, job_id=job_id).first()
        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404
        
        # Parse date
        try:
            interview_date = datetime.fromisoformat(scheduled_date.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use ISO format'}), 400
        
        # Create interview
        interview = Interview(
            resume_id=resume_id,
            job_id=job_id,
            interview_type=interview_type,
            scheduled_date=interview_date,
            duration_minutes=duration_minutes,
            interview_mode=interview_mode,
            meeting_link=meeting_link,
            location=location,
            interviewer_name=interviewer_name,
            interviewer_email=interviewer_email,
            notes=notes,
            status='scheduled'
        )
        
        db.session.add(interview)
        db.session.commit()
        
        # Send email invitation
        try:
            user = User.query.get(user_id)
            company_name = user.company or 'HireLens'
            
            email_service = EmailService()
            email_service.send_interview_invitation(
                candidate_name=candidate.candidate_name,
                candidate_email=candidate.email,
                job_title=job.title,
                interview_date=interview_date.strftime('%B %d, %Y at %I:%M %p'),
                interview_type=interview_type.capitalize(),
                meeting_link=meeting_link,
                duration_minutes=duration_minutes,
                company_name=company_name
            )
            logger.info(f"Interview invitation sent to {candidate.email}")
        except Exception as e:
            logger.error(f"Failed to send interview invitation: {str(e)}")
        
        # Invalidate caches
        cache_delete_pattern(f"interviews:*:{resume_id}")
        cache_delete_pattern(f"interviews:*:{job_id}")
        
        # Create notification for recruiter
        try:
            create_notification(
                user_id=user_id,
                notification_type='interview_scheduled',
                title='Interview Scheduled',
                message=f'Interview scheduled with {candidate.candidate_name} for {job.title}',
                related_type='interview',
                related_id=interview.id,
                action_url=f'/dashboard/candidates/{resume_id}'
            )
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
        
        return jsonify({
            'message': 'Interview scheduled successfully',
            'interview': interview.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Schedule interview error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@interviews_bp.route('/candidate/<int:resume_id>', methods=['GET'])
@jwt_required()
def get_candidate_interviews(resume_id):
    """Get all interviews for a candidate"""
    try:
        user_id = int(get_jwt_identity())  # Convert to int for DB queries
        
        # Get the candidate first
        candidate = Resume.query.get(resume_id)
        if not candidate:
            # Return empty list if candidate not found
            return jsonify({
                'interviews': [],
                'total': 0
            }), 200
        
        # Check if candidate's job belongs to user
        job = Job.query.filter_by(id=candidate.job_id, user_id=user_id).first()
        if not job:
            # Return empty list if not authorized
            return jsonify({
                'interviews': [],
                'total': 0
            }), 200
        
        # Get interviews for this candidate
        interviews = Interview.query.filter_by(resume_id=resume_id).order_by(Interview.scheduled_date.desc()).all()
        
        return jsonify({
            'interviews': [i.to_dict() for i in interviews],
            'total': len(interviews)
        }), 200
        
    except Exception as e:
        logger.error(f"Get candidate interviews error: {str(e)}")
        db.session.rollback()  # Rollback on error to clean up session
        return jsonify({'error': 'Failed to fetch interviews'}), 500

@interviews_bp.route('/job/<int:job_id>', methods=['GET'])
@jwt_required()
def get_job_interviews(job_id):
    """Get all interviews for a job"""
    try:
        user_id = int(get_jwt_identity())  # Convert to int for DB queries
        
        # Verify job belongs to user
        job = Job.query.filter_by(id=job_id, user_id=user_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        interviews = Interview.query.filter_by(job_id=job_id).order_by(Interview.scheduled_date.desc()).all()
        
        # Include candidate details
        interviews_data = []
        for interview in interviews:
            interview_dict = interview.to_dict()
            candidate = Resume.query.get(interview.resume_id)
            if candidate:
                interview_dict['candidate_name'] = candidate.candidate_name
                interview_dict['candidate_email'] = candidate.email
            interviews_data.append(interview_dict)
        
        return jsonify({
            'interviews': interviews_data,
            'total': len(interviews_data)
        }), 200
        
    except Exception as e:
        logger.error(f"Get job interviews error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@interviews_bp.route('/<int:interview_id>', methods=['PUT'])
@jwt_required()
def update_interview(interview_id):
    """Update interview details or status"""
    try:
        user_id = int(get_jwt_identity())  # Convert to int for DB queries
        
        # Get interview first
        interview = Interview.query.get(interview_id)
        if not interview:
            return jsonify({'error': 'Interview not found'}), 404
        
        # Check if job belongs to user
        job = Job.query.filter_by(id=interview.job_id, user_id=user_id).first()
        if not job:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        data = request.get_json()
        
        # Update allowed fields
        if 'status' in data:
            interview.status = data['status']
        if 'feedback' in data:
            interview.feedback = data['feedback']
        if 'notes' in data:
            interview.notes = data['notes']
        if 'scheduled_date' in data:
            try:
                interview.scheduled_date = datetime.fromisoformat(data['scheduled_date'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400
        if 'meeting_link' in data:
            interview.meeting_link = data['meeting_link']
        if 'duration_minutes' in data:
            interview.duration_minutes = data['duration_minutes']
        
        db.session.commit()
        
        # Invalidate caches
        cache_delete_pattern(f"interviews:*:{interview.resume_id}")
        cache_delete_pattern(f"interviews:*:{interview.job_id}")
        
        return jsonify({
            'message': 'Interview updated successfully',
            'interview': interview.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update interview error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@interviews_bp.route('/<int:interview_id>', methods=['DELETE'])
@jwt_required()
def delete_interview(interview_id):
    """Cancel/delete an interview"""
    try:
        user_id = int(get_jwt_identity())  # Convert to int for DB queries
        
        # Get interview first
        interview = Interview.query.get(interview_id)
        if not interview:
            return jsonify({'error': 'Interview not found'}), 404
        
        # Check if job belongs to user
        job = Job.query.filter_by(id=interview.job_id, user_id=user_id).first()
        if not job:
            return jsonify({'error': 'Unauthorized access'}), 403
        
        resume_id = interview.resume_id
        job_id = interview.job_id
        
        db.session.delete(interview)
        db.session.commit()
        
        # Invalidate caches
        cache_delete_pattern(f"interviews:*:{resume_id}")
        cache_delete_pattern(f"interviews:*:{job_id}")
        
        return jsonify({'message': 'Interview cancelled successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete interview error: {str(e)}")
        return jsonify({'error': str(e)}), 500
