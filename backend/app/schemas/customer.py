"""
Pydantic schemas for Customer Intelligence module.
Provides response DTOs for customer summaries, RFM metrics, segment statistics,
top customer rankings, at-risk/inactive cohorts, detailed profiles, and deterministic insights.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class CustomerResponse(BaseModel):
    """Basic customer record schema (Module 1 foundation)."""
    customer_id: str
    merchant_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    transaction_count: int
    total_spend: Decimal
    last_transaction: Optional[datetime] = None
    average_transaction: Decimal
    segment: str

    model_config = ConfigDict(from_attributes=True)


class TransactionResponse(BaseModel):
    """Basic transaction record schema (Module 1 foundation)."""
    transaction_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    timestamp: datetime
    amount: Decimal
    payment_method: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class CustomerSummaryResponse(BaseModel):
    """Aggregate customer statistics for a merchant."""
    merchant_id: str
    total_customers: int = Field(..., description="Total unique customers on record")
    active_customers: int = Field(..., description="Customers with successful transaction in last 30 days")
    inactive_customers: int = Field(..., description="Customers absent for >45 days")
    at_risk_customers: int = Field(..., description="Customers absent between 22 and 45 days")
    new_customers: int = Field(..., description="Customers with 1-2 visits and first seen in last 30 days")
    repeat_customers: int = Field(..., description="Customers with 2 or more successful transactions")
    repeat_customer_rate: float = Field(..., description="Percentage of customers with repeat visits (%)")
    average_customer_spend: float = Field(..., description="Average total spend per customer (in INR)")
    average_transactions_per_customer: float = Field(..., description="Average transaction count per customer")
    total_customer_revenue: float = Field(..., description="Total cumulative customer revenue (in INR)")

    model_config = ConfigDict(from_attributes=True)


class RFMScore(BaseModel):
    """Recency, Frequency, and Monetary calculation and scoring."""
    recency_days: int = Field(..., description="Days since last successful purchase")
    frequency: int = Field(..., description="Total successful transactions")
    monetary: float = Field(..., description="Total spend in INR")
    r_score: int = Field(..., ge=1, le=5, description="Recency score 1 (worst) to 5 (best)")
    f_score: int = Field(..., ge=1, le=5, description="Frequency score 1 to 5")
    m_score: int = Field(..., ge=1, le=5, description="Monetary score 1 to 5")
    rfm_code: str = Field(..., description="Concatenated RFM string, e.g. '555'")


class CustomerSegmentStat(BaseModel):
    """Aggregate performance and distribution metrics for a single segment."""
    segment: str = Field(..., description="Segment name: VIP, Loyal, New, At-Risk, Inactive, Regular")
    customer_count: int
    total_revenue: float
    average_revenue_per_customer: float
    average_transaction_count: float
    percentage_of_customers: float = Field(..., description="Share of total customer base (%)")
    percentage_of_revenue: float = Field(..., description="Share of total customer revenue (%)")
    description: str


class CustomerSegmentsResponse(BaseModel):
    """Breakdown of customer base across all behavioral segments."""
    merchant_id: str
    total_customers: int
    total_revenue: float
    segments: List[CustomerSegmentStat]


class CustomerRankingItem(BaseModel):
    """Summary item for leaderboard and top customer listings."""
    rank: int
    customer_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    total_spend: float
    transaction_count: int
    average_transaction_value: float
    last_transaction_date: Optional[str] = None
    segment: str


class TopCustomersResponse(BaseModel):
    """Ranked listing of top customers by spend or frequency."""
    merchant_id: str
    ranked_by: str = Field(..., description="Sorting criterion: revenue | frequency")
    count: int
    customers: List[CustomerRankingItem]


class AtRiskCustomerItem(BaseModel):
    """Detailed record of a customer currently at risk of churning."""
    customer_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    last_transaction_date: Optional[str] = None
    days_since_last_transaction: int
    historical_spend: float
    transaction_count: int
    average_transaction_value: float
    segment: str
    risk_level: str = Field(..., description="high | medium | moderate")
    risk_reason: str


class AtRiskCustomersResponse(BaseModel):
    """Cohort of at-risk customers requiring re-engagement."""
    merchant_id: str
    total_at_risk: int
    total_at_risk_revenue: float = Field(..., description="Cumulative historical spend of at-risk cohort")
    customers: List[AtRiskCustomerItem]


class InactiveCustomerItem(BaseModel):
    """Detailed record of an inactive/dormant customer."""
    customer_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    last_transaction_date: Optional[str] = None
    days_since_last_transaction: int
    historical_spend: float
    transaction_count: int
    average_transaction_value: float
    segment: str
    dormancy_reason: str


class InactiveCustomersResponse(BaseModel):
    """Cohort of dormant customers absent for more than 45 days."""
    merchant_id: str
    total_inactive: int
    total_inactive_historical_revenue: float
    customers: List[InactiveCustomerItem]


class CustomerTransactionSummary(BaseModel):
    """Brief transaction entry for customer profile history."""
    transaction_id: str
    timestamp: str
    amount: float
    payment_method: str
    status: str


class CustomerDetailResponse(BaseModel):
    """Comprehensive individual customer profile with behavioral metrics and RFM."""
    customer_id: str
    merchant_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    total_spend: float
    transaction_count: int
    average_transaction_value: float
    first_transaction_date: Optional[str] = None
    last_transaction_date: Optional[str] = None
    days_since_last_transaction: Optional[int] = None
    segment: str
    rfm: Optional[RFMScore] = None
    recent_transactions: List[CustomerTransactionSummary] = []

    model_config = ConfigDict(from_attributes=True)


class CustomerInsightItem(BaseModel):
    """Structured, machine-readable observation regarding customer behavior."""
    type: str = Field(..., description="Insight code: revenue_concentration | at_risk_revenue | dormancy_scale | loyalty_strength")
    severity: str = Field(..., description="critical | warning | info | positive")
    title: str
    message: str
    metric: Optional[float] = None
    recommendation_context: Optional[str] = Field(None, description="Contextual guidance for future growth actions")


class CustomerInsightsResponse(BaseModel):
    """Collection of deterministic customer intelligence insights."""
    merchant_id: str
    insights: List[CustomerInsightItem]
