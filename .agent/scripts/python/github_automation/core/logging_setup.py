"""Logging configuration and setup utilities."""

import json
import datetime
import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from ..config.models import LoggingConfig
from .exceptions import GitHubAutomationError


def setup_logging(config: LoggingConfig, logger_name: Optional[str] = None) -> logging.Logger:
    """
    Set up logging with Rich console support and optional file output.
    
    Args:
        config: Logging configuration
        logger_name: Optional logger name (defaults to root logger)
        
    Returns:
        Configured logger instance
    """
    # Get logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, config.level))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler with Rich
    if config.rich_console:
        console = Console(stderr=True, force_terminal=True)
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            enable_link_path=False,
            markup=False,  # Disable markup to prevent errors with brackets
            rich_tracebacks=True
        )
        console_handler.setLevel(getattr(logging, config.level))
        logger.addHandler(console_handler)
    else:
        # Standard console handler
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(getattr(logging, config.level))
        formatter = logging.Formatter(config.format)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler if specified
    if config.file_path:
        try:
            file_path = Path(config.file_path)
            
            # Security validation for file path
            resolved_path = file_path.resolve()
            
            # Ensure parent directory exists with proper permissions
            resolved_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            
            # Create file handler with secure permissions
            file_handler = logging.FileHandler(resolved_path, mode='a', encoding='utf-8')
            file_handler.setLevel(getattr(logging, config.level))
            
            if config.structured:
                # Secure JSON formatter for structured logging
                class SecureJSONFormatter(logging.Formatter):
                    def format(self, record):
                        try:
                            # Get the original message
                            message = record.getMessage()
                            
                            # If this is from our exception hierarchy, use sanitized message
                            if hasattr(record, 'exc_info') and record.exc_info:
                                exc_type, exc_value, _ = record.exc_info
                                if isinstance(exc_value, GitHubAutomationError):
                                    message = exc_value.message  # Already sanitized
                            
                            log_entry = {
                                'timestamp': datetime.datetime.fromtimestamp(record.created).isoformat(),
                                'level': record.levelname,
                                'logger': record.name,
                                'message': message,
                                'module': record.module,
                                'function': record.funcName,
                                'line': record.lineno,
                            }
                            
                            # Handle exceptions safely
                            if record.exc_info:
                                exc_type, exc_value, _ = record.exc_info
                                if isinstance(exc_value, GitHubAutomationError):
                                    # Use sanitized exception details
                                    log_entry['exception'] = {
                                        'type': exc_type.__name__,
                                        'message': exc_value.message,
                                        'details': exc_value.details
                                    }
                                else:
                                    # Sanitize generic exceptions
                                    exception_str = self.formatException(record.exc_info)
                                    # Basic sanitization for generic exceptions
                                    # Create a temporary error instance to use its sanitization method
                                    temp_error = GitHubAutomationError("")
                                    sanitized_exception = temp_error._sanitize_message(exception_str)
                                    log_entry['exception'] = sanitized_exception
                            
                            return json.dumps(log_entry, default=str)
                            
                        except Exception as e:
                            # Fallback to safe logging if JSON serialization fails
                            return json.dumps({
                                'timestamp': datetime.datetime.fromtimestamp(record.created).isoformat(),
                                'level': 'ERROR',
                                'logger': 'logging_setup',
                                'message': f'Failed to format log record: {str(e)}',
                                'original_level': record.levelname
                            })
                
                file_handler.setFormatter(SecureJSONFormatter())
            else:
                # Use regular formatter but ensure it's safe
                class SecureFormatter(logging.Formatter):
                    def format(self, record):
                        # Get formatted message
                        formatted = super().format(record)
                        # Apply basic sanitization
                        # Create a temporary error instance to use its sanitization method
                        temp_error = GitHubAutomationError("")
                        return temp_error._sanitize_message(formatted)
                
                file_handler.setFormatter(SecureFormatter(config.format))
            
            logger.addHandler(file_handler)
            
        except Exception as e:
            # If file logging fails, log warning to console and continue
            logger.warning(f"Failed to setup file logging: {e}")
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_logger(name: str, config: Optional[LoggingConfig] = None) -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name
        config: Optional logging configuration (uses defaults if not provided)
        
    Returns:
        Configured logger instance
    """
    if config is None:
        config = LoggingConfig()
    
    return setup_logging(config, name)