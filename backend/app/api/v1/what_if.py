"""
What-if Simulator API endpoints under /api/v1/what-if.
Provides RESTful access to baseline calculations, single-strategy promotional simulations,
multi-scenario comparisons, and standard strategy benchmarks.
All outputs are strictly labeled as synthetic demo projections.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.services.what_if_service import WhatIfSimulationService
from app.schemas.what_if import (
    SimulationBaselineResponse,
    SimulationRequest,
    SimulationScenario,
    WhatIfCompareRequest,
    WhatIfComparisonResponse,
)

router = APIRouter(tags=["What-if Simulator"])
settings = get_settings()


def resolve_merchant_id(merchant_id: Optional[str]) -> str:
    """Resolve merchant ID, defaulting to configured DEMO_MERCHANT_ID if omitted."""
    return merchant_id.strip() if merchant_id and merchant_id.strip() else settings.demo_merchant_id


@router.get(
    "/baseline",
    response_model=SimulationBaselineResponse,
    summary="Get Simulation Baseline",
    description="Returns the historical transaction baseline used as the benchmark for simulation scenarios."
)
def get_simulation_baseline(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    target_segment: Optional[str] = Query("All Customers", description="Target customer segment (All Customers, VIP, Loyal, New, At-Risk, Inactive, Regular)"),
    target_days: Optional[str] = Query(None, description="Filter: weekend | weekday | all"),
    target_hours: Optional[str] = Query(None, description="Filter: morning | afternoon | evening | night | all"),
    db: Session = Depends(get_db)
) -> SimulationBaselineResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = WhatIfSimulationService(db)
    return service.get_baseline(
        merchant_id=m_id,
        target_segment=target_segment,
        target_days=target_days,
        target_hours=target_hours,
    )


@router.post(
    "/simulate",
    response_model=SimulationScenario,
    summary="Simulate Promotional Scenario",
    description="Simulates a single custom promotional strategy (discount, cashback, or custom) and computes projected volume, revenue, costs, and ROI."
)
def simulate_promotional_scenario(
    request: SimulationRequest = Body(...),
    db: Session = Depends(get_db)
) -> SimulationScenario:
    m_id = resolve_merchant_id(request.merchant_id)
    service = WhatIfSimulationService(db)
    return service.simulate_scenario(merchant_id=m_id, request=request)


@router.post(
    "/compare",
    response_model=WhatIfComparisonResponse,
    summary="Compare Promotional Strategies",
    description="Simulates and compares standard promotional strategies (No Offer, 5% Discount, 10% Discount, ₹50 Cashback) against historical merchant baseline."
)
def compare_promotional_strategies(
    request: WhatIfCompareRequest = Body(...),
    db: Session = Depends(get_db)
) -> WhatIfComparisonResponse:
    m_id = resolve_merchant_id(request.merchant_id)
    service = WhatIfSimulationService(db)
    return service.compare_scenarios(merchant_id=m_id, request=request)


@router.get(
    "/scenarios",
    response_model=WhatIfComparisonResponse,
    summary="Get Standard Scenarios (GET)",
    description="Convenience GET endpoint to retrieve the standard multi-scenario comparison table for a merchant."
)
def get_standard_scenarios(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    target_segment: Optional[str] = Query("All Customers", description="Target customer cohort"),
    target_days: Optional[str] = Query(None, description="Filter: weekend | weekday | all"),
    target_hours: Optional[str] = Query(None, description="Filter: morning | afternoon | evening | night | all"),
    recommendation_id: Optional[str] = Query(None, description="Optional GrowthRecommendation ID to bind context from"),
    db: Session = Depends(get_db)
) -> WhatIfComparisonResponse:
    m_id = resolve_merchant_id(merchant_id)
    compare_req = WhatIfCompareRequest(
        merchant_id=m_id,
        target_segment=target_segment,
        target_days=target_days,
        target_hours=target_hours,
        recommendation_id=recommendation_id,
    )
    service = WhatIfSimulationService(db)
    return service.compare_scenarios(merchant_id=m_id, request=compare_req)
