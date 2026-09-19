"""
Pytest fixtures and test configuration.
Provides an isolated in-memory SQLite database and FastAPI TestClient.
Ensures tests run reliably in any environment without requiring live PostgreSQL.
"""

import sys
import os
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.abspath(os.path.join(TEST_DIR, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.main import app
from app.core.database import Base, get_db
from app.core.config import get_settings, Settings

# Create in-memory SQLite engine for tests with StaticPool
TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all schema tables in test in-memory database."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a clean transactional database session for each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient with overridden get_db dependency."""
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_test_network(request, monkeypatch):
    """Ensure agent tests run offline with deterministic engine and zero network latency."""
    if "test_cognee_client" not in request.node.nodeid:
        from app.core.config import get_settings
        settings = get_settings()
        monkeypatch.setattr(settings, "llm_api_key", "")
        from app.ai.cognee_client import CogneeClient
        monkeypatch.setattr(CogneeClient, "recall", lambda self, *args, **kwargs: [])
        monkeypatch.setattr(CogneeClient, "remember", lambda self, *args, **kwargs: True)

