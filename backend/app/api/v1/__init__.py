"""
API v1 package initialization.
"""

from app.api.v1.health import router as health_router

__all__ = ["health_router"]
