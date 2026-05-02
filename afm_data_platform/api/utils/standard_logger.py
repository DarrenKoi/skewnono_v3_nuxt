"""
Standard logging configuration for Flask production environment.
Replaces loguru with Python's built-in logging module for better compatibility.
"""
import logging
import logging.handlers
import json
import os
from pathlib import Path
from datetime import datetime
from functools import wraps
from typing import Optional, Callable, Dict, Any


class ExtraFieldsFormatter(logging.Formatter):
    """Custom formatter that includes extra fields in the log output."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Get the base formatted message
        base_msg = super().format(record)
        
        # Collect extra fields
        extra_fields = {}
        standard_fields = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'pathname', 'process', 'processName', 'relativeCreated',
            'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
            'getMessage', 'message', 'asctime', 'start_time'
        }
        
        for key, value in record.__dict__.items():
            if key not in standard_fields:
                extra_fields[key] = value
        
        # Append extra fields if any
        if extra_fields:
            extra_str = ' | ' + ' | '.join([f"{k}={v}" for k, v in extra_fields.items()])
            return base_msg + extra_str
        
        return base_msg


class StandardLoggerManager:
    """
    Production-ready logger using Python's standard logging module.
    Designed for Flask applications with WSGI server compatibility.
    """
    
    def __init__(self, *,
                 log_name: str = "app",
                 log_file_path: str = "logs/app.log",
                 level: str = "DEBUG",
                 retention_days: int = 7,
                 max_bytes: int = 100 * 1024 * 1024,  # 100MB
                 backup_count: int = 10,
                 json_format: bool = False,
                 mode: str = "dev",
                 console_level: Optional[str] = None):
        
        self.log_name = log_name
        self.log_file_path = Path(log_file_path)
        self.level = getattr(logging, level.upper())
        self.retention_days = retention_days
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.json_format = json_format
        self.mode = mode.lower()
        self.is_dev = self.mode == "dev"
        self.is_prod = self.mode == "prod"
        
        # Console level logic
        console_level_str = console_level or ("INFO" if self.is_dev else "WARNING")
        self.console_level = getattr(logging, console_level_str.upper())
        
        # Create logger
        self.logger = logging.getLogger(log_name)
        self.logger.setLevel(self.level)
        self.logger.propagate = False  # Prevent duplicate logs
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Configure console and file handlers."""
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.console_level)
        
        if self.is_dev:
            # Detailed format for development
            console_format = ExtraFieldsFormatter(
                '%(asctime)s | %(levelname)-5s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            # Simpler format for production console
            console_format = ExtraFieldsFormatter(
                '%(asctime)s | %(levelname)-5s | %(message)s',
                datefmt='%H:%M:%S'
            )
        
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # Create log directory if it doesn't exist
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_file_path,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.level)
        
        if self.json_format:
            # JSON formatter for structured logging
            file_handler.setFormatter(JsonFormatter())
        else:
            # Standard text format with extra fields support
            file_format = ExtraFieldsFormatter(
                '%(asctime)s | %(levelname)-5s | %(name)s | '
                '%(filename)s:%(lineno)d | %(funcName)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_format)
        
        self.logger.addHandler(file_handler)
    
    def get_logger(self) -> logging.Logger:
        """Get the configured logger instance."""
        return self.logger
    
    def log_performance(self, include_args: bool = False) -> Callable:
        """
        Decorator to log function performance.
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                func_name = func.__name__
                start_time = datetime.now()
                
                arg_str = ""
                if include_args:
                    arg_list = [repr(arg) for arg in args]
                    kwarg_list = [f"{k}={repr(v)}" for k, v in kwargs.items()]
                    arg_str = f" with args: ({', '.join(arg_list + kwarg_list)})"
                
                try:
                    result = func(*args, **kwargs)
                    duration = (datetime.now() - start_time).total_seconds()
                    self.logger.info(
                        f"Function '{func_name}'{arg_str} executed in {duration:.3f}s"
                    )
                    return result
                except Exception as e:
                    duration = (datetime.now() - start_time).total_seconds()
                    self.logger.exception(
                        f"Function '{func_name}'{arg_str} failed after {duration:.3f}s"
                    )
                    raise
            
            return wrapper
        return decorator
    
    def cleanup(self):
        """Clean up handlers."""
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
            'process': record.process,
            'thread': record.thread,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'pathname', 'process', 'processName', 'relativeCreated',
                          'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
                          'getMessage', 'message']:
                log_obj[key] = value
        
        return json.dumps(log_obj)


class FlaskLoggerIntegration:
    """
    Flask-specific logger integration for request/response logging.
    """
    
    @staticmethod
    def setup_request_logging(app, logger: logging.Logger):
        """Set up Flask request/response logging."""
        from flask import request
        
        @app.before_request
        def log_request():
            """Log incoming requests."""
            logger.info(
                f"Request: {request.method} {request.path}",
                extra={
                    'method': request.method,
                    'path': request.path,
                    'ip': request.remote_addr,
                    'user_agent': request.user_agent.string
                }
            )
        
        @app.after_request
        def log_response(response):
            """Log responses."""
            logger.info(
                f"Response: {response.status_code}",
                extra={
                    'status_code': response.status_code,
                    'content_length': response.content_length
                }
            )
            return response
        
        @app.errorhandler(Exception)
        def log_exception(error):
            """Log unhandled exceptions."""
            logger.exception(
                f"Unhandled exception: {error}",
                extra={'error_type': type(error).__name__}
            )
            raise


# Pre-configured setups
class LogConfigs:
    """Pre-configured logging setups for common scenarios."""
    
    @staticmethod
    def development():
        """Development configuration."""
        return StandardLoggerManager(
            log_name="afm_dev",
            log_file_path="logs/afm_dev.log",
            level="DEBUG",
            console_level="INFO",
            max_bytes=10 * 1024 * 1024,  # 10MB
            backup_count=3,
            mode="dev"
        )
    
    @staticmethod
    def production():
        """Production configuration."""
        return StandardLoggerManager(
            log_name="afm_prod",
            log_file_path="logs/afm_prod.log",
            level="INFO",
            console_level="WARNING",
            max_bytes=100 * 1024 * 1024,  # 100MB
            backup_count=10,
            mode="prod",
            json_format=True
        )
    
    @staticmethod
    def testing():
        """Testing configuration."""
        return StandardLoggerManager(
            log_name="afm_test",
            log_file_path="logs/afm_test.log",
            level="DEBUG",
            console_level="DEBUG",
            max_bytes=5 * 1024 * 1024,  # 5MB
            backup_count=1,
            mode="dev"
        )
