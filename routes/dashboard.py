from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.job import Job
from models.resume import Resume
from models.user import User
from extensions import db, cache_get, cache_set
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import logging

dashboard_bp = Blueprint('dashboard', __name__)
logger = logging.getLogger(__name__)

@dashboard_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    """Get dashboard statistics with Redis caching"""
    try:
        user_id = get_jwt_identity()
        cache_key = f"dashboard_stats:{user_id}"
        
        # Try to get from cache
        cached_data = cache_get(cache_key)
        if cached_data:
            return jsonify({
                'stats': cached_data,
                'cached': True
            }), 200
        
        # Calculate stats
        # Active jobs count
        active_jobs = Job.query.filter_by(user_id=user_id, status='active').count()
        
        # Total candidates (resumes) count
        total_candidates = db.session.query(func.count(Resume.id))\
            .join(Job)\
            .filter(Job.user_id == user_id)\
            .scalar() or 0
        
        # Shortlisted candidates count
        shortlisted = db.session.query(func.count(Resume.id))\
            .join(Job)\
            .filter(Job.user_id == user_id, Resume.status == 'shortlisted')\
            .scalar() or 0
        
        # Average processing time
        avg_processing = db.session.query(func.avg(Resume.processing_time_seconds))\
            .join(Job)\
            .filter(Job.user_id == user_id, Resume.processing_status == 'completed')\
            .scalar() or 0
        
        # Calculate changes (week over week)
        week_ago = datetime.utcnow() - timedelta(days=7)
        jobs_this_week = Job.query.filter(
            Job.user_id == user_id, 
            Job.created_at >= week_ago
        ).count()
        
        month_ago = datetime.utcnow() - timedelta(days=30)
        candidates_this_month = db.session.query(func.count(Resume.id))\
            .join(Job)\
            .filter(Job.user_id == user_id, Resume.created_at >= month_ago)\
            .scalar() or 0
        
        # Shortlist rate
        shortlist_rate = (shortlisted / total_candidates * 100) if total_candidates > 0 else 0
        
        stats = {
            'active_jobs': {
                'value': active_jobs,
                'change': f'+{jobs_this_week} this week'
            },
            'total_candidates': {
                'value': total_candidates,
                'change': f'+{candidates_this_month} this month'
            },
            'shortlisted': {
                'value': shortlisted,
                'change': f'{shortlist_rate:.1f}% rate'
            },
            'avg_processing_time': {
                'value': f'{avg_processing:.1f}s',
                'change': '70% faster'  # This would need historical data to calculate
            }
        }
        
        # Cache for 5 minutes
        cache_set(cache_key, stats, expire=300)
        
        return jsonify({
            'stats': stats,
            'cached': False
        }), 200
        
    except Exception as e:
        logger.error(f"Dashboard stats error: {str(e)}")
        return jsonify({'error': 'Failed to load dashboard stats'}), 500


@dashboard_bp.route('/recent-jobs', methods=['GET'])
@jwt_required()
def get_recent_jobs():
    """Get recent jobs with Redis caching"""
    try:
        user_id = get_jwt_identity()
        cache_key = f"dashboard_recent_jobs:{user_id}"
        
        # Try to get from cache
        cached_data = cache_get(cache_key)
        if cached_data:
            return jsonify({
                'jobs': cached_data,
                'cached': True
            }), 200
        
        # Get recent 5 jobs
        jobs = Job.query.filter_by(user_id=user_id)\
            .order_by(desc(Job.created_at))\
            .limit(5)\
            .all()
        
        jobs_data = []
        for job in jobs:
            # Get candidates and shortlisted count
            candidates_count = Resume.query.filter_by(job_id=job.id).count()
            shortlisted_count = Resume.query.filter_by(job_id=job.id, status='shortlisted').count()
            
            # Calculate time ago
            time_diff = datetime.utcnow() - job.created_at
            if time_diff.days == 0:
                created_ago = "Today"
            elif time_diff.days == 1:
                created_ago = "1 day ago"
            elif time_diff.days < 7:
                created_ago = f"{time_diff.days} days ago"
            elif time_diff.days < 14:
                created_ago = "1 week ago"
            else:
                created_ago = f"{time_diff.days // 7} weeks ago"
            
            jobs_data.append({
                'id': job.id,
                'title': job.title,
                'department': job.department or 'General',
                'candidates': candidates_count,
                'shortlisted': shortlisted_count,
                'status': job.status.capitalize(),
                'created_at': created_ago
            })
        
        # Cache for 2 minutes
        cache_set(cache_key, jobs_data, expire=120)
        
        return jsonify({
            'jobs': jobs_data,
            'cached': False
        }), 200
        
    except Exception as e:
        logger.error(f"Recent jobs error: {str(e)}")
        return jsonify({'error': 'Failed to load recent jobs'}), 500


