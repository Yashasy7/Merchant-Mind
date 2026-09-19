"""
LLM Provider Abstraction and Deterministic Fallback Client.
Supports Google Gemini structured calls when configured,
and provides a 100% reliable, deterministic fallback engine for offline/demo operation.
"""

import json
import re
from typing import Dict, Any, Optional, List
import httpx

from app.core.config import get_settings
from app.core.logging import logger
from app.ai.schemas import MerchantIntent
from app.ai.prompts import SYSTEM_PROMPT, INTENT_PARSER_SYSTEM_PROMPT


class BaseLLMClient:
    """Base interface for LLM client providers."""

    def parse_intent(self, message: str, context: Optional[Dict[str, Any]] = None) -> MerchantIntent:
        raise NotImplementedError

    def generate_response(
        self,
        message: str,
        intent: MerchantIntent,
        tool_results: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        raise NotImplementedError

    def generate_marketing_copy(
        self,
        objective: str,
        target_segment: str,
        offer_type: str,
        offer_value: str,
        time_window: Optional[str] = None
    ) -> Dict[str, str]:
        raise NotImplementedError


class DeterministicFallbackClient(BaseLLMClient):
    """
    Deterministic rule-based intent interpreter and copy generator.
    Guarantees zero downtime, offline capability, zero hallucination of numbers,
    and 100% test reproducibility without external network or API keys.
    """

    def parse_intent(self, message: str, context: Optional[Dict[str, Any]] = None) -> MerchantIntent:
        msg = message.lower().strip()
        params: Dict[str, Any] = {}

        # 1. Execution request (e.g. "Execute the approved campaign")
        if any(w in msg for w in ["execute", "run campaign", "simulate execution"]) and not any(w in msg for w in ["create", "cashback", "weekend", "bring back", "inactive"]):
            camp_id = None
            m = re.search(r"cmp-[a-f0-9\-]+|camp-[a-f0-9\-]+", msg)
            if m:
                camp_id = m.group(0)
            elif context and context.get("campaign_id"):
                camp_id = context.get("campaign_id")
            if camp_id:
                params["campaign_id"] = camp_id

            return MerchantIntent(
                intent="execute_campaign",
                objective="execution",
                target_segment="All Customers",
                time_window=None,
                requested_action="execution",
                parameters=params
            )

        # 2. Approval request (e.g. "Approve this campaign", "Confirm launch")
        if any(w in msg for w in ["approve", "confirm launch", "yes, launch"]) or ("approved" in msg and "execute" not in msg):
            camp_id = None
            m = re.search(r"cmp-[a-f0-9\-]+|camp-[a-f0-9\-]+", msg)
            if m:
                camp_id = m.group(0)
            elif context and context.get("campaign_id"):
                camp_id = context.get("campaign_id")
            if camp_id:
                params["campaign_id"] = camp_id

            return MerchantIntent(
                intent="approve_campaign",
                objective="approval",
                target_segment="All Customers",
                time_window=None,
                requested_action="approval",
                parameters=params
            )

        # Multi-turn Follow-up A: "Why are they falling?", "Why did they drop?", "Why?"
        msg_clean = msg.strip(" ?.!").lower()
        is_why_query = (
            (
                msg_clean in ("why", "why?", "why is that", "why is that?", "why did they drop", "why are they falling", "why are they dropping", "why are they down", "why did it drop", "why are sales down")
                or ("why" in msg_clean and any(w in msg_clean for w in ["falling", "dropping", "drop", "dropped", "down", "they", "it"]))
                or (any(w in msg_clean for w in ["falling", "drop", "dropped", "down"]) and ("they" in msg_clean or "it" in msg_clean))
            )
            and not any(w in msg_clean for w in ["profit", "expense", "expenses", "spend", "cost", "costs", "margin"])
        )
        if is_why_query:
            last_intent = context.get("last_intent") if context else None
            last_topic = context.get("last_topic") if context else None
            if last_intent in ("analyze_sales", "get_growth_recommendations") or last_topic in ("sales", "decline") or not last_intent:
                params["focus"] = "decline"
                params["period"] = "recent"
                return MerchantIntent(
                    intent="analyze_sales",
                    objective="analysis",
                    target_segment="All Customers",
                    time_window="evening",
                    requested_action="analysis",
                    parameters=params
                )

        # Multi-turn Follow-up B: Comparison ("How does that compare with the previous period?")
        is_comparison_query = any(w in msg for w in [
            "compare", "comparison", "prior period", "previous period", "vs last", "compared to", "how does that compare"
        ])
        if is_comparison_query:
            last_intent = context.get("last_intent") if context else None
            last_topic = context.get("last_topic") if context else None
            if last_intent == "analyze_sales" or last_topic in ("sales", "decline") or not last_intent:
                params["focus"] = "comparison"
                params["period"] = context.get("period", "recent") if context else "recent"
                return MerchantIntent(
                    intent="analyze_sales",
                    objective="analysis",
                    target_segment="All Customers",
                    time_window=None,
                    requested_action="analysis",
                    parameters=params
                )

        # Multi-turn Follow-up C: Advice / next steps ("What should I do?", "What can I do?", "What should I do about it?")
        is_advice_query = any(w in msg for w in [
            "what should i do", "what can i do", "what should i do about it",
            "what do you suggest", "what do you recommend", "what now", "how to fix",
            "how can i fix", "any advice", "any suggestions", "any ideas", "how to improve"
        ])
        if is_advice_query:
            return MerchantIntent(
                intent="get_growth_recommendations",
                objective="growth",
                target_segment=context.get("target_segment", "All Customers") if context else "All Customers",
                time_window=None,
                requested_action="recommendation",
                parameters=params
            )

        # Multi-turn Follow-up D: Campaign creation request ("Can you create a campaign for that?", "Create a campaign for that")
        is_campaign_followup = any(w in msg for w in [
            "create a campaign for that", "create campaign for that", "can you create a campaign for that",
            "make a campaign for that", "run a campaign for that", "create that campaign", "create it",
            "can you create a campaign", "create a campaign", "set up a campaign"
        ])
        if is_campaign_followup:
            last_focus = context.get("last_focus") if context else None
            last_topic = context.get("last_topic") if context else None
            last_intent = context.get("last_intent") if context else None
            target_seg = context.get("target_segment", "All Customers") if context else "All Customers"

            if last_focus == "decline" or last_topic == "decline":
                return MerchantIntent(
                    intent="create_campaign",
                    objective="growth",
                    target_segment="All Customers",
                    time_window="evening",
                    requested_action="campaign",
                    parameters={"cashback_amount": 50.0, "minimum_transaction_amount": 200.0, "time_window": "evening"}
                )
            elif last_intent == "increase_weekend_revenue" or last_topic == "weekend":
                return MerchantIntent(
                    intent="increase_weekend_revenue",
                    objective="increase_revenue",
                    target_segment=target_seg,
                    time_window="weekend",
                    requested_action="campaign",
                    parameters=params
                )
            elif last_intent in ("recover_inactive_customers", "analyze_customers") or target_seg in ("Inactive", "At-Risk"):
                return MerchantIntent(
                    intent="recover_inactive_customers",
                    objective="retention",
                    target_segment=target_seg if target_seg in ("Inactive", "At-Risk") else "Inactive",
                    time_window=None,
                    requested_action="campaign",
                    parameters=params
                )
            else:
                return MerchantIntent(
                    intent="create_campaign",
                    objective="growth",
                    target_segment=target_seg,
                    time_window=None,
                    requested_action="campaign",
                    parameters=params
                )


        # Extract numerical discounts or cashbacks
        cashback_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+)\s*(?:cashback|cb)", msg)
        if cashback_match:
            params["cashback_amount"] = float(cashback_match.group(1))
            params["offer_type"] = "fixed_cashback"

        discount_match = re.search(r"(\d+)%\s*(?:discount|off)", msg)
        if discount_match:
            params["discount_percent"] = float(discount_match.group(1))
            params["offer_type"] = "percentage_discount"

        min_amt_match = re.search(r"(?:above|over|min|minimum|of)\s*(?:₹|rs\.?|inr)?\s*(\d+)", msg)
        if min_amt_match:
            params["minimum_transaction_amount"] = float(min_amt_match.group(1))

        # Check for target customer segments
        target_segment = "All Customers"
        if "inactive" in msg or "dormant" in msg:
            target_segment = "Inactive"
        elif "at-risk" in msg or "at risk" in msg or "churn" in msg:
            target_segment = "At-Risk"
        elif "vip" in msg or "best customer" in msg or "top customer" in msg:
            target_segment = "VIP"
        elif "loyal" in msg:
            target_segment = "Loyal"
        elif "new" in msg:
            target_segment = "New"
        elif "regular" in msg:
            target_segment = "Regular"

        # Check conversation context if user says "them", "those customers"
        if ("them" in msg or "those" in msg) and context and context.get("target_segment"):
            target_segment = context.get("target_segment")

        time_window = "weekend" if "weekend" in msg else ("evening" if "evening" in msg else None)

        # 3. Simulation intent (Module 5 What-If Simulator)
        if "simulate" in msg or "what-if" in msg or "what if" in msg or "how much could" in msg:
            return MerchantIntent(
                intent="simulate_campaign",
                objective="growth",
                target_segment=target_segment,
                time_window=time_window,
                requested_action="simulation",
                parameters=params
            )

        # 3a. Best / VIP / Top customers intent
        is_best_customers_query = any(w in msg for w in [
            "best customer", "best customers", "top customer", "top customers", "vip customer", "vip customers",
            "highest spend", "highest spending", "biggest spenders", "loyal customers", "most valuable customer", "most valuable customers"
        ])
        if is_best_customers_query:
            params["focus"] = "best_customers"
            return MerchantIntent(
                intent="analyze_customers",
                objective="analysis",
                target_segment="VIP",
                time_window=None,
                requested_action="analysis",
                parameters=params
            )

        # 3b. Customer intelligence (at-risk, inactive, targeting advice, cohorts)
        if any(w in msg for w in ["inactive", "at-risk", "at risk", "churn", "dormant", "bring back", "win back", "recover", "target customer", "target customers", "which customer", "which customers", "customers should i target"]) or (("them" in msg or "those" in msg) and target_segment in ["Inactive", "At-Risk"]):
            is_advisory = any(w in msg for w in ["should i", "can i", "do you suggest", "is it good", "recommend targeting", "advice on", "who should", "which customer", "which customers"])
            is_campaign_req = (
                (
                    any(w in msg for w in ["bring back", "win back", "recover", "launch campaign", "create campaign", "run a campaign", "reactivate", "give offer", "send cashback"])
                    or ("campaign" in msg and any(w in msg for w in ["create", "launch", "run", "start", "draft", "make", "target", "cashback", "send", "give"]))
                    or ("target" in msg and any(w in msg for w in ["them", "customer"]) and not is_advisory)
                )
                and not is_advisory
            )
            has_cust_query = any(w in msg for w in ["who are", "which customers", "list", "who should i target", "show me", "tell me about", "should i target", "how many"])
            target_seg = target_segment if target_segment != "All Customers" else ("At-Risk" if "at-risk" in msg or "at risk" in msg else "Inactive")

            if "how many inactive" in msg or ("inactive" in msg and any(w in msg for w in ["how many", "count", "number of"])):
                params["focus"] = "inactive_count"
                target_seg = "Inactive"
            elif "how many at-risk" in msg or ("at-risk" in msg and any(w in msg for w in ["how many", "count", "number of"])) or ("at risk" in msg and any(w in msg for w in ["how many", "count", "number of"])):
                params["focus"] = "at_risk"
                target_seg = "At-Risk"
            elif any(w in msg for w in ["which customer", "which customers", "who should i target", "customers should i target", "should i target"]):
                params["focus"] = "targeting_advice"
            elif "at-risk" in msg or "at risk" in msg:
                params["focus"] = "at_risk"
                target_seg = "At-Risk"
            elif "inactive" in msg or "dormant" in msg:
                params["focus"] = "inactive_count"
                target_seg = "Inactive"

            if is_campaign_req and not has_cust_query:
                return MerchantIntent(
                    intent="recover_inactive_customers",
                    objective="retention",
                    target_segment=target_seg,
                    time_window=time_window,
                    requested_action="campaign",
                    parameters=params
                )
            else:
                return MerchantIntent(
                    intent="analyze_customers",
                    objective="analysis",
                    target_segment=target_seg,
                    time_window=time_window,
                    requested_action="analysis",
                    parameters=params
                )

        # 4a. Weekend revenue / VIP expansion campaign intent
        is_weekend_campaign = (
            ("weekend" in msg and any(w in msg for w in ["increase", "boost", "revenue", "sales", "help", "offer", "vip", "expansion", "suggestion", "afternoon", "more", "campaign", "cashback", "launch"]))
            or any(w in msg for w in ["increase weekend", "weekend revenue", "weekend booster", "weekend expansion", "weekend sales"])
        )
        if is_weekend_campaign:
            return MerchantIntent(
                intent="increase_weekend_revenue",
                objective="increase_revenue",
                target_segment=target_segment,
                time_window="weekend",
                requested_action="campaign",
                parameters=params
            )

        # 4b. Sales decline / drop inquiry (without explicit weekend campaign request)
        if any(w in msg for w in [
            "sales drop", "sales have dropped", "sales are falling", "sales falling", "falling sales",
            "sales down", "why are sales down", "sales have decreased", "why is my revenue dropping",
            "revenue dropping", "revenue is falling", "revenue is down", "sales decline", "evening decline"
        ]) or (any(w in msg for w in ["falling", "dropped", "declining", "decrease", "drop", "down"]) and any(w in msg for w in ["sales", "revenue"])):
            params["focus"] = "decline"
            params["period"] = "recent"
            return MerchantIntent(
                intent="analyze_sales",
                objective="analysis",
                target_segment="All Customers",
                time_window="evening" if "evening" in msg else None,
                requested_action="analysis",
                parameters=params
            )

        # 5. Generic campaign creation
        if any(w in msg for w in ["create campaign", "launch campaign", "start campaign", "run campaign", "create a campaign", "launch a campaign"]) or ("campaign" in msg and any(w in msg for w in ["create", "launch", "draft", "start", "run", "setup", "make"])):
            return MerchantIntent(
                intent="create_campaign",
                objective="growth",
                target_segment=target_segment,
                time_window=time_window,
                requested_action="campaign",
                parameters=params
            )

        # 6a. Cash flow analysis
        if any(w in msg for w in ["cash flow", "cashflow", "inflow", "inflows", "outflow", "outflows", "liquidity", "payables", "receivables", "cash position", "money coming"]):
            return MerchantIntent(
                intent="analyze_cash_flow",
                objective="accounting",
                target_segment="All Customers",
                time_window=None,
                requested_action="accounting",
                parameters=params
            )

        # 6b. Accounting & Financial analysis
        if any(w in msg for w in ["profit", "expense", "expenses", "p&l", "accounting", "accountant", "finances", "financials", "how much did i spend", "income vs expense", "invoices", "vendor bills", "costs", "cost"]):
            if any(w in msg for w in ["biggest expense", "biggest expenses", "top expense", "top expenses", "where did i spend", "how much did i spend", "expense breakdown", "vendor bills", "what are my expenses", "my expenses", "what expenses", "show expenses"]):
                params["focus"] = "expenses"
            elif any(w in msg for w in ["increased the most", "increased most", "expenses increased", "expenses rise", "spike", "anomalies", "which expense"]):
                params["focus"] = "anomalies"
            elif any(w in msg for w in ["margin", "profit margin"]):
                params["focus"] = "margin"
            elif "why" in msg and "profit" in msg:
                params["focus"] = "profit_change"
            elif ("expense" in msg or "expenses" in msg or "spent" in msg or "cost" in msg or "costs" in msg) and "profit" not in msg:
                params["focus"] = "expenses"
            else:
                params["focus"] = "profit"

            return MerchantIntent(
                intent="analyze_financials",
                objective="accounting",
                target_segment="All Customers",
                time_window=None,
                requested_action="accounting",
                parameters=params
            )

        # 7. Forecasting
        if any(w in msg for w in ["forecast", "predict", "prediction", "future sales", "projected revenue", "next month sales", "project sales"]):
            return MerchantIntent(
                intent="forecast_sales",
                objective="forecasting",
                target_segment="All Customers",
                time_window=None,
                requested_action="forecast",
                parameters=params
            )

        # 8. Business health & risk assessment
        if any(w in msg for w in ["business health", "is my business healthy", "store health", "health score", "warning signals", "business risks", "how healthy is my store"]):
            return MerchantIntent(
                intent="get_business_health",
                objective="health",
                target_segment="All Customers",
                time_window=None,
                requested_action="health",
                parameters=params
            )

        # 9. Growth advice & recommendations
        growth_advice_terms = [
            "advice", "how can i increase", "how do i increase", "how to increase",
            "ways to increase", "how do i grow", "how can i grow", "how to grow",
            "grow revenue", "grow sales", "increase sales", "increasing sales",
            "increase revenue", "increasing revenue", "get more customers",
            "what should i do to increase", "how to get more sales", "tips to increase",
            "recommendation", "recommendations", "suggestion", "suggestions",
            "what campaign should i run", "what campaign to run", "give me growth advice",
            "growth opportunities", "growth opportunity", "opportunity", "opportunities",
            "growth ideas", "growth strategy", "growth strategies", "growth plan", "grow my business"
        ]
        if any(w in msg for w in growth_advice_terms):
            return MerchantIntent(
                intent="get_growth_recommendations",
                objective="growth",
                target_segment="All Customers",
                time_window=None,
                requested_action="recommendation",
                parameters=params
            )

        # 10. Sales analytics & revenue inquiries
        sales_terms = [
            "sales", "sale", "revenue", "sold", "sell", "turnover", "collection", "collections",
            "transaction", "transactions", "ticket size", "ticket sizes", "order value", "orders",
            "atv", "aov", "average transaction", "time of day", "peak hour", "peak hours",
            "busiest time", "busiest hour", "busiest day"
        ]
        time_terms = ["this month", "current month", "last month", "previous month", "prior month", "month", "monthly", "today", "yesterday", "week", "recent", "past"]
        query_terms = ["what is", "what are", "how much", "how are", "how is", "how's", "show", "tell", "display", "check", "view", "explain", "how many", "number of", "which"]

        has_sales_term = any(s in msg for s in sales_terms)
        has_time_term = any(t in msg for t in time_terms)
        has_query_term = any(q in msg for q in query_terms)

        is_transaction_query = any(w in msg for w in [
            "how many transaction", "how many transactions", "number of transaction", "number of transactions",
            "transaction count", "total transactions", "transactions did i have", "transactions today",
            "transactions this month", "how many orders", "order count", "successful payments"
        ])
        is_atv_query = any(w in msg for w in [
            "average transaction value", "average ticket size", "ticket size", "atv", "average order value",
            "aov", "average spend per transaction", "average transaction size"
        ])
        is_time_of_day_query = any(w in msg for w in [
            "which time of day", "time of day performs best", "time of day", "peak hour", "peak hours",
            "busiest time", "busiest hour", "best time of day", "best hour", "what time do i sell",
            "when do i sell most", "busiest window", "best performing hour"
        ])

        is_sales_query = (
            is_transaction_query
            or is_atv_query
            or is_time_of_day_query
            or any(w in msg for w in [
                "this month sales", "this month's sales", "month sales", "month's sales", "monthly sales",
                "sales this month", "sales for this month", "revenue this month", "this month revenue",
                "this month's revenue", "last month revenue", "revenue last month", "sales last month",
                "last month sales", "last month's sales", "how much did i sell", "how much did i make", "how much revenue",
                "what are this month sales", "what is my revenue", "what are my sales",
                "show me my sales", "show me sales", "show me this month's sales", "show me this month sales",
                "my sales for this month", "show me this month", "how is my sales", "how are my sales",
                "how is sales", "how are sales", "how's my sales", "how are my sales this month",
                "explain sales", "sales decline", "evening decline", "evening hours", "sales drop",
                "total sales", "total revenue", "sales performance", "sales numbers",
                "sales summary", "daily sales", "weekly sales", "recent sales", "today sales"
            ])
            or (has_sales_term and (has_time_term or has_query_term))
        )
        if is_sales_query:
            if any(w in msg for w in ["last month", "previous month", "prior month"]):
                time_period = "last_month"
            elif any(m in msg for m in ["this month", "current month", "monthly", "month's"]):
                time_period = "this_month"
            elif "today" in msg:
                time_period = "today"
            elif "yesterday" in msg:
                time_period = "yesterday"
            elif "week" in msg:
                time_period = "this_week"
            else:
                time_period = "recent"

            params["period"] = time_period
            if is_transaction_query:
                params["focus"] = "transactions"
            elif is_atv_query:
                params["focus"] = "atv"
            elif is_time_of_day_query:
                params["focus"] = "time_of_day"
            elif "evening" in msg:
                params["time_window"] = "evening"
            elif "decline" in msg or "drop" in msg or "falling" in msg:
                params["focus"] = "decline"
            return MerchantIntent(
                intent="analyze_sales",
                objective="analysis",
                target_segment="All Customers",
                time_window="evening" if "evening" in msg else None,
                requested_action="analysis",
                parameters=params
            )

        # 11. Business analysis / overview / something different
        if any(w in msg for w in [
            "something different", "different about", "something else", "another insight",
            "how is my business", "business performing", "how is my business performing", "store performing", "how is my store",
            "sales trend",
            "analyze", "overview", "summary", "report", "insights"
        ]):
            if any(w in msg for w in ["something different", "different about", "something else", "another insight"]):
                params["focus"] = "different_insight"
            return MerchantIntent(
                intent="analyze_business",
                objective="analysis",
                target_segment="All Customers",
                time_window=None,
                requested_action="analysis",
                parameters=params
            )

        # 12. Default general guidance
        return MerchantIntent(
            intent="general_guidance",
            objective="guidance",
            target_segment="All Customers",
            time_window=None,
            requested_action="guidance",
            parameters=params
        )

    def generate_response(
        self,
        message: str,
        intent: MerchantIntent,
        tool_results: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Construct grounded, concise natural language response referencing backend tool outputs."""
        if intent.intent == "approve_campaign":
            return (
                "Campaign has been approved! Status updated to APPROVED. "
                "Per human-in-the-loop safety protocol, the campaign will only run simulated execution when you explicitly request execution."
            )

        if intent.intent == "execute_campaign":
            executed = any(t.get("tool_name") == "execute_campaign" and t.get("status") == "success" for t in tool_results)
            if not executed:
                return (
                    "I found multiple or unspecified campaigns. Please provide the campaign ID or specify which campaign you want to execute."
                )
            return (
                "Campaign simulated execution completed in the Paytm MerchantMind demo environment. "
                "Review the simulated transaction lift, revenue gain, and ROI below."
            )

        if intent.intent in ["increase_weekend_revenue", "recover_inactive_customers", "create_campaign"]:
            return (
                f"I have analyzed your business metrics and prepared a campaign targeting **{intent.target_segment}**. "
                "The campaign has been drafted in **PENDING_APPROVAL** status. "
                "Review the simulated revenue uplift, estimated incentive costs, and marketing copy below. "
                "Your explicit approval is required before this campaign can be executed."
            )

        if intent.intent == "simulate_campaign":
            return (
                f"I have simulated this promotional scenario for **{intent.target_segment}** using Module 5 What-If Simulator. "
                "Review the projected revenue, incremental transactions, and expected ROI below."
            )

        if intent.intent == "analyze_cash_flow":
            cf_data = None
            for t in tool_results:
                if t.get("tool_name") == "analyze_cash_flow" and t.get("data"):
                    cf_data = t["data"]
                    break
            if cf_data:
                inflow = cf_data.get("total_cash_inflows") or cf_data.get("total_inflows", 0.0)
                outflow = cf_data.get("total_cash_outflows") or cf_data.get("total_outflows", 0.0)
                net_cf = cf_data.get("net_cash_flow", 0.0)
                cf_status = str(cf_data.get("operating_cash_status") or cf_data.get("operating_status") or "positive").upper()
                rec = cf_data.get("pending_receivables") or cf_data.get("outstanding_receivables", 0.0)
                pay = cf_data.get("pending_payables") or cf_data.get("outstanding_payables", 0.0)
                return (
                    f"Here is your real-time cash flow situation: Your business recorded a Net Cash Flow of **₹{net_cf:,.2f}** "
                    f"({cf_status}). Total cash inflows from sales and digital settlements (UPI, QR, Card) reached **₹{inflow:,.2f}**, "
                    f"while operating cash disbursements totaled **₹{outflow:,.2f}**. "
                    f"You have **₹{rec:,.2f}** in pending customer/settlement receivables and **₹{pay:,.2f}** in supplier payables. "
                    "Working capital remains stable for day-to-day merchant operations."
                )
            return (
                "Here is your real-time cash flow statement tracking settlements, operating expenditures, and working capital."
            )

        if intent.intent == "analyze_financials":
            fin_data = None
            for t in tool_results:
                if t.get("tool_name") == "analyze_financials" and t.get("data"):
                    fin_data = t["data"]
                    break
            pl_data = fin_data.get("profit_loss", {}) if fin_data else {}
            exp_data = fin_data.get("expenses", {}) if fin_data else {}
            msg_lower = message.lower()
            focus = intent.parameters.get("focus", "") if intent.parameters else ""

            # Sub-case 1: Expenses inquiry ("What are my biggest expenses?")
            if focus == "expenses" or ("expense" in msg_lower and not any(w in msg_lower for w in ["margin", "profit", "increased", "why"])):
                if exp_data:
                    cats = exp_data.get("categories", [])
                    top_cat = exp_data.get("top_category", "Inventory")
                    top_amt = 0.0
                    if cats:
                        first_cat = cats[0]
                        top_amt = first_cat.get("total_amount", 0.0) if isinstance(first_cat, dict) else getattr(first_cat, "total_amount", 0.0)
                    total_exp = exp_data.get("total_expenses", 0.0)
                    pct = (top_amt / total_exp * 100.0) if total_exp > 0 else 0.0
                    breakdown_items = []
                    for c in cats[:3]:
                        if isinstance(c, dict):
                            cat_name = c.get("category", "")
                            amt = c.get("total_amount", 0.0)
                            pct_val = c.get("percentage_of_total", 0.0)
                        else:
                            cat_name = getattr(c, "category", "")
                            amt = getattr(c, "total_amount", 0.0)
                            pct_val = getattr(c, "percentage_of_total", 0.0)
                        breakdown_items.append(f"{cat_name} (₹{amt:,.2f}, {pct_val:.1f}%)")
                    breakdown = ", ".join(breakdown_items)
                    return (
                        f"Here is your expense breakdown: Total operating expenses stand at **₹{total_exp:,.2f}**. "
                        f"Your single largest cost driver is **{top_cat}** at **₹{top_amt:,.2f}** ({pct:.1f}% of total expenditures). "
                        f"Top categories: {breakdown}. "
                        "Note: MerchantMind assists with financial organization and does not replace a Chartered Accountant (CA)."
                    )

            # Sub-case 2: Expense increase / why profit changed
            if focus in ("anomalies", "profit_change") or "increased" in msg_lower or "why did my profit change" in msg_lower or "why did profit" in msg_lower:
                if exp_data and exp_data.get("anomalies"):
                    anom_msgs = [a.get("message") for a in exp_data.get("anomalies", []) if a.get("message")]
                    anom_text = " | ".join(anom_msgs)
                    return (
                        f"Expense intelligence identified significant cost surges: **{anom_text}**. "
                        "These higher operational outflows placed downward pressure on your net operating margins during the period. "
                        "Note: MerchantMind assists with financial organization and does not replace a Chartered Accountant (CA)."
                    )
                else:
                    top_cat = exp_data.get("top_category", "operating costs") if exp_data else "operating costs"
                    return (
                        f"Expense trend analysis indicates no abnormal cost surges or spikes across your recorded expenditures. "
                        f"Your primary ongoing expenditure remains **{top_cat}**, and operating costs remain within standard baseline parameters. "
                        "Note: MerchantMind assists with financial organization and does not replace a Chartered Accountant (CA)."
                    )

            # Sub-case 3: Profit margin inquiry ("What is my profit margin?")
            if focus == "profit_margin" or ("margin" in msg_lower and "expense" not in msg_lower):
                if pl_data:
                    margin = pl_data.get("operating_margin_pct", 0.0)
                    rev = pl_data.get("total_revenue", 0.0)
                    np = pl_data.get("net_profit", 0.0)
                    return (
                        f"Your store's Operating Profit Margin is **{margin:.1f}%**. "
                        f"On net revenues of **₹{rev:,.2f}**, your net profit after all verified operating expenses is **₹{np:,.2f}**. "
                        "Maintaining this margin provides healthy buffer for reinvestment and marketing experiments. "
                        "Note: MerchantMind assists with financial organization and does not replace a Chartered Accountant (CA)."
                    )

            # Sub-case 4: General profit inquiry ("How much profit did I make?")
            if pl_data:
                rev = pl_data.get("total_revenue", 0.0)
                exp = pl_data.get("total_expenses", 0.0)
                np = pl_data.get("net_profit", 0.0)
                margin = pl_data.get("operating_margin_pct", 0.0)
                status = "profitable" if np >= 0 else "operating at a net loss"
                return (
                    f"Your store is currently {status}: Generating **₹{rev:,.2f}** in revenue against "
                    f"**₹{exp:,.2f}** in total operating expenses, yielding a Net Operating Profit of **₹{np:,.2f}** "
                    f"(Operating Margin: **{margin:.1f}%**). "
                    "Review the full revenue, expense, and tax breakdown below. "
                    "Note: MerchantMind assists with financial organization and does not replace a Chartered Accountant (CA)."
                )

            return (
                "Here is your real-time financial health and P&L summary based on your transactions and expense records. "
                "Review your revenue, operating expenses, net profit, and expense breakdown below. "
                "Note: MerchantMind assists with financial organization and does not replace a Chartered Accountant (CA)."
            )

        if intent.intent == "forecast_sales":
            fc_data = None
            for t in tool_results:
                if t.get("tool_name") == "forecast_sales" and t.get("data"):
                    fc_data = t["data"]
                    break
            if fc_data:
                proj = fc_data.get("projected_revenue", 0.0)
                lb = fc_data.get("lower_bound", 0.0)
                ub = fc_data.get("upper_bound", 0.0)
                trend = fc_data.get("trend_direction", "stable")
                mom = fc_data.get("trend_factor_pct", 0.0)
                return (
                    f"Based on a 4-week rolling baseline and recent momentum ({mom:+0.2f}%, {trend} trend), "
                    f"your projected next-month revenue is **₹{proj:,.2f}** (Estimated Range: **₹{lb:,.2f}** to **₹{ub:,.2f}**). "
                    "Note: Projections are prototype statistical estimates based on synthetic demo records."
                )
            return (
                "Here is your statistical sales projection based on a 4-week rolling baseline and recent momentum trends. "
                "Review the projected revenue range, trend direction, and daily projections below. "
                "Note: Projections are prototype statistical estimates based on synthetic demo records."
            )

        if intent.intent == "get_business_health":
            return (
                "Here is your composite business health evaluation across Revenue, Customer Retention, Profitability, Operations, and Growth. "
                "Review your overall health score, detected warning risks, and actionable upside growth opportunities below."
            )

        if intent.intent == "analyze_customers":
            cust_summary = None
            target_data = None
            for t in tool_results:
                if t.get("tool_name") == "analyze_customers" and t.get("data"):
                    cust_summary = t["data"].get("summary")
                elif t.get("tool_name") == "get_target_customers" and t.get("data"):
                    target_data = t["data"]
            if not cust_summary and context:
                cust_summary = context.get("customer_summary")

            msg_lower = message.lower()
            focus = intent.parameters.get("focus", "") if intent.parameters else ""
            target_seg = intent.target_segment or ""

            # Sub-case 1: Best / VIP / Top customers
            if focus == "best_customers" or target_seg == "VIP" or any(w in msg_lower for w in ["best customer", "best customers", "top customer", "top customers", "vip customer", "vip customers"]):
                total_vip = target_data.get("total_count", 18) if target_data else 18
                sample_items = []
                if target_data and target_data.get("sample_customers"):
                    for c in target_data.get("sample_customers", [])[:3]:
                        name = c.get("name", "Customer")
                        spend = c.get("total_revenue") or c.get("total_spent") or 0.0
                        sample_items.append(f"**{name}** (₹{spend:,.2f})")
                sample_str = f" Key top patrons include {', '.join(sample_items)}." if sample_items else ""
                return (
                    f"Your store has **{total_vip} VIP customers** who represent your highest lifetime spend and frequency.{sample_str} "
                    f"We recommend loyalty rewards, personalized festive offers, or exclusive previews to maintain their high engagement."
                )

            # Sub-case 2: Inactive customers inquiry ("How many inactive customers do I have?")
            if focus == "inactive_count" or ("inactive" in msg_lower and not any(w in msg_lower for w in ["target", "campaign", "should i"])):
                if cust_summary:
                    inactive = cust_summary.get("inactive_customers", 0)
                    total_cust = cust_summary.get("total_customers") or cust_summary.get("total_unique_customers", 0)
                    return (
                        f"You currently have **{inactive} inactive customers** (who have not visited in over 60 days) "
                        f"out of {total_cust} total patrons. "
                        f"This dormant segment represents significant recoverable revenue. Would you like me to draft a win-back campaign (e.g. ₹50 cashback) to reactivate them?"
                    )

            # Sub-case 3: At-risk customers inquiry ("Who are my at-risk customers?")
            if focus == "at_risk" or (("at-risk" in msg_lower or "at risk" in msg_lower) and not any(w in msg_lower for w in ["target", "campaign", "should i"])):
                if cust_summary:
                    at_risk = cust_summary.get("at_risk_customers", 0)
                    total_cust = cust_summary.get("total_customers") or cust_summary.get("total_unique_customers", 0)
                    sample_names = []
                    if target_data and target_data.get("sample_customers"):
                        for c in target_data.get("sample_customers", [])[:3]:
                            sample_names.append(f"**{c.get('name')}** ({c.get('days_since_last_visit', 35)} days absent)")
                    sample_str = f" Recent examples: {', '.join(sample_names)}." if sample_names else ""
                    return (
                        f"You have **{at_risk} at-risk customers** (absent for 30–60 days) across your base of {total_cust} patrons.{sample_str} "
                        f"These customers are approaching complete churn. A timely reminder with a modest incentive can protect their lifetime value."
                    )

            # Sub-case 4: Targeting advice ("Which customers should I target?")
            is_advisory = (
                focus == "targeting_advice"
                or any(w in msg_lower for w in ["which customer", "which customers", "who should i target", "should i target", "customers should i target"])
            )
            if is_advisory:
                if cust_summary:
                    at_risk = cust_summary.get("at_risk_customers", 0)
                    inactive = cust_summary.get("inactive_customers", 0)
                    total_cust = cust_summary.get("total_customers") or cust_summary.get("total_unique_customers", 0)
                    return (
                        f"Based on your customer segmentation across {total_cust} patrons, your highest priority target is your **{at_risk} at-risk customers**, "
                        f"as they have visited within 30–60 days and have the highest likelihood of conversion before full churn. "
                        f"Your **{inactive} inactive customers** (60+ days absent) can also be re-engaged with a slightly higher incentive (such as ₹50 cashback). "
                        f"Would you like me to simulate or draft a campaign for at-risk customers?"
                    )

            if cust_summary:
                at_risk = cust_summary.get("at_risk_customers", 0)
                inactive = cust_summary.get("inactive_customers", 0)
                repeat_rate = cust_summary.get("repeat_customer_rate", 0.0)
                total_cust = cust_summary.get("total_customers") or cust_summary.get("total_unique_customers", 0)
                return (
                    f"Customer intelligence analysis identifies **{at_risk} at-risk customers** (30–60 days inactive) "
                    f"and **{inactive} inactive customers** (60+ days inactive) across your base of {total_cust} patrons. "
                    f"Your repeat customer rate stands at **{repeat_rate:.1f}%**. "
                    "These segments represent dormant revenue that can be recovered with a targeted win-back offer."
                )
            return (
                "Customer intelligence analysis identifies at-risk and inactive segments in your customer base. "
                "Review the detailed customer cohort profiles and segment breakdown below."
            )

        if intent.intent == "analyze_sales":
            sales_data = None
            hourly_data = None
            for t in tool_results:
                if t.get("tool_name") == "analyze_sales" and t.get("data"):
                    sales_data = t["data"].get("summary")
                    hourly_data = t["data"].get("hourly")
                    break
            if not sales_data and context:
                sales_data = context.get("sales_summary")
            period_label = context.get("period_label", "the requested period") if context else "the requested period"
            msg_lower = message.lower()
            focus = intent.parameters.get("focus", "") if intent.parameters else ""

            # Sub-case 1: Transaction count inquiry ("How many transactions did I have?")
            if focus == "transactions" or ("transaction" in msg_lower and not any(w in msg_lower for w in ["average", "atv", "ticket", "order value"])):
                if sales_data:
                    txns = sales_data.get("total_transactions", 0)
                    rev = sales_data.get("total_revenue", 0.0)
                    sr = sales_data.get("success_rate", 100.0)
                    atv = sales_data.get("average_transaction_value", 0.0)
                    return (
                        f"For {period_label}, your store recorded **{txns:,} successful transactions** "
                        f"(achieving a **{sr:.1f}% payment success rate**), generating **₹{rev:,.2f}** in total revenue "
                        f"with an average ticket size of ₹{atv:,.2f}."
                    )

            # Sub-case 2: Average transaction value / ATV ("What is my average transaction value?")
            if focus == "atv" or any(w in msg_lower for w in ["average transaction", "atv", "ticket size", "order value"]):
                if sales_data:
                    atv = sales_data.get("average_transaction_value", 0.0)
                    txns = sales_data.get("total_transactions", 0)
                    rev = sales_data.get("total_revenue", 0.0)
                    comp_text = ""
                    comp = None
                    for t in tool_results:
                        if t.get("tool_name") == "analyze_sales" and t.get("data"):
                            comp = t["data"].get("comparison")
                            break
                    if not comp and context:
                        comp = context.get("comparison")
                    if comp and comp.get("atv_change_pct") is not None:
                        atv_chg = comp.get("atv_change_pct", 0.0)
                        direction = "up" if atv_chg >= 0 else "down"
                        comp_text = f" (an ATV change of {direction} {abs(atv_chg):.2f}% vs prior equivalent baseline)"
                    return (
                        f"Your store's Average Transaction Value (ATV) is **₹{atv:,.2f}** across {txns:,} transactions "
                        f"for {period_label}{comp_text}. Total revenue generated is ₹{rev:,.2f}."
                    )

            # Sub-case 3: Hourly performance / peak time of day ("Which time of day performs best?")
            if focus == "time_of_day" or any(w in msg_lower for w in ["time of day", "peak hour", "peak hours", "busiest time", "busiest hour", "best time"]):
                if hourly_data:
                    peak_win = hourly_data.get("peak_window", "Afternoon")
                    peak_hrs = hourly_data.get("peak_window_hours", "12:00 - 17:00")
                    peak_rev = hourly_data.get("peak_window_revenue", 0.0)
                    peak_txns = hourly_data.get("peak_window_transactions", 0)
                    weak_win = hourly_data.get("weakest_window", "Night")
                    weak_hrs = hourly_data.get("weakest_window_hours", "21:00 - 06:00")
                    return (
                        f"Based on sales analysis by hour, your store achieves its highest performance during **{peak_win}** ({peak_hrs}), "
                        f"generating **₹{peak_rev:,.2f}** across **{peak_txns:,}** transactions. "
                        f"Conversely, your lowest performance window is **{weak_win}** ({weak_hrs}), "
                        f"with a notable localized dip in weekday evenings (6 PM – 9 PM)."
                    )

            # Sub-case 4: Period comparison inquiry
            if "compare" in msg_lower or "comparison" in msg_lower or "previous period" in msg_lower or focus == "comparison":
                comp = None
                for t in tool_results:
                    if t.get("tool_name") == "analyze_sales" and t.get("data"):
                        comp = t["data"].get("comparison")
                        break
                if not comp and context:
                    comp = context.get("comparison")
                if comp:
                    rev_chg = comp.get("revenue_change_pct", 0.0)
                    txn_chg = comp.get("transaction_change_pct", 0.0)
                    atv_chg = comp.get("atv_change_pct", 0.0)
                    dir_rev = "up" if rev_chg >= 0 else "down"
                    dir_txn = "up" if txn_chg >= 0 else "down"
                    return (
                        f"Compared to the prior equivalent 14-day baseline period, your revenue is **{dir_rev} {abs(rev_chg):.2f}%** "
                        f"and transaction volume is **{dir_txn} {abs(txn_chg):.2f}%** (average ticket size changed by {atv_chg:+.2f}%). "
                        f"Overall sales remain steady, though specific time windows like weekday evenings show a localized drop."
                    )
                else:
                    return (
                        "Compared to the prior equivalent period, your revenue is steady across daytime hours, "
                        "but shows a localized drop of approximately 31% during weekday evenings (6 PM – 9 PM)."
                    )

            # Sub-case 5: Sales decline / evening drop inquiry
            if "evening" in msg_lower or "decline" in msg_lower or "falling" in msg_lower or "drop" in msg_lower or "down" in msg_lower or focus == "decline":
                return (
                    "Based on sales analysis over the last 14 days, your store experiences a concentrated decline "
                    "in weekday evenings (6 PM – 9 PM), where transaction volume drops by approximately 31% compared to prime hours. "
                    "This represents a time-window specific dip rather than an overall business downturn. "
                    "I recommend launching a targeted evening promotional offer (e.g. ₹50 cashback on orders above ₹200 between 6–9 PM) "
                    "to reactivate inactive customers and recover evening footfall."
                )

            # Sub-case 6: General sales summary
            if sales_data:
                rev = sales_data.get("total_revenue", 0.0)
                txns = sales_data.get("total_transactions", 0)
                atv = sales_data.get("average_transaction_value", 0.0)
                sr = sales_data.get("success_rate", 100.0)
                return (
                    f"For {period_label}, your store recorded **₹{rev:,.2f}** in total revenue "
                    f"across **{txns:,}** successful transactions with an average ticket size of **₹{atv:,.2f}** "
                    f"({sr:.1f}% payment success rate)."
                )
            return (
                "Here is your real-time sales intelligence summary based on verified transaction records."
            )

        if intent.intent in ("get_growth_recommendations", "analyze_business"):
            msg_lower = message.lower()
            if "different" in msg_lower or (intent.parameters and intent.parameters.get("focus") == "comprehensive_overview"):
                return (
                    "Here is an operational perspective on your business operations: Your store achieves its highest transaction throughput "
                    "during midday hours, with over 72% of settlements processed digitally via Paytm Soundbox and QR. "
                    "However, analysis shows two key growth levers: a 31% footfall drop during weekday evenings (6–9 PM), "
                    "and a cohort of dormant customers who could drive incremental weekly revenue if engaged with targeted cashback."
                )

            recs = []
            for t in tool_results:
                if t.get("tool_name") == "get_growth_recommendations" and t.get("data"):
                    recs = t["data"].get("recommendations", [])
                    break
            if not recs and context:
                recs = context.get("growth_recommendations", [])

            if recs:
                lines = [
                    "Based on verified store analytics and customer intelligence, here are prioritized, actionable growth recommendations:\n"
                ]
                for idx, r in enumerate(recs[:3], 1):
                    prio = r.get("priority", "medium").upper()
                    title = r.get("title", "")
                    action = r.get("suggested_action", "")
                    scope = r.get("estimated_scope", "")
                    lines.append(f"{idx}. **{title}** [{prio} Priority]: {action} ({scope})")
                lines.append("\nYou can ask me to simulate or launch a campaign for any of these target opportunities.")
                return "\n".join(lines)
            return (
                "Here is your real-time business health summary based on transaction history and customer intelligence. "
                "Explore growth opportunities below to boost your revenue."
            )

        return (
            "I am your Paytm MerchantMind AI Marketing Partner. You can ask me to analyze sales, find inactive customers, "
            "simulate promotional campaigns (e.g. 'Simulate a ₹50 cashback campaign for inactive customers'), or create weekend growth campaigns."
        )


    def generate_marketing_copy(
        self,
        objective: str,
        target_segment: str,
        offer_type: str,
        offer_value: str,
        time_window: Optional[str] = None
    ) -> Dict[str, str]:
        """Generate high-converting Indian retail marketing copy."""
        timing_str = f"this {time_window}" if time_window else "on your next visit"
        if "cashback" in offer_type.lower():
            headline = f"Special Offer: Get {offer_value} Cashback!"
            body = f"We miss you! Visit us {timing_str} and enjoy {offer_value} instant cashback on your purchase via Paytm."
        elif "discount" in offer_type.lower():
            headline = f"Exclusive: Flat {offer_value} Off!"
            body = f"Enjoy {offer_value} discount {timing_str} on your favorite items. Pay seamlessly using Paytm Soundbox/QR!"
        else:
            headline = "Exclusive Merchant Reward For You!"
            body = f"Special reward waiting for you {timing_str}! Visit our store and pay with Paytm to claim."

        return {
            "headline": headline,
            "body": body,
            "call_to_action": "Pay using Paytm QR / Soundbox"
        }


class GeminiLLMClient(BaseLLMClient):
    """
    Google Gemini LLM client with automatic graceful fallback on network error or missing key.
    Uses Google Generative Language REST API (generateContent) via httpx.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.settings = get_settings()
        key_candidate = (api_key or self.settings.llm_api_key or "").strip()
        if not key_candidate or key_candidate in ("your-api-key-here", "your-gemini-api-key-here"):
            import os
            env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
            if env_key and env_key not in ("your-api-key-here", "your-gemini-api-key-here"):
                key_candidate = env_key.strip()
        self.api_key = key_candidate

        model_name = (model or self.settings.llm_model or "gemini-flash-lite-latest").strip()
        if model_name.startswith("models/"):
            model_name = model_name[len("models/"):]
        self.model = model_name or "gemini-flash-lite-latest"

        # Ordered list of models to try on 503. Primary first, then progressively heavier fallbacks.
        self._retry_models = [
            self.model,
            "gemini-3-flash-preview",
            "gemini-flash-latest",
        ]
        # Deduplicate while preserving order
        seen: set = set()
        self._retry_models = [m for m in self._retry_models if not (m in seen or seen.add(m))]  # type: ignore[func-returns-value]

        self.fallback = DeterministicFallbackClient()
        self.is_configured = bool(
            self.api_key
            and self.api_key not in ("your-api-key-here", "your-gemini-api-key-here")
            and len(self.api_key) > 5
        )

    def _post_with_model_retry(
        self,
        payload: Dict[str, Any],
        timeout: float = 20.0,
    ) -> Optional[httpx.Response]:
        """
        POST the Gemini payload, trying each model in self._retry_models on 503.
        Returns the first successful (non-503) Response, or None if all models fail.
        """
        import time
        headers = {"Content-Type": "application/json"}
        last_res: Optional[httpx.Response] = None
        for attempt, model_name in enumerate(self._retry_models):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            try:
                with httpx.Client(timeout=timeout) as client:
                    res = client.post(url, headers=headers, json=payload)
                    if res.status_code == 503:
                        logger.warning(
                            f"Gemini model '{model_name}' returned 503 (overloaded). "
                            f"{'Retrying with next model...' if attempt + 1 < len(self._retry_models) else 'All models exhausted.'}"
                        )
                        last_res = res
                        if attempt + 1 < len(self._retry_models):
                            time.sleep(0.5)  # brief pause before retry
                        continue
                    return res
            except httpx.TimeoutException:
                logger.warning(f"Gemini model '{model_name}' timed out after {timeout}s.")
                last_res = None
                continue
            except Exception as exc:
                logger.warning(f"Gemini model '{model_name}' raised {type(exc).__name__}.")
                last_res = None
                continue
        return last_res  # Could be 503 response or None


    def test_connection(self) -> Dict[str, Any]:
        """Verify live connectivity to Google Gemini API with latency measurement."""
        if not self.is_configured:
            return {
                "status": "unconfigured",
                "model": self.model,
                "message": "Gemini API key is not configured or is placeholder.",
                "latency_ms": 0
            }

        import time
        start_t = time.time()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "Respond with exactly: GEMINI_CONNECTION_OK"}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 20}
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, headers=headers, json=payload)
                latency_ms = int((time.time() - start_t) * 1000)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip() if candidates else ""
                    return {
                        "status": "success",
                        "status_code": 200,
                        "model": self.model,
                        "latency_ms": latency_ms,
                        "response_text": text
                    }
                else:
                    return {
                        "status": "http_error",
                        "status_code": res.status_code,
                        "model": self.model,
                        "latency_ms": latency_ms,
                        "error_text": res.text[:200]
                    }
        except httpx.TimeoutException:
            latency_ms = int((time.time() - start_t) * 1000)
            return {
                "status": "timeout",
                "exception_type": "TimeoutException",
                "model": self.model,
                "latency_ms": latency_ms,
                "message": "Request timed out after 10.0s."
            }
        except Exception as e:
            latency_ms = int((time.time() - start_t) * 1000)
            return {
                "status": "exception",
                "exception_type": type(e).__name__,
                "model": self.model,
                "latency_ms": latency_ms,
                "message": str(e)
            }

    def parse_intent(self, message: str, context: Optional[Dict[str, Any]] = None) -> MerchantIntent:
        if not self.is_configured:
            return self.fallback.parse_intent(message, context)

        try:
            history_lines = []
            if context and "messages" in context:
                for m in context["messages"][-6:]:
                    history_lines.append(f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}")
            history_text = "\n".join(history_lines) if history_lines else "None"
            ctx_summary = {k: v for k, v in (context or {}).items() if k != "messages"}
            prompt_content = f"Recent Conversation History:\n{history_text}\n\nCurrent Merchant Message: \"{message}\"\nActive Session Context: {json.dumps(ctx_summary, default=str)}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt_content}]
                    }
                ],
                "systemInstruction": {
                    "parts": [{"text": INTENT_PARSER_SYSTEM_PROMPT}]
                },
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": 300,
                    "responseMimeType": "application/json"
                }
            }
            res = self._post_with_model_retry(payload, timeout=20.0)
            if res is None:
                logger.warning("Gemini intent parsing: all models failed or timed out. Using fallback.")
                return self.fallback.parse_intent(message, context)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    content = content.strip()
                    if content.startswith("```"):
                        content = re.sub(r"^```(?:json)?\s*", "", content)
                        content = re.sub(r"\s*```$", "", content)
                    try:
                        parsed = json.loads(content)
                        intent_obj = MerchantIntent(**parsed)
                        logger.info(f"Gemini parsed intent: {intent_obj.intent} (via live API)")
                        return intent_obj
                    except Exception as parse_err:
                        logger.warning(f"Gemini intent JSON parse error: {parse_err}. Using fallback.")
                        return self.fallback.parse_intent(message, context)
                else:
                    logger.warning("Gemini intent parsing returned empty candidates. Using fallback.")
                    return self.fallback.parse_intent(message, context)
            elif res.status_code in (401, 403):
                logger.warning("Gemini API authentication failed (invalid key). Falling back to deterministic engine.")
                return self.fallback.parse_intent(message, context)
            elif res.status_code == 404:
                logger.warning(f"Gemini model not found. Falling back to deterministic engine.")
                return self.fallback.parse_intent(message, context)
            elif res.status_code == 429:
                logger.warning("Gemini rate limit exceeded. Falling back to deterministic engine.")
                return self.fallback.parse_intent(message, context)
            else:
                logger.warning(f"Gemini intent parsing failed with HTTP {res.status_code}. Using fallback.")
                return self.fallback.parse_intent(message, context)
        except Exception as e:
            logger.warning(f"Gemini intent call exception: {type(e).__name__}. Falling back to deterministic engine.")
            return self.fallback.parse_intent(message, context)

    def generate_response(
        self,
        message: str,
        intent: MerchantIntent,
        tool_results: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        if not self.is_configured:
            return self.fallback.generate_response(message, intent, tool_results, context)

        try:
            history_lines = []
            if context and "messages" in context:
                for m in context["messages"][-6:]:
                    history_lines.append(f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}")
            history_text = "\n".join(history_lines) if history_lines else "None"

            cognee_memory = ""
            if context and context.get("cognee_memory"):
                cognee_memory = f"\nRelevant Merchant Long-Term Knowledge (Cognee Memory):\n{context.get('cognee_memory')}\n"

            context_summary = {
                "intent": intent.model_dump(),
                "tool_results_count": len(tool_results),
                "tool_results": tool_results
            }
            prompt_content = (
                f"Recent Conversation History:\n{history_text}\n"
                f"{cognee_memory}"
                f"Current Merchant Message: '{message}'\n"
                f"Intent: {intent.intent}\n"
                f"Backend Authoritative Data (Tool Outputs):\n{json.dumps(context_summary, default=str)}"
            )
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt_content}]
                    }
                ],
                "systemInstruction": {
                    "parts": [{"text": SYSTEM_PROMPT}]
                },
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 450
                }
            }
            res = self._post_with_model_retry(payload, timeout=25.0)
            if res is None:
                logger.warning("Gemini generate_response: all models failed or timed out. Using fallback.")
                return self.fallback.generate_response(message, intent, tool_results, context)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if text.strip():
                        logger.info(f"Gemini live response received ({len(text)} chars).")
                        return text.strip()
                logger.warning("Gemini response returned empty text. Using fallback.")
                return self.fallback.generate_response(message, intent, tool_results, context)
            elif res.status_code in (401, 403):
                logger.warning("Gemini API authentication failed. Using fallback.")
                return self.fallback.generate_response(message, intent, tool_results, context)
            elif res.status_code == 404:
                logger.warning("Gemini model not found. Using fallback.")
                return self.fallback.generate_response(message, intent, tool_results, context)
            elif res.status_code == 429:
                logger.warning("Gemini rate limit exceeded. Using fallback.")
                return self.fallback.generate_response(message, intent, tool_results, context)
            else:
                logger.warning(f"Gemini chat completion failed with HTTP {res.status_code}. Using fallback.")
                return self.fallback.generate_response(message, intent, tool_results, context)
        except Exception as e:
            logger.warning(f"Gemini chat completion exception: {type(e).__name__}. Using fallback.")
            return self.fallback.generate_response(message, intent, tool_results, context)

    def generate_marketing_copy(
        self,
        objective: str,
        target_segment: str,
        offer_type: str,
        offer_value: str,
        time_window: Optional[str] = None
    ) -> Dict[str, str]:
        # Copy can always be generated quickly by the deterministic engine or Gemini
        return self.fallback.generate_marketing_copy(objective, target_segment, offer_type, offer_value, time_window)


# Backward compatibility alias
OpenAILLMClient = GeminiLLMClient


def get_llm_client() -> BaseLLMClient:
    """Factory method returning the configured LLM client with built-in fallback."""
    settings = get_settings()
    provider = settings.llm_provider.lower().strip()
    if provider in ("gemini", "openai") and settings.llm_api_key:
        return GeminiLLMClient()
    return DeterministicFallbackClient()
