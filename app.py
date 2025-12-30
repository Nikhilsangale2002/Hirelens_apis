from flask import Flask
from flask_cors import CORS
from config import Config
from extensions import db, jwt
from routes.auth import auth_bp
from routes.jobs import jobs_bp
from routes.resumes import resumes_bp
from routes.candidates import candidates_bp
import threading
import time

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    
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
