"""
AI Interview Routes
Handles AI-powered interview operations
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.interview import Interview
from models.job import Job
from models.resume import Resume
from models.interview_security_log import InterviewSecurityLog
from extensions import db, cache_get, cache_set, cache_delete, redis_client
from services.ai_interview_service import ai_interview_service
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

ai_interviews = Blueprint('ai_interviews', __name__)


@ai_interviews.route('/interviews/<int:interview_id>/verify-access', methods=['POST'])
def verify_access(interview_id):
    """
    Verify candidate access to AI interview using email and access code
    With Redis-based rate limiting and multi-device detection
    """
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        access_code = data.get('access_code', '').strip().upper()
        
        if not email or not access_code:
            return jsonify({'error': 'Email and access code are required'}), 400
        
        # Get IP address
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        # Redis rate limiting - max 5 attempts per IP per interview in 5 minutes
        rate_limit_key = f"login_attempts:{interview_id}:{ip_address}"
        if redis_client:
            attempts = redis_client.get(rate_limit_key)
            if attempts and int(attempts) >= 5:
                logger.warning(f"Rate limit exceeded for interview {interview_id} from IP {ip_address}")
                return jsonify({'error': 'Too many login attempts. Please try again in 5 minutes.'}), 429
        
        # Get the interview
        interview = Interview.query.filter_by(id=interview_id).first()
        if not interview:
            return jsonify({'error': 'Interview not found'}), 404
        
        # Get the resume to check candidate email
        resume = Resume.query.filter_by(id=interview.resume_id).first()
        if not resume:
            return jsonify({'error': 'Candidate not found'}), 404
        
        # Verify email matches
        if resume.email.strip().lower() != email:
            # Increment failed attempts
            if redis_client:
                redis_client.incr(rate_limit_key)
                redis_client.expire(rate_limit_key, 300)  # 5 minutes
            return jsonify({'error': 'Invalid email address'}), 401
        
        # Verify access code
        if not interview.access_code or interview.access_code != access_code:
            # Increment failed attempts
            if redis_client:
                redis_client.incr(rate_limit_key)
                redis_client.expire(rate_limit_key, 300)  # 5 minutes
            return jsonify({'error': 'Invalid access code'}), 401
        
        # Success - check for multi-device access
        device_key = f"interview_device:{interview_id}"
        if redis_client:
            existing_ip = redis_client.get(device_key)
            if existing_ip and existing_ip != ip_address:
                logger.critical(f"Multi-device access detected for interview {interview_id}: {existing_ip} vs {ip_address}")
                # Log security event
                security_log = InterviewSecurityLog(
                    interview_id=interview_id,
                    event_type='multi_device_detected',
                    timestamp=datetime.utcnow(),
                    ip_address=ip_address,
                    event_metadata={'original_ip': existing_ip, 'new_ip': ip_address}
                )
                db.session.add(security_log)
                db.session.commit()
            
            # Store current device (expires in 24 hours)
            redis_client.setex(device_key, 86400, ip_address)
            
            # Clear login attempts on success
            redis_client.delete(rate_limit_key)
            
            # Create session
            session_key = f"interview_session:{interview_id}"
            session_data = {
                'email': email,
                'ip_address': ip_address,
                'verified_at': datetime.utcnow().isoformat(),
                'violations': 0
            }
            redis_client.setex(session_key, 86400, json.dumps(session_data))
        
        return jsonify({
            'message': 'Access verified',
            'interview_id': interview_id,
            'candidate_name': resume.candidate_name
        }), 200
        
    except Exception as e:
        print(f"Error verifying access: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to verify access'}), 500


@ai_interviews.route('/interviews/<int:interview_id>/generate-questions', methods=['POST'])
@jwt_required()
def generate_questions(interview_id):
    """
    Generate AI interview questions for a scheduled interview
    """
    try:
        user_id = int(get_jwt_identity())
        
        # Get the interview
        interview = Interview.query.filter_by(id=interview_id).first()
        if not interview:
            return jsonify({'error': 'Interview not found'}), 404
        
        # Get the job
        job = Job.query.filter_by(id=interview.job_id).first()
        if not job or job.user_id != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get the resume/candidate
        resume = Resume.query.filter_by(id=interview.resume_id).first()
        if not resume:
            return jsonify({'error': 'Resume not found'}), 404
        
        # Get parameters
        data = request.get_json() or {}
        num_questions = data.get('num_questions', 5)
        
        # Build required skills list
        required_skills = []
        if job.skills_required:
            try:
                skills_data = json.loads(job.skills_required) if isinstance(job.skills_required, str) else job.skills_required
                if isinstance(skills_data, list):
                    required_skills = skills_data
            except:
                pass
        
        # Get resume text for personalization
        resume_text = None
        if resume.parsed_data:
            try:
                parsed = json.loads(resume.parsed_data) if isinstance(resume.parsed_data, str) else resume.parsed_data
                # Extract text from parsed data - could be summary, experience, etc.
                text_parts = []
                if isinstance(parsed, dict):
                    for key in ['summary', 'experience', 'skills', 'education']:
                        if key in parsed and parsed[key]:
                            text_parts.append(str(parsed[key]))
                resume_text = ' '.join(text_parts)[:2000] if text_parts else None
            except:
                pass
        
        # Generate questions using AI
        questions = ai_interview_service.generate_interview_questions(
            job_title=job.title,
            job_description=job.description,
            required_skills=required_skills,
            candidate_resume=resume_text,
            num_questions=num_questions
        )
        
        # Store questions in interview
        interview.ai_questions = json.dumps(questions)
        interview.interview_status = 'pending'
        interview.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Questions generated successfully',
            'interview_id': interview_id,
            'questions': questions,
            'total_questions': len(questions)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error generating questions: {e}")
        return jsonify({'error': f'Failed to generate questions: {str(e)}'}), 500


@ai_interviews.route('/interviews/<int:interview_id>/questions', methods=['GET'])
def get_questions(interview_id):
    """
    Get AI interview questions (for candidate to view)
    No authentication required - candidates access via email link
    """
    try:
        print(f"=== GET QUESTIONS CALLED ===")
        print(f"Interview ID: {interview_id}")
        
        # Get the interview
        interview = Interview.query.filter_by(id=interview_id).first()
        print(f"Interview found: {interview is not None}")
        
        if not interview:
            print(f"Interview {interview_id} not found in database")
            return jsonify({'error': 'Interview not found'}), 404
        
        print(f"Interview status: {interview.interview_status}")
        print(f"AI questions exist: {interview.ai_questions is not None}")
        
        # Check if questions exist
        if not interview.ai_questions:
            print(f"No questions generated for interview {interview_id}")
            return jsonify({'error': 'Questions not generated yet'}), 404
        
        # Parse questions
        try:
            questions = json.loads(interview.ai_questions) if isinstance(interview.ai_questions, str) else interview.ai_questions
        except Exception as e:
            print(f"Error parsing questions: {e}")
            return jsonify({'error': 'Invalid questions data'}), 500
        
        # Get job and resume info
        job = Job.query.filter_by(id=interview.job_id).first()
        resume = Resume.query.filter_by(id=interview.resume_id).first()
        
        # Remove expected_points from questions (don't show to candidate)
        for q in questions:
            q.pop('expected_points', None)
        
        return jsonify({
            'interview_id': interview_id,
            'job_title': job.title if job else None,
            'candidate_name': resume.candidate_name if resume else None,
            'interview_status': interview.interview_status,
            'questions': questions,
            'total_questions': len(questions),
            'duration_minutes': interview.duration_minutes,
            'scheduled_date': interview.scheduled_date.isoformat() if interview.scheduled_date else None
        }), 200
        
    except Exception as e:
        print(f"Error getting questions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to get questions: {str(e)}'}), 500


@ai_interviews.route('/interviews/<int:interview_id>/submit-answer', methods=['POST'])
def submit_answer(interview_id):
    """
    Submit answer to a single question
    No authentication required - candidates access via email link
    """
    try:
        # Get the interview
        interview = Interview.query.filter_by(id=interview_id).first()
        if not interview:
            return jsonify({'error': 'Interview not found'}), 404
        
        # Get request data
        data = request.get_json()
        question_id = data.get('question_id')
        answer = data.get('answer', '').strip()
        
        if not question_id or not answer:
            return jsonify({'error': 'Question ID and answer are required'}), 400
        
        # Get questions
        if not interview.ai_questions:
            return jsonify({'error': 'Questions not found'}), 404
        
        try:
            questions = json.loads(interview.ai_questions) if isinstance(interview.ai_questions, str) else interview.ai_questions
        except:
            return jsonify({'error': 'Invalid questions data'}), 500
        
        # Find the question
        question_data = None
        for q in questions:
            if q.get('id') == question_id:
                question_data = q
                break
        
        if not question_data:
            return jsonify({'error': 'Question not found'}), 404
        
        # Store the answer
        question_data['answer'] = answer
        question_data['answered_at'] = datetime.utcnow().isoformat()
        
        # Update interview
        interview.ai_questions = json.dumps(questions)
        interview.interview_status = 'in_progress'
        interview.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Answer submitted successfully',
            'question_id': question_id,
            'answered': True
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error submitting answer: {e}")
        return jsonify({'error': f'Failed to submit answer: {str(e)}'}), 500


@ai_interviews.route('/interviews/<int:interview_id>/complete', methods=['POST'])
def complete_interview(interview_id):
    """
    Mark interview as completed and trigger AI analysis
    No authentication required - candidates access via email link
    """
    try:
        # Get the interview
        interview = Interview.query.filter_by(id=interview_id).first()
        if not interview:
            return jsonify({'error': 'Interview not found'}), 404
        
        # Get questions
        if not interview.ai_questions:
            return jsonify({'error': 'Questions not found'}), 404
        
        try:
            questions = json.loads(interview.ai_questions) if isinstance(interview.ai_questions, str) else interview.ai_questions
        except:
            return jsonify({'error': 'Invalid questions data'}), 500
        
        # Check if all questions are answered
        unanswered = [q['id'] for q in questions if not q.get('answer')]
        if unanswered:
            return jsonify({
                'error': 'Not all questions answered',
                'unanswered_questions': unanswered
            }), 400
        
        # Analyze each answer
        for question in questions:
            if not question.get('score'):  # Don't re-analyze
                try:
                    analysis = ai_interview_service.analyze_answer(
                        question=question['question'],
                        answer=question['answer'],
                        expected_points=question.get('expected_points', []),
                        max_score=question.get('max_score', 20)
                    )
                    
                    question['score'] = analysis.get('score', 0)
                    question['feedback'] = analysis.get('feedback', '')
                    question['covered_points'] = analysis.get('covered_points', [])
                    question['missed_points'] = analysis.get('missed_points', [])
                    question['strengths'] = analysis.get('strengths', [])
                    question['improvements'] = analysis.get('improvements', [])
                    
                except Exception as e:
                    print(f"Error analyzing question {question['id']}: {e}")
                    question['score'] = 0
                    question['feedback'] = "Analysis unavailable"
        
        # Get job for overall analysis
        job = Job.query.filter_by(id=interview.job_id).first()
        job_title = job.title if job else "Position"
        
        # Perform overall analysis
        overall_analysis = ai_interview_service.analyze_complete_interview(
            questions_with_answers=questions,
            job_title=job_title
        )
        
        # Update interview
        interview.ai_questions = json.dumps(questions)
        interview.ai_responses = json.dumps([{
            'question_id': q['id'],
            'answer': q.get('answer'),
            'score': q.get('score', 0)
        } for q in questions])
        interview.ai_analysis = json.dumps(overall_analysis)
        interview.ai_score = overall_analysis.get('percentage', 0)
        interview.ai_feedback = overall_analysis.get('summary', '')
        interview.interview_status = 'completed'
        interview.completed_at = datetime.utcnow()
        interview.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Interview completed and analyzed successfully',
            'interview_id': interview_id,
            'ai_score': interview.ai_score,
            'recommendation': overall_analysis.get('recommendation'),
            'total_questions': len(questions)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error completing interview: {e}")
        return jsonify({'error': f'Failed to complete interview: {str(e)}'}), 500


@ai_interviews.route('/interviews/<int:interview_id>/analysis', methods=['GET'])
@jwt_required()
def get_analysis(interview_id):
    """
    Get detailed AI analysis of completed interview (for recruiter)
    """
    try:
        user_id = int(get_jwt_identity())
        
        # Get the interview
        interview = Interview.query.filter_by(id=interview_id).first()
        if not interview:
            return jsonify({'error': 'Interview not found'}), 404
        
        # Check authorization (must be job owner)
        job = Job.query.filter_by(id=interview.job_id).first()
        if not job or job.user_id != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Check if completed
        if interview.interview_status != 'completed':
            return jsonify({'error': 'Interview not completed yet'}), 400
        
        # Parse data
        try:
            questions = json.loads(interview.ai_questions) if interview.ai_questions else []
            analysis = json.loads(interview.ai_analysis) if interview.ai_analysis else {}
        except:
            return jsonify({'error': 'Invalid analysis data'}), 500
        
        # Get resume info
        resume = Resume.query.filter_by(id=interview.resume_id).first()
        
        return jsonify({
            'interview_id': interview_id,
            'candidate_name': resume.candidate_name if resume else None,
            'candidate_email': resume.email if resume else None,
            'job_title': job.title,
            'interview_status': interview.interview_status,
            'completed_at': interview.completed_at.isoformat() if interview.completed_at else None,
            'ai_score': float(interview.ai_score) if interview.ai_score else 0,
            'questions_with_answers': questions,
            'overall_analysis': analysis,
            'total_questions': len(questions)
        }), 200
        
    except Exception as e:
        print(f"Error getting analysis: {e}")
        return jsonify({'error': f'Failed to get analysis: {str(e)}'}), 500


@ai_interviews.route('/interviews/<int:interview_id>/log-activity', methods=['POST'])
def log_activity(interview_id):
    """
    Log security and activity events during AI interview
    With Redis-based real-time violation tracking
    """
    try:
        data = request.get_json()
        event_type = data.get('event_type', 'unknown')
        timestamp_str = data.get('timestamp')
        metadata = data.get('metadata', {})
        
        # Get IP address
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        
        # Extract key metrics
        violations = metadata.get('violations', 0)
        device_fingerprint = metadata.get('deviceFingerprint', {})
        
        # Parse timestamp
        try:
            log_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')) if timestamp_str else datetime.utcnow()
        except:
            log_timestamp = datetime.utcnow()
        
        # Update Redis session with violations
        session_key = f"interview_session:{interview_id}"
        if redis_client:
            session_data = redis_client.get(session_key)
            if session_data:
                session = json.loads(session_data)
                session['violations'] = violations
                session['last_activity'] = log_timestamp.isoformat()
                session['last_event'] = event_type
                redis_client.setex(session_key, 86400, json.dumps(session))
            
            # Track real-time violations
            violation_key = f"interview_violations:{interview_id}"
            redis_client.setex(violation_key, 86400, violations)
            
            # Check for IP address changes (potential device switch)
            if session_data:
                session = json.loads(session_data)
                original_ip = session.get('ip_address')
                if original_ip and original_ip != ip_address:
                    logger.critical(f"IP address changed during interview {interview_id}: {original_ip} -> {ip_address}")
                    event_type = 'ip_address_changed'
                    metadata['original_ip'] = original_ip
                    metadata['new_ip'] = ip_address
        
        # Create security log entry
        security_log = InterviewSecurityLog(
            interview_id=interview_id,
            event_type=event_type,
            timestamp=log_timestamp,
            ip_address=ip_address,
            user_agent=user_agent,
            violation_count=violations,
            device_fingerprint=device_fingerprint,
            event_metadata=metadata,
            auto_submitted=event_type.startswith('auto_submit')
        )
        
        db.session.add(security_log)
        db.session.commit()
        
        # Log to console/file
        logger.warning(
            f"[INTERVIEW {interview_id}] Security Event: {event_type} | "
            f"Violations: {violations} | IP: {ip_address} | "
            f"Time: {log_timestamp}"
        )
        
        # Check for critical violations
        critical_events = [
            'devtools_opened', 
            'auto_submit_timeout', 
            'auto_submit_idle',
            'ip_address_changed',
            'multi_device_detected'
        ]
        
        if event_type in critical_events:
            logger.critical(f"[CRITICAL] Interview {interview_id}: {event_type}")
            
            # Flag interview for manual review in Redis
            if redis_client:
                flag_key = f"interview_flagged:{interview_id}"
                redis_client.setex(flag_key, 86400, event_type)
            
            # Flag interview for manual review in DB
            interview = Interview.query.filter_by(id=interview_id).first()
            if interview:
                current_notes = interview.notes or ''
                interview.notes = f"{current_notes}\n[SECURITY ALERT] {event_type} at {log_timestamp.isoformat()}"
                db.session.commit()
        
        return jsonify({
            'logged': True,
            'log_id': security_log.id,
            'event_type': event_type,
            'timestamp': log_timestamp.isoformat(),
            'violations': violations
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error logging activity: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to log activity'}), 500


@ai_interviews.route('/interviews/<int:interview_id>/security-status', methods=['GET'])
@jwt_required()
def get_security_status(interview_id):
    """
    Get real-time security status from Redis for recruiter dashboard
    """
    try:
        user_id = int(get_jwt_identity())
        
        # Verify interview belongs to user's job
        interview = Interview.query.filter_by(id=interview_id).first()
        if not interview:
            return jsonify({'error': 'Interview not found'}), 404
        
        job = Job.query.filter_by(id=interview.job_id).first()
        if not job or job.user_id != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        security_status = {
            'interview_id': interview_id,
            'interview_status': interview.interview_status,
            'violations': 0,
            'is_flagged': False,
            'active_session': False,
            'device_ip': None,
            'last_activity': None,
            'total_security_events': 0
        }
        
        if redis_client:
            # Get violation count
            violation_key = f"interview_violations:{interview_id}"
            violations = redis_client.get(violation_key)
            if violations:
                security_status['violations'] = int(violations)
            
            # Check if flagged
            flag_key = f"interview_flagged:{interview_id}"
            flagged = redis_client.get(flag_key)
            if flagged:
                security_status['is_flagged'] = True
                security_status['flag_reason'] = flagged
            
            # Get session info
            session_key = f"interview_session:{interview_id}"
            session_data = redis_client.get(session_key)
            if session_data:
                session = json.loads(session_data)
                security_status['active_session'] = True
                security_status['device_ip'] = session.get('ip_address')
                security_status['last_activity'] = session.get('last_activity')
                security_status['last_event'] = session.get('last_event')
        
        # Get total security events from DB
        event_count = InterviewSecurityLog.query.filter_by(interview_id=interview_id).count()
        security_status['total_security_events'] = event_count
        
        # Get recent critical events
        critical_events = InterviewSecurityLog.query.filter(
            InterviewSecurityLog.interview_id == interview_id,
            InterviewSecurityLog.event_type.in_([
                'devtools_opened', 
                'auto_submit_timeout', 
                'auto_submit_idle',
                'ip_address_changed',
                'multi_device_detected'
            ])
        ).order_by(InterviewSecurityLog.timestamp.desc()).limit(5).all()
        
        security_status['critical_events'] = [
            {
                'event_type': event.event_type,
                'timestamp': event.timestamp.isoformat(),
                'ip_address': event.ip_address
            } for event in critical_events
        ]
        
        return jsonify(security_status), 200
        
    except Exception as e:
        logger.error(f"Error getting security status: {e}")
        return jsonify({'error': 'Failed to get security status'}), 500


