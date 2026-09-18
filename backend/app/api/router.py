"""
Main API router registering all modular sub-routers under /api.
"""

from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.sales import router as sales_router
from app.api.v1.customers import router as customers_router
from app.api.v1.growth import router as growth_router
from app.api.v1.what_if import router as what_if_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.agent import router as agent_router
from app.api.v1.accountant import router as accountant_router

api_router = APIRouter()

# Health diagnostics endpoint: /api/health
api_router.include_router(health_router)

# Module 2 — Sales Intelligence endpoints: /api/v1/sales/* and alias /api/sales/*
api_router.include_router(sales_router, prefix="/v1/sales")
api_router.include_router(sales_router, prefix="/sales", include_in_schema=False)

# Module 3 — Customer Intelligence endpoints: /api/v1/customers/* and alias /api/customers/*
api_router.include_router(customers_router, prefix="/v1/customers")
api_router.include_router(customers_router, prefix="/customers", include_in_schema=False)

# Module 4 — Growth Recommendation Engine endpoints: /api/v1/growth/* and alias /api/growth/*
api_router.include_router(growth_router, prefix="/v1/growth")
api_router.include_router(growth_router, prefix="/growth", include_in_schema=False)

# Module 5 — What-if Simulator endpoints: /api/v1/what-if/* and aliases /api/what-if/*, /api/campaign/*
api_router.include_router(what_if_router, prefix="/v1/what-if")
api_router.include_router(what_if_router, prefix="/what-if", include_in_schema=False)
api_router.include_router(what_if_router, prefix="/campaign", include_in_schema=False)

# Module 6 — Campaign / Approval / Action endpoints: /api/v1/campaigns/* and alias /api/campaigns/*
api_router.include_router(campaigns_router, prefix="/v1/campaigns")
api_router.include_router(campaigns_router, prefix="/campaigns", include_in_schema=False)

# Module 7 — AI Marketing / Campaign Agent endpoints: /api/v1/agent/* and alias /api/agent/*
api_router.include_router(agent_router, prefix="/v1/agent")
api_router.include_router(agent_router, prefix="/agent", include_in_schema=False)

# Module 8 — AI Accountant endpoints: /api/v1/accountant/* and alias /api/accountant/*
api_router.include_router(accountant_router, prefix="/v1/accountant")
api_router.include_router(accountant_router, prefix="/accountant", include_in_schema=False)

# Note: Future modules will register their routers here:
# api_router.include_router(copilot_router, prefix="/copilot", tags=["AI Copilot"])
# api_router.include_router(accounting_router, prefix="/accounting", tags=["AI Accountant"])
# api_router.include_router(forecast_router, prefix="/forecast", tags=["Forecasting"])


