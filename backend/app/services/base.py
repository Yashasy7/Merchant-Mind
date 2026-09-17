"""
Base service interface for MerchantMind business logic.
"""

from sqlalchemy.orm import Session
from app.core.logging import logger


class BaseService:
    """Base class for all business services providing session and logging."""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
