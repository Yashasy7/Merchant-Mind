"""
AI Marketing / Campaign Agent Package for Module 7.
Provides conversational orchestration, allowlisted tools,
and deterministic human-in-the-loop campaign workflows.
"""

from app.ai.agent import MarketingCampaignAgent
from app.ai.tools import ToolRegistry, ALLOWED_TOOLS
from app.ai.llm_client import BaseLLMClient, get_llm_client, DeterministicFallbackClient, GeminiLLMClient, OpenAILLMClient
from app.ai.schemas import (
    MerchantIntent,
    AgentChatRequest,
    AgentChatResponse,
    AgentToolCall,
    AgentToolDefinition,
    AgentToolsCatalogResponse,
)

__all__ = [
    "MarketingCampaignAgent",
    "ToolRegistry",
    "ALLOWED_TOOLS",
    "BaseLLMClient",
    "get_llm_client",
    "DeterministicFallbackClient",
    "GeminiLLMClient",
    "OpenAILLMClient",
    "MerchantIntent",
    "AgentChatRequest",
    "AgentChatResponse",
    "AgentToolCall",
    "AgentToolDefinition",
    "AgentToolsCatalogResponse",
]
