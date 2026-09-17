"""
Pydantic schemas for Growth Recommendation Engine (Module 4).
Provides structured, deterministic DTOs for business growth recommendations,
evidence objects, priority levels, and growth summary KPIs.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class RecommendationEvidence(BaseModel):
    """Structured analytical evidence supporting a growth recommendation."""
    metric_name: str = Field(..., description="Primary metric identifier")
    metric_value: float = Field(..., description="Numeric value observed")
    baseline_value: Optional[float] = Field(None, description="Comparative baseline or previous period value")
    threshold_applied: Optional[str] = Field(None, description="Deterministic rule threshold applied")
    context: str = Field(..., description="Human-readable context of the evidence")


class RecommendationItem(BaseModel):
    """Actionable, evidence-backed business growth recommendation."""
    recommendation_id: str = Field(..., description="Unique deterministic identifier, e.g. 'rec-decl-001'")
    type: str = Field(
        ...,
        description="Opportunity type: sales_decline_recovery | at_risk_reengagement | inactive_winback | vip_retention | weekend_growth | time_of_day_opportunity | revenue_concentration_risk"
    )
    title: str = Field(..., description="Concise, action-oriented headline")
    description: str = Field(..., description="Comprehensive explanation of the business situation")
    priority: str = Field(..., description="Deterministic priority: high | medium | low")
    confidence: str = Field(..., description="Evidence strength: strong | moderate | weak")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Normalized evidence strength (0.0 to 1.0)")
    target_segment: str = Field(..., description="Target customer cohort: At-Risk | Inactive | VIP | Loyal | New | All Customers")
    objective: str = Field(..., description="Measurable business goal (e.g. 'recover declining revenue', 'reactivate at-risk customers')")
    suggested_action: str = Field(..., description="Strategic business intervention recommended")
    rationale: str = Field(..., description="Why this recommendation matters for merchant growth")
    estimated_scope: str = Field(..., description="Quantitative scale of impact (customers or revenue exposed)")
    evidence: List[RecommendationEvidence] = Field(default_factory=list, description="Granular analytical proofs")
    supporting_metrics: Dict[str, float] = Field(default_factory=dict, description="Raw numeric values for frontend display")

    model_config = ConfigDict(from_attributes=True)


class GrowthRecommendationsResponse(BaseModel):
    """Collection of structured growth recommendations for a merchant."""
    merchant_id: str
    goal_filter: Optional[str] = Field(None, description="Applied business goal filter, if any")
    total_recommendations: int
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    recommendations: List[RecommendationItem]


class GrowthOpportunitiesResponse(BaseModel):
    """Listing of detected growth opportunities."""
    merchant_id: str
    total_opportunities: int
    opportunities: List[RecommendationItem]


class GrowthSummaryResponse(BaseModel):
    """High-level merchant growth diagnostics and opportunity summary."""
    merchant_id: str
    total_opportunities: int
    high_priority_opportunities: int
    revenue_at_risk: float = Field(..., description="Total revenue exposed to churning customers (INR)")
    customers_at_risk: int = Field(..., description="Count of customers showing churn signals")
    strongest_opportunity_type: Optional[str] = Field(None, description="Primary recommendation type recommended")
    current_sales_trend: str = Field(..., description="Sales direction: declining | stable | growing | insufficient_data")
    current_retention_signal: str = Field(..., description="Customer retention health: strong | moderate | at_risk | no_data")
    key_recommendation: Optional[RecommendationItem] = Field(None, description="Top ranked actionable recommendation")

    model_config = ConfigDict(from_attributes=True)
