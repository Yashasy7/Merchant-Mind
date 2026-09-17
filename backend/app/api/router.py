"""
Main API router registering all modular sub-routers under /api.
"""

from fastapi import APIRouter
from app.api.v1.health import router as health_router

api_router = APIRouter()

# Health diagnostics endpoint: /api/health
api_router.include_router(health_router)

# Note: Future modules will register their routers here:
# api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
# api_router.include_router(sales_router, prefix="/sales", tags=["Sales Intelligence"])
# api_router.include_router(customers_router, prefix="/customers", tags=["Customer Intelligence"])
# api_router.include_router(growth_router, prefix="/growth", tags=["Growth AI"])
# api_router.include_router(campaign_router, prefix="/campaign", tags=["Campaign Simulator"])
# api_router.include_router(copilot_router, prefix="/copilot", tags=["AI Copilot"])
# api_router.include_router(accounting_router, prefix="/accounting", tags=["AI Accountant"])
# api_router.include_router(forecast_router, prefix="/forecast", tags=["Forecasting"])
