"""
Customer Intelligence API endpoints under /api/v1/customers.
Provides RESTful access to customer summaries, behavioral segments, top customer rankings,
at-risk cohorts, inactive cohorts, individual customer profiles, and deterministic insights.
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException, status, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.services.customer_service import CustomerService
from app.schemas.customer import (
    CustomerSummaryResponse,
    CustomerSegmentsResponse,
    TopCustomersResponse,
    AtRiskCustomersResponse,
    InactiveCustomersResponse,
    CustomerDetailResponse,
    CustomerInsightsResponse,
)

router = APIRouter(tags=["Customer Intelligence"])
settings = get_settings()


def resolve_merchant_id(merchant_id: Optional[str]) -> str:
    """Resolve merchant ID, defaulting to configured DEMO_MERCHANT_ID if omitted."""
    return merchant_id.strip() if merchant_id and merchant_id.strip() else settings.demo_merchant_id


@router.get(
    "/summary",
    response_model=CustomerSummaryResponse,
    summary="Get Customer Summary",
    description="Returns merchant-level customer KPIs: total, active, inactive, at-risk, new, repeat rates, and spend."
)
def get_customer_summary(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    as_of_date: Optional[date] = Query(None, description="Reference date for recency calculations (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
) -> CustomerSummaryResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = CustomerService(db)
    return service.get_summary(merchant_id=m_id, as_of_date=as_of_date)


@router.get(
    "/segments",
    response_model=CustomerSegmentsResponse,
    summary="Get Customer Segments",
    description="Returns aggregate distribution, revenue contribution, and metrics across all behavioral segments."
)
def get_customer_segments(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    db: Session = Depends(get_db)
) -> CustomerSegmentsResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = CustomerService(db)
    return service.get_segments(merchant_id=m_id)


@router.get(
    "/top",
    response_model=TopCustomersResponse,
    summary="Get Top Customers",
    description="Returns ranked top customers sorted by monetary revenue or visit frequency."
)
def get_top_customers(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    by: str = Query("revenue", description="Ranking metric: 'revenue' | 'frequency'"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of customers to return (1-100)"),
    db: Session = Depends(get_db)
) -> TopCustomersResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = CustomerService(db)
    return service.get_top_customers(merchant_id=m_id, by=by, limit=limit)


@router.get(
    "/at-risk",
    response_model=AtRiskCustomersResponse,
    summary="Get At-Risk Customers",
    description="Identifies previously active customers who have not visited in 22-45 days and are at risk of churning."
)
def get_at_risk_customers(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of customers to return (1-200)"),
    db: Session = Depends(get_db)
) -> AtRiskCustomersResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = CustomerService(db)
    return service.get_at_risk_customers(merchant_id=m_id, limit=limit)


@router.get(
    "/inactive",
    response_model=InactiveCustomersResponse,
    summary="Get Inactive Customers",
    description="Identifies dormant customers who have not visited for more than 45 days."
)
def get_inactive_customers(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of customers to return (1-200)"),
    db: Session = Depends(get_db)
) -> InactiveCustomersResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = CustomerService(db)
    return service.get_inactive_customers(merchant_id=m_id, limit=limit)


@router.get(
    "/insights",
    response_model=CustomerInsightsResponse,
    summary="Get Customer Insights",
    description="Provides deterministic, rule-based observations on revenue concentration, churn risk, and retention."
)
def get_customer_insights(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    db: Session = Depends(get_db)
) -> CustomerInsightsResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = CustomerService(db)
    return service.get_insights(merchant_id=m_id)


@router.get(
    "/{customer_id}",
    response_model=CustomerDetailResponse,
    summary="Get Customer Detail",
    description="Returns detailed customer profile including RFM scores and recent transactions. Enforces merchant isolation."
)
def get_customer_detail(
    customer_id: str = Path(..., description="Unique customer identifier"),
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    db: Session = Depends(get_db)
) -> CustomerDetailResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = CustomerService(db)
    return service.get_customer_detail(customer_id=customer_id, merchant_id=m_id)
