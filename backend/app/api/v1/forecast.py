"""
Revenue Forecasting API endpoints under /api/v1/forecast.
Provides statistical sales projections, lower/upper range estimates, and daily timeline trends.
Strictly merchant-isolated with deterministic calculations.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.services.forecast_service import ForecastService
from app.schemas.forecast import ForecastSummaryResponse

router = APIRouter(tags=["Revenue Forecasting"])
settings = get_settings()


def resolve_merchant_id(merchant_id: Optional[str]) -> str:
    """Resolve merchant ID, defaulting to configured DEMO_MERCHANT_ID if omitted."""
    return (
        merchant_id.strip()
        if merchant_id and merchant_id.strip()
        else settings.demo_merchant_id
    )


@router.get(
    "/summary",
    response_model=ForecastSummaryResponse,
    summary="Get Revenue Forecast Summary",
    description=(
        "Returns statistical sales forecast based on 4-week rolling average, 2-week momentum, "
        "and day-of-week seasonality. Includes lower bound, central estimate, and upper bound."
    ),
)
def get_forecast_summary(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    historical_days: int = Query(28, ge=7, le=365, description="Historical lookback window in days (default: 28)"),
    horizon_days: int = Query(30, ge=1, le=180, description="Projected horizon in days (default: 30)"),
    days: Optional[int] = Query(None, ge=1, le=180, description="Forecast horizon in days (alias for horizon_days)"),
    db: Session = Depends(get_db),
) -> ForecastSummaryResponse:
    target_horizon = days if days is not None else horizon_days
    m_id = resolve_merchant_id(merchant_id)
    service = ForecastService(db)
    return service.get_forecast_summary(
        merchant_id=m_id,
        historical_days=historical_days,
        horizon_days=target_horizon,
    )


@router.get(
    "/sales",
    response_model=ForecastSummaryResponse,
    summary="Get Daily Sales Forecast Timeline",
    description="Returns full daily timeline combining observed historical revenue with future projected points.",
)
def get_forecast_sales_timeline(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    historical_days: int = Query(28, ge=7, le=365, description="Historical lookback window in days (default: 28)"),
    horizon_days: int = Query(30, ge=1, le=180, description="Projected horizon in days (default: 30)"),
    days: Optional[int] = Query(None, ge=1, le=180, description="Forecast horizon in days (alias for horizon_days)"),
    db: Session = Depends(get_db),
) -> ForecastSummaryResponse:
    target_horizon = days if days is not None else horizon_days
    m_id = resolve_merchant_id(merchant_id)
    service = ForecastService(db)
    return service.get_forecast_summary(
        merchant_id=m_id,
        historical_days=historical_days,
        horizon_days=target_horizon,
    )
