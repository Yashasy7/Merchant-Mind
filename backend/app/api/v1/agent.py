"""
Agent API endpoints under /api/v1/agent.
Provides conversational AI campaign orchestration, allowlisted tool catalog,
and structured merchant intent classification.
Strictly merchant-isolated and human-in-the-loop enforced.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.ai.agent import MarketingCampaignAgent
from app.ai.tools import ToolRegistry
from app.ai.llm_client import get_llm_client
from app.ai.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    MerchantIntent,
    AgentToolsCatalogResponse,
)

router = APIRouter(tags=["AI Marketing Agent"])
settings = get_settings()


def resolve_merchant_id(merchant_id: Optional[str]) -> str:
    """Resolve merchant ID, defaulting to configured DEMO_MERCHANT_ID if omitted."""
    return (
        merchant_id.strip()
        if merchant_id and merchant_id.strip()
        else settings.demo_merchant_id
    )


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Chat with AI Marketing Partner",
    description=(
        "Conversational partner that analyzes merchant sales & customer data, identifies growth opportunities, "
        "simulates campaign outcomes using Module 5, and creates campaigns in Module 6 in PENDING_APPROVAL status. "
        "NEVER autonomously executes campaigns. Human approval is strictly required."
    ),
)
def agent_chat(
    request: AgentChatRequest = Body(...),
    merchant_id: Optional[str] = Query(None, description="Optional merchant ID override"),
    db: Session = Depends(get_db),
) -> AgentChatResponse:
    effective_merchant_id = resolve_merchant_id(request.merchant_id or merchant_id)
    agent = MarketingCampaignAgent(db=db, merchant_id=effective_merchant_id)
    return agent.chat(request)


@router.get(
    "/tools",
    response_model=AgentToolsCatalogResponse,
    summary="List Allowlisted Agent Tools",
    description="Returns public catalog of allowlisted backend tools available for agent orchestration.",
)
def list_agent_tools() -> AgentToolsCatalogResponse:
    tools = ToolRegistry.get_tool_catalog()
    return AgentToolsCatalogResponse(tools=tools, total_tools=len(tools))


@router.post(
    "/intent",
    response_model=MerchantIntent,
    summary="Extract Merchant Intent",
    description="Extracts structured intent, target cohort, time window, and parameters from a merchant query.",
)
def extract_intent(
    request: AgentChatRequest = Body(...),
) -> MerchantIntent:
    client = get_llm_client()
    return client.parse_intent(request.message, request.context)
