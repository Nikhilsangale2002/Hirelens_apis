"""
Performance Monitoring and Logging Middleware
"""
from flask import request, g
from functools import wraps
import time
import logging
import json
from typing import Callable

# Configure logger
logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Track request performance metrics"""
    
    def __init__(self):
        self.metrics = {
            'total_requests': 0,
            'slow_requests': 0,
            'failed_requests': 0,
            'endpoint_stats': {}
        }
    
    def record_request(self, endpoint: str, duration: float, status_code: int):
        """Record request metrics"""
        self.metrics['total_requests'] += 1
        
        if endpoint not in self.metrics['endpoint_stats']:
            self.metrics['endpoint_stats'][endpoint] = {
                'count': 0,
                'total_time': 0,
                'avg_time': 0,
                'slow_count': 0
            }
        
        stats = self.metrics['endpoint_stats'][endpoint]
        stats['count'] += 1
        stats['total_time'] += duration
        stats['avg_time'] = stats['total_time'] / stats['count']
        
        # Track slow requests (> 1 second)
        if duration > 1.0:
            self.metrics['slow_requests'] += 1
            stats['slow_count'] += 1
        
        # Track failed requests
        if status_code >= 400:
            self.metrics['failed_requests'] += 1
    
    def get_stats(self):
        """Get current metrics"""
        return self.metrics


# Global monitor instance
performance_monitor = PerformanceMonitor()


def performance_logging(f: Callable):
    """
    Decorator to log request performance
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Start timer
        start_time = time.time()
        
        # Store in request context
        g.start_time = start_time
        
        try:
            # Execute request
            response = f(*args, **kwargs)
            status_code = response[1] if isinstance(response, tuple) else 200
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log performance
            logger.info(
                f"REQUEST: {request.method} {request.path} | "
                f"Status: {status_code} | "
                f"Duration: {duration:.3f}s | "
                f"IP: {request.remote_addr}"
            )
            
            # Record metrics
            performance_monitor.record_request(
                endpoint=request.endpoint or request.path,
                duration=duration,
                status_code=status_code
            )
            
            # Warn on slow requests
            if duration > 1.0:
                logger.warning(
                    f"SLOW REQUEST: {request.method} {request.path} took {duration:.3f}s"
                )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"REQUEST ERROR: {request.method} {request.path} | "
                f"Error: {str(e)} | "
                f"Duration: {duration:.3f}s"
            )
            performance_monitor.record_request(
                endpoint=request.endpoint or request.path,
                duration=duration,
                status_code=500
            )
            raise
    
    return decorated_function


def log_database_query(query_type: str, model: str, duration: float):
    """Log database query performance"""
    if duration > 0.5:
        logger.warning(
            f"SLOW QUERY: {query_type} on {model} took {duration:.3f}s"
        )
    else:
        logger.debug(
            f"DB QUERY: {query_type} on {model} took {duration:.3f}s"
        )


def request_logger_middleware(app):
    """
    Middleware to log all requests
    """
    @app.before_request
    def before_request():
        g.start_time = time.time()
        
        # Log incoming request
        logger.info(
            f"Incoming: {request.method} {request.path} | "
            f"IP: {request.remote_addr} | "
            f"User-Agent: {request.headers.get('User-Agent', 'Unknown')}"
        )
        
        # Log request body for POST/PUT (excluding sensitive data)
        if request.method in ['POST', 'PUT', 'PATCH'] and request.is_json:
            body = request.get_json()
            # Redact sensitive fields
            safe_body = {k: '***' if k in ['password', 'token', 'secret'] else v 
                        for k, v in body.items()}
            logger.debug(f"Request body: {json.dumps(safe_body)}")
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            
            logger.info(
                f"Response: {request.method} {request.path} | "
                f"Status: {response.status_code} | "
                f"Duration: {duration:.3f}s"
            )
            
            # Add performance header
            response.headers['X-Response-Time'] = f"{duration:.3f}s"
            
            # Record metrics
            performance_monitor.record_request(
                endpoint=request.endpoint or request.path,
                duration=duration,
                status_code=response.status_code
            )
        
        return response


class ErrorTracker:
    """Track and log application errors"""
    
    def __init__(self):
        self.errors = []
        self.max_errors = 100  # Keep last 100 errors
    
    def log_error(self, error_type: str, message: str, traceback: str = None, context: dict = None):
        """Log an error with context"""
        error_entry = {
            'timestamp': time.time(),
            'type': error_type,
            'message': message,
            'traceback': traceback,
            'context': context or {},
            'request': {
                'method': request.method if request else None,
                'path': request.path if request else None,
                'ip': request.remote_addr if request else None
            }
        }
        
        self.errors.append(error_entry)
        
        # Keep only last max_errors
        if len(self.errors) > self.max_errors:
            self.errors = self.errors[-self.max_errors:]
        
        # Log to file
        logger.error(
            f"ERROR TRACKED: {error_type} | {message}",
            extra={'error_context': context}
        )
    
    def get_recent_errors(self, limit: int = 10):
        """Get recent errors"""
        return self.errors[-limit:]
    
    def get_error_stats(self):
        """Get error statistics"""
        error_types = {}
        for error in self.errors:
            error_type = error['type']
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            'total_errors': len(self.errors),
            'by_type': error_types,
            'recent_errors': self.get_recent_errors(5)
        }


# Global error tracker
error_tracker = ErrorTracker()
