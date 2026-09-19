"""
Pydantic schemas for Module 7: AI Marketing / Campaign Agent.
Provides strongly typed DTOs for merchant intents, tool definitions,
agent request/responses, and orchestration metadata.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.campaign import CampaignResponse, CampaignResultResponse
from app.schemas.what_if import SimulationScenario


class MerchantIntent(BaseModel):
    """Structured representation of interpreted merchant intent."""
    intent: str = Field(..., description="Canonical intent key, e.g. increase_weekend_revenue, recover_inactive_customers")
    objective: str = Field(..., description="High level goal: increase_revenue | retention | recovery | growth | approval | execution | analysis | guidance")
    target_segment: str = Field("All Customers", description="Target customer segment")
    time_window: Optional[str] = Field(None, description="Target time window, e.g. weekend, weekday, evening")
    requested_action: str = Field("analysis", description="Action requested: campaign | simulation | approval | execution | analysis | guidance")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Extracted numerical or categorical parameters")

    model_config = ConfigDict(from_attributes=True)


class AgentToolCall(BaseModel):
    """Record of a tool invocation executed during agent orchestration."""
    tool_name: str = Field(..., description="Name of the invoked tool")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Sanitized arguments passed to tool")
    status: str = Field("success", description="Execution outcome: success | error")
    result_summary: Optional[str] = Field(None, description="Concise human-readable summary of tool result")

    model_config = ConfigDict(from_attributes=True)


class AgentChatRequest(BaseModel):
    """Input payload for merchant conversational agent endpoint."""
    message: str = Field(..., min_length=1, max_length=1000, description="Natural language merchant query or instruction")
    conversation_id: Optional[str] = Field(None, description="Optional conversational session identifier")
    merchant_id: Optional[str] = Field(None, description="Optional merchant identifier override")
    context: Optional[Dict[str, Any]] = Field(None, description="Optional client-side state or active entity context")


class AgentChatResponse(BaseModel):
    """Structured response envelope returned by the AI Marketing Agent."""
    message: str = Field(..., description="Natural language explanation and guidance for the merchant")
    intent: MerchantIntent = Field(..., description="Interpreted merchant intent")
    actions_taken: List[AgentToolCall] = Field(default_factory=list, description="Sequence of backend tools orchestrated")
    insights: List[str] = Field(default_factory=list, description="Grounding business insights extracted from tools")
    recommendation: Optional[Dict[str, Any]] = Field(None, description="Module 4 Growth Recommendation if relevant")
    campaign: Optional[CampaignResponse] = Field(None, description="Module 6 Campaign draft if created or referenced")
    simulation: Optional[SimulationScenario] = Field(None, description="Module 5 What-If simulation if simulated")
    approval_required: bool = Field(False, description="True if merchant human approval is required before proceeding")
    campaign_id: Optional[str] = Field(None, description="ID of campaign currently in workflow")
    status: Optional[str] = Field(None, description="Current campaign status, e.g. PENDING_APPROVAL, APPROVED, COMPLETED")
    execution_result: Optional[CampaignResultResponse] = Field(None, description="Module 6 Campaign result if executed")
    conversation_id: Optional[str] = Field(None, description="Active conversation session ID")
    disclaimer: str = Field(
        default=(
            "Synthetic Demo / Decision Support — All financial projections and campaign execution are "
            "simulated in the Paytm MerchantMind demo environment. No live SMS/WhatsApp messages or Paytm coupon APIs were dispatched."
        ),
        description="Mandatory demo / simulation disclaimer"
    )

    model_config = ConfigDict(from_attributes=True)


class AgentToolParameter(BaseModel):
    """Parameter definition for an allowlisted agent tool."""
    name: str
    type: str
    description: str
    required: bool = False
    default: Optional[Any] = None


class AgentToolDefinition(BaseModel):
    """Public catalog description of an allowlisted agent tool."""
    name: str
    description: str
    category: str
    parameters: List[AgentToolParameter] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AgentToolsCatalogResponse(BaseModel):
    """Catalog of all allowlisted agent capabilities."""
    tools: List[AgentToolDefinition]
    total_tools: int

    model_config = ConfigDict(from_attributes=True)
