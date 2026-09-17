"""
Tests for database connection handling and session dependency.
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import check_db_connection, get_db


def test_database_session_dependency(db_session: Session):
    """Verify that database session dependency is structurally valid and can execute queries."""
    assert db_session is not None
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_check_db_connection_structure():
    """Verify that check_db_connection returns a valid diagnostic dictionary."""
    result = check_db_connection()
    assert isinstance(result, dict)
    assert "status" in result
    assert "dialect" in result
    assert "connected" in result


def test_models_registered_on_base_metadata():
    """Verify that all six core models are registered on Base.metadata without manual model imports."""
    from app.core.database import Base
    tables = list(Base.metadata.tables.keys())
    assert len(tables) == 6
    assert set(tables) == {"merchants", "customers", "transactions", "expenses", "invoices", "campaigns"}

