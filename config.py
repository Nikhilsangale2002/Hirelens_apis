import os
from datetime import timedelta

class Config:
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///hirelens.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # MySQL Connection Pool Settings (Fix "Lost connection" errors)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,  # Recycle connections after 1 hour
        'pool_pre_ping': True,  # Verify connections before using
        'max_overflow': 20,
        'pool_timeout': 30,
        'echo': False
    }
    
    # Redis Configuration
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    CACHE_TTL = 300  # 5 minutes default cache
    
    # Email Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@hirelens.ai')
    CONTACT_EMAIL = 'nikhilsangale121@gmail.com'
    
    # SMTP for EmailService
    SMTP_SERVER = os.getenv('SMTP_SERVER', os.getenv('MAIL_SERVER', 'smtp.gmail.com'))
    SMTP_PORT = int(os.getenv('SMTP_PORT', os.getenv('MAIL_PORT', 587)))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', os.getenv('MAIL_USERNAME', ''))
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', os.getenv('MAIL_PASSWORD', ''))
    FROM_EMAIL = os.getenv('FROM_EMAIL', os.getenv('MAIL_DEFAULT_SENDER', 'noreply@hirelens.ai'))
    FROM_NAME = os.getenv('FROM_NAME', 'HireLens Recruitment')
    
    # JWT - Hybrid Security Approach
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30)  # Long-lived session
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)    # Long-lived in DB for security
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'
    
    # File Upload
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}
    
    # AI Configuration
    AI_PROVIDER = os.getenv('AI_PROVIDER', 'gemini')  # gemini, openai, local
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    
    # Supabase OAuth Configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL', '')
    SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY', '')
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', '')
    
    # Plans Configuration
    PLANS = {
        'starter': {
            'jobs_limit': 3,
            'resumes_limit': 500,
            'price': 1999
        },
        'pro': {
            'jobs_limit': 10,
            'resumes_limit': 2000,
            'price': 4999
        },
        'enterprise': {
            'jobs_limit': -1,  # unlimited
            'resumes_limit': -1,
            'price': 0  # custom pricing
        }
    }

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
