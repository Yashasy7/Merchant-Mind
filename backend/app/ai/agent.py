"""
MarketingCampaignAgent — Agentic Orchestration Layer for Module 7.
Coordinates Module 2 (Sales), Module 3 (Customers), Module 4 (Recommendations),
Module 5 (Simulator), and Module 6 (Campaigns & Approvals).
Strictly enforces human-in-the-loop lifecycle and deterministic financial boundaries.
"""

import uuid
from datetime import date, datetime, timezone, timedelta
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
from app.ai.cognee_client import get_cognee_client
from app.schemas.campaign import CampaignResponse, CampaignResultResponse
from app.schemas.what_if import SimulationScenario


# Simple in-memory bounded cache for short conversation continuity (max 200 sessions)
_CONVERSATION_CACHE: OrderedDict[str, Dict[str, Any]] = OrderedDict()
MAX_CACHE_SIZE = 200
MAX_HISTORY_MESSAGES = 10  # 5 user turns, 5 assistant turns
MAX_TOOL_CALLS_PER_REQUEST = 8


def get_conversation_context(conversation_id: Optional[str], merchant_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve short-term session context with merchant tenant isolation."""
    if not conversation_id:
        return {}
    cache_key = f"{merchant_id}:{conversation_id}" if merchant_id else conversation_id
    if cache_key not in _CONVERSATION_CACHE:
        if conversation_id in _CONVERSATION_CACHE:
            cache_key = conversation_id
        else:
            return {}
    _CONVERSATION_CACHE.move_to_end(cache_key)
    return dict(_CONVERSATION_CACHE[cache_key])


def update_conversation_context(
    conversation_id: Optional[str],
    context_update: Dict[str, Any],
    merchant_id: Optional[str] = None,
) -> None:
    """Update short-term session state with bounded message history and tenant isolation."""
    if not conversation_id:
        return
    cache_key = f"{merchant_id}:{conversation_id}" if merchant_id else conversation_id
    current = _CONVERSATION_CACHE.get(cache_key, {})

    # Merge message history if present
    if "messages" in context_update:
        existing_msgs = current.get("messages", [])
        new_msgs = context_update["messages"]
        merged = existing_msgs + new_msgs
        current["messages"] = merged[-MAX_HISTORY_MESSAGES:]
        other_updates = {k: v for k, v in context_update.items() if k != "messages"}
        current.update(other_updates)
    else:
        current.update(context_update)
        if "messages" in current:
            current["messages"] = current["messages"][-MAX_HISTORY_MESSAGES:]

    _CONVERSATION_CACHE[cache_key] = current
    _CONVERSATION_CACHE.move_to_end(cache_key)

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
        self.executed_tool_data: List[Dict[str, Any]] = []
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
        self.executed_tool_data.append(
            {
                "tool_name": tool_name,
                "arguments": {k: v for k, v in arguments.items() if k != "merchant_id"},
                "status": res.get("status", "error"),
                "result_summary": summary,
                "data": res.get("data")
            }
        )
        return res

    def _normalize_intent(
        self,
        message: str,
        intent: MerchantIntent,
        session_context: Optional[Dict[str, Any]] = None
    ) -> MerchantIntent:
        """
        Validate and normalize extracted intent.
        Prevents general_guidance or vague classification when merchant message
        contains specific analytical questions (sales, revenue, profit, churn, etc.).
        """
        # If intent is general_guidance, analyze_business, or empty, check deterministic rules
        if intent.intent in ("general_guidance", "analyze_business", "", None):
            from app.ai.llm_client import DeterministicFallbackClient
            fallback_intent = DeterministicFallbackClient().parse_intent(message, session_context)
            if fallback_intent.intent != "general_guidance":
                logger.info(
                    f"Intent normalized from '{intent.intent}' to '{fallback_intent.intent}' "
                    f"via deterministic normalization safety net."
                )
                return fallback_intent
        elif intent.intent in ("analyze_sales", "analyze_customers", "analyze_financials"):
            from app.ai.llm_client import DeterministicFallbackClient
            fallback_intent = DeterministicFallbackClient().parse_intent(message, session_context)
            if fallback_intent.intent == intent.intent and fallback_intent.parameters:
                if not intent.parameters:
                    intent.parameters = {}
                for k, v in fallback_intent.parameters.items():
                    if k not in intent.parameters or not intent.parameters[k]:
                        intent.parameters[k] = v
            if fallback_intent.target_segment and not intent.target_segment:
                intent.target_segment = fallback_intent.target_segment

        return intent

    def chat(self, request: AgentChatRequest) -> AgentChatResponse:
        """
        Main entry point for agent orchestration.
        Interprets natural language, invokes allowlisted tools,
        constructs campaign proposal, simulates impact, and stops at PENDING_APPROVAL.
        """
        self.actions_taken.clear()
        self.executed_tool_data.clear()
        self._tool_call_count = 0

        conv_id = request.conversation_id or f"conv-{uuid.uuid4().hex[:12]}"
        session_context = get_conversation_context(conv_id, merchant_id=self.merchant_id)
        if request.context:
            session_context.update(request.context)

        # 1. Intent interpretation
        try:
            intent = self.llm.parse_intent(request.message, session_context)
        except Exception as e:
            logger.warning(f"LLM parse_intent failed ({e}). Using deterministic fallback parser.")
            from app.ai.llm_client import DeterministicFallbackClient
            intent = DeterministicFallbackClient().parse_intent(request.message, session_context)

        # 1a. Intent normalization safety net
        intent = self._normalize_intent(request.message, intent, session_context)

        logger.info(f"Interpreted intent for merchant '{self.merchant_id}': {intent.intent} ({intent.requested_action})")

        # 1b. Recall relevant merchant memory from Cognee (best-effort, non-blocking)
        cognee_context_text = ""
        try:
            cognee = get_cognee_client()
            recall_results = cognee.recall(
                merchant_id=self.merchant_id,
                query=request.message,
            )
            cognee_context_text = cognee.extract_context_text(recall_results)
            if cognee_context_text:
                session_context["cognee_memory"] = cognee_context_text
                logger.info(
                    f"CogneeClient: Injected {len(recall_results)} memory item(s) "
                    f"into context for merchant '{self.merchant_id}'."
                )
        except Exception as _cog_err:  # noqa: BLE001
            logger.warning(f"Cognee recall failed (non-fatal): {_cog_err}")



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
            is_vip = (intent.target_segment == "VIP")
            cb_amount = float(intent.parameters.get("cashback_amount") or (75.0 if is_vip else 50.0))
            disc_pct = float(intent.parameters.get("discount_percent") or 0.0)
            min_amt = float(intent.parameters.get("minimum_transaction_amount") or (450.0 if is_vip else 200.0))
            offer_type = "fixed_cashback" if cb_amount > 0 else "percentage_discount"
            scenario_name = "VIP Weekend Basket Expansion" if is_vip else "Weekend Revenue Booster"
            camp_name = "VIP Weekend Basket Expansion Campaign" if is_vip else "Weekend Revenue Booster Campaign"
            camp_desc = (
                "Targeted weekend promotional offer for VIP customers to test basket size expansion (target ₹450+ orders)."
                if is_vip else
                "Targeted weekend promotional offer to drive higher basket sizes and recover weekend footfall."
            )

            sim_res = self._invoke_tool(
                "simulate_campaign",
                {
                    "offer_type": offer_type,
                    "cashback_amount": cb_amount if offer_type == "fixed_cashback" else None,
                    "discount_percent": disc_pct if offer_type == "percentage_discount" else None,
                    "target_segment": intent.target_segment or "All Customers",
                    "target_days": "weekend",
                    "minimum_transaction_amount": min_amt,
                    "scenario_name": scenario_name
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
                    "name": camp_name,
                    "description": camp_desc,
                    "target_segment": intent.target_segment or "All Customers",
                    "offer_type": offer_type,
                    "cashback_amount": cb_amount if offer_type == "fixed_cashback" else None,
                    "discount_percent": disc_pct if offer_type == "percentage_discount" else None,
                    "minimum_transaction_amount": min_amt,
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

        elif intent.intent == "analyze_sales":
            period = intent.parameters.get("period")
            start_date_str: Optional[str] = None
            end_date_str: Optional[str] = None
            period_days = int(intent.parameters.get("period_days") or 14)
            period_label = "recent period"

            msg_lower = request.message.lower()
            if period == "this_month" or "this month" in msg_lower or ("month" in msg_lower and "last" not in msg_lower and "prev" not in msg_lower):
                all_df = self.tools.sales_service.repo.get_transactions_df(merchant_id=self.merchant_id, status="success")
                if not all_df.empty:
                    ref_date = all_df["date"].max()
                else:
                    ref_date = datetime.now(timezone.utc).date()

                m_start = date(ref_date.year, ref_date.month, 1)
                m_end = ref_date
                start_date_str = m_start.isoformat()
                end_date_str = m_end.isoformat()
                period_days = max((m_end - m_start).days + 1, 1)
                period_label = f"this month ({m_start.strftime('%B %Y')})"
            elif period == "last_month" or "last month" in msg_lower or "previous month" in msg_lower or "prior month" in msg_lower:
                all_df = self.tools.sales_service.repo.get_transactions_df(merchant_id=self.merchant_id, status="success")
                if not all_df.empty:
                    ref_date = all_df["date"].max()
                else:
                    ref_date = datetime.now(timezone.utc).date()
                first_of_this_month = date(ref_date.year, ref_date.month, 1)
                last_day_of_last_month = first_of_this_month - timedelta(days=1)
                first_day_of_last_month = date(last_day_of_last_month.year, last_day_of_last_month.month, 1)
                start_date_str = first_day_of_last_month.isoformat()
                end_date_str = last_day_of_last_month.isoformat()
                period_days = (last_day_of_last_month - first_day_of_last_month).days + 1
                period_label = f"last month ({first_day_of_last_month.strftime('%B %Y')})"
            elif "today" in msg_lower:
                all_df = self.tools.sales_service.repo.get_transactions_df(merchant_id=self.merchant_id, status="success")
                ref_date = all_df["date"].max() if not all_df.empty else datetime.now(timezone.utc).date()
                start_date_str = ref_date.isoformat()
                end_date_str = ref_date.isoformat()
                period_days = 1
                period_label = "today"
            elif "evening" in msg_lower or "decline" in msg_lower or "falling" in msg_lower or (intent.parameters and intent.parameters.get("focus") == "decline"):
                period_days = 14
                period_label = "the last 14 days (Sales Decline Analysis)"
            else:
                period_days = 14
                period_label = "the last 14 days"

            sales_args: Dict[str, Any] = {"period_days": period_days}
            if start_date_str and end_date_str:
                sales_args["start_date"] = start_date_str
                sales_args["end_date"] = end_date_str

            sales_res = self._invoke_tool("analyze_sales", sales_args)
            if sales_res.get("status") == "success":
                data = sales_res.get("data", {})
                summary = data.get("summary", {})
                comp = data.get("comparison", {})
                rev = summary.get("total_revenue", 0.0)
                txns = summary.get("total_transactions", 0)
                atv = summary.get("average_transaction_value", 0.0)
                sr = summary.get("success_rate", 100.0)

                session_context["sales_summary"] = summary
                session_context["comparison"] = comp
                session_context["period_label"] = period_label

                insights.append(
                    f"For {period_label}, your store generated ₹{rev:,.2f} in total revenue "
                    f"across {txns:,} successful transactions with an average ticket size of ₹{atv:,.2f} "
                    f"({sr:.1f}% payment success rate)."
                )

                rev_chg = comp.get("revenue_change_pct")
                if rev_chg is not None:
                    direction = "up" if rev_chg >= 0 else "down"
                    insights.append(f"Revenue is {direction} {abs(rev_chg):0.2f}% compared to the prior equivalent period.")

                for ins in data.get("insights", []):
                    if isinstance(ins, dict) and ins.get("explanation"):
                        insights.append(ins.get("explanation"))

            # If sales decline inquiry, also fetch growth recommendations
            if (intent.parameters and intent.parameters.get("focus") == "decline") or "falling" in msg_lower or "decline" in msg_lower or "drop" in msg_lower:
                rec_res = self._invoke_tool("get_growth_recommendations", {"limit": 3})
                if rec_res.get("status") == "success":
                    recommendation_dict = rec_res["data"].get("top_recommendation")
                    session_context["growth_recommendations"] = rec_res["data"].get("recommendations", [])

        elif intent.intent == "analyze_customers":
            target_seg = intent.target_segment if intent.target_segment in ["VIP", "Loyal", "At-Risk", "Inactive"] else (
                "VIP" if (intent.parameters and intent.parameters.get("focus") == "best_customers") or any(w in request.message.lower() for w in ["vip", "best", "top"])
                else ("At-Risk" if "at-risk" in request.message.lower() or "at risk" in request.message.lower()
                else "Inactive")
            )
            cust_res = self._invoke_tool("analyze_customers", {})
            if cust_res.get("status") == "success":
                session_context["customer_summary"] = cust_res["data"].get("summary")
                insights.extend(cust_res["data"].get("insights", []))

            target_res = self._invoke_tool("get_target_customers", {"segment": target_seg, "limit": 10})
            if target_res.get("status") == "success":
                cnt = target_res["data"].get("total_count", 0)
                if target_seg in ["VIP", "Loyal"]:
                    insights.append(f"Identified {cnt} top-tier {target_seg} customers contributing significant store revenue.")
                else:
                    insights.append(f"Identified {cnt} {target_seg} customers available for reactivation.")

        elif intent.intent in ("get_growth_recommendations", "analyze_business"):
            sales_res = self._invoke_tool("analyze_sales", {"period_days": 14})
            cust_res = self._invoke_tool("analyze_customers", {})
            rec_res = self._invoke_tool("get_growth_recommendations", {"limit": 3})

            if sales_res.get("status") == "success":
                insights.extend([i.get("observation", "") for i in sales_res["data"].get("insights", []) if isinstance(i, dict)])
            if cust_res.get("status") == "success":
                insights.extend(cust_res["data"].get("insights", []))
            if rec_res.get("status") == "success":
                recs = rec_res["data"].get("recommendations", [])
                recommendation_dict = rec_res["data"].get("top_recommendation")
                session_context["growth_recommendations"] = recs
                for r in recs[:3]:
                    insights.append(f"{r.get('title')} [{r.get('priority', 'medium').upper()}]: {r.get('suggested_action')}")

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

        elif intent.intent == "analyze_cash_flow":
            cf_res = self._invoke_tool("analyze_cash_flow", {})
            if cf_res.get("status") == "success":
                data = cf_res.get("data", {})
                session_context["cash_flow"] = data
                inflow = data.get("total_cash_inflow", 0.0)
                outflow = data.get("total_cash_outflow", 0.0)
                net_cf = data.get("net_cash_flow", 0.0)
                insights.append(
                    f"Net Cash Flow is ₹{net_cf:,.2f} (Total Inflows: ₹{inflow:,.2f}, Total Outflows: ₹{outflow:,.2f})."
                )

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
            tool_results = self.executed_tool_data
            try:
                response_text = self.llm.generate_response(request.message, intent, tool_results, session_context)
            except Exception as e:
                logger.warning(f"LLM generate_response failed ({e}). Using deterministic fallback generator.")
                from app.ai.llm_client import DeterministicFallbackClient
                response_text = DeterministicFallbackClient().generate_response(request.message, intent, tool_results, session_context)


        # 4. Update short-term session continuity
        topic = "guidance"
        if intent.intent == "analyze_sales":
            topic = "decline" if (intent.parameters and intent.parameters.get("focus") == "decline") else "sales"
        elif intent.intent in ("get_growth_recommendations", "analyze_business"):
            topic = "growth_recommendations"
        elif intent.intent == "analyze_customers":
            topic = "customer_intelligence"
        elif intent.intent in ("increase_weekend_revenue", "recover_inactive_customers", "create_campaign"):
            topic = "campaign"
        elif intent.intent == "analyze_financials":
            topic = "financials"
        elif intent.intent == "analyze_cash_flow":
            topic = "cash_flow"

        user_entry = {"role": "user", "content": request.message}
        assistant_entry = {"role": "assistant", "content": response_text}

        context_update: Dict[str, Any] = {
            "messages": [user_entry, assistant_entry],
            "last_intent": intent.intent,
            "last_topic": topic,
            "target_segment": intent.target_segment,
        }
        if intent.parameters.get("focus"):
            context_update["last_focus"] = intent.parameters["focus"]
        if campaign_id:
            context_update["campaign_id"] = campaign_id
        if status_str:
            context_update["status"] = status_str
        if recommendation_dict:
            context_update["last_recommendation"] = recommendation_dict
        if session_context.get("sales_summary"):
            context_update["sales_summary"] = session_context["sales_summary"]
        if session_context.get("growth_recommendations"):
            context_update["growth_recommendations"] = session_context["growth_recommendations"]
        if session_context.get("comparison"):
            context_update["comparison"] = session_context["comparison"]

        update_conversation_context(conv_id, context_update, merchant_id=self.merchant_id)

        # 5. Persist useful business context to Cognee memory (best-effort, non-blocking)
        try:
            cognee = get_cognee_client()
            memory_parts: list = []

            if insights:
                memory_parts.append("Business Insights: " + " | ".join(insights[:3]))
            if intent.intent in (
                "increase_weekend_revenue",
                "recover_inactive_customers",
                "create_campaign",
                "analyze_business",
                "analyze_sales",
            ) and self.actions_taken:
                memory_parts.append(
                    f"Intent processed: {intent.intent} "
                    f"for segment '{intent.target_segment}'."
                )
            if campaign_id and status_str:
                memory_parts.append(
                    f"Campaign {campaign_id} created with status {status_str}."
                )
            if simulation_obj:
                memory_parts.append(
                    f"Simulation projected ROI: {simulation_obj.roi_multiplier_label}, "
                    f"net impact: INR {simulation_obj.net_incremental_impact:,.2f}."
                )

            if memory_parts:
                memory_text = " ".join(memory_parts)
                cognee.remember(merchant_id=self.merchant_id, content=memory_text)
        except Exception as _cog_err:  # noqa: BLE001
            logger.warning(f"Cognee remember failed (non-fatal): {_cog_err}")


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
            conversation_id=conv_id,
        )
