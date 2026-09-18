"""
Pydantic schemas for Module 9: Business Health & Risk Assessment.
Provides strongly-typed schemas for multidimensional business health scoring,
evidence-based risk signals, and upside growth opportunities.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

HEALTH_DISCLAIMER = (
    "Business health indicators and risk signals are derived deterministically from historical transaction, "
    "customer, and operational records. They provide decision support and do not constitute an audited financial assessment."
)


class HealthDimension(BaseModel):
    """Evaluation of a specific business health dimension (0-100 score)."""
    dimension_name: str = Field(..., description="revenue_trend | customer_retention | profitability | operational_risk | growth_readiness")
    score: float = Field(..., ge=0.0, le=100.0, description="Normalized dimension score from 0 to 100")
    status: str = Field(..., description="excellent | good | warning | critical")
    metric_summary: str = Field(..., description="Concise human-readable explanation of the metric state")
    details: Dict[str, Any] = Field(default_factory=dict, description="Key numerical metrics supporting the score")

    model_config = ConfigDict(from_attributes=True)


class RiskInsight(BaseModel):
    """Identified business risk signal backed by deterministic evidence."""
    risk_id: str = Field(..., description="Unique risk identifier")
    category: str = Field(..., description="revenue | customer | margin | operational")
    severity: str = Field(..., description="high | medium | low")
    title: str = Field(..., description="Short risk headline")
    description: str = Field(..., description="Detailed description of the observed warning signal")
    metric_evidence: str = Field(..., description="Specific metric data proving this risk")
    suggested_action: Optional[str] = Field(None, description="Recommended operational or marketing remedy")

    model_config = ConfigDict(from_attributes=True)


class OpportunityInsight(BaseModel):
    """Identified positive business growth opportunity backed by deterministic evidence."""
    opportunity_id: str = Field(..., description="Unique opportunity identifier")
    category: str = Field(..., description="revenue_expansion | retention | weekend_lift | basket_size")
    potential_impact: str = Field(..., description="high | medium | low")
    title: str = Field(..., description="Short opportunity headline")
    description: str = Field(..., description="Detailed explanation of the growth opportunity")
    metric_evidence: str = Field(..., description="Specific metric data supporting this opportunity")
    recommendation_id: Optional[str] = Field(None, description="Linked Module 4 growth recommendation ID if applicable")

    model_config = ConfigDict(from_attributes=True)


class BusinessHealthResponse(BaseModel):
    """Unified composite business health assessment across 5 core dimensions."""
    merchant_id: str
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Composite weighted health score (0 to 100)")
    overall_status: str = Field(..., description="healthy | stable | at_risk | critical")
    dimensions: List[HealthDimension] = Field(default_factory=list, description="Scores and metrics across 5 dimensions")
    risks: List[RiskInsight] = Field(default_factory=list, description="Identified warning signals")
    opportunities: List[OpportunityInsight] = Field(default_factory=list, description="Identified growth opportunities")
    summary: str = Field(..., description="High-level executive narrative of store health")
    disclaimer: str = Field(default=HEALTH_DISCLAIMER)

    model_config = ConfigDict(from_attributes=True)


class RiskListResponse(BaseModel):
    """List of identified business risks."""
    merchant_id: str
    total_risks: int
    risks: List[RiskInsight] = Field(default_factory=list)
    disclaimer: str = Field(default=HEALTH_DISCLAIMER)

    model_config = ConfigDict(from_attributes=True)


class OpportunityListResponse(BaseModel):
    """List of identified growth opportunities."""
    merchant_id: str
    total_opportunities: int
    opportunities: List[OpportunityInsight] = Field(default_factory=list)
    disclaimer: str = Field(default=HEALTH_DISCLAIMER)

    model_config = ConfigDict(from_attributes=True)
