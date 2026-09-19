"""
Pydantic schemas for Module 6 — Campaign / Approval / Action layer.
Provides strongly typed, validated DTOs for campaign creation, human approval workflows,
rejections, simulated executions, audit logs, and status queries.
"""

from typing import List, Optional, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator


class CampaignStatus(str, Enum):
    """Rigorous state machine enum for campaign lifecycle."""
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    VALIDATING = "VALIDATING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CampaignOfferType(str, Enum):
    """Supported promotional incentive categories."""
    FIXED_CASHBACK = "fixed_cashback"
    PERCENTAGE_DISCOUNT = "percentage_discount"
    CUSTOM = "custom"


class CampaignAuditAction(str, Enum):
    """Audit trail actions for critical lifecycle state changes."""
    CREATE = "CREATE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    VALIDATE = "VALIDATE"
    EXECUTE = "EXECUTE"
    COMPLETE = "COMPLETE"
    CANCEL = "CANCEL"
    FAIL = "FAIL"


class CampaignCreateRequest(BaseModel):
    """Payload to create a new campaign in PENDING_APPROVAL status."""
    merchant_id: Optional[str] = Field(None, description="Merchant identifier (defaults to demo merchant)")
    name: str = Field(..., min_length=3, max_length=200, description="Campaign headline name")
    description: Optional[str] = Field(None, max_length=500, description="Campaign business purpose")
    target_segment: str = Field("All Customers", description="Target customer segment (VIP, Loyal, New, At-Risk, Inactive, Regular, All Customers)")
    offer_type: str = Field("fixed_cashback", description="fixed_cashback | percentage_discount | custom")
    discount_percent: Optional[float] = Field(None, ge=0.0, le=100.0, description="Discount percentage (0-100%)")
    cashback_amount: Optional[float] = Field(None, ge=0.0, le=2000.0, description="Cashback in INR per order")
    minimum_transaction_amount: Optional[float] = Field(0.0, ge=0.0, description="Minimum order threshold in INR")
    target_days: Optional[str] = Field(None, description="Day filter: weekend | weekday | all")
    target_hours: Optional[str] = Field(None, description="Hour filter: morning | afternoon | evening | night | all")
    start_date: Optional[datetime] = Field(None, description="Campaign start date")
    end_date: Optional[datetime] = Field(None, description="Campaign end date")
    source_recommendation_id: Optional[str] = Field(None, description="Optional link to Module 4 GrowthRecommendation ID")
    source_simulation_id: Optional[str] = Field(None, description="Optional link to Module 5 WhatIf Simulation scenario ID")
    created_by: Optional[str] = Field("Merchant", description="Creating user or role")

    # Optional explicit projection overrides
    projected_revenue: Optional[float] = Field(None, description="Pre-calculated projected revenue")
    projected_transactions: Optional[int] = Field(None, description="Pre-calculated projected transaction volume")
    estimated_incentive_cost: Optional[float] = Field(None, description="Pre-calculated estimated incentive cost")
    estimated_roi: Optional[float] = Field(None, description="Pre-calculated estimated ROI")

    @field_validator("offer_type")
    @classmethod
    def validate_offer_type(cls, v: str) -> str:
        valid = {"fixed_cashback", "percentage_discount", "custom", "cashback", "discount"}
        norm = v.lower().strip()
        if norm not in valid:
            raise ValueError(f"Invalid offer_type '{v}'. Must be one of: fixed_cashback, percentage_discount, custom.")
        if norm == "cashback":
            return "fixed_cashback"
        if norm == "discount":
            return "percentage_discount"
        return norm


class CampaignApproveRequest(BaseModel):
    """Payload to record merchant approval for campaign launch."""
    merchant_id: Optional[str] = Field(None, description="Merchant identifier (defaults to demo merchant)")
    actor: Optional[str] = Field(None, description="Approving merchant identity or role")
    approved_by: Optional[str] = Field("Merchant", description="Approving merchant identity or role")


class CampaignRejectRequest(BaseModel):
    """Payload to record merchant rejection of a campaign draft."""
    merchant_id: Optional[str] = Field(None, description="Merchant identifier (defaults to demo merchant)")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for declining the campaign")
    actor: Optional[str] = Field("Merchant", description="Rejecting merchant identity or role")


