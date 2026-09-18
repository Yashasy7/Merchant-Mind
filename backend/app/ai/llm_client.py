"""
LLM Provider Abstraction and Deterministic Fallback Client.
Supports OpenAI-compatible structured tool calls when configured,
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
            if context and context.get("campaign_id"):
                camp_id = context.get("campaign_id")
            else:
                m = re.search(r"cmp-[a-f0-9\-]+|camp-[a-f0-9\-]+", msg)
                if m:
                    camp_id = m.group(0)
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
            if context and context.get("campaign_id"):
                camp_id = context.get("campaign_id")
            else:
                m = re.search(r"cmp-[a-f0-9\-]+|camp-[a-f0-9\-]+", msg)
                if m:
                    camp_id = m.group(0)
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
        elif "vip" in msg:
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

        # 3. Inactive / at-risk customer recovery intent
        if any(w in msg for w in ["inactive", "at-risk", "at risk", "churn", "bring back", "win back", "recover"]):
            return MerchantIntent(
                intent="recover_inactive_customers",
                objective="retention",
                target_segment=target_segment if target_segment != "All Customers" else "Inactive",
                time_window=time_window,
                requested_action="campaign",
                parameters=params
            )

        # 4. Weekend revenue / sales drop intent
        if any(w in msg for w in ["sales drop", "sales have dropped", "dropped", "down", "weekend sales", "weekend revenue", "increase weekend"]):
            return MerchantIntent(
                intent="increase_weekend_revenue",
                objective="increase_revenue",
                target_segment=target_segment,
                time_window="weekend",
                requested_action="campaign",
                parameters=params
            )

        # 5. Generic campaign creation or simulation
        if "simulate" in msg or "what-if" in msg or "what if" in msg or "how much could" in msg:
            return MerchantIntent(
                intent="simulate_campaign",
                objective="growth",
                target_segment=target_segment,
                time_window=time_window,
                requested_action="simulation",
                parameters=params
            )

        if "create" in msg or "campaign" in msg or "offer" in msg or "give me a cashback" in msg:
            return MerchantIntent(
                intent="create_campaign",
                objective="growth",
                target_segment=target_segment,
                time_window=time_window,
                requested_action="campaign",
                parameters=params
            )

        # 6. Accounting & Financial analysis
        if any(w in msg for w in ["profit", "expense", "expenses", "p&l", "accounting", "accountant", "finances", "financials", "how much did i spend", "income vs expense", "invoices", "vendor bills"]):
            return MerchantIntent(
                intent="analyze_financials",
                objective="accounting",
                target_segment="All Customers",
                time_window=None,
                requested_action="accounting",
                parameters=params
            )

        # 7. Business analysis / overview
        if any(w in msg for w in ["how is my business", "how are sales", "analyze", "overview", "summary", "report", "insights"]):
            return MerchantIntent(
                intent="analyze_business",
                objective="analysis",
                target_segment="All Customers",
                time_window=None,
                requested_action="analysis",
                parameters=params
            )

        # 8. Default general guidance
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

        if intent.intent == "analyze_financials":
            return (
                "Here is your real-time financial health and P&L summary based on your transactions and expense records. "
                "Review your revenue, operating expenses, net profit, and expense breakdown below. "
                "Note: MerchantMind assists with financial organization and does not replace a Chartered Accountant (CA)."
            )

        if intent.intent == "analyze_business":
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


class OpenAILLMClient(BaseLLMClient):
    """
    OpenAI-compatible LLM client with automatic graceful fallback on network error or missing key.
    """

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.llm_api_key.strip()
        self.model = self.settings.llm_model
        self.fallback = DeterministicFallbackClient()
        self.is_configured = bool(self.api_key and self.api_key != "your-api-key-here" and len(self.api_key) > 5)

    def parse_intent(self, message: str, context: Optional[Dict[str, Any]] = None) -> MerchantIntent:
        if not self.is_configured:
            return self.fallback.parse_intent(message, context)

        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            prompt_content = f"Merchant Message: \"{message}\"\nActive Context: {json.dumps(context or {})}"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": INTENT_PARSER_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_content}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0,
                "max_tokens": 250
            }
            with httpx.Client(timeout=8.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return MerchantIntent(**parsed)
                else:
                    logger.warning(f"OpenAI intent parsing failed with HTTP {res.status_code}. Using fallback.")
                    return self.fallback.parse_intent(message, context)
        except Exception as e:
            logger.warning(f"OpenAI intent call exception: {e}. Falling back to deterministic engine.")
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
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            context_summary = {
                "intent": intent.model_dump(),
                "tool_results_count": len(tool_results),
                "tool_results": tool_results
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Merchant asked: '{message}'\nIntent: {intent.intent}\nBackend Tool Data: {json.dumps(context_summary)}"
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 400
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    return self.fallback.generate_response(message, intent, tool_results, context)
        except Exception as e:
            logger.warning(f"OpenAI chat completion exception: {e}. Using fallback.")
            return self.fallback.generate_response(message, intent, tool_results, context)

    def generate_marketing_copy(
        self,
        objective: str,
        target_segment: str,
        offer_type: str,
        offer_value: str,
        time_window: Optional[str] = None
    ) -> Dict[str, str]:
        # Copy can always be generated quickly by the deterministic engine or LLM
        return self.fallback.generate_marketing_copy(objective, target_segment, offer_type, offer_value, time_window)


def get_llm_client() -> BaseLLMClient:
    """Factory method returning the configured LLM client with built-in fallback."""
    settings = get_settings()
    if settings.llm_provider.lower() == "openai" and settings.llm_api_key:
        return OpenAILLMClient()
    return DeterministicFallbackClient()
