"""
Structured logging configuration using loguru
"""
import sys
from loguru import logger
from app.core.config import settings
import os


def setup_logging():
    """Configure structured logging with loguru."""
    # Remove default handler
    logger.remove()
    
    # Ensure logs directory exists
    os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)
    
    # Add console handler with colored output
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    
    # Add file handler with JSON format for structured logging
    logger.add(
        settings.LOG_FILE,
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {extra[correlation_id]:<36} | {message}",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        serialize=True,
    )
    
    # Bind default correlation_id
    logger.configure(patcher=lambda record: record["extra"].setdefault("correlation_id", "-"))
    logger.info("Logging initialized")


def get_logger(name: str = __name__):
    """Get a logger instance with the given name."""
    return logger.bind(name=name)


# Initialize logging on module import
setup_logging()
