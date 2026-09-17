"""
Growth Recommendation Service (Module 4).
Deterministically synthesizes Sales Intelligence (Module 2) and Customer Intelligence (Module 3)
into structured, evidence-backed business growth recommendations.
Zero LLM dependencies.
"""

from typing import Optional, List, Dict, Any, Set
import math
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.services.base import BaseService
from app.services.sales_service import SalesService
from app.services.customer_service import CustomerService
from app.schemas.growth import (
    RecommendationEvidence,
    RecommendationItem,
    GrowthRecommendationsResponse,
    GrowthOpportunitiesResponse,
    GrowthSummaryResponse,
)

VALID_GOALS = {
    "all": "All opportunities across all dimensions",
    "revenue": "Opportunities to increase top-line merchant sales",
    "increase_revenue": "Opportunities to increase top-line merchant sales",
    "retention": "Protect existing high-value customer relationships",
    "improve_retention": "Protect existing high-value customer relationships",
    "recovery": "Counter sales drops and re-engage slipping volume",
    "recover_sales": "Counter sales drops and re-engage slipping volume",
    "reactivation": "Win back at-risk and dormant customer cohorts",
    "reactivate_customers": "Win back at-risk and dormant customer cohorts",
    "weekend": "Stimulate weekend store footfall and ticket sizes",
    "weekend_growth": "Stimulate weekend store footfall and ticket sizes",
    "frequency": "Accelerate repeat visit cadence across regular shoppers",
    "increase_repeat_purchases": "Accelerate repeat visit cadence across regular shoppers",
}

GOAL_TYPE_MAPPING: Dict[str, Set[str]] = {
    "revenue": {"sales_decline_recovery", "weekend_growth", "time_of_day_opportunity", "vip_retention"},
    "increase_revenue": {"sales_decline_recovery", "weekend_growth", "time_of_day_opportunity", "vip_retention"},
    "retention": {"vip_retention", "revenue_concentration_risk", "at_risk_reengagement"},
    "improve_retention": {"vip_retention", "revenue_concentration_risk", "at_risk_reengagement"},
    "recovery": {"sales_decline_recovery", "at_risk_reengagement"},
    "recover_sales": {"sales_decline_recovery", "at_risk_reengagement"},
    "reactivation": {"at_risk_reengagement", "inactive_winback"},
    "reactivate_customers": {"at_risk_reengagement", "inactive_winback"},
    "weekend": {"weekend_growth"},
    "weekend_growth": {"weekend_growth"},
    "frequency": {"at_risk_reengagement", "revenue_concentration_risk", "vip_retention"},
    "increase_repeat_purchases": {"at_risk_reengagement", "revenue_concentration_risk", "vip_retention"},
}


