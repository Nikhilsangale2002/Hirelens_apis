"""
Pagination utility for API endpoints
"""
from flask import request, jsonify
from typing import Any, Dict, List
from sqlalchemy.orm import Query


def paginate(query: Query, page: int = None, per_page: int = None, max_per_page: int = 100):
    """
    Paginate a SQLAlchemy query
    
    Args:
        query: SQLAlchemy query object
        page: Page number (1-indexed), defaults to request arg
        per_page: Items per page, defaults to request arg or 20
        max_per_page: Maximum items per page allowed (default: 100)
    
    Returns:
        Dict with paginated data and metadata
    """
    # Get pagination params from request if not provided
    if page is None:
        page = request.args.get('page', 1, type=int)
    if per_page is None:
        per_page = request.args.get('per_page', 20, type=int)
    
    # Validate and limit per_page
    per_page = min(per_page, max_per_page)
    page = max(page, 1)  # Ensure page is at least 1
    
    # Get paginated results first
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    
    # Get total count (expensive operation, cached if possible)
    # Use a fresh query to avoid column issues with complex queries
    try:
        total = query.count()
    except Exception:
        # If count fails, estimate from items
        total = len(items) if page == 1 else (page - 1) * per_page + len(items)
    
    # Calculate pagination
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1
    
    return {
        'items': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_next': has_next,
            'has_prev': has_prev,
            'next_page': page + 1 if has_next else None,
            'prev_page': page - 1 if has_prev else None
        }
    }


def paginate_response(items: List[Any], serializer=None):
    """
    Convert paginated items to JSON response
    
    Args:
        items: List of model instances
        serializer: Function to serialize each item (default: to_dict)
    
    Returns:
        JSON response with data and pagination metadata
    """
    if serializer is None:
        serializer = lambda x: x.to_dict() if hasattr(x, 'to_dict') else x
    
    return {
        'data': [serializer(item) for item in items['items']],
        'pagination': items['pagination']
    }


class PaginationMixin:
    """
    Mixin for models to add pagination helper
    """
    @classmethod
    def paginate(cls, query=None, **kwargs):
        """
        Paginate query for this model
        
        Usage:
            result = Job.paginate(Job.query.filter_by(status='active'))
        """
        if query is None:
            query = cls.query
        return paginate(query, **kwargs)
