"""
Sales Intelligence API endpoints under /api/v1/sales.
Provides RESTful access to sales summaries, daily trends, period comparisons,
day-of-week distribution, hourly patterns, weekend metrics, and deterministic insights.
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.services.sales_service import SalesService
from app.schemas.sales import (
    SalesSummaryResponse,
    SalesTrendsResponse,
    SalesComparisonResponse,
    DayOfWeekAnalysisResponse,
    HourlyAnalysisResponse,
    WeekendAnalysisResponse,
    SalesInsightsResponse,
)

router = APIRouter(tags=["Sales Intelligence"])
settings = get_settings()


def validate_date_range(start_date: Optional[date], end_date: Optional[date]) -> None:
    """Validate that start_date does not exceed end_date."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date range: start_date ({start_date}) cannot be after end_date ({end_date})."
        )


def resolve_merchant_id(merchant_id: Optional[str]) -> str:
    """Resolve merchant ID, defaulting to configured DEMO_MERCHANT_ID if omitted."""
    return (merchant_id.strip() if merchant_id and merchant_id.strip() else settings.demo_merchant_id)


@router.get(
    "/summary",
    response_model=SalesSummaryResponse,
    summary="Get Sales Summary",
    description="Returns aggregate sales performance metrics, revenue, transaction counts, and success rate."
)
def get_sales_summary(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    start_date: Optional[date] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date filter (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
) -> SalesSummaryResponse:
    validate_date_range(start_date, end_date)
    m_id = resolve_merchant_id(merchant_id)
    service = SalesService(db)
    return service.get_summary(merchant_id=m_id, start_date=start_date, end_date=end_date)


@router.get(
    "/trends",
    response_model=SalesTrendsResponse,
    summary="Get Daily Sales Trends",
    description="Returns chronological daily time-series of revenue, transaction volume, and average basket sizes."
)
def get_sales_trends(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    start_date: Optional[date] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date filter (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
) -> SalesTrendsResponse:
    validate_date_range(start_date, end_date)
    m_id = resolve_merchant_id(merchant_id)
    service = SalesService(db)
    return service.get_daily_trends(merchant_id=m_id, start_date=start_date, end_date=end_date)


@router.get(
    "/comparison",
    response_model=SalesComparisonResponse,
    summary="Get Period Comparison",
    description="Compares current period against immediately preceding equivalent period, calculating percentage changes."
)
def get_sales_comparison(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    current_days: int = Query(14, ge=1, le=365, description="Number of days in the comparison window"),
    start_date: Optional[date] = Query(None, description="Custom current period start date"),
    end_date: Optional[date] = Query(None, description="Custom current period end date"),
    db: Session = Depends(get_db)
) -> SalesComparisonResponse:
    validate_date_range(start_date, end_date)
    m_id = resolve_merchant_id(merchant_id)
    service = SalesService(db)
    return service.get_period_comparison(
        merchant_id=m_id,
        current_days=current_days,
        start_date=start_date,
        end_date=end_date
    )


@router.get(
    "/day-of-week",
    response_model=DayOfWeekAnalysisResponse,
    summary="Get Day of Week Distribution",
    description="Analyzes sales performance across Monday through Sunday, highlighting strongest and weakest days."
)
def get_day_of_week(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    start_date: Optional[date] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date filter (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
) -> DayOfWeekAnalysisResponse:
    validate_date_range(start_date, end_date)
    m_id = resolve_merchant_id(merchant_id)
    service = SalesService(db)
    return service.get_day_of_week_analysis(merchant_id=m_id, start_date=start_date, end_date=end_date)


@router.get(
    "/hourly",
    response_model=HourlyAnalysisResponse,
    summary="Get Hourly & Time Window Breakdown",
    description="Aggregates sales by hour (0-23) and operating windows (Morning, Afternoon, Evening, Night)."
)
def get_hourly_analysis(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    start_date: Optional[date] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date filter (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
) -> HourlyAnalysisResponse:
    validate_date_range(start_date, end_date)
    m_id = resolve_merchant_id(merchant_id)
    service = SalesService(db)
    return service.get_hourly_analysis(merchant_id=m_id, start_date=start_date, end_date=end_date)


@router.get(
    "/weekend",
    response_model=WeekendAnalysisResponse,
    summary="Get Weekday vs Weekend Comparison",
    description="Compares weekday (Mon-Fri) and weekend (Sat-Sun) revenue, identifying weekend underperformance gaps."
)
def get_weekend_analysis(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    start_date: Optional[date] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date filter (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
) -> WeekendAnalysisResponse:
    validate_date_range(start_date, end_date)
    m_id = resolve_merchant_id(merchant_id)
    service = SalesService(db)
    return service.get_weekend_analysis(merchant_id=m_id, start_date=start_date, end_date=end_date)


@router.get(
    "/insights",
    response_model=SalesInsightsResponse,
    summary="Get Deterministic Sales Insights",
    description="Returns machine-readable, rule-based observations on sales decline, drivers, weekend gaps, and prime windows."
)
def get_sales_insights(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    current_days: int = Query(14, ge=1, le=365, description="Analysis lookback window in days"),
    db: Session = Depends(get_db)
) -> SalesInsightsResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = SalesService(db)
    return service.get_sales_insights(merchant_id=m_id, current_days=current_days)
