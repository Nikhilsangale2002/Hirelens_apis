from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_mail import Mail
import redis
import json
from datetime import timedelta

db = SQLAlchemy()
jwt = JWTManager()
mail = Mail()

# Redis client
redis_client = None

def init_redis(app):
    """Initialize Redis connection"""
    global redis_client
    try:
        redis_client = redis.Redis(
            host=app.config['REDIS_HOST'],
            port=app.config['REDIS_PORT'],
            db=app.config['REDIS_DB'],
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        # Test connection
        redis_client.ping()
        print("✓ Redis connected successfully")
    except Exception as e:
        print(f"⚠ Redis connection failed: {e}")
        print("  Application will continue without caching")
        redis_client = None

def cache_set(key, value, expire=300):
    """Set cache with JSON serialization"""
    if redis_client:
        try:
            redis_client.setex(key, expire, json.dumps(value))
            return True
        except Exception as e:
            print(f"Cache set error: {e}")
    return False

def cache_get(key):
    """Get cache with JSON deserialization"""
    if redis_client:
        try:
            data = redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"Cache get error: {e}")
    return None

def cache_delete(key):
    """Delete cache key"""
    if redis_client:
        try:
            redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Cache delete error: {e}")
    return False

def cache_delete_pattern(pattern):
    """Delete all keys matching pattern"""
    if redis_client:
        try:
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
            return True
        except Exception as e:
            print(f"Cache delete pattern error: {e}")
    return False
