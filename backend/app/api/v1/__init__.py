"""
API v1 package initialization.
"""

from app.api.v1.health import router as health_router
from app.api.v1.sales import router as sales_router

__all__ = ["health_router", "sales_router"]
