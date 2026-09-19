"""
Agent Tool Registry and Execution Layer for Module 7.
Wraps Modules 2–6 service classes into deterministic, allowlisted tools
with strict merchant isolation and parameter validation.
"""

from typing import Dict, Any, Optional, List, Callable
from datetime import date, datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.logging import logger
from app.services.sales_service import SalesService
from app.services.customer_service import CustomerService
from app.services.growth_service import GrowthRecommendationService
from app.services.what_if_service import WhatIfSimulationService
from app.services.campaign_service import CampaignService
from app.services.accountant_service import AccountantService
from app.services.forecast_service import ForecastService
from app.services.business_health_service import BusinessHealthService

from app.schemas.what_if import SimulationRequest
from app.schemas.campaign import (
    CampaignCreateRequest,
    CampaignApproveRequest,
    CampaignExecuteRequest,
)
from app.ai.schemas import AgentToolDefinition, AgentToolParameter


# Explicit list of allowed tool names for security
ALLOWED_TOOLS = {
    "analyze_sales",
    "analyze_customers",
    "get_growth_recommendations",
    "get_target_customers",
    "simulate_campaign",
    "create_campaign",
    "approve_campaign",
    "execute_campaign",
    "get_campaign_status",
    "get_campaign_result",
    "analyze_financials",
    "analyze_cash_flow",
    "get_expenses",
    "get_campaign_history",
    "forecast_sales",
    "get_business_health",
}


