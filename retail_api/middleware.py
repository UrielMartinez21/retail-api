"""
Custom middleware for structured logging
"""
import logging
import time
import uuid
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class StructuredLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to add structured logging for each request
    """
    
    def process_request(self, request):
        """Log incoming request details"""
        request.start_time = time.time()
        request.log_id = str(uuid.uuid4())
        
        logger.info(
            "Request started",
            extra={
                'log_id': request.log_id,
                'method': request.method,
                'path': request.path,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'remote_addr': self.get_client_ip(request),
                'content_type': request.content_type,
                'event_type': 'request_started'
            }
        )
        
    def process_response(self, request, response):
        """Log response details"""
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
        else:
            duration = 0
            
        log_id = getattr(request, 'log_id', 'unknown')
        
        logger.info(
            "Request completed",
            extra={
                'log_id': log_id,
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration_seconds': round(duration, 4),
                'content_length': len(response.content) if hasattr(response, 'content') else 0,
                'event_type': 'request_completed'
            }
        )
        return response
    
    def process_exception(self, request, exception):
        """Log exceptions"""
        log_id = getattr(request, 'log_id', 'unknown')
        
        logger.error(
            "Request failed with exception",
            extra={
                'log_id': log_id,
                'method': request.method,
                'path': request.path,
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'event_type': 'request_exception'
            },
            exc_info=True
        )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip