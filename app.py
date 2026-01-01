from flask import Flask
from flask_cors import CORS
from config import Config
from extensions import db, jwt, init_redis, mail
from migrate_config import init_migrate
from utils.monitoring import request_logger_middleware, performance_monitor, error_tracker
from routes.auth import auth_bp
from routes.jobs import jobs_bp
from routes.resumes import resumes_bp
from routes.candidates import candidates_bp
from routes.interviews import interviews_bp
from routes.ai_interviews import ai_interviews
from routes.users import users_bp
from routes.contact import contact_bp
from routes.dashboard import dashboard_bp
from routes.notifications import notifications_bp
from werkzeug.exceptions import HTTPException
import threading
import time
import logging


class ValidationError(Exception):
    """Custom exception for validation errors"""
    status_code = 400
    
    def __init__(self, message, status_code=None, payload=None):
        super().__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload
    
    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv


class DatabaseError(Exception):
    """Custom exception for database errors"""
    status_code = 500


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Enable debug logging
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    init_redis(app)  # Initialize Redis
    mail.init_app(app)  # Initialize Mail
    init_migrate(app)  # Initialize Flask-Migrate
    
    # Initialize monitoring middleware
    request_logger_middleware(app)
    
    # JWT error handlers with detailed logging
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        app.logger.warning(f'Expired token: {jwt_payload}')
        return {'error': 'Token has expired'}, 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        app.logger.error(f'Invalid token error: {error}')
        return {'error': 'Invalid token', 'details': str(error)}, 422
    
    @jwt.unauthorized_loader
    def unauthorized_callback(error):
        app.logger.warning(f'Unauthorized: {error}')
        return {'error': 'Missing authorization token'}, 401
    
    @jwt.needs_fresh_token_loader
    def needs_fresh_token_callback(jwt_header, jwt_payload):
        app.logger.warning('Fresh token required')
        return {'error': 'Fresh token required'}, 401
    
    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        app.logger.warning('Token revoked')
        return {'error': 'Token has been revoked'}, 401
    
    # Configure CORS with specific origin (security improvement)
    allowed_origins = app.config.get('ALLOWED_ORIGINS', 'http://localhost:3000')
    CORS(app, 
         origins=allowed_origins.split(','),
         supports_credentials=True,
         allow_headers=['Content-Type', 'Authorization', 'X-Session-Token'],
         expose_headers=['X-RateLimit-Remaining', 'X-RateLimit-Reset']
    )
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
    app.register_blueprint(resumes_bp, url_prefix='/api/resumes')
    app.register_blueprint(candidates_bp, url_prefix='/api/candidates')
    app.register_blueprint(interviews_bp, url_prefix='/api/interviews')
    app.register_blueprint(ai_interviews, url_prefix='/api/ai')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(contact_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
    
    # Centralized error handlers
    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        """Handle custom validation errors"""
        response = e.to_dict()
        return response, e.status_code
    
    @app.errorhandler(DatabaseError)
    def handle_database_error(e):
        """Handle database errors"""
        app.logger.error(f'Database error: {str(e)}')
        return {'error': 'Database operation failed', 'details': str(e)}, 500
    
    @app.errorhandler(404)
    def handle_not_found(e):
        """Handle 404 errors"""
        return {'error': 'Resource not found', 'path': str(e)}, 404
    
    @app.errorhandler(500)
    def handle_internal_error(e):
        """Handle internal server errors"""
        app.logger.error(f'Internal server error: {str(e)}')
        return {'error': 'Internal server error', 'message': str(e)}, 500
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        """Handle all HTTP exceptions"""
        return {'error': e.description, 'code': e.code}, e.code
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        """Handle unexpected errors"""
        app.logger.error(f'Unexpected error: {str(e)}', exc_info=True)
        
        # Track error
        error_tracker.log_error(
            error_type=type(e).__name__,
            message=str(e),
            traceback=str(e.__traceback__) if hasattr(e, '__traceback__') else None,
            context={'endpoint': str(e)}
        )
        
        # Don't expose internal error details in production
        if app.config['DEBUG']:
            return {'error': 'Unexpected error', 'details': str(e), 'type': type(e).__name__}, 500
        return {'error': 'An unexpected error occurred'}, 500
    
    # Monitoring endpoints
    @app.route('/api/monitoring/metrics')
    def get_metrics():
        """Get performance metrics (admin only in production)"""
        return {
            'performance': performance_monitor.get_stats(),
            'errors': error_tracker.get_error_stats()
        }, 2
        if app.config['DEBUG']:
            return {'error': 'Unexpected error', 'details': str(e), 'type': type(e).__name__}, 500
        return {'error': 'An unexpected error occurred'}, 500
    
    # Create tables (only if they don't exist)
    with app.app_context():
        try:
            # Validate configuration
            config_class.validate()
            db.create_all()
        except Exception as e:
            # Log error but don't fail - tables may already exist or be in process of creation
            print(f"Table creation skipped or failed: {e}")
    
    @app.route('/api/health')
    def health_check():
        return {'status': 'healthy', 'message': 'HireLens AI Backend Running'}, 200
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