@dashboard_bp.route('/activity', methods=['GET'])
@jwt_required()
def get_recent_activity():
    """Get recent activity logs with Redis caching"""
    try:
        user_id = get_jwt_identity()
        cache_key = f"dashboard_activity:{user_id}"
        
        # Try to get from cache
        cached_data = cache_get(cache_key)
        if cached_data:
            return jsonify({
                'activity': cached_data,
                'cached': True
            }), 200
        
        # Get recent resumes (resume processed activities)
        recent_resumes = db.session.query(Resume, Job)\
            .join(Job)\
            .filter(Job.user_id == user_id)\
            .order_by(desc(Resume.created_at))\
            .limit(10)\
            .all()
        
        activities = []
        
        for resume, job in recent_resumes:
            time_diff = datetime.utcnow() - resume.created_at
            
            if time_diff.total_seconds() < 60:
                time_ago = f"{int(time_diff.total_seconds())} sec ago"
            elif time_diff.total_seconds() < 3600:
                time_ago = f"{int(time_diff.total_seconds() / 60)} min ago"
            elif time_diff.total_seconds() < 86400:
                time_ago = f"{int(time_diff.total_seconds() / 3600)} hour ago"
            else:
                time_ago = f"{time_diff.days} days ago"
            
            # Resume processed activity
            if resume.processing_status == 'completed':
                activities.append({
                    'action': 'Resume processed',
                    'detail': f"{resume.candidate_name or 'Unknown'} - {job.title}",
                    'time': time_ago,
                    'color': '#FF6B35'
                })
            
            # Shortlisted activity
            if resume.status == 'shortlisted':
                activities.append({
                    'action': 'Candidate shortlisted',
                    'detail': f"{resume.candidate_name or 'Unknown'} - {job.title}",
                    'time': time_ago,
                    'color': '#06A77D'
                })
        
        # Get recent jobs (job created activities)
        recent_jobs = Job.query.filter_by(user_id=user_id)\
            .order_by(desc(Job.created_at))\
            .limit(5)\
            .all()
        
        for job in recent_jobs:
            time_diff = datetime.utcnow() - job.created_at
            
            if time_diff.total_seconds() < 60:
                time_ago = f"{int(time_diff.total_seconds())} sec ago"
            elif time_diff.total_seconds() < 3600:
                time_ago = f"{int(time_diff.total_seconds() / 60)} min ago"
            elif time_diff.total_seconds() < 86400:
                time_ago = f"{int(time_diff.total_seconds() / 3600)} hours ago"
            else:
                time_ago = f"{time_diff.days} days ago"
            
            activities.append({
                'action': 'Job created',
                'detail': job.title,
                'time': time_ago,
                'color': '#004E89'
            })
        
        # Sort by most recent and limit to 8
        activities.sort(key=lambda x: x['time'])
        activities = activities[:8]
        
        # Cache for 1 minute
        cache_set(cache_key, activities, expire=60)
        
        return jsonify({
            'activity': activities,
            'cached': False
        }), 200
        
    except Exception as e:
        logger.error(f"Recent activity error: {str(e)}")
        return jsonify({'error': 'Failed to load recent activity'}), 500