class CampaignExecuteRequest(BaseModel):
    """Payload to initiate safe simulated execution of an approved campaign."""
    merchant_id: Optional[str] = Field(None, description="Merchant identifier (defaults to demo merchant)")
    actor: Optional[str] = Field("Merchant", description="Initiator of campaign execution")


class CampaignAuditLogResponse(BaseModel):
    """Audit log entry capturing state transitions and approvals."""
    id: Union[int, str]
    campaign_id: str
    merchant_id: str
    action: str
    previous_status: Optional[str] = None
    new_status: str
    actor: str
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignResultResponse(BaseModel):
    """Deterministic simulated campaign execution result."""
    campaign_id: str
    merchant_id: str
    status: str
    executed_at: Optional[datetime] = None
    target_segment: str
    offer_type: str
    simulated_transactions: int
    simulated_revenue: float
    simulated_cost: float
    simulated_incremental_revenue: Optional[float] = 0.0
    simulated_net_impact: float
    simulated_roi: Optional[float] = None
    roi_multiplier_label: Optional[str] = None
    result_summary: str
    execution_summary: Optional[str] = None
    is_demo_result: bool = Field(True, description="Always true; flags that figures are simulated demo metrics")
    data_type: str = Field("SYNTHETIC_DEMO", description="Mandatory metadata label")
    disclaimer: str = Field(
        "Synthetic / Illustrative Demo Result — Simulated campaign outcome for demonstration only. No actual messages or coupons were sent.",
        description="Mandatory disclaimer"
    )

    model_config = ConfigDict(from_attributes=True)


class CampaignResponse(BaseModel):
    """Complete campaign record including metadata, financial projections, and status."""
    campaign_id: str
    merchant_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    target_segment: str
    offer_type: str
    discount_percent: Optional[float] = None
    cashback_amount: Optional[float] = None
    minimum_transaction_amount: float = 0.0
    target_days: Optional[str] = None
    target_hours: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: str
    source_recommendation_id: Optional[str] = None
    source_simulation_id: Optional[str] = None

    # Pre-execution projections
    projected_revenue: float = 0.0
    projected_transactions: int = 0
    estimated_incentive_cost: float = 0.0
    estimated_roi: Optional[float] = None

    # Post-execution simulated results
    simulated_revenue: Optional[float] = None
    simulated_transactions: Optional[int] = None
    simulated_cost: Optional[float] = None
    simulated_net_impact: Optional[float] = None
    simulated_roi: Optional[float] = None

    # Lifecycle Timestamps & Actors
    created_at: datetime
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_by: str = "Merchant"
    approved_by: Optional[str] = None
    is_demo_campaign: bool = Field(True, description="Always true")
    data_type: str = Field("SYNTHETIC_DEMO", description="Mandatory metadata tag")

    model_config = ConfigDict(from_attributes=True)


class CampaignListResponse(BaseModel):
    """Collection of campaigns for a merchant."""
    merchant_id: str
    total_campaigns: int
    total_count: Optional[int] = None
    status_filter: Optional[str] = None
    campaigns: List[CampaignResponse]


class CampaignAuditHistoryResponse(BaseModel):
    """Audit trail history for a single campaign."""
    campaign_id: str
    merchant_id: str
    total_audit_events: int
    total_events: Optional[int] = None
    events: List[CampaignAuditLogResponse] = Field(default_factory=list)
    audit_logs: List[CampaignAuditLogResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# n8n Callback Schemas
# ---------------------------------------------------------------------------

class N8nCallbackRequest(BaseModel):
    """
    Payload posted back to FastAPI by the n8n workflow after campaign delivery.
    All fields are optional so partial n8n responses are handled gracefully.
    """
    campaign_id: str = Field(..., description="Campaign unique identifier")
    merchant_id: str = Field(..., description="Merchant unique identifier for isolation validation")
    status: Optional[str] = Field(None, description="Workflow execution status from n8n")
    targeted: Optional[int] = Field(None, ge=0, description="Number of customers targeted by n8n")
    delivered: Optional[int] = Field(None, ge=0, description="Number of successful deliveries")
    failed: Optional[int] = Field(None, ge=0, description="Number of failed deliveries")
    execution_mode: Optional[str] = Field(None, description="live | simulated_demo")
    message: Optional[str] = Field(None, max_length=500, description="Human-readable status message from n8n")


class N8nCallbackResponse(BaseModel):
    """Response returned to n8n after processing the callback."""
    accepted: bool
    campaign_id: str
    merchant_id: str
    message: str


