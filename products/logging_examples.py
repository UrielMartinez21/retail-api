"""
Logging Examples - How to use structured logging in your Django views and functions

This file demonstrates best practices for structured logging in a Django application.
"""

import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import Product, Store

# Get logger for this module
logger = logging.getLogger(__name__)


class LoggingExamples:
    """Examples of how to implement structured logging"""
    
    @staticmethod
    def log_user_action(request, action, resource_type, resource_id=None, **extra_data):
        """
        Log user actions with consistent structure
        
        Args:
            request: Django request object
            action: Action performed (create, read, update, delete, etc.)
            resource_type: Type of resource (product, store, inventory, etc.)
            resource_id: ID of the resource if applicable
            **extra_data: Additional data to include in the log
        """
        log_id = getattr(request, 'log_id', 'unknown')
        user_id = request.user.id if request.user.is_authenticated else None
        
        logger.info(
            f"User action: {action} {resource_type}",
            extra={
                'log_id': log_id,
                'user_id': user_id,
                'action': action,
                'resource_type': resource_type,
                'resource_id': resource_id,
                'ip_address': LoggingExamples.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'event_type': 'user_action',
                **extra_data
            }
        )
    
    @staticmethod
    def log_database_operation(operation, model_name, record_id=None, **extra_data):
        """
        Log database operations
        
        Args:
            operation: Database operation (create, update, delete, query)
            model_name: Name of the model/table
            record_id: ID of the record if applicable
            **extra_data: Additional data to include in the log
        """
        logger.info(
            f"Database operation: {operation} on {model_name}",
            extra={
                'operation': operation,
                'model_name': model_name,
                'record_id': record_id,
                'event_type': 'database_operation',
                **extra_data
            }
        )
    
    @staticmethod
    def log_business_logic(operation, description, success=True, **extra_data):
        """
        Log business logic operations
        
        Args:
            operation: Business operation name
            description: Description of the operation
            success: Whether the operation was successful
            **extra_data: Additional data to include in the log
        """
        level = logging.INFO if success else logging.WARNING
        
        logger.log(
            level,
            f"Business operation: {operation}",
            extra={
                'operation': operation,
                'description': description,
                'success': success,
                'event_type': 'business_logic',
                **extra_data
            }
        )
    
    @staticmethod
    def log_error(request, error_type, error_message, **extra_data):
        """
        Log errors with context
        
        Args:
            request: Django request object
            error_type: Type of error
            error_message: Error message
            **extra_data: Additional data to include in the log
        """
        log_id = getattr(request, 'log_id', 'unknown')
        
        logger.error(
            f"Error occurred: {error_type}",
            extra={
                'log_id': log_id,
                'error_type': error_type,
                'error_message': error_message,
                'path': request.path,
                'method': request.method,
                'event_type': 'error',
                **extra_data
            }
        )
    
    @staticmethod
    def get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# Example view using structured logging
@csrf_exempt
@require_http_methods(["GET", "POST"])
def example_products_view(request):
    """
    Example view demonstrating structured logging usage
    """
    try:
        # Log the incoming request
        LoggingExamples.log_user_action(
            request, 
            'access', 
            'products_endpoint',
            extra_data={'query_params': dict(request.GET)}
        )
        
        if request.method == "GET":
            # Log database query attempt
            LoggingExamples.log_database_operation(
                'query', 
                'Product',
                extra_data={'filters': dict(request.GET)}
            )
            
            # Simulate getting products
            products = Product.objects.all()[:10]
            
            # Log successful operation
            LoggingExamples.log_business_logic(
                'get_products',
                'Retrieved products list',
                success=True,
                extra_data={'product_count': len(products)}
            )
            
            # Log user action completion
            LoggingExamples.log_user_action(
                request,
                'read',
                'products',
                extra_data={
                    'products_returned': len(products),
                    'success': True
                }
            )
            
            return JsonResponse({
                'status': 'success',
                'data': [{'id': p.id, 'name': p.name} for p in products]
            })
            
        elif request.method == "POST":
            # Log creation attempt
            LoggingExamples.log_user_action(
                request,
                'create',
                'product',
                extra_data={'request_data': request.body.decode()}
            )
            
            # Log business logic
            LoggingExamples.log_business_logic(
                'create_product',
                'Creating new product',
                success=True,
                extra_data={'validation_passed': True}
            )
            
            return JsonResponse({'status': 'success', 'message': 'Product created'})
            
    except Exception as e:
        # Log the error with context
        LoggingExamples.log_error(
            request,
            type(e).__name__,
            str(e),
            extra_data={'stack_trace': True}
        )
        
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred'
        }, status=500)


# Performance logging example
def log_performance(func):
    """
    Decorator to log function performance
    """
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            logger.info(
                f"Function execution completed: {func.__name__}",
                extra={
                    'function_name': func.__name__,
                    'duration_seconds': round(duration, 4),
                    'success': True,
                    'event_type': 'performance'
                }
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(
                f"Function execution failed: {func.__name__}",
                extra={
                    'function_name': func.__name__,
                    'duration_seconds': round(duration, 4),
                    'success': False,
                    'error': str(e),
                    'event_type': 'performance'
                }
            )
            raise
            
    return wrapper


# Example usage of performance decorator
@log_performance
def expensive_operation(data):
    """Example function with performance logging"""
    import time
    time.sleep(0.1)  # Simulate work
    return len(data)