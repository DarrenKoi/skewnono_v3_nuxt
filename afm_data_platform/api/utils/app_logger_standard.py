"""
Centralized logger configuration using Python's standard logging.
Production-ready replacement for loguru-based logging.
"""
import os
import logging
from .standard_logger import StandardLoggerManager

# Singleton instances
_system_log_manager = None
_activity_log_manager = None
_error_log_manager = None


def get_system_logger() -> logging.Logger:
    """
    Get the system logger for application lifecycle events.
    """
    global _system_log_manager
    
    if _system_log_manager is None:
        _system_log_manager = StandardLoggerManager(
            log_name="afm.system",
            log_file_path="logs/system/afm_system.log",
            level=os.getenv('LOG_LEVEL', 'INFO'),
            mode="prod" if os.getenv('FLASK_ENV') == 'production' else "dev",
            console_level="INFO",
            max_bytes=50 * 1024 * 1024,  # 50MB
            backup_count=10,
            json_format=os.getenv('FLASK_ENV') == 'production'
        )
        
        logger = _system_log_manager.get_logger()
        logger.info("System logger initialized", extra={
            'pid': os.getpid(),
            'log_file': str(_system_log_manager.log_file_path.absolute())
        })
    
    return _system_log_manager.get_logger()


def get_activity_logger() -> logging.Logger:
    """
    Get the activity logger for user activities and API requests.
    """
    global _activity_log_manager
    
    if _activity_log_manager is None:
        _activity_log_manager = StandardLoggerManager(
            log_name="afm.activity",
            log_file_path="logs/activity/afm_activity.log",
            level=os.getenv('LOG_LEVEL', 'INFO'),
            mode="prod" if os.getenv('FLASK_ENV') == 'production' else "dev",
            console_level="WARNING",
            max_bytes=200 * 1024 * 1024,  # 200MB
            backup_count=20,
            json_format=True  # Always JSON for activity logs
        )
        
        logger = _activity_log_manager.get_logger()
        logger.info("Activity logger initialized", extra={
            'pid': os.getpid(),
            'log_file': str(_activity_log_manager.log_file_path.absolute())
        })
    
    return _activity_log_manager.get_logger()


def get_error_logger() -> logging.Logger:
    """
    Get the error logger for exceptions and error handling.
    """
    global _error_log_manager
    
    if _error_log_manager is None:
        _error_log_manager = StandardLoggerManager(
            log_name="afm.error",
            log_file_path="logs/error/afm_error.log",
            level="WARNING",
            mode="prod" if os.getenv('FLASK_ENV') == 'production' else "dev",
            console_level="ERROR",
            max_bytes=100 * 1024 * 1024,  # 100MB
            backup_count=30,
            json_format=os.getenv('FLASK_ENV') == 'production'
        )
        
        logger = _error_log_manager.get_logger()
        logger.info("Error logger initialized", extra={
            'pid': os.getpid(),
            'log_file': str(_error_log_manager.log_file_path.absolute())
        })
    
    return _error_log_manager.get_logger()


def get_task_logger(task_name: str) -> logging.Logger:
    """
    Get a logger for a specific background task.
    Uses a child logger with task context.
    """
    base_logger = get_system_logger()
    task_logger = logging.getLogger(f"{base_logger.name}.task.{task_name}")
    task_logger.setLevel(base_logger.level)
    return task_logger


def cleanup_loggers():
    """
    Clean up all logger instances.
    Should be called when the application shuts down.
    """
    global _system_log_manager, _activity_log_manager, _error_log_manager
    
    if _system_log_manager:
        _system_log_manager.get_logger().info("Shutting down system logger")
        _system_log_manager.cleanup()
        _system_log_manager = None
    
    if _activity_log_manager:
        _activity_log_manager.get_logger().info("Shutting down activity logger")
        _activity_log_manager.cleanup()
        _activity_log_manager = None
    
    if _error_log_manager:
        _error_log_manager.get_logger().info("Shutting down error logger")
        _error_log_manager.cleanup()
        _error_log_manager = None


# Flask integration example
def setup_flask_logging(app):
    """
    Set up Flask application logging.
    
    Usage:
        from flask import Flask
        from api.utils.app_logger_standard import setup_flask_logging
        
        app = Flask(__name__)
        setup_flask_logging(app)
    """
    from flask import request
    from .standard_logger import FlaskLoggerIntegration
    
    # Disable Flask's default logger
    app.logger.handlers = []
    app.logger.propagate = False
    
    # Use our loggers
    system_logger = get_system_logger()
    activity_logger = get_activity_logger()
    error_logger = get_error_logger()
    
    # Set up request logging
    FlaskLoggerIntegration.setup_request_logging(app, activity_logger)
    
    # Log application startup
    system_logger.info("Flask application started", extra={
        'app_name': app.name,
        'debug': app.debug,
        'testing': app.testing
    })
    
    # Register cleanup on teardown
    @app.teardown_appcontext
    def teardown(exception=None):
        if exception:
            error_logger.exception("Request context teardown with exception")
    
    return system_logger, activity_logger, error_logger
