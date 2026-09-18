"""
MarketingCampaignAgent — Agentic Orchestration Layer for Module 7.
Coordinates Module 2 (Sales), Module 3 (Customers), Module 4 (Recommendations),
Module 5 (Simulator), and Module 6 (Campaigns & Approvals).
Strictly enforces human-in-the-loop lifecycle and deterministic financial boundaries.
"""

from typing import Dict, Any, Optional, List, Tuple
from collections import OrderedDict
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.ai.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    MerchantIntent,
    AgentToolCall,
)
from app.ai.tools import ToolRegistry, ALLOWED_TOOLS
from app.ai.llm_client import get_llm_client, BaseLLMClient
from app.schemas.campaign import CampaignResponse, CampaignResultResponse
from app.schemas.what_if import SimulationScenario


# Simple in-memory bounded cache for short conversation continuity (max 200 sessions)
_CONVERSATION_CACHE: OrderedDict[str, Dict[str, Any]] = OrderedDict()
MAX_CACHE_SIZE = 200
MAX_TOOL_CALLS_PER_REQUEST = 8


def get_conversation_context(conversation_id: Optional[str]) -> Dict[str, Any]:
    """Retrieve short-term session context without storing raw PII."""
    if not conversation_id or conversation_id not in _CONVERSATION_CACHE:
        return {}
    # Move to end for LRU order
    _CONVERSATION_CACHE.move_to_end(conversation_id)
    return dict(_CONVERSATION_CACHE[conversation_id])


def update_conversation_context(conversation_id: Optional[str], context_update: Dict[str, Any]) -> None:
    """Update short-term session state with size cap."""
    if not conversation_id:
        return
    current = _CONVERSATION_CACHE.get(conversation_id, {})
    current.update(context_update)
    _CONVERSATION_CACHE[conversation_id] = current
    _CONVERSATION_CACHE.move_to_end(conversation_id)

    while len(_CONVERSATION_CACHE) > MAX_CACHE_SIZE:
        _CONVERSATION_CACHE.popitem(last=False)