class ToolRegistry:
    """
    Registry and execution engine for all agent tools.
    Strictly forces the use of the authenticated merchant_id across all operations.
    """

    def __init__(self, db: Session, merchant_id: str):
        self.db = db
        self.merchant_id = merchant_id.strip()
        self.sales_service = SalesService(db)
        self.customer_service = CustomerService(db)
        self.growth_service = GrowthRecommendationService(db)
        self.what_if_service = WhatIfSimulationService(db)
        self.campaign_service = CampaignService(db)
        self.accountant_service = AccountantService(db)
        self.forecast_service = ForecastService(db)
        self.business_health_service = BusinessHealthService(db)

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an allowlisted tool deterministically with authenticated merchant context.
        Rejects arbitrary unapproved tool invocations.
        """
        if tool_name not in ALLOWED_TOOLS:
            logger.warning(f"Security: Rejected unauthorized tool call '{tool_name}' for merchant {self.merchant_id}")
            return {
                "status": "error",
                "tool_name": tool_name,
                "message": f"Tool '{tool_name}' is not in the allowed tool registry. Allowed: {sorted(list(ALLOWED_TOOLS))}"
            }

        # Override any merchant_id passed in arguments to guarantee tenant isolation
        sanitized_args = dict(arguments or {})
        sanitized_args["merchant_id"] = self.merchant_id

        try:
            handler: Callable[..., Dict[str, Any]] = getattr(self, f"_tool_{tool_name}")
            result = handler(**sanitized_args)
            return {
                "status": "success",
                "tool_name": tool_name,
                "data": result
            }
        except HTTPException as he:
            logger.warning(f"HTTP exception in tool '{tool_name}': {he.detail}")
            return {
                "status": "error",
                "tool_name": tool_name,
                "message": str(he.detail)
            }
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}' for merchant {self.merchant_id}: {e}", exc_info=True)
            return {
                "status": "error",
                "tool_name": tool_name,
                "message": f"Execution of {tool_name} failed: {str(e)}"
            }

    # -------------------------------------------------------------------------
    # Tool Implementations (Module 2-6 Orchestration)
    # -------------------------------------------------------------------------

    def _tool_analyze_sales(
        self,
        merchant_id: str,
        period_days: int = 14,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 2: Analyze sales summary, trends, and deterministic insights."""
        s_date = date.fromisoformat(start_date) if start_date else None
        e_date = date.fromisoformat(end_date) if end_date else None

        summary = self.sales_service.get_summary(merchant_id=merchant_id, start_date=s_date, end_date=e_date)
        comparison = self.sales_service.get_period_comparison(merchant_id=merchant_id, current_days=period_days)
        insights = self.sales_service.get_sales_insights(merchant_id=merchant_id, current_days=period_days)
        weekend = self.sales_service.get_weekend_analysis(merchant_id=merchant_id)
        hourly = self.sales_service.get_hourly_analysis(merchant_id=merchant_id, start_date=s_date, end_date=e_date)

        peak_win = max(hourly.time_windows, key=lambda w: w.revenue) if hourly.time_windows else None
        weak_win = min(hourly.time_windows, key=lambda w: w.revenue) if hourly.time_windows else None

        return {
            "summary": {
                "total_revenue": summary.total_revenue,
                "total_transactions": summary.total_transactions,
                "average_transaction_value": summary.average_transaction_value,
                "success_rate": summary.success_rate,
            },
            "comparison": {
                "revenue_change_pct": comparison.revenue_change_percentage,
                "transaction_change_pct": comparison.transaction_change_percentage,
                "atv_change_pct": comparison.average_transaction_value_change_percentage,
            },
            "weekend": {
                "weekday_daily_avg": weekend.daily_avg_weekday_revenue,
                "weekend_daily_avg": weekend.daily_avg_weekend_revenue,
                "weekend_gap_ratio": weekend.weekend_to_weekday_revenue_ratio,
                "weekend_drop_flag": weekend.is_weekend_underperforming,
            },
            "hourly": {
                "peak_hour": hourly.peak_hour,
                "lowest_hour": hourly.lowest_hour,
                "peak_window": peak_win.window_name if peak_win else "Afternoon",
                "peak_window_hours": peak_win.hours_range if peak_win else "12:00 - 17:00",
                "peak_window_revenue": peak_win.revenue if peak_win else 0.0,
                "peak_window_transactions": peak_win.transaction_count if peak_win else 0,
                "weakest_window": weak_win.window_name if weak_win else "Night",
                "weakest_window_hours": weak_win.hours_range if weak_win else "21:00 - 06:00",
                "weakest_window_revenue": weak_win.revenue if weak_win else 0.0,
            },
            "insights": [ins.model_dump() for ins in insights.insights[:3]],
        }

    def _tool_analyze_customers(
        self,
        merchant_id: str,
        as_of_date: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 3: Analyze customer cohort distributions, churn risk, and segments."""
        ref_date = date.fromisoformat(as_of_date) if as_of_date else None
        summary = self.customer_service.get_summary(merchant_id=merchant_id, as_of_date=ref_date)
        segments = self.customer_service.get_segments(merchant_id=merchant_id)
        insights = self.customer_service.get_insights(merchant_id=merchant_id)

        return {
            "summary": {
                "total_customers": summary.total_customers,
                "active_customers": summary.active_customers,
                "at_risk_customers": summary.at_risk_customers,
                "inactive_customers": summary.inactive_customers,
                "repeat_customer_rate": summary.repeat_customer_rate,
                "average_customer_spend": summary.average_customer_spend,
            },
            "segments": [
                {
                    "name": seg.segment,
                    "count": seg.customer_count,
                    "revenue": seg.total_revenue,
                    "revenue_percentage": seg.percentage_of_revenue,
                }
                for seg in segments.segments
            ],
            "insights": [ins.message for ins in insights.insights[:3]],
        }


    def _tool_get_growth_recommendations(
        self,
        merchant_id: str,
        goal: Optional[str] = None,
        limit: int = 5,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 4: Retrieve prioritized, evidence-backed business growth recommendations."""
        recs = self.growth_service.generate_recommendations(merchant_id=merchant_id, goal=goal, limit=limit)
        return {
            "recommendations": [rec.model_dump() for rec in recs.recommendations],
            "top_recommendation": recs.recommendations[0].model_dump() if recs.recommendations else None,
            "total_count": len(recs.recommendations),
        }

    def _tool_get_target_customers(
        self,
        merchant_id: str,
        segment: str = "All Customers",
        limit: int = 20,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 3: Retrieve customer records for a targeted segment."""
        seg_lower = segment.lower().strip()
        if "at-risk" in seg_lower or "at risk" in seg_lower:
            res = self.customer_service.get_at_risk_customers(merchant_id=merchant_id, limit=limit)
            return {
                "target_segment": "At-Risk",
                "total_count": res.total_at_risk,
                "sample_customers": [
                    {
                        "customer_id": c.customer_id,
                        "name": c.name,
                        "days_since_last_visit": c.days_since_last_transaction,
                        "total_spent": c.historical_spend,
                        "churn_risk": c.risk_level,
                    }
                    for c in res.customers[:5]
                ]
            }
        elif "inactive" in seg_lower:
            res = self.customer_service.get_inactive_customers(merchant_id=merchant_id, limit=limit)
            return {
                "target_segment": "Inactive",
                "total_count": res.total_inactive,
                "sample_customers": [
                    {
                        "customer_id": c.customer_id,
                        "name": c.name,
                        "days_since_last_visit": c.days_since_last_transaction,
                        "total_spent": c.historical_spend,
                    }
                    for c in res.customers[:5]
                ]
            }
        else:
            res = self.customer_service.get_top_customers(merchant_id=merchant_id, by="revenue", limit=limit)
            return {
                "target_segment": segment,
                "total_count": res.count,
                "sample_customers": [
                    {
                        "customer_id": c.customer_id,
                        "name": c.name,
                        "total_revenue": c.total_spend,
                        "transaction_count": c.transaction_count,
                        "segment": c.segment,
                    }
                    for c in res.customers[:5]
                ]
            }


    def _tool_simulate_campaign(
        self,
        merchant_id: str,
        offer_type: str = "fixed_cashback",
        discount_percent: Optional[float] = None,
        cashback_amount: Optional[float] = None,
        target_segment: str = "All Customers",
        minimum_transaction_amount: Optional[float] = 0.0,
        target_days: Optional[str] = None,
        target_hours: Optional[str] = None,
        scenario_name: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 5: Run deterministic What-If simulation to predict uplift, incentive cost, and ROI."""
        # Normalize scenario type
        clean_offer = offer_type.lower().strip()
        scenario_type = "percentage_discount" if "discount" in clean_offer else "fixed_cashback"
        
        sim_request = SimulationRequest(
            merchant_id=merchant_id,
            scenario_name=scenario_name or f"Simulated {target_segment} {clean_offer}",
            scenario_type=scenario_type,
            target_segment=target_segment,
            discount_percent=discount_percent if scenario_type == "percentage_discount" else None,
            cashback_amount=cashback_amount if scenario_type == "fixed_cashback" else None,
            minimum_transaction_amount=minimum_transaction_amount or 0.0,
            target_days=target_days,
            target_hours=target_hours,
        )

        simulation = self.what_if_service.simulate_scenario(merchant_id=merchant_id, request=sim_request)
        return simulation.model_dump()

    def _tool_create_campaign(
        self,
        merchant_id: str,
        name: str,
        offer_type: str = "fixed_cashback",
        discount_percent: Optional[float] = None,
        cashback_amount: Optional[float] = None,
        target_segment: str = "All Customers",
        minimum_transaction_amount: Optional[float] = 0.0,
        target_days: Optional[str] = None,
        target_hours: Optional[str] = None,
        description: Optional[str] = None,
        source_recommendation_id: Optional[str] = None,
        source_simulation_id: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Module 6: Create campaign draft.
        MANDATORY: Always enters PENDING_APPROVAL status. Autonomous execution is strictly blocked.
        """
        create_req = CampaignCreateRequest(
            merchant_id=merchant_id,
            name=name,
            description=description,
            target_segment=target_segment,
            offer_type=offer_type,
            discount_percent=discount_percent,
            cashback_amount=cashback_amount,
            minimum_transaction_amount=minimum_transaction_amount or 0.0,
            target_days=target_days,
            target_hours=target_hours,
            source_recommendation_id=source_recommendation_id,
            source_simulation_id=source_simulation_id,
            created_by="MerchantMind AI Agent",
        )

        campaign = self.campaign_service.create_campaign(merchant_id=merchant_id, request=create_req)
        return campaign.model_dump()

    def _tool_approve_campaign(
        self,
        merchant_id: str,
        campaign_id: str,
        approved_by: Optional[str] = "Merchant",
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 6: Explicit human merchant approval."""
        approve_req = CampaignApproveRequest(
            merchant_id=merchant_id,
            approved_by=approved_by or "Merchant",
            actor=approved_by or "Merchant",
        )
        approved = self.campaign_service.approve_campaign(
            campaign_id=campaign_id, merchant_id=merchant_id, request=approve_req
        )
        return approved.model_dump()

    def _tool_execute_campaign(
        self,
        merchant_id: str,
        campaign_id: str,
        actor: Optional[str] = "Merchant",
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 6: Safe simulated execution of an APPROVED campaign."""
        exec_req = CampaignExecuteRequest(merchant_id=merchant_id, actor=actor or "Merchant")
        result = self.campaign_service.execute_campaign(
            campaign_id=campaign_id, merchant_id=merchant_id, request=exec_req
        )
        return result.model_dump()

    def _tool_get_campaign_status(
        self,
        merchant_id: str,
        campaign_id: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 6: Retrieve campaign status and details."""
        campaign = self.campaign_service.get_campaign(campaign_id=campaign_id, merchant_id=merchant_id)
        return campaign.model_dump()

    def _tool_get_campaign_result(
        self,
        merchant_id: str,
        campaign_id: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 6: Retrieve simulated campaign execution result."""
        result = self.campaign_service.get_campaign_result(campaign_id=campaign_id, merchant_id=merchant_id)
        return result.model_dump()

    def _tool_analyze_financials(
        self,
        merchant_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 8: Analyze profit & loss, expense categories, anomalies, and financial summary."""
        s_date = date.fromisoformat(start_date) if start_date else None
        e_date = date.fromisoformat(end_date) if end_date else None
        summary = self.accountant_service.get_accountant_summary(merchant_id=merchant_id, start_date=s_date, end_date=e_date)
        return summary.model_dump()

    def _tool_analyze_cash_flow(
        self,
        merchant_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 8: Analyze cash inflows, outflows, net cash flow, settlements, and payables."""
        s_date = date.fromisoformat(start_date) if start_date else None
        e_date = date.fromisoformat(end_date) if end_date else None
        res = self.accountant_service.get_cash_flow(merchant_id=merchant_id, start_date=s_date, end_date=e_date)
        return res.model_dump()

    def _tool_get_expenses(
        self,
        merchant_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 8: Analyze detailed operational expense categories and anomalies."""
        s_date = date.fromisoformat(start_date) if start_date else None
        e_date = date.fromisoformat(end_date) if end_date else None
        res = self.accountant_service.get_expenses_breakdown(merchant_id=merchant_id, start_date=s_date, end_date=e_date)
        return res.model_dump()

    def _tool_get_campaign_history(
        self,
        merchant_id: str,
        limit: int = 5,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 6: Retrieve historical campaign performance and conversion records."""
        res = self.campaign_service.list_campaigns(merchant_id=merchant_id, limit=limit)
        return res.model_dump()

    def _tool_forecast_sales(
        self,
        merchant_id: str,
        historical_days: int = 28,
        horizon_days: int = 30,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 9: Generate statistical revenue forecast and daily projections."""
        h_days = int(historical_days) if historical_days else 28
        hz_days = int(kwargs["days"]) if "days" in kwargs and kwargs["days"] else (int(horizon_days) if horizon_days else 30)
        res = self.forecast_service.get_forecast_summary(
            merchant_id=merchant_id,
            historical_days=h_days,
            horizon_days=hz_days,
        )
        return res.model_dump()

    def _tool_get_business_health(
        self,
        merchant_id: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Module 9: Evaluate composite business health score, risks, and growth opportunities."""
        res = self.business_health_service.get_business_health(merchant_id=merchant_id)
        return res.model_dump()

    @staticmethod
    def get_tool_catalog() -> List[AgentToolDefinition]:
        """Public schema catalog for all allowlisted tools."""
        return [
            AgentToolDefinition(
                name="analyze_sales",
                description="Analyze sales performance, period comparisons, trends, and deterministic insights (Module 2).",
                category="Sales Intelligence",
                parameters=[
                    AgentToolParameter(name="period_days", type="integer", description="Lookback window in days (default: 14)", required=False, default=14),
                    AgentToolParameter(name="start_date", type="string", description="Optional start date (YYYY-MM-DD)", required=False),
                    AgentToolParameter(name="end_date", type="string", description="Optional end date (YYYY-MM-DD)", required=False),
                ]
            ),
            AgentToolDefinition(
                name="analyze_customers",
                description="Analyze customer segments, active/inactive counts, churn risk, and RFM distributions (Module 3).",
                category="Customer Intelligence",
                parameters=[
                    AgentToolParameter(name="as_of_date", type="string", description="Optional reference date (YYYY-MM-DD)", required=False),
                ]
            ),
            AgentToolDefinition(
                name="get_growth_recommendations",
                description="Fetch prioritized, evidence-backed business growth recommendations (Module 4).",
                category="Growth Recommendation",
                parameters=[
                    AgentToolParameter(name="goal", type="string", description="Filter by goal: revenue, retention, recovery, weekend, frequency", required=False),
                    AgentToolParameter(name="limit", type="integer", description="Maximum number of recommendations (default: 5)", required=False, default=5),
                ]
            ),
            AgentToolDefinition(
                name="get_target_customers",
                description="Fetch target customer profiles for a specific cohort: At-Risk, Inactive, VIP, Loyal (Module 3).",
                category="Customer Intelligence",
                parameters=[
                    AgentToolParameter(name="segment", type="string", description="Target customer segment", required=True, default="All Customers"),
                    AgentToolParameter(name="limit", type="integer", description="Max customer count to inspect", required=False, default=20),
                ]
            ),
            AgentToolDefinition(
                name="simulate_campaign",
                description="Simulate projected revenue uplift, customer uptake, incentive cost, and ROI using What-If simulator (Module 5).",
                category="What-If Simulator",
                parameters=[
                    AgentToolParameter(name="offer_type", type="string", description="Offer type: fixed_cashback | percentage_discount", required=True),
                    AgentToolParameter(name="discount_percent", type="number", description="Discount percent (0-50%)", required=False),
                    AgentToolParameter(name="cashback_amount", type="number", description="Cashback in INR (0-2000)", required=False),
                    AgentToolParameter(name="target_segment", type="string", description="Target cohort: All Customers, At-Risk, Inactive, VIP, etc.", required=False, default="All Customers"),
                    AgentToolParameter(name="minimum_transaction_amount", type="number", description="Minimum order threshold in INR", required=False, default=0.0),
                    AgentToolParameter(name="target_days", type="string", description="Filter: weekend | weekday | all", required=False),
                    AgentToolParameter(name="target_hours", type="string", description="Filter: morning | afternoon | evening | night | all", required=False),
                ]
            ),
            AgentToolDefinition(
                name="create_campaign",
                description="Create campaign draft in Module 6. ALWAYS enters PENDING_APPROVAL status. Never executes autonomously.",
                category="Campaign Management",
                parameters=[
                    AgentToolParameter(name="name", type="string", description="Campaign headline name", required=True),
                    AgentToolParameter(name="offer_type", type="string", description="fixed_cashback | percentage_discount | custom", required=True),
                    AgentToolParameter(name="discount_percent", type="number", description="Discount percentage", required=False),
                    AgentToolParameter(name="cashback_amount", type="number", description="Cashback amount in INR", required=False),
                    AgentToolParameter(name="target_segment", type="string", description="Customer segment", required=False, default="All Customers"),
                    AgentToolParameter(name="minimum_transaction_amount", type="number", description="Minimum order threshold in INR", required=False, default=0.0),
                    AgentToolParameter(name="target_days", type="string", description="Day filter: weekend | weekday | all", required=False),
                    AgentToolParameter(name="target_hours", type="string", description="Hour filter", required=False),
                    AgentToolParameter(name="description", type="string", description="Business purpose of campaign", required=False),
                    AgentToolParameter(name="source_recommendation_id", type="string", description="Optional Module 4 recommendation ID", required=False),
                    AgentToolParameter(name="source_simulation_id", type="string", description="Optional Module 5 simulation scenario ID", required=False),
                ]
            ),
            AgentToolDefinition(
                name="approve_campaign",
                description="Record explicit human merchant approval for a PENDING_APPROVAL campaign (Module 6).",
                category="Campaign Management",
                parameters=[
                    AgentToolParameter(name="campaign_id", type="string", description="Unique campaign ID", required=True),
                    AgentToolParameter(name="approved_by", type="string", description="Merchant identity or role", required=False, default="Merchant"),
                ]
            ),
            AgentToolDefinition(
                name="execute_campaign",
                description="Execute an APPROVED campaign in safe simulated demo mode (Module 6). Rejects if not APPROVED.",
                category="Campaign Management",
                parameters=[
                    AgentToolParameter(name="campaign_id", type="string", description="Unique campaign ID", required=True),
                    AgentToolParameter(name="actor", type="string", description="Executor role", required=False, default="Merchant"),
                ]
            ),
            AgentToolDefinition(
                name="get_campaign_status",
                description="Fetch current status and details of a campaign (Module 6).",
                category="Campaign Management",
                parameters=[
                    AgentToolParameter(name="campaign_id", type="string", description="Unique campaign ID", required=True),
                ]
            ),
            AgentToolDefinition(
                name="get_campaign_result",
                description="Fetch deterministic simulated performance metrics of an executed campaign (Module 6).",
                category="Campaign Management",
                parameters=[
                    AgentToolParameter(name="campaign_id", type="string", description="Unique campaign ID", required=True),
                ]
            ),
            AgentToolDefinition(
                name="analyze_financials",
                description="Analyze P&L, revenue, expenses, net profit, operating margin, and anomalies (Module 8).",
                category="AI Accountant",
                parameters=[
                    AgentToolParameter(name="start_date", type="string", description="Optional start date (YYYY-MM-DD)", required=False),
                    AgentToolParameter(name="end_date", type="string", description="Optional end date (YYYY-MM-DD)", required=False),
                ]
            ),
            AgentToolDefinition(
                name="forecast_sales",
                description="Generate statistical revenue forecast and daily projections for future horizons (Module 9).",
                category="Forecasting",
                parameters=[
                    AgentToolParameter(name="historical_days", type="integer", description="Lookback window in days (default: 28)", required=False, default=28),
                    AgentToolParameter(name="horizon_days", type="integer", description="Forecast horizon in days (default: 30)", required=False, default=30),
                ]
            ),
            AgentToolDefinition(
                name="get_business_health",
                description="Evaluate composite store business health, dimension scores, warning risks, and growth opportunities (Module 9).",
                category="Business Health",
                parameters=[]
            ),
            AgentToolDefinition(
                name="analyze_cash_flow",
                description="Analyze cash inflows, outflows, operating cash flow, payment settlements, and pending/overdue payables (Module 8).",
                category="AI Accountant",
                parameters=[
                    AgentToolParameter(name="start_date", type="string", description="Optional start date (YYYY-MM-DD)", required=False),
                    AgentToolParameter(name="end_date", type="string", description="Optional end date (YYYY-MM-DD)", required=False),
                ]
            ),
            AgentToolDefinition(
                name="get_expenses",
                description="Fetch breakdown of operational expenses by category, top expense driver, and detected spending anomalies (Module 8).",
                category="AI Accountant",
                parameters=[
                    AgentToolParameter(name="start_date", type="string", description="Optional start date (YYYY-MM-DD)", required=False),
                    AgentToolParameter(name="end_date", type="string", description="Optional end date (YYYY-MM-DD)", required=False),
                ]
            ),
            AgentToolDefinition(
                name="get_campaign_history",
                description="Fetch historical promotional campaigns, their statuses, conversion counts, and delivered revenue (Module 6).",
                category="Campaign Management",
                parameters=[
                    AgentToolParameter(name="limit", type="integer", description="Max number of past campaigns to retrieve (default: 5)", required=False, default=5),
                ]
            ),
        ]

