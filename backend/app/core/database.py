"""
Database connection and session management using modern SQLAlchemy 2.x.
Provides session factory, FastAPI dependency, connection checking, and table initialization.
"""

from typing import Generator, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import get_settings
from app.core.logging import logger

settings = get_settings()


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.0 models."""
    pass


def get_engine_args(db_url: str) -> Dict[str, Any]:
    """Generate appropriate engine arguments based on database dialect."""
    kwargs: Dict[str, Any] = {
        "echo": settings.db_echo,
    }
    if db_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow
        kwargs["pool_pre_ping"] = True
    return kwargs


# Global engine and sessionmaker
engine = create_engine(settings.database_url, **get_engine_args(settings.database_url))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Ensure all SQLAlchemy models are registered on Base.metadata whenever database is imported
import app.models  # noqa: F401


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session per request.
    Ensures safe session closing and rollback on unhandled exceptions.
    """
    db: Session = SessionLocal()
    try:
        yield db
    except Exception as exc:
        db.rollback()
        logger.error(f"Database session error occurred: {exc}")
        raise
    finally:
        db.close()


def check_db_connection() -> Dict[str, Any]:
    """
    Safely tests database connectivity with a lightweight query.
    Returns status dictionary without throwing uncaught exceptions.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "status": "connected",
            "dialect": engine.dialect.name,
            "connected": True
        }
    except SQLAlchemyError as err:
        logger.warning(f"Database connectivity check failed: {err}")
        return {
            "status": "disconnected",
            "dialect": engine.dialect.name,
            "connected": False,
            "error": "Database connection unavailable"
        }
    except Exception as err:
        logger.warning(f"Unexpected error during database check: {err}")
        return {
            "status": "disconnected",
            "dialect": "unknown",
            "connected": False,
            "error": str(err)
        }


def init_db() -> bool:
    """
    Safely creates database tables for registered models if they do not exist.
    Does NOT drop or alter existing tables.
    Only reports success if create_all actually succeeds with registered models.
    """
    try:
        # Ensure all models are imported and registered on Base.metadata
        import app.models  # noqa: F401

        registered_tables = list(Base.metadata.tables.keys())
        if not registered_tables:
            logger.error("Database initialization failed: No models registered on Base.metadata before create_all.")
            return False

        logger.info(f"Initializing database schema ({len(registered_tables)} tables: {registered_tables})...")
        Base.metadata.create_all(bind=engine)

        # Synchronize new Campaign columns if table already existed from earlier milestones
        if "campaigns" in registered_tables and not settings.database_url.startswith("sqlite"):
            with engine.begin() as conn:
                conn.execute(text("""
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS name VARCHAR(200);
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS description VARCHAR(500);
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS discount_percent NUMERIC(5, 2);
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS cashback_amount NUMERIC(8, 2);
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS minimum_transaction_amount NUMERIC(8, 2) DEFAULT 0.00;
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS target_days VARCHAR(50);
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS target_hours VARCHAR(50);
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS source_recommendation_id VARCHAR(100);
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS source_simulation_id VARCHAR(100);
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS projected_revenue NUMERIC(12, 2) DEFAULT 0.00;
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS projected_transactions INTEGER DEFAULT 0;
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS estimated_incentive_cost NUMERIC(10, 2) DEFAULT 0.00;
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS estimated_roi NUMERIC(6, 2);
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS simulated_revenue NUMERIC(12, 2) DEFAULT 0.00;
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS simulated_transactions INTEGER DEFAULT 0;
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS simulated_cost NUMERIC(10, 2) DEFAULT 0.00;
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS simulated_net_impact NUMERIC(12, 2) DEFAULT 0.00;
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS simulated_roi NUMERIC(6, 2);
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE;
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS executed_at TIMESTAMP WITH TIME ZONE;
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMP WITH TIME ZONE;
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR(500);
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) DEFAULT 'Merchant';
                    ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS approved_by VARCHAR(100);
                """))

        logger.info("Database schema initialized successfully.")
        return True

    except Exception as exc:
        logger.error(f"Database initialization failed: {exc}")
        return False

