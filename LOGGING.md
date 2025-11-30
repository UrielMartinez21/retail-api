# Structured Logging Implementation

## Overview

This Django application implements structured logging using JSON format to improve observability, debugging, and monitoring capabilities.

## Features

- **JSON Formatted Logs**: All logs are output in JSON format for easy parsing
- **Request Tracking**: Each request gets a unique ID for tracing
- **Performance Monitoring**: Automatic logging of request duration
- **Error Tracking**: Detailed error logging with context
- **User Actions**: Logging of user interactions with resources
- **Database Operations**: Tracking of database queries and modifications

## Configuration

### Settings

The logging configuration is defined in `settings.py`:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
        },
    },
    'handlers': {
        'console_json': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'file_json': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/app.log',
            'maxBytes': 5242880,  # 5MB
            'backupCount': 5,
            'formatter': 'json',
        },
    },
    'loggers': {
        'products': {
            'handlers': ['console_json', 'file_json'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### Environment Variables

Add to your `.env` file:

```
LOG_LEVEL=INFO
```

Available levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## Middleware

The `StructuredLoggingMiddleware` automatically logs:

- Request start and completion
- Request duration
- Response status codes
- Client IP addresses
- User agents
- Exceptions during request processing

## Usage Examples

### Basic Logging

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Something happened", extra={
    'user_id': 123,
    'action': 'create_product',
    'event_type': 'user_action'
})
```

### Using LoggingExamples Class

```python
from .logging_examples import LoggingExamples

# Log user actions
LoggingExamples.log_user_action(
    request, 
    'create', 
    'product',
    resource_id=product.id,
    extra_data={'product_name': product.name}
)

# Log database operations
LoggingExamples.log_database_operation(
    'create', 
    'Product',
    record_id=product.id,
    extra_data={'operation_time': 0.045}
)

# Log business logic
LoggingExamples.log_business_logic(
    'inventory_transfer',
    'Transferred items between stores',
    success=True,
    extra_data={
        'from_store': source_store.id,
        'to_store': target_store.id,
        'quantity': 50
    }
)

# Log errors
LoggingExamples.log_error(
    request,
    'ValidationError',
    'Invalid product data provided',
    extra_data={'invalid_fields': ['name', 'price']}
)
```

### Performance Logging

```python
from .logging_examples import log_performance

@log_performance
def expensive_function(data):
    # Function automatically logs execution time
    return process_data(data)
```

## Log Structure

### Request Logs

```json
{
    "asctime": "2025-11-30T15:45:00Z",
    "name": "retail_api.middleware",
    "levelname": "INFO",
    "message": "Request started",
    "log_id": "550e8400-e29b-41d4-a716-446655440000",
    "method": "GET",
    "path": "/api/products/",
    "user_agent": "Mozilla/5.0...",
    "remote_addr": "192.168.1.1",
    "event_type": "request_started"
}
```

### User Action Logs

```json
{
    "asctime": "2025-11-30T15:45:01Z",
    "name": "products.views",
    "levelname": "INFO", 
    "message": "User action: create product",
    "log_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": 123,
    "action": "create",
    "resource_type": "product",
    "resource_id": 456,
    "event_type": "user_action"
}
```

### Error Logs

```json
{
    "asctime": "2025-11-30T15:45:02Z",
    "name": "products.views",
    "levelname": "ERROR",
    "message": "Error occurred: ValidationError",
    "log_id": "550e8400-e29b-41d4-a716-446655440000",
    "error_type": "ValidationError",
    "error_message": "Product name is required",
    "path": "/api/products/",
    "method": "POST",
    "event_type": "error"
}
```

## Best Practices

1. **Use Meaningful Event Types**: Always include `event_type` in extra data
2. **Include Context**: Add relevant IDs, user information, and operation details
3. **Log at Appropriate Levels**: Use INFO for normal operations, WARNING for issues, ERROR for failures
4. **Include Request IDs**: Use `getattr(request, 'log_id', 'unknown')` to track requests
5. **Performance Logging**: Log slow operations with timing information
6. **Structured Data**: Always use the `extra` parameter for structured data

## Monitoring and Analysis

### Log Aggregation

The JSON format makes it easy to integrate with log aggregation tools:

- **ELK Stack**: Elasticsearch + Logstash + Kibana
- **Fluentd**: For log collection and forwarding
- **Splunk**: Enterprise log analysis
- **DataDog**: Cloud monitoring and analytics
- **New Relic**: Application performance monitoring

### Filtering Examples

```bash
# Filter by event type
cat logs/app.log | jq '.event_type == "user_action"'

# Filter by log level
cat logs/app.log | jq '.levelname == "ERROR"'

# Filter by user
cat logs/app.log | jq '.user_id == 123'
```

### Monitoring Queries

- Response times: Track `duration_seconds` in request_completed events
- Error rates: Count ERROR level logs per time period
- User activity: Track user_action events by user_id
- Database performance: Monitor database_operation events

## File Locations

- **Log Files**: `logs/app.log` (rotated when > 5MB)
- **Configuration**: `settings.py` (LOGGING section)
- **Middleware**: `retail_api/middleware.py`
- **Examples**: `products/logging_examples.py`

## Troubleshooting

### Common Issues

1. **Logs not appearing**: Check LOG_LEVEL in environment
2. **Permission errors**: Ensure `logs/` directory is writable
3. **Disk space**: Monitor log file sizes (auto-rotation enabled)

### Debug Mode

Set `LOG_LEVEL=DEBUG` in your environment to see detailed logging information.