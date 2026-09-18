"""
Business Health API endpoints under /api/v1/business-health.
Provides multidimensional health scoring, evidence-backed risk alerts, and growth opportunities.
Strictly merchant-isolated with deterministic calculations.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.services.business_health_service import BusinessHealthService
from app.schemas.business_health import (
    BusinessHealthResponse,
    RiskListResponse,
    OpportunityListResponse,
)

router = APIRouter(tags=["Business Health"])
settings = get_settings()


def resolve_merchant_id(merchant_id: Optional[str]) -> str:
    """Resolve merchant ID, defaulting to configured DEMO_MERCHANT_ID if omitted."""
    return (
        merchant_id.strip()
        if merchant_id and merchant_id.strip()
        else settings.demo_merchant_id
    )


@router.get(
    "",
    response_model=BusinessHealthResponse,
    summary="Get Business Health Assessment",
    description=(
        "Returns composite merchant health score (0-100) and multidimensional evaluations across "
        "Revenue Trend, Customer Retention, Profitability, Operational Risk, and Growth Readiness."
    ),
)
def get_business_health(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    db: Session = Depends(get_db),
) -> BusinessHealthResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = BusinessHealthService(db)
    return service.get_business_health(merchant_id=m_id)


@router.get(
    "/risks",
    response_model=RiskListResponse,
    summary="Get Business Risk Warning Signals",
    description="Returns actionable business risk alerts backed by quantitative transaction and customer evidence.",
)
def get_business_risks(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    db: Session = Depends(get_db),
) -> RiskListResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = BusinessHealthService(db)
    return service.get_risks(merchant_id=m_id)


@router.get(
    "/opportunities",
    response_model=OpportunityListResponse,
    summary="Get Business Growth Opportunities",
    description="Returns identified growth upside levers linked to actionable marketing recommendations.",
)
def get_business_opportunities(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    db: Session = Depends(get_db),
) -> OpportunityListResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = BusinessHealthService(db)
    return service.get_opportunities(merchant_id=m_id)