class MarketingCampaignAgent:
    """
    AI Marketing Partner orchestrating multi-module campaign workflows.
    Human-in-the-loop is strictly enforced: campaigns enter PENDING_APPROVAL
    and can NEVER be autonomously executed.
    """

    def __init__(self, db: Session, merchant_id: str, llm_client: Optional[BaseLLMClient] = None):
        self.db = db
        self.merchant_id = merchant_id.strip()
        self.tools = ToolRegistry(db, self.merchant_id)
        self.llm = llm_client or get_llm_client()
        self.actions_taken: List[AgentToolCall] = []
        self._tool_call_count = 0

    def _invoke_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for invoking tools with loop guard and execution logging."""
        if self._tool_call_count >= MAX_TOOL_CALLS_PER_REQUEST:
            logger.warning(f"Agent loop limit reached ({MAX_TOOL_CALLS_PER_REQUEST} calls) for merchant {self.merchant_id}")
            return {
                "status": "error",
                "tool_name": tool_name,
                "message": "Maximum allowable tool executions exceeded for this request."
            }

        self._tool_call_count += 1
        res = self.tools.execute_tool(tool_name, arguments)
        
        summary = None
        if res.get("status") == "success":
            data = res.get("data", {})
            if "total_revenue" in str(data):
                summary = "Retrieved sales summary & trends"
            elif "campaign_id" in data:
                summary = f"Processed campaign {data.get('campaign_id')} (Status: {data.get('status')})"
            elif "scenario_id" in data:
                summary = f"Simulated scenario {data.get('scenario_name')} with projected ROI {data.get('roi_multiplier_label')}"
            elif "recommendations" in data:
                summary = f"Fetched {data.get('total_count')} growth recommendations"
            elif "total_count" in data:
                summary = f"Identified {data.get('total_count')} target customers"
            else:
                summary = f"Tool {tool_name} completed successfully"
        else:
            summary = f"Tool {tool_name} error: {res.get('message')}"

        self.actions_taken.append(
            AgentToolCall(
                tool_name=tool_name,
                arguments={k: v for k, v in arguments.items() if k != "merchant_id"},
                status=res.get("status", "error"),
                result_summary=summary
            )
        )
        return res

    def chat(self, request: AgentChatRequest) -> AgentChatResponse:
        """
        Main entry point for agent orchestration.
        Interprets natural language, invokes allowlisted tools,
        constructs campaign proposal, simulates impact, and stops at PENDING_APPROVAL.
        """
        self.actions_taken.clear()
        self._tool_call_count = 0

        conv_id = request.conversation_id
        session_context = get_conversation_context(conv_id)
        if request.context:
            session_context.update(request.context)

        # 1. Intent interpretation
        try:
            intent = self.llm.parse_intent(request.message, session_context)
        except Exception as e:
            logger.warning(f"LLM parse_intent failed ({e}). Using deterministic fallback parser.")
            from app.ai.llm_client import DeterministicFallbackClient
            intent = DeterministicFallbackClient().parse_intent(request.message, session_context)

        logger.info(f"Interpreted intent for merchant '{self.merchant_id}': {intent.intent} ({intent.requested_action})")


        insights: List[str] = []
        recommendation_dict: Optional[Dict[str, Any]] = None
        simulation_obj: Optional[SimulationScenario] = None
        campaign_obj: Optional[CampaignResponse] = None
        execution_result_obj: Optional[CampaignResultResponse] = None
        approval_required = False
        campaign_id: Optional[str] = None
        status_str: Optional[str] = None

        response_text: Optional[str] = None

        # 2. Orchestration based on intent
        if intent.intent == "increase_weekend_revenue":
            # Step A: Analyze sales
            sales_res = self._invoke_tool("analyze_sales", {"period_days": 14})
            if sales_res.get("status") == "success":
                insights.extend([i.get("observation", "") for i in sales_res["data"].get("insights", []) if isinstance(i, dict)])
                if not insights and sales_res["data"].get("weekend", {}).get("weekend_drop_flag"):
                    insights.append("Weekend transaction volume is lower than weekday average.")

            # Step B: Get growth recommendations
            rec_res = self._invoke_tool("get_growth_recommendations", {"goal": "weekend", "limit": 3})
            rec_id = None
            if rec_res.get("status") == "success":
                recommendation_dict = rec_res["data"].get("top_recommendation")
                if recommendation_dict:
                    rec_id = recommendation_dict.get("recommendation_id")

            # Step C: Simulate campaign (Module 5)
            cb_amount = float(intent.parameters.get("cashback_amount") or 50.0)
            disc_pct = float(intent.parameters.get("discount_percent") or 0.0)
            offer_type = "fixed_cashback" if cb_amount > 0 else "percentage_discount"

            sim_res = self._invoke_tool(
                "simulate_campaign",
                {
                    "offer_type": offer_type,
                    "cashback_amount": cb_amount if offer_type == "fixed_cashback" else None,
                    "discount_percent": disc_pct if offer_type == "percentage_discount" else None,
                    "target_segment": intent.target_segment or "All Customers",
                    "target_days": "weekend",
                    "minimum_transaction_amount": float(intent.parameters.get("minimum_transaction_amount") or 200.0),
                    "scenario_name": "Weekend Revenue Booster"
                }
            )
            sim_id = None
            if sim_res.get("status") == "success":
                simulation_obj = SimulationScenario(**sim_res["data"])
                sim_id = simulation_obj.scenario_id

            # Step D: Create campaign draft (Module 6) — Strictly PENDING_APPROVAL
            camp_res = self._invoke_tool(
                "create_campaign",
                {
                    "name": "Weekend Revenue Booster Campaign",
                    "description": "Targeted weekend promotional offer to drive higher basket sizes and recover weekend footfall.",
                    "target_segment": intent.target_segment or "All Customers",
                    "offer_type": offer_type,
                    "cashback_amount": cb_amount if offer_type == "fixed_cashback" else None,
                    "discount_percent": disc_pct if offer_type == "percentage_discount" else None,
                    "minimum_transaction_amount": float(intent.parameters.get("minimum_transaction_amount") or 200.0),
                    "target_days": "weekend",
                    "source_recommendation_id": rec_id,
                    "source_simulation_id": sim_id,
                }
            )
            if camp_res.get("status") == "success":
                campaign_obj = CampaignResponse(**camp_res["data"])
                campaign_id = campaign_obj.campaign_id
                status_str = campaign_obj.status
                approval_required = True

        elif intent.intent == "recover_inactive_customers":
            target_seg = intent.target_segment if intent.target_segment in ["Inactive", "At-Risk"] else "Inactive"
            # Step A: Analyze customers
            cust_res = self._invoke_tool("analyze_customers", {})
            if cust_res.get("status") == "success":
                insights.extend(cust_res["data"].get("insights", []))

            # Step B: Identify target customers
            target_res = self._invoke_tool("get_target_customers", {"segment": target_seg, "limit": 10})
            if target_res.get("status") == "success":
                cnt = target_res["data"].get("total_count", 0)
                insights.append(f"Identified {cnt} {target_seg} customers available for reactivation.")

            # Step C: Simulate win-back campaign (Module 5)
            cb_amount = float(intent.parameters.get("cashback_amount") or 50.0)
            disc_pct = float(intent.parameters.get("discount_percent") or 0.0)
            offer_type = "fixed_cashback" if cb_amount > 0 else "percentage_discount"

            sim_res = self._invoke_tool(
                "simulate_campaign",
                {
                    "offer_type": offer_type,
                    "cashback_amount": cb_amount if offer_type == "fixed_cashback" else None,
                    "discount_percent": disc_pct if offer_type == "percentage_discount" else None,
                    "target_segment": target_seg,
                    "minimum_transaction_amount": float(intent.parameters.get("minimum_transaction_amount") or 300.0),
                    "scenario_name": f"Win-Back {target_seg} Customers"
                }
            )
            sim_id = None
            if sim_res.get("status") == "success":
                simulation_obj = SimulationScenario(**sim_res["data"])
                sim_id = simulation_obj.scenario_id

            # Step D: Create campaign draft (Module 6) — Strictly PENDING_APPROVAL
            camp_res = self._invoke_tool(
                "create_campaign",
                {
                    "name": f"Win-Back {target_seg} Customers Offer",
                    "description": f"Targeted promotional incentive to reactivate {target_seg} customers who have not visited recently.",
                    "target_segment": target_seg,
                    "offer_type": offer_type,
                    "cashback_amount": cb_amount if offer_type == "fixed_cashback" else None,
                    "discount_percent": disc_pct if offer_type == "percentage_discount" else None,
                    "minimum_transaction_amount": float(intent.parameters.get("minimum_transaction_amount") or 300.0),
                    "source_simulation_id": sim_id,
                }
            )
            if camp_res.get("status") == "success":
                campaign_obj = CampaignResponse(**camp_res["data"])
                campaign_id = campaign_obj.campaign_id
                status_str = campaign_obj.status
                approval_required = True

        elif intent.intent == "simulate_campaign":
            cb_amount = intent.parameters.get("cashback_amount")
            disc_pct = intent.parameters.get("discount_percent")
            offer_type = "fixed_cashback" if cb_amount else ("percentage_discount" if disc_pct else "fixed_cashback")
            if not cb_amount and not disc_pct:
                cb_amount = 50.0

            sim_res = self._invoke_tool(
                "simulate_campaign",
                {
                    "offer_type": offer_type,
                    "cashback_amount": float(cb_amount) if cb_amount else None,
                    "discount_percent": float(disc_pct) if disc_pct else None,
                    "target_segment": intent.target_segment or "All Customers",
                    "minimum_transaction_amount": float(intent.parameters.get("minimum_transaction_amount") or 0.0),
                    "target_days": intent.time_window if intent.time_window in ["weekend", "weekday"] else None,
                    "scenario_name": f"Simulation for {intent.target_segment}"
                }
            )
            if sim_res.get("status") == "success":
                simulation_obj = SimulationScenario(**sim_res["data"])
                insights.append(
                    f"Projected {simulation_obj.roi_multiplier_label} ROI with net impact of ₹{simulation_obj.net_incremental_impact:,.2f}"
                )

        elif intent.intent == "create_campaign":
            # Run simulation first
            cb_amount = intent.parameters.get("cashback_amount")
            disc_pct = intent.parameters.get("discount_percent")
            offer_type = "fixed_cashback" if cb_amount else ("percentage_discount" if disc_pct else "fixed_cashback")
            if not cb_amount and not disc_pct:
                cb_amount = 50.0

            sim_res = self._invoke_tool(
                "simulate_campaign",
                {
                    "offer_type": offer_type,
                    "cashback_amount": float(cb_amount) if cb_amount else None,
                    "discount_percent": float(disc_pct) if disc_pct else None,
                    "target_segment": intent.target_segment or "All Customers",
                    "minimum_transaction_amount": float(intent.parameters.get("minimum_transaction_amount") or 0.0),
                    "target_days": intent.time_window if intent.time_window in ["weekend", "weekday"] else None,
                }
            )
            sim_id = None
            if sim_res.get("status") == "success":
                simulation_obj = SimulationScenario(**sim_res["data"])
                sim_id = simulation_obj.scenario_id

            camp_res = self._invoke_tool(
                "create_campaign",
                {
                    "name": f"Custom {intent.target_segment} Promotional Campaign",
                    "description": f"Merchant-requested promotional campaign for {intent.target_segment}.",
                    "target_segment": intent.target_segment or "All Customers",
                    "offer_type": offer_type,
                    "cashback_amount": float(cb_amount) if cb_amount else None,
                    "discount_percent": float(disc_pct) if disc_pct else None,
                    "minimum_transaction_amount": float(intent.parameters.get("minimum_transaction_amount") or 0.0),
                    "target_days": intent.time_window if intent.time_window in ["weekend", "weekday"] else None,
                    "source_simulation_id": sim_id,
                }
            )
            if camp_res.get("status") == "success":
                campaign_obj = CampaignResponse(**camp_res["data"])
                campaign_id = campaign_obj.campaign_id
                status_str = campaign_obj.status
                approval_required = True

        elif intent.intent == "approve_campaign":
            target_camp_id = intent.parameters.get("campaign_id") or session_context.get("campaign_id")
            if not target_camp_id:
                # Find latest PENDING_APPROVAL campaign for this merchant
                from app.services.campaign_service import CampaignService
                c_service = CampaignService(self.db)
                pending_list = c_service.list_campaigns(merchant_id=self.merchant_id, status_filter="PENDING_APPROVAL", limit=1)
                if pending_list.campaigns:
                    target_camp_id = pending_list.campaigns[0].campaign_id

            if target_camp_id:
                appr_res = self._invoke_tool("approve_campaign", {"campaign_id": target_camp_id, "approved_by": "Merchant"})
                if appr_res.get("status") == "success":
                    campaign_obj = CampaignResponse(**appr_res["data"])
                    campaign_id = campaign_obj.campaign_id
                    status_str = campaign_obj.status
                    approval_required = False
                else:
                    insights.append(f"Approval failed: {appr_res.get('message')}")
            else:
                insights.append("No active campaign draft found pending approval.")

        elif intent.intent == "execute_campaign":
            target_camp_id = intent.parameters.get("campaign_id") or session_context.get("campaign_id")
            if not target_camp_id:
                # Execution safety invariant: NEVER select implicit / latest approved campaign.
                # Strictly require explicit campaign_id in request or active conversation context.
                clarification_msg = "I found multiple or unspecified campaigns. Please provide the campaign ID or specify which campaign you want to execute."
                insights.append(clarification_msg)
                response_text = clarification_msg
            else:
                exec_res = self._invoke_tool("execute_campaign", {"campaign_id": target_camp_id})
                if exec_res.get("status") == "success":
                    execution_result_obj = CampaignResultResponse(**exec_res["data"])
                    campaign_id = target_camp_id
                    status_str = "COMPLETED"
                    approval_required = False
                else:
                    insights.append(f"Execution failed: {exec_res.get('message')}")
                    response_text = f"Campaign execution failed: {exec_res.get('message')}"

        elif intent.intent == "analyze_business":
            sales_res = self._invoke_tool("analyze_sales", {"period_days": 14})
            cust_res = self._invoke_tool("analyze_customers", {})
            rec_res = self._invoke_tool("get_growth_recommendations", {"limit": 3})

            if sales_res.get("status") == "success":
                insights.extend([i.get("observation", "") for i in sales_res["data"].get("insights", []) if isinstance(i, dict)])
            if cust_res.get("status") == "success":
                insights.extend(cust_res["data"].get("insights", []))
            if rec_res.get("status") == "success":
                recommendation_dict = rec_res["data"].get("top_recommendation")

        elif intent.intent == "analyze_financials":
            fin_res = self._invoke_tool("analyze_financials", {})
            if fin_res.get("status") == "success":
                data = fin_res.get("data", {})
                pl_data = data.get("profit_loss", {})
                exp_data = data.get("expenses", {})
                insights.append(
                    f"Net Operating Profit is ₹{pl_data.get('net_profit', 0.0):,.2f} "
                    f"with {pl_data.get('operating_margin_pct', 0.0)}% operating margin."
                )
                if exp_data.get("top_category"):
                    insights.append(f"Largest expense category is '{exp_data.get('top_category')}'.")
                for anom in exp_data.get("anomalies", []):
                    insights.append(anom.get("message"))

        elif intent.intent == "forecast_sales":
            fc_res = self._invoke_tool("forecast_sales", {})
            if fc_res.get("status") == "success":
                data = fc_res.get("data", {})
                insights.append(
                    f"Projected next-month revenue is ₹{data.get('projected_revenue', 0.0):,.2f} "
                    f"(Range: ₹{data.get('lower_bound', 0.0):,.2f} to ₹{data.get('upper_bound', 0.0):,.2f})."
                )
                insights.append(
                    f"Historical baseline trend is {data.get('trend_direction', 'stable')} "
                    f"({data.get('trend_factor_pct', 0.0):+0.2f}% momentum)."
                )

        elif intent.intent == "get_business_health":
            bh_res = self._invoke_tool("get_business_health", {})
            if bh_res.get("status") == "success":
                data = bh_res.get("data", {})
                insights.append(
                    f"Overall Store Health Score is {data.get('overall_score', 0.0)}/100 "
                    f"({str(data.get('overall_status', 'stable')).upper()})."
                )
                for r in data.get("risks", []):
                    insights.append(f"Risk: {r.get('title')} — {r.get('description')}")
                for o in data.get("opportunities", []):
                    insights.append(f"Opportunity: {o.get('title')} — {o.get('description')}")

        else:
            # Guidance / unsupported
            insights.append("Supported goals: increase weekend sales, recover inactive customers, simulate offers, create campaigns, view financial P&L, forecast revenue, assess business health.")

        # 3. Generate response text
        if not response_text:
            tool_results_summary = [a.model_dump() for a in self.actions_taken]
            try:
                response_text = self.llm.generate_response(request.message, intent, tool_results_summary, session_context)
            except Exception as e:
                logger.warning(f"LLM generate_response failed ({e}). Using deterministic fallback generator.")
                from app.ai.llm_client import DeterministicFallbackClient
                response_text = DeterministicFallbackClient().generate_response(request.message, intent, tool_results_summary, session_context)


        # 4. Update short-term session continuity
        context_update: Dict[str, Any] = {
            "last_intent": intent.intent,
            "target_segment": intent.target_segment,
        }
        if campaign_id:
            context_update["campaign_id"] = campaign_id
        if status_str:
            context_update["status"] = status_str
        update_conversation_context(conv_id, context_update)

        return AgentChatResponse(
            message=response_text,
            intent=intent,
            actions_taken=self.actions_taken,
            insights=insights[:5],
            recommendation=recommendation_dict,
            campaign=campaign_obj,
            simulation=simulation_obj,
            approval_required=approval_required,
            campaign_id=campaign_id,
            status=status_str,
            execution_result=execution_result_obj,
        )
