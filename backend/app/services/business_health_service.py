"""
Business Health & Risk Assessment Service for Module 9.
Orchestrates deterministic intelligence from:
- Module 2: SalesService (revenue growth, volume, weekend performance)
- Module 3: CustomerService (customer segments, retention, at-risk/inactive exposure)
- Module 4: GrowthRecommendationService (growth opportunities, promotional levers)
- Module 8: AccountantService (P&L, operating margin, expense pressure, anomalies)

Computes composite health score (0-100) and extracts evidence-backed risks and opportunities.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.services.base import BaseService
from app.services.sales_service import SalesService
from app.services.customer_service import CustomerService
from app.services.accountant_service import AccountantService
from app.services.growth_service import GrowthRecommendationService
from app.schemas.business_health import (
    HEALTH_DISCLAIMER,
    HealthDimension,
    RiskInsight,
    OpportunityInsight,
    BusinessHealthResponse,
    RiskListResponse,
    OpportunityListResponse,
)


class BusinessHealthService(BaseService):
    """Business service orchestrating cross-module data to evaluate overall merchant health."""

    def __init__(self, db: Session):
        super().__init__(db)
        self.sales_service = SalesService(db)
        self.customer_service = CustomerService(db)
        self.accountant_service = AccountantService(db)
        self.growth_service = GrowthRecommendationService(db)

    def get_business_health(self, merchant_id: str) -> BusinessHealthResponse:
        """
        Evaluate composite merchant health across 5 core dimensions:
        Revenue Trend, Customer Retention, Profitability, Operational Risk, and Growth Readiness.
        """
        # 1. Fetch cross-module validated metrics
        sales_summary = self.sales_service.get_summary(merchant_id=merchant_id)
        sales_comp = self.sales_service.get_period_comparison(merchant_id=merchant_id, current_days=14)
        weekend_analysis = self.sales_service.get_weekend_analysis(merchant_id=merchant_id)
        cust_summary = self.customer_service.get_summary(merchant_id=merchant_id)
        cust_segments = self.customer_service.get_segments(merchant_id=merchant_id)
        pl = self.accountant_service.get_profit_loss(merchant_id=merchant_id)
        exp_breakdown = self.accountant_service.get_expenses_breakdown(merchant_id=merchant_id)
        growth_recs = self.growth_service.generate_recommendations(merchant_id=merchant_id)

        # ---------------------------------------------------------------------
        # Dimension 1: Revenue Trend (Weight: 25%)
        # ---------------------------------------------------------------------
        rev_change = sales_comp.revenue_change_percentage
        if rev_change >= 10.0:
            rev_score = 95.0
            rev_status = "excellent"
            rev_summary = f"Strong revenue acceleration (+{rev_change}% vs previous 14 days)."
        elif rev_change >= 2.0:
            rev_score = 85.0
            rev_status = "good"
            rev_summary = f"Steady positive revenue growth (+{rev_change}%)."
        elif rev_change >= -3.0:
            rev_score = 75.0
            rev_status = "good"
            rev_summary = f"Stable revenue velocity ({rev_change}% variance)."
        elif rev_change >= -10.0:
            rev_score = 55.0
            rev_status = "warning"
            rev_summary = f"Mild revenue contraction ({rev_change}% vs previous 14 days)."
        else:
            rev_score = 35.0
            rev_status = "critical"
            rev_summary = f"Sharp revenue drop ({rev_change}% contraction)."

        dim_revenue = HealthDimension(
            dimension_name="revenue_trend",
            score=round(rev_score, 1),
            status=rev_status,
            metric_summary=rev_summary,
            details={
                "current_revenue": sales_comp.current_period.revenue,
                "previous_revenue": sales_comp.previous_period.revenue,
                "revenue_change_percentage": rev_change,
                "total_transactions": sales_summary.total_transactions,
            },
        )


        # ---------------------------------------------------------------------
        # Dimension 2: Customer Retention & Health (Weight: 25%)
        # ---------------------------------------------------------------------
        total_customers = max(cust_summary.total_customers, 1)
        inactive_count = cust_summary.inactive_customers
        at_risk_count = cust_summary.at_risk_customers
        inactive_pct = round((inactive_count / total_customers) * 100.0, 1)
        at_risk_pct = round((at_risk_count / total_customers) * 100.0, 1)

        vip_count = next((s.customer_count for s in cust_segments.segments if s.segment == "VIP"), 0)
        regular_count = next((s.customer_count for s in cust_segments.segments if s.segment in ["Regular", "Loyal"]), cust_summary.active_customers)

        raw_cust_score = 100.0 - (inactive_pct * 0.5 + at_risk_pct * 0.5)
        cust_score = float(max(min(raw_cust_score, 100.0), 20.0))

        if cust_score >= 85.0:
            cust_status = "excellent"
            cust_summary_text = f"High customer engagement ({vip_count} VIPs, low churn exposure)."
        elif cust_score >= 70.0:
            cust_status = "good"
            cust_summary_text = f"Solid regular customer base with manageable attrition ({inactive_pct}% inactive)."
        elif cust_score >= 50.0:
            cust_status = "warning"
            cust_summary_text = f"Elevated retention risk ({inactive_count} inactive, {at_risk_count} at-risk)."
        else:
            cust_status = "critical"
            cust_summary_text = f"Critical customer attrition ({inactive_pct}% of total customer base is inactive)."

        dim_customer = HealthDimension(
            dimension_name="customer_retention",
            score=round(cust_score, 1),
            status=cust_status,
            metric_summary=cust_summary_text,
            details={
                "total_customers": cust_summary.total_customers,
                "vip_customers": vip_count,
                "regular_customers": regular_count,
                "at_risk_customers": at_risk_count,
                "inactive_customers": inactive_count,
                "inactive_percentage": inactive_pct,
            },
        )


        # ---------------------------------------------------------------------
        # Dimension 3: Profitability (Weight: 25%)
        # ---------------------------------------------------------------------
        margin = pl.operating_margin_pct
        if pl.is_profitable:
            if margin >= 25.0:
                prof_score = 95.0
                prof_status = "excellent"
                prof_summary = f"Excellent operating profitability ({margin}% margin)."
            elif margin >= 15.0:
                prof_score = 80.0
                prof_status = "good"
                prof_summary = f"Healthy operating margin ({margin}%)."
            elif margin >= 5.0:
                prof_score = 65.0
                prof_status = "good"
                prof_summary = f"Modest operating profit ({margin}% margin)."
            else:
                prof_score = 50.0
                prof_status = "warning"
                prof_summary = f"Thin operating cushion ({margin}% margin)."
        else:
            prof_score = float(max(40.0 + margin * 0.2, 10.0))
            prof_status = "critical"
            prof_summary = f"Operating deficit: Expenses exceed revenue by ₹{abs(pl.net_profit):,.2f}."

        dim_profitability = HealthDimension(
            dimension_name="profitability",
            score=round(prof_score, 1),
            status=prof_status,
            metric_summary=prof_summary,
            details={
                "total_revenue": pl.total_revenue,
                "total_expenses": pl.total_expenses,
                "net_profit": pl.net_profit,
                "operating_margin_pct": margin,
                "is_profitable": pl.is_profitable,
            },
        )

        # ---------------------------------------------------------------------
        # Dimension 4: Operational & Expense Risk (Weight: 15%)
        # ---------------------------------------------------------------------
        anomaly_count = len(exp_breakdown.anomalies)
        exp_ratio = (pl.total_expenses / pl.total_revenue) if pl.total_revenue > 0 else 1.0

        ops_score = 90.0
        if anomaly_count > 0:
            ops_score -= min(anomaly_count * 15.0, 30.0)
        if exp_ratio > 0.75:
            ops_score -= 20.0
        ops_score = float(max(min(ops_score, 100.0), 20.0))

        if ops_score >= 80.0:
            ops_status = "excellent"
            ops_summary = "Well-controlled operational overhead with zero expense anomalies."
        elif ops_score >= 65.0:
            ops_status = "good"
            ops_summary = "Stable overhead with standard operational expenditure distribution."
        elif ops_score >= 50.0:
            ops_status = "warning"
            ops_summary = f"Operational expense alert: {anomaly_count} category anomaly detected."
        else:
            ops_status = "critical"
            ops_summary = f"High expense pressure: {anomaly_count} spending anomalies and high overhead ratio."

        dim_operations = HealthDimension(
            dimension_name="operational_risk",
            score=round(ops_score, 1),
            status=ops_status,
            metric_summary=ops_summary,
            details={
                "anomaly_count": anomaly_count,
                "expense_to_revenue_ratio": round(exp_ratio, 2),
                "top_expense_category": exp_breakdown.top_category,
            },
        )

        # ---------------------------------------------------------------------
        # Dimension 5: Growth Readiness & Opportunity (Weight: 10%)
        # ---------------------------------------------------------------------
        recs_count = len(growth_recs.recommendations)
        growth_score = 70.0 + min(recs_count * 5.0, 25.0)
        if weekend_analysis.weekend_to_weekday_revenue_ratio > 1.2:
            growth_score += 5.0
        growth_score = float(max(min(growth_score, 100.0), 30.0))

        dim_growth = HealthDimension(
            dimension_name="growth_readiness",
            score=round(growth_score, 1),
            status="excellent" if growth_score >= 80 else "good",
            metric_summary=f"{recs_count} actionable growth levers available with weekend expansion headroom.",
            details={
                "available_recommendations": recs_count,
                "weekend_revenue_share": weekend_analysis.weekend_revenue_share_percentage,
                "weekend_to_weekday_revenue_ratio": weekend_analysis.weekend_to_weekday_revenue_ratio,
            },
        )


        dimensions = [dim_revenue, dim_customer, dim_profitability, dim_operations, dim_growth]

        # ---------------------------------------------------------------------
        # Composite Health Score
        # ---------------------------------------------------------------------
        overall_score = round(
            0.25 * rev_score +
            0.25 * cust_score +
            0.25 * prof_score +
            0.15 * ops_score +
            0.10 * growth_score,
            1,
        )

        if overall_score >= 80.0:
            overall_status = "healthy"
        elif overall_score >= 65.0:
            overall_status = "stable"
        elif overall_score >= 50.0:
            overall_status = "at_risk"
        else:
            overall_status = "critical"

        # ---------------------------------------------------------------------
        # Evidence-Backed Risk Detection
        # ---------------------------------------------------------------------
        risks: List[RiskInsight] = []

        if rev_change < -5.0:
            risks.append(
                RiskInsight(
                    risk_id="risk-rev-contraction",
                    category="revenue",
                    severity="high" if rev_change < -12.0 else "medium",
                    title="Revenue Contraction Detected",
                    description=f"Store revenue declined by {abs(rev_change)}% over the recent 14-day window.",
                    metric_evidence=f"Recent 14d: ₹{sales_comp.current_period.revenue:,.2f} vs Prior 14d: ₹{sales_comp.previous_period.revenue:,.2f}",
                    suggested_action="Deploy targeted weekend cashback campaign to reverse sales drop.",
                )
            )

        if inactive_pct >= 25.0:
            risks.append(
                RiskInsight(
                    risk_id="risk-inactive-customers",
                    category="customer",
                    severity="high" if inactive_pct >= 40.0 else "medium",
                    title="High Inactive Customer Exposure",
                    description=f"{inactive_pct}% of registered customers haven't transacted in over 60 days.",
                    metric_evidence=f"{inactive_count} inactive customers out of {cust_summary.total_customers} total",
                    suggested_action="Trigger automated winback offer for inactive customer segment.",
                )
            )

        if not pl.is_profitable:
            risks.append(
                RiskInsight(
                    risk_id="risk-operating-deficit",
                    category="margin",
                    severity="high",
                    title="Operating Deficit Alert",
                    description="Operating expenditures exceed business revenue over the selected period.",
                    metric_evidence=f"Revenue: ₹{pl.total_revenue:,.2f}, Expenses: ₹{pl.total_expenses:,.2f} (Deficit: ₹{abs(pl.net_profit):,.2f})",
                    suggested_action="Review procurement invoices and eliminate non-essential overhead.",
                )
            )

        for anom in exp_breakdown.anomalies:
            risks.append(
                RiskInsight(
                    risk_id=f"risk-anomaly-{anom.category.lower()}",
                    category="operational",
                    severity="medium",
                    title=f"Expense Surge in {anom.category}",
                    description=anom.message,
                    metric_evidence=f"Current: ₹{anom.current_amount:,.2f} vs Baseline: ₹{anom.baseline_amount:,.2f} (+{anom.change_percentage}%)",
                    suggested_action="Audit vendor billings and check utility metering.",
                )
            )

        # ---------------------------------------------------------------------
        # Evidence-Backed Opportunity Detection
        # ---------------------------------------------------------------------
        opportunities: List[OpportunityInsight] = []

        if weekend_analysis.weekend_to_weekday_revenue_ratio > 1.1:
            opportunities.append(
                OpportunityInsight(
                    opportunity_id="opp-weekend-expansion",
                    category="weekend_lift",
                    potential_impact="high",
                    title="Strong Weekend Demand Headroom",
                    description=f"Weekend daily revenue is {weekend_analysis.weekend_to_weekday_revenue_ratio:.1f}x higher than weekday averages.",
                    metric_evidence=f"Weekend ATV: ₹{weekend_analysis.weekend_average_transaction_value:,.2f} | Weekend Share: {weekend_analysis.weekend_revenue_share_percentage}%",
                    recommendation_id="rec-weekend-rush",
                )
            )


        if inactive_count > 0:
            opportunities.append(
                OpportunityInsight(
                    opportunity_id="opp-winback-recovery",
                    category="retention",
                    potential_impact="high" if inactive_count > 30 else "medium",
                    title="Inactive Customer Revenue Recovery",
                    description=f"{inactive_count} dormant customers can be reactivated with an incentive coupon.",
                    metric_evidence=f"{inactive_count} dormant customers identified with zero visits in 60+ days",
                    recommendation_id="at_risk_reengagement",
                )
            )

        if sales_summary.average_transaction_value > 0:
            opportunities.append(
                OpportunityInsight(
                    opportunity_id="opp-basket-size-growth",
                    category="basket_size",
                    potential_impact="medium",
                    title="Basket Size (ATV) Upsell Potential",
                    description="Incentivizing slightly higher minimum bill values can lift gross revenue by 10-15%.",
                    metric_evidence=f"Current ATV: ₹{sales_summary.average_transaction_value:,.2f}",
                    recommendation_id="rec-atv-boost",
                )
            )

        summary_narrative = (
            f"Store business health is rated {overall_status.upper()} with an overall score of {overall_score}/100. "
            f"Revenue velocity score is {rev_score}/100, customer retention score is {cust_score}/100, and "
            f"operating profitability score is {prof_score}/100. "
            f"{len(risks)} risk signal(s) and {len(opportunities)} growth opportunity(ies) detected."
        )

        return BusinessHealthResponse(
            merchant_id=merchant_id,
            overall_score=overall_score,
            overall_status=overall_status,
            dimensions=dimensions,
            risks=risks,
            opportunities=opportunities,
            summary=summary_narrative,
            disclaimer=HEALTH_DISCLAIMER,
        )

    def get_risks(self, merchant_id: str) -> RiskListResponse:
        """Retrieve detected business risk signals for the merchant."""
        health = self.get_business_health(merchant_id)
        return RiskListResponse(
            merchant_id=merchant_id,
            total_risks=len(health.risks),
            risks=health.risks,
            disclaimer=HEALTH_DISCLAIMER,
        )

    def get_opportunities(self, merchant_id: str) -> OpportunityListResponse:
        """Retrieve detected growth opportunities for the merchant."""
        health = self.get_business_health(merchant_id)
        return OpportunityListResponse(
            merchant_id=merchant_id,
            total_opportunities=len(health.opportunities),
            opportunities=health.opportunities,
            disclaimer=HEALTH_DISCLAIMER,
        )
