"""
Pydantic schemas for Module 9: Revenue Forecasting.
Provides models for daily timeline points, range projections, and summary estimates.
"""

from typing import List, Optional
from datetime import date
from pydantic import BaseModel, Field, ConfigDict

FORECAST_DISCLAIMER = (
    "Prototype estimate based on synthetic demo data only. "
    "Projections are statistical indications and do not guarantee actual future revenue or business performance."
)


class ForecastPoint(BaseModel):
    """Data point in the historical or projected daily timeline."""
    date: str = Field(..., description="Date formatted as YYYY-MM-DD")
    amount: float = Field(..., description="Observed historical or projected central revenue in INR")
    lower_bound: Optional[float] = Field(None, description="Lower statistical confidence bound")
    upper_bound: Optional[float] = Field(None, description="Upper statistical confidence bound")
    is_forecast: bool = Field(False, description="True if point is projected; False if observed historical data")

    model_config = ConfigDict(from_attributes=True)


class ForecastSummaryResponse(BaseModel):
    """Complete summary of revenue forecast and historical baseline."""
    merchant_id: str
    historical_period_days: int = Field(28, description="Lookback window in days (default: 28 days / 4 weeks)")
    forecast_horizon_days: int = Field(30, description="Projected horizon in days (default: 30 days)")
    historical_revenue: float = Field(..., description="Total observed revenue across lookback window")
    projected_revenue: float = Field(..., description="Total projected central revenue for forecast horizon")
    lower_bound: float = Field(..., description="Total projected lower bound (-10%)")
    upper_bound: float = Field(..., description="Total projected upper bound (+10%)")
    trend_direction: str = Field("stable", description="growing | declining | stable")
    trend_factor_pct: float = Field(0.0, description="Percentage change in recent 2-week momentum vs prior 2-weeks")
    forecast_method: str = Field("4-week rolling average with 2-week trend factor & day-of-week seasonality")
    is_sufficient_data: bool = Field(True, description="False if historical records are fewer than 7 days")
    daily_points: List[ForecastPoint] = Field(default_factory=list, description="Historical observed + projected points")
    disclaimer: str = Field(default=FORECAST_DISCLAIMER)

    model_config = ConfigDict(from_attributes=True)
