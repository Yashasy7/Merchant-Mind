"""
Pydantic schemas for Sales Intelligence module.
Provides response DTOs for sales summaries, daily trends, period comparisons,
day-of-week distributions, hourly/window breakdowns, weekend analysis, and deterministic insights.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class SalesSummaryResponse(BaseModel):
    """Aggregate sales performance summary for a merchant."""
    merchant_id: str
    total_revenue: float = Field(..., description="Total revenue from successful transactions (in INR)")
    total_transactions: int = Field(..., description="Total transaction count (all statuses)")
    average_transaction_value: float = Field(..., description="Average value per successful transaction")
    minimum_transaction_value: float = Field(..., description="Smallest single transaction amount")
    maximum_transaction_value: float = Field(..., description="Largest single transaction amount")
    successful_transactions: int = Field(..., description="Count of completed successful transactions")
    failed_transactions: int = Field(..., description="Count of failed or declined transactions")
    success_rate: float = Field(..., description="Percentage of transactions successfully completed")
    start_date: Optional[str] = Field(None, description="Start date of analysis range (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date of analysis range (YYYY-MM-DD)")

    model_config = ConfigDict(from_attributes=True)


class SalesTrendPoint(BaseModel):
    """Daily aggregated sales metric point."""
    date: str = Field(..., description="Calendar date (YYYY-MM-DD)")
    revenue: float = Field(..., description="Daily successful revenue")
    transaction_count: int = Field(..., description="Daily successful transaction count")
    average_transaction_value: float = Field(..., description="Average spend per transaction on this day")


class SalesTrendsResponse(BaseModel):
    """Time-series daily sales trend response."""
    merchant_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_days: int
    trends: List[SalesTrendPoint]


class PeriodMetrics(BaseModel):
    """Sales metrics for a distinct time period."""
    start_date: str
    end_date: str
    revenue: float
    transaction_count: int
    average_transaction_value: float


class SalesComparisonResponse(BaseModel):
    """Period-over-period sales performance comparison."""
    merchant_id: str
    current_period: PeriodMetrics
    previous_period: PeriodMetrics
    revenue_change: float = Field(..., description="Absolute change in revenue (current - previous)")
    revenue_change_percentage: float = Field(..., description="Percentage change in revenue")
    transaction_change: int = Field(..., description="Absolute change in transaction count")
    transaction_change_percentage: float = Field(..., description="Percentage change in transaction volume")
    average_transaction_value_change: float = Field(..., description="Absolute change in average basket size")
    average_transaction_value_change_percentage: float = Field(..., description="Percentage change in average basket size")


class DayOfWeekMetric(BaseModel):
    """Aggregated sales metric for a specific day of the week."""
    day_name: str = Field(..., description="Name of day (Monday through Sunday)")
    day_index: int = Field(..., description="0 for Monday, 6 for Sunday")
    revenue: float
    transaction_count: int
    average_transaction_value: float
    revenue_share_percentage: float = Field(..., description="Share of total weekly revenue (%)")


class DayOfWeekAnalysisResponse(BaseModel):
    """Sales breakdown by day of the week."""
    merchant_id: str
    days: List[DayOfWeekMetric]
    strongest_day: str = Field(..., description="Day with highest total revenue")
    weakest_day: str = Field(..., description="Day with lowest total revenue")


class HourlyMetric(BaseModel):
    """Aggregated sales metric for an individual hour of the day."""
    hour: int = Field(..., ge=0, le=23, description="Hour of day (0 to 23)")
    hour_label: str = Field(..., description="Human-readable hour interval (e.g. 18:00 - 19:00)")
    revenue: float
    transaction_count: int
    average_transaction_value: float


class TimeWindowMetric(BaseModel):
    """Aggregated sales metric for broader operating time windows."""
    window_name: str = Field(..., description="Morning, Afternoon, Evening, or Night")
    hours_range: str = Field(..., description="Time span (e.g. 06:00 - 12:00)")
    revenue: float
    transaction_count: int
    average_transaction_value: float
    revenue_share_percentage: float


class HourlyAnalysisResponse(BaseModel):
    """Hourly and time-window sales distribution response."""
    merchant_id: str
    hourly_metrics: List[HourlyMetric]
    time_windows: List[TimeWindowMetric]
    peak_hour: int
    lowest_hour: int


class WeekendAnalysisResponse(BaseModel):
    """Comparative analysis between weekday (Mon-Fri) and weekend (Sat-Sun) performance."""
    merchant_id: str
    weekday_revenue: float
    weekend_revenue: float
    weekday_transactions: int
    weekend_transactions: int
    weekday_average_transaction_value: float
    weekend_average_transaction_value: float
    weekend_revenue_share_percentage: float = Field(..., description="Weekend revenue as % of total sales")
    daily_avg_weekday_revenue: float = Field(..., description="Average revenue per weekday (Mon-Fri)")
    daily_avg_weekend_revenue: float = Field(..., description="Average revenue per weekend day (Sat-Sun)")
    weekend_to_weekday_revenue_ratio: float = Field(..., description="Ratio of weekend daily avg to weekday daily avg")
    is_weekend_underperforming: bool = Field(..., description="True if weekend daily avg is lower than weekday daily avg")


class SalesInsight(BaseModel):
    """Structured, machine-readable insight produced by deterministic analysis."""
    insight_type: str = Field(..., description="Type code (e.g. revenue_decline, volume_drop, weekend_gap)")
    severity: str = Field(..., description="Severity level: critical | warning | info | positive")
    metric: str = Field(..., description="Target metric (revenue | transactions | basket_size | timing)")
    title: str = Field(..., description="Concise insight title")
    explanation: str = Field(..., description="Clear explanation of the observed pattern")
    current_value: Optional[float] = None
    previous_value: Optional[float] = None
    change_percentage: Optional[float] = None


class SalesInsightsResponse(BaseModel):
    """Collection of structured sales intelligence insights for a merchant."""
    merchant_id: str
    has_decline: bool = Field(..., description="True if a meaningful sales decline is detected")
    primary_driver: Optional[str] = Field(None, description="Primary cause: volume_driven | basket_driven | volume_and_basket_driven | none")
    insights: List[SalesInsight]
