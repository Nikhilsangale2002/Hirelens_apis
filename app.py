from flask import Flask
from flask_cors import CORS
from config import Config
from extensions import db, jwt, init_redis, mail
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
import threading
import time
import logging

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
    
    # Create tables (only if they don't exist)
    with app.app_context():
        try:
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
