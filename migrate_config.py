"""
Database Migration Manager
Initialize with: flask db init
Create migration: flask db migrate -m "description"
Apply migration: flask db upgrade
"""
from flask_migrate import Migrate
from extensions import db

migrate = Migrate()

def init_migrate(app):
    """Initialize Flask-Migrate"""
    migrate.init_app(app, db)
    return migrate
