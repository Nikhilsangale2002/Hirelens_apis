from flask import Flask
from config import Config
from extensions import db, jwt
from routes.auth import auth_bp
from routes.jobs import jobs_bp
from routes.resumes import resumes_bp
from routes.candidates import candidates_bp
import sys
import os

# Add middleware to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Hirelens_monitoring'))
from middleware import register_error_handlers, request_logger
from middleware.cors import configure_cors
from middleware.rate_limiter import RateLimiter
import threading
import time

def cleanup_rate_limits():
    """Background task to cleanup old rate limit entries"""
    while True:
        time.sleep(3600)  # Run every hour
        RateLimiter.cleanup_old_entries()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    
    # Configure CORS
    configure_cors(app)
    
    # Register middleware
    register_error_handlers(app)
    request_logger(app)
    
    # Start rate limit cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_rate_limits, daemon=True)
    cleanup_thread.start()
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
    app.register_blueprint(resumes_bp, url_prefix='/api/resumes')
    app.register_blueprint(candidates_bp, url_prefix='/api/candidates')
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    @app.route('/api/health')
    def health_check():
        return {'status': 'healthy', 'message': 'HireLens AI Backend Running'}, 200
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
