"""
Application logging configuration.
Provides clean and consistent console logging for startup, database, and API events.
"""

import logging
import sys


def setup_logging(debug: bool = True) -> logging.Logger:
    """Configure and return the root logger for Paytm MerchantMind backend."""
    log_level = logging.DEBUG if debug else logging.INFO

    # Custom log format with timestamps
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # Base merchantmind logger
    logger = logging.getLogger("merchantmind")
    logger.setLevel(log_level)

    # Avoid duplicate handlers on re-import
    if not logger.handlers:
        logger.addHandler(console_handler)

    # Reduce verbosity of third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    return logger


logger = setup_logging()
