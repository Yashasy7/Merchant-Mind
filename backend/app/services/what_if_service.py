"""
What-if Simulation Engine (Module 5).
Computes deterministic promotional simulation scenarios, comparing No Offer, Percentage Discounts,
and Fixed Cashback incentives against historical merchant baselines.
All outputs are strictly labeled as synthetic demo projections.
Guarantees merchant isolation and zero LLM dependencies.
"""

from typing import Optional, List, Dict, Any, Tuple
import math
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.services.base import BaseService
from app.services.sales_service import SalesService
from app.services.customer_service import CustomerService
from app.services.growth_service import GrowthRecommendationService
from app.schemas.what_if import (
    ScenarioAssumptions,
    SimulationScenario,
    SimulationBaselineResponse,
    SimulationRequest,
    WhatIfCompareRequest,
    WhatIfComparisonResponse,
)

VALID_SEGMENTS = {
    "all": "All Customers",
    "all customers": "All Customers",
    "vip": "VIP",
    "loyal": "Loyal",
    "new": "New",
    "at-risk": "At-Risk",
    "at_risk": "At-Risk",
    "inactive": "Inactive",
    "regular": "Regular",
}


class WhatIfSimulationService(BaseService):
    """
    Core business service providing deterministic scenario simulations,
    incentive costing, net incremental impact analysis, and multi-scenario comparison.
    """

    def __init__(self, db: Session):
        super().__init__(db)
        self.sales_service = SalesService(db)
        self.customer_service = CustomerService(db)
        self.growth_service = GrowthRecommendationService(db)

    def _canonicalize_segment(self, segment: Optional[str]) -> str:
        """Normalize customer segment string or raise HTTP 400."""
        if not segment or not segment.strip():
            return "All Customers"
        cleaned = segment.strip().lower()
        if cleaned not in VALID_SEGMENTS:
            valid_list = ", ".join(["All Customers", "VIP", "Loyal", "New", "At-Risk", "Inactive", "Regular"])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target segment '{segment}'. Valid options: {valid_list}."
            )
        return VALID_SEGMENTS[cleaned]

    def get_baseline(
        self,
        merchant_id: str,
        target_segment: Optional[str] = "All Customers",
        target_days: Optional[str] = None,
        target_hours: Optional[str] = None,
    ) -> SimulationBaselineResponse:
        """
        Compute historical merchant baseline metrics using existing Sales and Customer Intelligence.
        Scoped strictly by merchant_id.
        """
        canonical_segment = self._canonicalize_segment(target_segment)
        days_filter = target_days.strip().lower() if target_days and target_days.strip() else None
        hours_filter = target_hours.strip().lower() if target_hours and target_hours.strip() else None

        # 1. Base transaction analytics from SalesService
        baseline_revenue = 0.0
        baseline_txns = 0
        baseline_atv = 0.0
        window_desc = "Last 30 days transactions"
        notes = "Standard 30-day historical window"

        if days_filter == "weekend":
            weekend_res = self.sales_service.get_weekend_analysis(merchant_id=merchant_id)
            baseline_revenue = round(float(weekend_res.weekend_revenue), 2)
            baseline_txns = int(weekend_res.weekend_transactions)
            baseline_atv = round(float(weekend_res.weekend_average_transaction_value), 2)
            window_desc = "Historical weekend transactions"
            notes = "Filtered strictly for Saturday and Sunday transactions"
        elif hours_filter in {"morning", "afternoon", "evening", "night"}:
            hourly_res = self.sales_service.get_hourly_analysis(merchant_id=merchant_id)
            matched_window = next((w for w in hourly_res.time_windows if w.window_name.lower() == hours_filter), None)
            if matched_window:
                baseline_revenue = round(float(matched_window.revenue), 2)
                baseline_txns = int(matched_window.transaction_count)
                baseline_atv = round(float(matched_window.average_transaction_value), 2)
                window_desc = f"Historical {hours_filter.title()} window ({matched_window.hours_range})"
                notes = f"Filtered for hours {matched_window.hours_range}"

        else:
            sales_summary = self.sales_service.get_summary(merchant_id=merchant_id)
            baseline_revenue = round(float(sales_summary.total_revenue), 2)
            baseline_txns = int(sales_summary.successful_transactions)
            baseline_atv = round(float(sales_summary.average_transaction_value), 2)

        # 2. Segment customer count and volume calibration
        target_size: Optional[int] = None
        try:
            segments_res = self.customer_service.get_segments(merchant_id=merchant_id)
            if canonical_segment != "All Customers":
                target_stat = next((s for s in segments_res.segments if s.segment == canonical_segment), None)
                if target_stat:
                    target_size = int(target_stat.customer_count)
                    # If simulating a niche segment, calibrate baseline to segment's historical footprint if non-zero
                    if target_stat.total_revenue > 0 and target_stat.customer_count > 0:
                        seg_txns = max(1, round(target_stat.customer_count * max(1.0, target_stat.average_transaction_count)))
                        # Only scale down if segment volume is less than full store volume
                        if seg_txns < baseline_txns:
                            baseline_txns = seg_txns
                            baseline_revenue = round(float(target_stat.total_revenue), 2)
                            baseline_atv = round(baseline_revenue / baseline_txns, 2)
                            notes += f" | Segment '{canonical_segment}' historical spend calibrated"
                else:
                    target_size = 0
            else:
                target_size = sum(s.customer_count for s in segments_res.segments)

        except Exception:
            # Fallback if customer records are sparse
            target_size = None

        has_data = baseline_txns > 0 and baseline_revenue > 0.0
        if not has_data:
            notes = "Insufficient historical transaction data for merchant in this window."

        return SimulationBaselineResponse(
            merchant_id=merchant_id,
            has_sufficient_data=has_data,
            baseline_window=window_desc,
            target_segment=canonical_segment,
            target_segment_size=target_size,
            baseline_revenue=baseline_revenue,
            baseline_transactions=baseline_txns,
            baseline_average_order_value=baseline_atv,
            data_notes=notes,
            is_demo_projection=True,
        )

    def simulate_scenario(self, merchant_id: str, request: SimulationRequest) -> SimulationScenario:
        """
        Deterministically simulate a single promotional strategy against the merchant's baseline.
        """
        # Resolve recommendation context if provided
        rec_context_id = request.recommendation_id
        target_seg = request.target_segment
        if rec_context_id:
            try:
                recs = self.growth_service.generate_recommendations(merchant_id=merchant_id)
                matched_rec = next((r for r in recs.recommendations if r.recommendation_id == rec_context_id), None)
                if matched_rec and (not target_seg or target_seg == "All Customers"):
                    target_seg = matched_rec.target_segment
            except Exception:
                pass

        baseline = self.get_baseline(
            merchant_id=merchant_id,
            target_segment=target_seg,
            target_days=request.target_days,
            target_hours=request.target_hours,
        )

        stype = request.scenario_type.lower()
        sname = request.scenario_name or (
            "No Offer (Baseline)" if stype == "no_offer" else
            f"{request.discount_percent:.0f}% Discount" if stype == "percentage_discount" and request.discount_percent else
            f"₹{request.cashback_amount:.0f} Cashback" if stype == "fixed_cashback" and request.cashback_amount else
            "Custom Strategy"
        )

        # Handle empty/insufficient data safely
        if not baseline.has_sufficient_data:
            assumptions = ScenarioAssumptions(
                transaction_uplift_percent=0.0,
                discount_percent=request.discount_percent or 0.0,
                cashback_amount=request.cashback_amount or 0.0,
                eligibility_rate_percent=0.0,
                minimum_transaction_amount=request.minimum_transaction_amount or 0.0,
                explanation="Simulation unavailable due to insufficient historical transaction data.",
            )
            return SimulationScenario(
                scenario_id=f"scenario-{stype}-empty",
                scenario_name=sname,
                scenario_type=stype,
                description="Insufficient historical data to compute projection.",
                target_segment=baseline.target_segment,
                target_segment_size=baseline.target_segment_size,
                target_days=request.target_days,
                target_hours=request.target_hours,
                baseline_revenue=0.0,
                baseline_transactions=0,
                baseline_average_order_value=0.0,
                projected_revenue=0.0,
                gross_projected_revenue=0.0,
                projected_transactions=0,
                incremental_transactions=0,
                projected_average_order_value=0.0,
                estimated_incentive_cost=0.0,
                gross_incremental_revenue=0.0,
                net_incremental_impact=0.0,
                estimated_roi=None,
                roi_multiplier_label="N/A",
                confidence_score=0.0,
                assumptions=assumptions,
                is_demo_projection=True,
            )

        b_txns = baseline.baseline_transactions
        b_rev = baseline.baseline_revenue
        b_atv = baseline.baseline_average_order_value

        # --- Deterministic Mathematical Simulation ---
        if stype == "no_offer":
            uplift_pct = 0.0
            discount_pct = 0.0
            cashback_amt = 0.0
            eligibility_pct = 100.0
            min_order = 0.0
            p_txns = b_txns
            inc_txns = 0
            gross_p_rev = b_rev
            incentive_cost = 0.0
            p_rev = b_rev
            gross_inc_rev = 0.0
            net_impact = 0.0
            roi = None
            roi_label = "N/A"
            confidence = 0.95
            desc = "Maintain status quo business operations without promotional marketing or incentive spending."
            explanation = "Assumes 0% promotional cost and standard baseline trajectory."

        elif stype == "percentage_discount":
            discount_pct = float(request.discount_percent if request.discount_percent is not None else 5.0)
            cashback_amt = 0.0
            min_order = float(request.minimum_transaction_amount or 0.0)
            eligibility_pct = float(request.participation_rate if request.participation_rate is not None else 85.0)

            # Uplift model: default price elasticity curve (capped at 50%) or user assumption
            if request.uplift_assumption is not None:
                uplift_pct = float(request.uplift_assumption)
            else:
                # Deterministic elasticity: 5% discount -> 15% uplift; 10% discount -> 25% uplift
                uplift_pct = round(min(50.0, max(5.0, discount_pct * 2.5)), 1)

            inc_txns = int(round(b_txns * (uplift_pct / 100.0)))
            p_txns = b_txns + inc_txns

            gross_p_rev = round(p_txns * b_atv, 2)
            eligible_gross_rev = gross_p_rev * (eligibility_pct / 100.0)
            incentive_cost = round(eligible_gross_rev * (discount_pct / 100.0), 2)
            p_rev = round(gross_p_rev - incentive_cost, 2)

            gross_inc_rev = round(gross_p_rev - b_rev, 2)
            net_impact = round(gross_inc_rev - incentive_cost, 2)

            roi = round(net_impact / incentive_cost, 2) if incentive_cost > 0 else None
            roi_label = f"{round(net_impact / incentive_cost, 1)}x" if incentive_cost > 0 else "N/A"
            confidence = 0.88
            desc = f"Provide a {discount_pct:.1f}% discount to eligible transactions to accelerate order volume."
            explanation = (
                f"Assumes a {uplift_pct:.1f}% transaction volume uplift and {eligibility_pct:.1f}% "
                f"customer participation taking advantage of a {discount_pct:.1f}% discount."
            )

        elif stype == "fixed_cashback":
            discount_pct = 0.0
            cashback_amt = float(request.cashback_amount if request.cashback_amount is not None else 50.0)
            min_order = float(request.minimum_transaction_amount or max(200.0, round(b_atv * 0.5, 0)))
            eligibility_pct = float(request.participation_rate if request.participation_rate is not None else 80.0)

            if request.uplift_assumption is not None:
                uplift_pct = float(request.uplift_assumption)
            else:
                # Deterministic cashback elasticity based on ATV ratio
                ratio = cashback_amt / max(50.0, b_atv)
                uplift_pct = round(min(50.0, max(8.0, ratio * 120.0)), 1)

            inc_txns = int(round(b_txns * (uplift_pct / 100.0)))
            p_txns = b_txns + inc_txns

            gross_p_rev = round(p_txns * b_atv, 2)
            eligible_txns = p_txns * (eligibility_pct / 100.0)
            incentive_cost = round(eligible_txns * cashback_amt, 2)
            # For cashback, merchant collects full GMV at billing, and cashback is paid from promotional budget
            p_rev = round(gross_p_rev, 2)

            gross_inc_rev = round(gross_p_rev - b_rev, 2)
            net_impact = round(gross_inc_rev - incentive_cost, 2)

            roi = round(net_impact / incentive_cost, 2) if incentive_cost > 0 else None
            roi_label = f"{round(net_impact / incentive_cost, 1)}x" if incentive_cost > 0 else "N/A"
            confidence = 0.86
            desc = f"Offer ₹{cashback_amt:.0f} Paytm cashback on qualifying transactions above ₹{min_order:.0f}."
            explanation = (
                f"Assumes a {uplift_pct:.1f}% transaction uplift with {eligibility_pct:.1f}% of orders "
                f"qualifying for ₹{cashback_amt:.0f} cashback above ₹{min_order:.0f} basket size."
            )

        else:  # custom
            discount_pct = float(request.discount_percent or 0.0)
            cashback_amt = float(request.cashback_amount or 0.0)
            min_order = float(request.minimum_transaction_amount or 0.0)
            eligibility_pct = float(request.participation_rate or 80.0)
            uplift_pct = float(request.uplift_assumption or 10.0)

            inc_txns = int(round(b_txns * (uplift_pct / 100.0)))
            p_txns = b_txns + inc_txns
            gross_p_rev = round(p_txns * b_atv, 2)

            disc_cost = (gross_p_rev * (eligibility_pct / 100.0)) * (discount_pct / 100.0)
            cb_cost = (p_txns * (eligibility_pct / 100.0)) * cashback_amt
            incentive_cost = round(disc_cost + cb_cost, 2)
            p_rev = round(gross_p_rev - disc_cost, 2)

            gross_inc_rev = round(gross_p_rev - b_rev, 2)
            net_impact = round(gross_inc_rev - incentive_cost, 2)
            roi = round(net_impact / incentive_cost, 2) if incentive_cost > 0 else None
            roi_label = f"{round(net_impact / incentive_cost, 1)}x" if incentive_cost > 0 else "N/A"
            confidence = 0.80
            desc = "Custom tailored promotional scenario."
            explanation = f"Custom scenario with {uplift_pct:.1f}% volume uplift and ₹{incentive_cost:.2f} incentive budget."

        p_atv = round(p_rev / p_txns, 2) if p_txns > 0 else 0.0

        scenario_id = (
            "scenario-no-offer" if stype == "no_offer" else
            f"scenario-{int(discount_pct)}pct-discount" if stype == "percentage_discount" else
            f"scenario-{int(cashback_amt)}-cashback" if stype == "fixed_cashback" else
            "scenario-custom"
        )

        assumptions_obj = ScenarioAssumptions(
            transaction_uplift_percent=uplift_pct,
            discount_percent=discount_pct,
            cashback_amount=cashback_amt,
            eligibility_rate_percent=eligibility_pct,
            minimum_transaction_amount=min_order,
            assumption_type="illustrative_demo_assumption",
            explanation=explanation,
        )

        return SimulationScenario(
            scenario_id=scenario_id,
            scenario_name=sname,
            scenario_type=stype,
            description=desc,
            target_segment=baseline.target_segment,
            target_segment_size=baseline.target_segment_size,
            target_days=request.target_days,
            target_hours=request.target_hours,
            baseline_revenue=b_rev,
            baseline_transactions=b_txns,
            baseline_average_order_value=b_atv,
            projected_revenue=p_rev,
            gross_projected_revenue=gross_p_rev,
            projected_transactions=p_txns,
            incremental_transactions=inc_txns,
            projected_average_order_value=p_atv,
            estimated_incentive_cost=incentive_cost,
            gross_incremental_revenue=gross_inc_rev,
            net_incremental_impact=net_impact,
            estimated_roi=roi,
            roi_multiplier_label=roi_label,
            confidence_score=confidence,
            assumptions=assumptions_obj,
            is_demo_projection=True,
        )

    def compare_scenarios(self, merchant_id: str, request: WhatIfCompareRequest) -> WhatIfComparisonResponse:
        """
        Compare standard promotional strategies (No Offer, 5% Discount, 10% Discount, ₹50 Cashback)
        and deterministically identify the highest net-yield outcome.
        """
        # Resolve baseline
        baseline = self.get_baseline(
            merchant_id=merchant_id,
            target_segment=request.target_segment,
            target_days=request.target_days,
            target_hours=request.target_hours,
        )

        if not baseline.has_sufficient_data:
            return WhatIfComparisonResponse(
                merchant_id=merchant_id,
                status="insufficient_data",
                target_segment=baseline.target_segment,
                target_segment_size=baseline.target_segment_size,
                target_days=request.target_days,
                target_hours=request.target_hours,
                recommendation_context_id=request.recommendation_id,
                baseline=baseline,
                scenarios=[],
                recommended_scenario_id=None,
                recommended_scenario_name=None,
                recommendation_reason=None,
                comparison_summary="Insufficient historical transaction data to simulate promotional strategies.",
                assumptions_notice="Simulation requires at least one successful historical transaction.",
                disclaimer="Synthetic / Illustrative Demo Projection — Not a guaranteed forecast or real Paytm campaign prediction.",
                is_demo_projection=True,
                data_type="SYNTHETIC_DEMO",
            )

        # Standard blueprint scenario suite:
        # 1. No Offer
        # 2. 5% Discount
        # 3. 10% Discount
        # 4. ₹50 Cashback
        standard_specs = [
            SimulationRequest(
                merchant_id=merchant_id,
                scenario_name="No Offer (Baseline)",
                scenario_type="no_offer",
                target_segment=baseline.target_segment,
                target_days=request.target_days,
                target_hours=request.target_hours,
                recommendation_id=request.recommendation_id,
            ),
            SimulationRequest(
                merchant_id=merchant_id,
                scenario_name="5% Discount",
                scenario_type="percentage_discount",
                discount_percent=5.0,
                uplift_assumption=15.0,
                participation_rate=85.0,
                target_segment=baseline.target_segment,
                target_days=request.target_days,
                target_hours=request.target_hours,
                recommendation_id=request.recommendation_id,
            ),
            SimulationRequest(
                merchant_id=merchant_id,
                scenario_name="10% Discount",
                scenario_type="percentage_discount",
                discount_percent=10.0,
                uplift_assumption=25.0,
                participation_rate=85.0,
                target_segment=baseline.target_segment,
                target_days=request.target_days,
                target_hours=request.target_hours,
                recommendation_id=request.recommendation_id,
            ),
            SimulationRequest(
                merchant_id=merchant_id,
                scenario_name="₹50 Cashback",
                scenario_type="fixed_cashback",
                cashback_amount=50.0,
                minimum_transaction_amount=max(200.0, round(baseline.baseline_average_order_value * 0.5, 0)),
                uplift_assumption=30.0,
                participation_rate=80.0,
                target_segment=baseline.target_segment,
                target_days=request.target_days,
                target_hours=request.target_hours,
                recommendation_id=request.recommendation_id,
            ),
        ]

        # Optional custom strategy if requested
        if request.custom_discount_percent is not None:
            standard_specs.append(
                SimulationRequest(
                    merchant_id=merchant_id,
                    scenario_name=f"Custom {request.custom_discount_percent:.0f}% Discount",
                    scenario_type="percentage_discount",
                    discount_percent=request.custom_discount_percent,
                    target_segment=baseline.target_segment,
                    target_days=request.target_days,
                    target_hours=request.target_hours,
                    recommendation_id=request.recommendation_id,
                )
            )
        if request.custom_cashback_amount is not None:
            standard_specs.append(
                SimulationRequest(
                    merchant_id=merchant_id,
                    scenario_name=f"Custom ₹{request.custom_cashback_amount:.0f} Cashback",
                    scenario_type="fixed_cashback",
                    cashback_amount=request.custom_cashback_amount,
                    target_segment=baseline.target_segment,
                    target_days=request.target_days,
                    target_hours=request.target_hours,
                    recommendation_id=request.recommendation_id,
                )
            )

        simulated_scenarios: List[SimulationScenario] = []
        for spec in standard_specs:
            simulated_scenarios.append(self.simulate_scenario(merchant_id=merchant_id, request=spec))

        # Deterministic identification of the recommended scenario:
        # Candidate pool: exclude "no_offer" if any positive incentive scenario has positive net incremental impact
        promo_candidates = [s for s in simulated_scenarios if s.scenario_type != "no_offer" and s.net_incremental_impact > 0]
        if not promo_candidates:
            # If no promo produces positive net gain, status quo is safest
            best_scenario = simulated_scenarios[0]
            reason = "Status quo baseline recommended as promotional incentives do not cover estimated marketing costs."
        else:
            # Primary sort: highest net_incremental_impact
            # Tie-break 1: highest estimated_roi
            # Tie-break 2: lowest incentive_cost
            # Tie-break 3: scenario_id alphabetical
            best_scenario = sorted(
                promo_candidates,
                key=lambda s: (
                    -s.net_incremental_impact,
                    -(s.estimated_roi if s.estimated_roi is not None else -999.0),
                    s.estimated_incentive_cost,
                    s.scenario_id,
                )
            )[0]
            roi_text = f"{best_scenario.roi_multiplier_label} ROI" if best_scenario.roi_multiplier_label else "positive yield"
            reason = (
                f"Highest estimated net incremental impact among simulated strategies: generates ₹{best_scenario.net_incremental_impact:,.2f} "
                f"in net economic gain over baseline at an estimated {roi_text}."
            )

        summary = (
            f"Evaluated {len(simulated_scenarios)} strategies against historical baseline of ₹{baseline.baseline_revenue:,.2f} "
            f"({baseline.baseline_transactions} txns). '{best_scenario.scenario_name}' is projected as the strongest outcome "
            f"with ₹{best_scenario.projected_revenue:,.2f} revenue and ₹{best_scenario.estimated_incentive_cost:,.2f} estimated incentive cost."
        )

        return WhatIfComparisonResponse(
            merchant_id=merchant_id,
            status="success",
            target_segment=baseline.target_segment,
            target_segment_size=baseline.target_segment_size,
            target_days=request.target_days,
            target_hours=request.target_hours,
            recommendation_context_id=request.recommendation_id,
            baseline=baseline,
            scenarios=simulated_scenarios,
            recommended_scenario_id=best_scenario.scenario_id,
            recommended_scenario_name=best_scenario.scenario_name,
            recommendation_reason=reason,
            comparison_summary=summary,
            assumptions_notice=(
                "All simulated projections are based on synthetic demo elasticity assumptions and historical trends."
            ),
            disclaimer=(
                "Synthetic / Illustrative Demo Projection — Not a guaranteed forecast or real Paytm campaign prediction."
            ),
            is_demo_projection=True,
            data_type="SYNTHETIC_DEMO",
        )
