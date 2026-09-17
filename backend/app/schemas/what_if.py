"""
Pydantic schemas for Module 5 — What-if Simulator.
Defines strongly typed, JSON-safe DTOs for baseline calculations, individual scenario simulations,
multi-strategy comparisons, and deterministic assumptions.
All models are strictly labeled as synthetic demo projections.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ScenarioAssumptions(BaseModel):
    """Explicit, explainable assumptions underlying a simulated scenario."""
    transaction_uplift_percent: float = Field(..., description="Estimated percentage increase in transaction volume")
    discount_percent: float = Field(0.0, description="Applied discount percentage")
    cashback_amount: float = Field(0.0, description="Applied cashback amount in INR per transaction")
    eligibility_rate_percent: float = Field(80.0, description="Estimated percentage of transactions/customers qualifying")
    minimum_transaction_amount: float = Field(0.0, description="Minimum order amount required to receive offer")
    assumption_type: str = Field("illustrative_demo_assumption", description="Metadata category for assumptions")
    explanation: str = Field(..., description="Plain-language breakdown of model assumptions")

    model_config = ConfigDict(from_attributes=True)


class SimulationScenario(BaseModel):
    """Projected outcomes and financials for a single promotional strategy."""
    scenario_id: str = Field(..., description="Unique scenario identifier, e.g. 'scenario-5pct-discount'")
    scenario_name: str = Field(..., description="Display name, e.g. '5% Discount'")
    scenario_type: str = Field(..., description="Strategy type: no_offer | percentage_discount | fixed_cashback | custom")
    description: str = Field(..., description="Tactical description of the promotional scenario")
    target_segment: str = Field("All Customers", description="Target customer cohort")
    target_segment_size: Optional[int] = Field(None, description="Estimated number of customers in target cohort")
    target_days: Optional[str] = Field(None, description="Targeted days filter (weekend, weekday, all)")
    target_hours: Optional[str] = Field(None, description="Targeted time window (morning, afternoon, evening, night, all)")

    # Baseline financials
    baseline_revenue: float = Field(..., description="Historical baseline revenue over evaluation window (INR)")
    baseline_transactions: int = Field(..., description="Historical baseline transaction count")
    baseline_average_order_value: float = Field(..., description="Historical baseline ATV/AOV (INR)")

    # Projected outcomes
    projected_revenue: float = Field(..., description="Expected merchant revenue after offer execution (INR)")
    gross_projected_revenue: float = Field(..., description="Expected gross GMV before promotional deductions (INR)")
    projected_transactions: int = Field(..., description="Expected total transactions with promotional uplift")
    incremental_transactions: int = Field(..., description="Projected incremental transactions (projected - baseline)")
    projected_average_order_value: float = Field(..., description="Expected average order value after offer (INR)")

    # Costs & Net Return
    estimated_incentive_cost: float = Field(..., description="Estimated cost of discounts or cashbacks funded (INR)")
    gross_incremental_revenue: float = Field(..., description="Gross incremental revenue (gross_projected - baseline)")
    net_incremental_impact: float = Field(..., description="Net economic gain (gross_incremental_revenue - incentive_cost)")
    estimated_roi: Optional[float] = Field(None, description="Estimated return on incentive investment (net_gain / cost)")
    roi_multiplier_label: Optional[str] = Field(None, description="Human-readable ROI multiplier string, e.g. '2.7x' or 'N/A'")

    # Confidence & Assumptions
    confidence_score: float = Field(0.85, ge=0.0, le=1.0, description="Analytical certainty of the simulation estimate")
    assumptions: ScenarioAssumptions = Field(..., description="Explicit parameters used to generate this projection")
    is_demo_projection: bool = Field(True, description="Always true; flags that figures are demo estimates")

    model_config = ConfigDict(from_attributes=True)


class SimulationBaselineResponse(BaseModel):
    """Historical baseline metrics used as the benchmark for simulation scenarios."""
    merchant_id: str
    has_sufficient_data: bool = Field(..., description="Whether the merchant has adequate historical data for simulation")
    baseline_window: str = Field(..., description="Historical time window analyzed (e.g. 'Last 30 days')")
    target_segment: str = Field("All Customers", description="Target customer segment")
    target_segment_size: Optional[int] = Field(None, description="Number of customers in target segment")
    baseline_revenue: float = Field(..., description="Total baseline revenue (INR)")
    baseline_transactions: int = Field(..., description="Total baseline successful transactions")
    baseline_average_order_value: float = Field(..., description="Baseline average order value (INR)")
    data_notes: Optional[str] = Field(None, description="Additional context on historical data completeness")
    is_demo_projection: bool = Field(True, description="Always true")

    model_config = ConfigDict(from_attributes=True)


class SimulationRequest(BaseModel):
    """Input payload to simulate a single custom promotional scenario."""
    merchant_id: Optional[str] = Field(None, description="Merchant identifier (defaults to demo merchant)")
    scenario_name: Optional[str] = Field(None, description="Custom label for this scenario")
    scenario_type: str = Field("percentage_discount", description="Strategy type: no_offer | percentage_discount | fixed_cashback | custom")
    target_segment: Optional[str] = Field("All Customers", description="Target customer segment: All Customers | VIP | Loyal | New | At-Risk | Inactive | Regular")
    discount_percent: Optional[float] = Field(None, ge=0.0, le=50.0, description="Discount percentage between 0% and 50%")
    cashback_amount: Optional[float] = Field(None, ge=0.0, le=2000.0, description="Cashback amount in INR per qualifying transaction")
    minimum_transaction_amount: Optional[float] = Field(0.0, ge=0.0, description="Minimum order amount required to qualify (INR)")
    target_days: Optional[str] = Field(None, description="Filter: weekend | weekday | all")
    target_hours: Optional[str] = Field(None, description="Filter: morning | afternoon | evening | night | all")
    uplift_assumption: Optional[float] = Field(None, ge=0.0, le=100.0, description="Custom transaction volume uplift percentage (0-100%)")
    participation_rate: Optional[float] = Field(None, ge=0.0, le=100.0, description="Estimated customer eligibility/participation percentage (0-100%)")
    recommendation_id: Optional[str] = Field(None, description="Optional GrowthRecommendation ID to import target context from")

    @field_validator("scenario_type")
    @classmethod
    def validate_scenario_type(cls, v: str) -> str:
        valid = {"no_offer", "percentage_discount", "fixed_cashback", "custom"}
        if v.lower() not in valid:
            raise ValueError(f"Invalid scenario_type '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return v.lower()


class WhatIfCompareRequest(BaseModel):
    """Input payload to run standard multi-scenario comparison."""
    merchant_id: Optional[str] = Field(None, description="Merchant identifier (defaults to demo merchant)")
    target_segment: Optional[str] = Field("All Customers", description="Customer segment to evaluate against")
    target_days: Optional[str] = Field(None, description="Optional day targeting: weekend | weekday | all")
    target_hours: Optional[str] = Field(None, description="Optional hour targeting: morning | afternoon | evening | night | all")
    custom_discount_percent: Optional[float] = Field(None, ge=0.0, le=50.0, description="Optional custom discount % to include")
    custom_cashback_amount: Optional[float] = Field(None, ge=0.0, le=2000.0, description="Optional custom cashback to include")
    recommendation_id: Optional[str] = Field(None, description="Optional GrowthRecommendation ID (Module 4) to bind context from")


class WhatIfComparisonResponse(BaseModel):
    """Standard multi-strategy comparison table and recommendation."""
    merchant_id: str
    status: str = Field("success", description="Status code: success | insufficient_data")
    target_segment: str = Field("All Customers", description="Evaluated customer cohort")
    target_segment_size: Optional[int] = Field(None, description="Size of the customer cohort")
    target_days: Optional[str] = Field(None, description="Active day filter if applicable")
    target_hours: Optional[str] = Field(None, description="Active hour filter if applicable")
    recommendation_context_id: Optional[str] = Field(None, description="Associated GrowthRecommendation ID if bound")
    baseline: SimulationBaselineResponse = Field(..., description="Historical baseline reference")
    scenarios: List[SimulationScenario] = Field(default_factory=list, description="List of simulated promotional strategies")
    recommended_scenario_id: Optional[str] = Field(None, description="Deterministic scenario ID with highest net incremental impact")
    recommended_scenario_name: Optional[str] = Field(None, description="Display name of the recommended scenario")
    recommendation_reason: Optional[str] = Field(None, description="Analytical rationale for selecting this strategy")
    comparison_summary: str = Field(..., description="Executive summary comparing the strategies")
    assumptions_notice: str = Field(
        "All simulated projections are based on synthetic demo elasticity assumptions and historical trends.",
        description="Standard transparency notice"
    )
    disclaimer: str = Field(
        "Synthetic / Illustrative Demo Projection — Not a guaranteed forecast or real Paytm campaign prediction.",
        description="Mandatory product disclaimer"
    )
    is_demo_projection: bool = Field(True, description="Always true")
    data_type: str = Field("SYNTHETIC_DEMO", description="Mandatory metadata tag")

    model_config = ConfigDict(from_attributes=True)
