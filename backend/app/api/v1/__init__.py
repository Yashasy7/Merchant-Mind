"""
API v1 package initialization.
"""

from app.api.v1.health import router as health_router
from app.api.v1.sales import router as sales_router
from app.api.v1.customers import router as customers_router
from app.api.v1.growth import router as growth_router
from app.api.v1.what_if import router as what_if_router

__all__ = [
    "health_router",
    "sales_router",
    "customers_router",
    "growth_router",
    "what_if_router",
]