class GrowthRecommendationService(BaseService):
    """
    Core business service synthesizing sales and customer intelligence
    into deterministic, ranked growth recommendations.
    """

    def __init__(self, db: Session):
        super().__init__(db)
        self.sales_service = SalesService(db)
        self.customer_service = CustomerService(db)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """Sanitize floats to avoid NaN or Infinity values."""
        if value is None:
            return default
        try:
            val = float(value)
            if math.isnan(val) or math.isinf(val):
                return default
            return round(val, 2)
        except (ValueError, TypeError):
            return default

    def generate_recommendations(
        self,
        merchant_id: str,
        goal: Optional[str] = None,
        limit: Optional[int] = None
    ) -> GrowthRecommendationsResponse:
        """
        Evaluate all deterministic growth opportunities and return ranked recommendations.
        Optionally filters by business goal and truncates to limit.
        """
        norm_goal = goal.strip().lower() if goal else "all"
        if norm_goal not in VALID_GOALS:
            allowed_list = ", ".join(sorted(VALID_GOALS.keys()))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid goal '{goal}'. Allowed goals: {allowed_list}."
            )

        if limit is not None and (limit < 1 or limit > 50):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid limit {limit}. Limit must be between 1 and 50."
            )

        # 1. Fetch baseline analytics from Module 2 (Sales) and Module 3 (Customers)
        sales_summary = self.sales_service.get_summary(merchant_id=merchant_id)
        period_comparison = self.sales_service.get_period_comparison(merchant_id=merchant_id, current_days=14)
        weekend_analysis = self.sales_service.get_weekend_analysis(merchant_id=merchant_id)
        hourly_analysis = self.sales_service.get_hourly_analysis(merchant_id=merchant_id)

        customer_summary = self.customer_service.get_summary(merchant_id=merchant_id)
        segments_res = self.customer_service.get_segments(merchant_id=merchant_id)
        at_risk_res = self.customer_service.get_at_risk_customers(merchant_id=merchant_id, limit=50)
        inactive_res = self.customer_service.get_inactive_customers(merchant_id=merchant_id, limit=50)

        # Handle empty/insufficient data cleanly
        if sales_summary.total_transactions == 0 and customer_summary.total_customers == 0:
            return GrowthRecommendationsResponse(
                merchant_id=merchant_id,
                goal_filter=norm_goal if norm_goal != "all" else None,
                total_recommendations=0,
                high_priority_count=0,
                medium_priority_count=0,
                low_priority_count=0,
                recommendations=[]
            )

        all_recommendations: List[RecommendationItem] = []

        # -------------------------------------------------------------
        # Rule 1: Sales Decline / Recovery
        # -------------------------------------------------------------
        if period_comparison.revenue_change_percentage < -5.0:
            rev_change = period_comparison.revenue_change_percentage
            is_steep = rev_change <= -15.0
            priority = "high" if is_steep else "medium"
            conf_score = 0.90 if is_steep else 0.80

            at_risk_count = at_risk_res.total_at_risk
            at_risk_rev = at_risk_res.total_at_risk_revenue

            all_recommendations.append(
                RecommendationItem(
                    recommendation_id=f"rec-{merchant_id[:8]}-decline-recovery",
                    type="sales_decline_recovery",
                    title="Recover Declining Revenue via Targeted Re-engagement",
                    description=(
                        f"Sales contracted by {abs(rev_change):.1f}% over the last 14 days compared to the prior period. "
                        f"Targeting active and at-risk regulars during peak operational hours can arrest this contraction."
                    ),
                    priority=priority,
                    confidence="strong",
                    confidence_score=conf_score,
                    target_segment="At-Risk",
                    objective="recover declining revenue",
                    suggested_action="Launch a targeted win-back re-engagement campaign for at-risk customers during peak traffic hours.",
                    rationale="Reactivating customers who already know your store provides the fastest, highest-ROI path to revenue stabilization.",
                    estimated_scope=f"{at_risk_count} at-risk customers representing ₹{at_risk_rev:,.2f} in historical revenue",
                    evidence=[
                        RecommendationEvidence(
                            metric_name="revenue_change_percentage",
                            metric_value=rev_change,
                            baseline_value=period_comparison.previous_period.revenue,
                            threshold_applied="< -5.0%",
                            context="14-day period-over-period sales drop"
                        ),
                        RecommendationEvidence(
                            metric_name="current_period_revenue",
                            metric_value=period_comparison.current_period.revenue,
                            baseline_value=period_comparison.previous_period.revenue,
                            threshold_applied="Period comparison",
                            context="Current 14-day cumulative sales"
                        )
                    ],
                    supporting_metrics={
                        "revenue_change_percentage": rev_change,
                        "current_revenue": period_comparison.current_period.revenue,
                        "previous_revenue": period_comparison.previous_period.revenue,
                        "at_risk_customers_count": float(at_risk_count),
                        "at_risk_revenue_exposed": at_risk_rev
                    }
                )
            )

        # -------------------------------------------------------------
        # Rule 2: At-Risk Customer Re-engagement
        # -------------------------------------------------------------
        if at_risk_res.total_at_risk > 0 and at_risk_res.total_at_risk_revenue > 0:
            at_risk_count = at_risk_res.total_at_risk
            at_risk_rev = at_risk_res.total_at_risk_revenue
            tot_rev = customer_summary.total_customer_revenue
            rev_share = self._safe_float((at_risk_rev / tot_rev) * 100.0) if tot_rev > 0 else 0.0

            priority = "high" if (at_risk_count >= 10 or rev_share >= 10.0) else "medium"

            all_recommendations.append(
                RecommendationItem(
                    recommendation_id=f"rec-{merchant_id[:8]}-at-risk-reengage",
                    type="at_risk_reengagement",
                    title="Re-engage At-Risk Customers Before Full Churn",
                    description=(
                        f"{at_risk_count} regular customers representing ₹{at_risk_rev:,.2f} ({rev_share:.1f}% of store revenue) "
                        f"have not transacted in 22 to 45 days."
                    ),
                    priority=priority,
                    confidence="strong",
                    confidence_score=0.90,
                    target_segment="At-Risk",
                    objective="reactivate at-risk customers",
                    suggested_action="Send personalized win-back reminders via WhatsApp or SMS to customers absent for 22–45 days.",
                    rationale="At-risk customers have demonstrated repeated brand affinity; timely re-engagement prevents permanent lapse into inactivity.",
                    estimated_scope=f"{at_risk_count} customers with cumulative past spend of ₹{at_risk_rev:,.2f}",
                    evidence=[
                        RecommendationEvidence(
                            metric_name="at_risk_customer_count",
                            metric_value=float(at_risk_count),
                            baseline_value=float(customer_summary.total_customers),
                            threshold_applied="Recency 22-45 days, >=3 visits",
                            context="Shoppers nearing dormant status"
                        ),
                        RecommendationEvidence(
                            metric_name="revenue_at_risk",
                            metric_value=at_risk_rev,
                            baseline_value=tot_rev,
                            threshold_applied="Lifetime spend of at-risk cohort",
                            context="Direct revenue exposure from slipping cohort"
                        )
                    ],
                    supporting_metrics={
                        "at_risk_customer_count": float(at_risk_count),
                        "total_at_risk_revenue": at_risk_rev,
                        "revenue_share_percentage": rev_share
                    }
                )
            )

        # -------------------------------------------------------------
        # Rule 3: Inactive Customer Win-Back
        # -------------------------------------------------------------
        if inactive_res.total_inactive >= 5:
            inact_count = inactive_res.total_inactive
            inact_rev = inactive_res.total_inactive_historical_revenue
            tot_cust = customer_summary.total_customers
            inact_pct = self._safe_float((inact_count / tot_cust) * 100.0) if tot_cust > 0 else 0.0

            all_recommendations.append(
                RecommendationItem(
                    recommendation_id=f"rec-{merchant_id[:8]}-inactive-winback",
                    type="inactive_winback",
                    title="Reactivate Dormant Customer Base",
                    description=(
                        f"{inact_count} shoppers ({inact_pct:.1f}% of total base) have been inactive for over 45 days. "
                        f"Their combined historical spend is ₹{inact_rev:,.2f}."
                    ),
                    priority="medium",
                    confidence="moderate",
                    confidence_score=0.75,
                    target_segment="Inactive",
                    objective="reactivate dormant customers",
                    suggested_action="Test a store reactivation incentive highlighting newly stocked items and seasonal discounts.",
                    rationale="Re-energizing even 10% of dormant accounts generates substantial top-line gains with zero customer acquisition expense.",
                    estimated_scope=f"{inact_count} dormant accounts with ₹{inact_rev:,.2f} prior spend",
                    evidence=[
                        RecommendationEvidence(
                            metric_name="inactive_customer_count",
                            metric_value=float(inact_count),
                            baseline_value=float(tot_cust),
                            threshold_applied="Recency > 45 days",
                            context="Lapsed customer accounts"
                        ),
                        RecommendationEvidence(
                            metric_name="inactive_historical_revenue",
                            metric_value=inact_rev,
                            baseline_value=customer_summary.total_customer_revenue,
                            threshold_applied="Cumulative historical spend",
                            context="Prior commercial contribution"
                        )
                    ],
                    supporting_metrics={
                        "inactive_customer_count": float(inact_count),
                        "inactive_percentage_of_base": inact_pct,
                        "inactive_historical_revenue": inact_rev
                    }
                )
            )

        # -------------------------------------------------------------
        # Rule 4: High-Value VIP Retention
        # -------------------------------------------------------------
        seg_dict = {s.segment: s for s in segments_res.segments}
        vip_stat = seg_dict.get("VIP")
        if vip_stat and vip_stat.customer_count > 0:
            if vip_stat.percentage_of_revenue >= 15.0 or vip_stat.customer_count >= 5:
                all_recommendations.append(
                    RecommendationItem(
                        recommendation_id=f"rec-{merchant_id[:8]}-vip-retention",
                        type="vip_retention",
                        title="Protect and Nurture VIP Customer Relationships",
                        description=(
                            f"{vip_stat.customer_count} VIP customers generate {vip_stat.percentage_of_revenue:.1f}% "
                            f"(₹{vip_stat.total_revenue:,.2f}) of store revenue with an average spend of ₹{vip_stat.average_revenue_per_customer:,.2f}."
                        ),
                        priority="high",
                        confidence="strong",
                        confidence_score=0.95,
                        target_segment="VIP",
                        objective="protect VIP revenue",
                        suggested_action="Establish dedicated VIP perks, express billing, and personal previews for incoming seasonal merchandise.",
                        rationale="VIP customers represent your core financial foundation. Losing even a single VIP materially impairs monthly profitability.",
                        estimated_scope=f"{vip_stat.customer_count} VIP shoppers contributing ₹{vip_stat.total_revenue:,.2f}",
                        evidence=[
                            RecommendationEvidence(
                                metric_name="vip_revenue_percentage",
                                metric_value=vip_stat.percentage_of_revenue,
                                baseline_value=15.0,
                                threshold_applied=">= 15.0% revenue share",
                                context="Disproportionate revenue contribution"
                            ),
                            RecommendationEvidence(
                                metric_name="vip_average_spend",
                                metric_value=vip_stat.average_revenue_per_customer,
                                baseline_value=customer_summary.average_customer_spend,
                                threshold_applied="VIP ticket magnitude",
                                context="Significantly higher order value"
                            )
                        ],
                        supporting_metrics={
                            "vip_customer_count": float(vip_stat.customer_count),
                            "vip_total_revenue": vip_stat.total_revenue,
                            "vip_revenue_share_percentage": vip_stat.percentage_of_revenue,
                            "vip_average_spend": vip_stat.average_revenue_per_customer
                        }
                    )
                )

        # -------------------------------------------------------------
        # Rule 5: Weekend Growth Opportunity
        # -------------------------------------------------------------
        if weekend_analysis.is_weekend_underperforming or (
            weekend_analysis.weekday_revenue > 0 and weekend_analysis.weekend_revenue_share_percentage < 25.0
        ):
            wday_avg = weekend_analysis.daily_avg_weekday_revenue
            wend_avg = weekend_analysis.daily_avg_weekend_revenue
            share_pct = weekend_analysis.weekend_revenue_share_percentage

            gap_pct = 0.0
            if wday_avg > 0:
                gap_pct = self._safe_float(((wday_avg - wend_avg) / wday_avg) * 100.0)

            priority = "high" if gap_pct >= 40.0 else "medium"

            all_recommendations.append(
                RecommendationItem(
                    recommendation_id=f"rec-{merchant_id[:8]}-weekend-growth",
                    type="weekend_growth",
                    title="Boost Weekend Sales Performance",
                    description=(
                        f"Weekend daily revenue averages ₹{wend_avg:,.2f} versus ₹{wday_avg:,.2f} on weekdays, "
                        f"representing an underperformance gap of {gap_pct:.1f}%."
                    ),
                    priority=priority,
                    confidence="strong",
                    confidence_score=0.85,
                    target_segment="All Customers",
                    objective="increase weekend sales",
                    suggested_action="Run a dedicated weekend special promotion to attract footfall during Saturday and Sunday midday hours.",
                    rationale="Closing the weekend gap offers straightforward revenue expansion without altering regular weekday operations.",
                    estimated_scope=f"₹{wday_avg - wend_avg:,.2f} daily revenue gap between weekdays and weekends",
                    evidence=[
                        RecommendationEvidence(
                            metric_name="weekend_revenue_share_percentage",
                            metric_value=share_pct,
                            baseline_value=28.57,  # 2/7 days = ~28.6%
                            threshold_applied="< 25.0% or flagged underperforming",
                            context="Weekend contribution lagging expectations"
                        ),
                        RecommendationEvidence(
                            metric_name="daily_avg_weekend_revenue",
                            metric_value=wend_avg,
                            baseline_value=wday_avg,
                            threshold_applied="Daily average comparison",
                            context="Lower daily run-rate on weekends"
                        )
                    ],
                    supporting_metrics={
                        "daily_avg_weekday_revenue": wday_avg,
                        "daily_avg_weekend_revenue": wend_avg,
                        "weekend_revenue_share_percentage": share_pct,
                        "underperformance_gap_percentage": gap_pct
                    }
                )
            )

        # -------------------------------------------------------------
        # Rule 6: Time-of-Day Opportunity
        # -------------------------------------------------------------
        if hourly_analysis.time_windows and len(hourly_analysis.time_windows) >= 2:
            windows_by_rev = sorted(hourly_analysis.time_windows, key=lambda w: w.revenue, reverse=True)
            peak_w = windows_by_rev[0]
            slow_w = windows_by_rev[-1]

            if peak_w.revenue > 0 and slow_w.revenue < (peak_w.revenue * 0.60):
                ratio = self._safe_float((slow_w.revenue / peak_w.revenue) * 100.0)
                all_recommendations.append(
                    RecommendationItem(
                        recommendation_id=f"rec-{merchant_id[:8]}-time-window",
                        type="time_of_day_opportunity",
                        title=f"Stimulate Footfall During Slow {slow_w.window_name} Hours",
                        description=(
                            f"The {slow_w.window_name} window generates ₹{slow_w.revenue:,.2f}, which is only "
                            f"{ratio:.1f}% of the peak {peak_w.window_name} volume (₹{peak_w.revenue:,.2f})."
                        ),
                        priority="medium",
                        confidence="moderate",
                        confidence_score=0.70,
                        target_segment="All Customers",
                        objective="increase off-peak transaction volume",
                        suggested_action=f"Introduce limited-time happy hour discounts or combo specials during the {slow_w.window_name} ({slow_w.hours_range}) window.",
                        rationale="Smoothing operational demand into slower windows monetizes store capacity during idle staff hours.",
                        estimated_scope=f"₹{peak_w.revenue - slow_w.revenue:,.2f} revenue spread between peak and off-peak windows",
                        evidence=[
                            RecommendationEvidence(
                                metric_name="slowest_window_revenue",
                                metric_value=slow_w.revenue,
                                baseline_value=peak_w.revenue,
                                threshold_applied="< 60% of peak window volume",
                                context=f"Off-peak {slow_w.window_name} lag"
                            )
                        ],
                        supporting_metrics={
                            "slow_window_revenue": slow_w.revenue,
                            "peak_window_revenue": peak_w.revenue,
                            "slow_to_peak_ratio_percentage": ratio
                        }
                    )
                )

        # -------------------------------------------------------------
        # Rule 7: Revenue Concentration / Diversification
        # -------------------------------------------------------------
        tot_cust = customer_summary.total_customers
        tot_rev = customer_summary.total_customer_revenue
        if tot_cust >= 10 and tot_rev > 0:
            top_customers = self.customer_service.get_top_customers(merchant_id=merchant_id, by="revenue", limit=max(1, int(tot_cust * 0.10)))
            top_10_spend = sum(c.total_spend for c in top_customers.customers)
            top_10_pct = self._safe_float((top_10_spend / tot_rev) * 100.0)

            if top_10_pct >= 40.0:
                all_recommendations.append(
                    RecommendationItem(
                        recommendation_id=f"rec-{merchant_id[:8]}-concentration-risk",
                        type="revenue_concentration_risk",
                        title="Mitigate Customer Revenue Concentration Risk",
                        description=(
                            f"Top 10% of shoppers ({len(top_customers.customers)} customers) account for {top_10_pct:.1f}% "
                            f"(₹{top_10_spend:,.2f}) of store revenue. Diversifying this reliance is essential for resilient growth."
                        ),
                        priority="medium",
                        confidence="moderate",
                        confidence_score=0.75,
                        target_segment="Loyal",
                        objective="broaden high-value customer base",
                        suggested_action="Nurture Loyal shoppers with tier progression perks to expand your VIP customer cohort.",
                        rationale="Broadening your top-spending base protects cash flow against the departure of any single shopper.",
                        estimated_scope=f"{len(top_customers.customers)} shoppers generating {top_10_pct:.1f}% of total revenue",
                        evidence=[
                            RecommendationEvidence(
                                metric_name="top_10_percent_revenue_share",
                                metric_value=top_10_pct,
                                baseline_value=40.0,
                                threshold_applied=">= 40.0% revenue concentration",
                                context="High reliance on top 10% customer group"
                            )
                        ],
                        supporting_metrics={
                            "top_10_percent_revenue_share": top_10_pct,
                            "top_10_percent_customer_count": float(len(top_customers.customers)),
                            "top_10_percent_spend": top_10_spend
                        }
                    )
                )

        # -------------------------------------------------------------
        # Filter by Goal (if specified)
        # -------------------------------------------------------------
        filtered_recommendations = all_recommendations
        if norm_goal != "all":
            allowed_types = GOAL_TYPE_MAPPING.get(norm_goal, set())
            filtered_recommendations = [r for r in all_recommendations if r.type in allowed_types]

        # -------------------------------------------------------------
        # Deterministic Ranking
        # Priority: high (1) -> medium (2) -> low (3), then confidence_score descending
        # -------------------------------------------------------------
        priority_rank = {"high": 1, "medium": 2, "low": 3}
        filtered_recommendations.sort(
            key=lambda r: (priority_rank.get(r.priority, 10), -r.confidence_score, r.recommendation_id)
        )

        if limit is not None and limit > 0:
            filtered_recommendations = filtered_recommendations[:limit]

        high_count = sum(1 for r in filtered_recommendations if r.priority == "high")
        med_count = sum(1 for r in filtered_recommendations if r.priority == "medium")
        low_count = sum(1 for r in filtered_recommendations if r.priority == "low")

        return GrowthRecommendationsResponse(
            merchant_id=merchant_id,
            goal_filter=norm_goal if norm_goal != "all" else None,
            total_recommendations=len(filtered_recommendations),
            high_priority_count=high_count,
            medium_priority_count=med_count,
            low_priority_count=low_count,
            recommendations=filtered_recommendations,
        )

    def get_opportunities(
        self,
        merchant_id: str,
        limit: Optional[int] = 10
    ) -> GrowthOpportunitiesResponse:
        """
        List all detected growth opportunities for the merchant.
        """
        recs = self.generate_recommendations(merchant_id=merchant_id, goal=None, limit=limit)
        return GrowthOpportunitiesResponse(
            merchant_id=merchant_id,
            total_opportunities=recs.total_recommendations,
            opportunities=recs.recommendations,
        )

    def get_summary(self, merchant_id: str) -> GrowthSummaryResponse:
        """
        Produce high-level growth diagnostics, risk exposures, and primary recommendation.
        """
        recs_response = self.generate_recommendations(merchant_id=merchant_id, goal=None, limit=None)
        sales_summary = self.sales_service.get_summary(merchant_id=merchant_id)
        customer_summary = self.customer_service.get_summary(merchant_id=merchant_id)
        comparison = self.sales_service.get_period_comparison(merchant_id=merchant_id, current_days=14)
        at_risk = self.customer_service.get_at_risk_customers(merchant_id=merchant_id, limit=1)

        # Sales trend classification
        if sales_summary.total_transactions == 0:
            sales_trend = "insufficient_data"
        elif comparison.revenue_change_percentage < -5.0:
            sales_trend = "declining"
        elif comparison.revenue_change_percentage > 5.0:
            sales_trend = "growing"
        else:
            sales_trend = "stable"

        # Customer retention signal
        if customer_summary.total_customers == 0:
            retention_signal = "no_data"
        elif at_risk.total_at_risk > 15:
            retention_signal = "at_risk"
        elif customer_summary.repeat_customer_rate >= 50.0:
            retention_signal = "strong"
        else:
            retention_signal = "moderate"

        key_rec = recs_response.recommendations[0] if recs_response.recommendations else None
        strongest_type = key_rec.type if key_rec else None

        return GrowthSummaryResponse(
            merchant_id=merchant_id,
            total_opportunities=recs_response.total_recommendations,
            high_priority_opportunities=recs_response.high_priority_count,
            revenue_at_risk=self._safe_float(at_risk.total_at_risk_revenue),
            customers_at_risk=at_risk.total_at_risk,
            strongest_opportunity_type=strongest_type,
            current_sales_trend=sales_trend,
            current_retention_signal=retention_signal,
            key_recommendation=key_rec,
        )
