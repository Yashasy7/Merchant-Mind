"""
Growth Recommendation API endpoints under /api/v1/growth.
Provides RESTful access to evidence-backed growth recommendations,
ranked opportunities, and high-level growth diagnostics.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.services.growth_service import GrowthRecommendationService
from app.schemas.growth import (
    GrowthRecommendationsResponse,
    GrowthOpportunitiesResponse,
    GrowthSummaryResponse,
)

router = APIRouter(tags=["Growth Recommendation Engine"])
settings = get_settings()


def resolve_merchant_id(merchant_id: Optional[str]) -> str:
    """Resolve merchant ID, defaulting to configured DEMO_MERCHANT_ID if omitted."""
    return merchant_id.strip() if merchant_id and merchant_id.strip() else settings.demo_merchant_id


@router.get(
    "/recommendations",
    response_model=GrowthRecommendationsResponse,
    summary="Get Growth Recommendations",
    description="Returns prioritized, evidence-backed business growth recommendations synthesized from sales and customer intelligence."
)
def get_recommendations(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    goal: Optional[str] = Query(None, description="Filter by business goal: revenue, retention, recovery, reactivation, weekend, frequency"),
    limit: Optional[int] = Query(None, ge=1, le=50, description="Maximum number of recommendations to return (1-50)"),
    db: Session = Depends(get_db)
) -> GrowthRecommendationsResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = GrowthRecommendationService(db)
    return service.generate_recommendations(merchant_id=m_id, goal=goal, limit=limit)


@router.get(
    "/opportunities",
    response_model=GrowthOpportunitiesResponse,
    summary="Get Growth Opportunities",
    description="Lists all detected growth opportunities ranked by impact priority and evidence confidence."
)
def get_opportunities(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    limit: Optional[int] = Query(10, ge=1, le=50, description="Maximum number of opportunities to return (1-50)"),
    db: Session = Depends(get_db)
) -> GrowthOpportunitiesResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = GrowthRecommendationService(db)
    return service.get_opportunities(merchant_id=m_id, limit=limit)


@router.get(
    "/summary",
    response_model=GrowthSummaryResponse,
    summary="Get Growth Summary",
    description="Provides an executive overview of active growth opportunities, churn risk exposure, sales trend, and top recommendation."
)
def get_growth_summary(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    db: Session = Depends(get_db)
) -> GrowthSummaryResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = GrowthRecommendationService(db)
    return service.get_summary(merchant_id=m_id)
