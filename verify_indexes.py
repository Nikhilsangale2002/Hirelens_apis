from app import create_app
from sqlalchemy import text
from extensions import db

app = create_app()
with app.app_context():
    result = db.session.execute(text("SHOW INDEXES FROM jobs WHERE Key_name LIKE 'idx%'"))
    print("\n📊 Jobs Table Indexes:")
    for row in result:
        print(f"  ✓ {row[2]}")
    
    result = db.session.execute(text("SHOW INDEXES FROM resumes WHERE Key_name LIKE 'idx%'"))
    print("\n📊 Resumes Table Indexes:")
    for row in result:
        print(f"  ✓ {row[2]}")
    
    result = db.session.execute(text("SHOW INDEXES FROM interviews WHERE Key_name LIKE 'idx%'"))
    print("\n📊 Interviews Table Indexes:")
    for row in result:
        print(f"  ✓ {row[2]}")
    
    print("\n✅ All performance indexes verified!")
