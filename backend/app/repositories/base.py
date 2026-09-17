"""
Base repository pattern providing common database operations.
"""

from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic repository providing standardized CRUD queries."""

    def __init__(self, model: Type[ModelT], db: Session):
        self.model = model
        self.db = db

    def get_by_id(self, entity_id: Any) -> Optional[ModelT]:
        """Fetch a single record by primary key."""
        return self.db.get(self.model, entity_id)

    def list_all(self, limit: int = 100, offset: int = 0) -> List[ModelT]:
        """List records with pagination."""
        stmt = select(self.model).offset(offset).limit(limit)
        return list(self.db.scalars(stmt).all())

    def add(self, entity: ModelT) -> ModelT:
        """Add and persist a new record."""
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity
