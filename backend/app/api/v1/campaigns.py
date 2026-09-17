"""
Campaign API endpoints under /api/v1/campaigns.
Provides RESTful access to:
  - Campaign creation (always enters PENDING_APPROVAL)
  - Explicit human approval & rejection
  - Safe simulated execution (approved only, zero real external calls)
  - Campaign detail, listing, performance result, and audit history
Strictly merchant-isolated.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.services.campaign_service import CampaignService
from app.schemas.campaign import (
    CampaignCreateRequest,
    CampaignApproveRequest,
    CampaignRejectRequest,
    CampaignExecuteRequest,
    CampaignResponse,
    CampaignListResponse,
    CampaignResultResponse,
    CampaignAuditHistoryResponse,
)

router = APIRouter(tags=["Campaign Management"])
settings = get_settings()


def resolve_merchant_id(merchant_id: Optional[str]) -> str:
    """Resolve merchant ID, defaulting to configured DEMO_MERCHANT_ID if omitted."""
    return (
        merchant_id.strip()
        if merchant_id and merchant_id.strip()
        else settings.demo_merchant_id
    )


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Campaign Draft",
    description=(
        "Creates a new campaign draft and places it in PENDING_APPROVAL state. "
        "Does NOT execute automatically. Requires human merchant approval."
    ),
)
def create_campaign(
    request: CampaignCreateRequest,
    merchant_id: Optional[str] = Query(None, description="Optional merchant ID override"),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    effective_merchant_id = resolve_merchant_id(request.merchant_id or merchant_id)
    service = CampaignService(db)
    return service.create_campaign(merchant_id=effective_merchant_id, request=request)


@router.get(
    "",
    response_model=CampaignListResponse,
    summary="List Merchant Campaigns",
    description="Returns all campaigns belonging to the specified merchant, optionally filtered by status.",
)
def list_campaigns(
    merchant_id: Optional[str] = Query(None, description="Merchant ID"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. PENDING_APPROVAL, APPROVED, COMPLETED)"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> CampaignListResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = CampaignService(db)
    return service.list_campaigns(
        merchant_id=m_id, status_filter=status, limit=limit, offset=offset
    )


@router.get(
    "/{campaign_id}",
    response_model=CampaignResponse,
    summary="Get Campaign Details",
    description="Fetches detailed campaign metadata, projected numbers, and status for a specific merchant.",
)
def get_campaign(
    campaign_id: str,
    merchant_id: Optional[str] = Query(None, description="Merchant ID"),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = CampaignService(db)
    return service.get_campaign(campaign_id=campaign_id, merchant_id=m_id)


@router.post(
    "/{campaign_id}/approve",
    response_model=CampaignResponse,
    summary="Approve Campaign (Human Approval)",
    description=(
        "Explicitly approves a campaign in PENDING_APPROVAL state. "
        "Transitions status to APPROVED. Does NOT trigger execution."
    ),
)
def approve_campaign(
    campaign_id: str,
    merchant_id: Optional[str] = Query(None, description="Merchant ID"),
    request: Optional[CampaignApproveRequest] = Body(None),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    m_id = resolve_merchant_id(
        request.merchant_id if request and request.merchant_id else merchant_id
    )
    service = CampaignService(db)
    return service.approve_campaign(
        campaign_id=campaign_id, merchant_id=m_id, request=request
    )


@router.post(
    "/{campaign_id}/reject",
    response_model=CampaignResponse,
    summary="Reject Campaign",
    description="Rejects a campaign in PENDING_APPROVAL state and records the rejection reason and audit event.",
)
def reject_campaign(
    campaign_id: str,
    merchant_id: Optional[str] = Query(None, description="Merchant ID"),
    request: Optional[CampaignRejectRequest] = Body(None),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    m_id = resolve_merchant_id(
        request.merchant_id if request and request.merchant_id else merchant_id
    )
    service = CampaignService(db)
    return service.reject_campaign(
        campaign_id=campaign_id, merchant_id=m_id, request=request
    )


@router.post(
    "/{campaign_id}/execute",
    response_model=CampaignResultResponse,
    summary="Execute Approved Campaign (Safe Simulated)",
    description=(
        "Executes an APPROVED campaign in a safe simulated manner. "
        "Strictly fails (HTTP 409) if campaign is not already APPROVED. "
        "Does NOT contact real Paytm APIs or external messaging gateways."
    ),
)
def execute_campaign(
    campaign_id: str,
    merchant_id: Optional[str] = Query(None, description="Merchant ID"),
    request: Optional[CampaignExecuteRequest] = Body(None),
    db: Session = Depends(get_db),
) -> CampaignResultResponse:
    m_id = resolve_merchant_id(
        request.merchant_id if request and request.merchant_id else merchant_id
    )
    service = CampaignService(db)
    return service.execute_campaign(
        campaign_id=campaign_id, merchant_id=m_id, request=request
    )


@router.get(
    "/{campaign_id}/result",
    response_model=CampaignResultResponse,
    summary="Get Campaign Execution Result",
    description="Returns the deterministic simulated performance result of an executed campaign.",
)
def get_campaign_result(
    campaign_id: str,
    merchant_id: Optional[str] = Query(None, description="Merchant ID"),
    db: Session = Depends(get_db),
) -> CampaignResultResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = CampaignService(db)
    return service.get_campaign_result(campaign_id=campaign_id, merchant_id=m_id)


@router.get(
    "/{campaign_id}/audit",
    response_model=CampaignAuditHistoryResponse,
    summary="Get Campaign Audit History",
    description="Returns chronological audit log of all lifecycle events and transitions for the campaign.",
)
def get_campaign_audit(
    campaign_id: str,
    merchant_id: Optional[str] = Query(None, description="Merchant ID"),
    db: Session = Depends(get_db),
) -> CampaignAuditHistoryResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = CampaignService(db)
    return service.get_audit_history(campaign_id=campaign_id, merchant_id=m_id)


@router.post(
    "/{campaign_id}/cancel",
    response_model=CampaignResponse,
    summary="Cancel Campaign",
    description="Cancels a campaign that is in PENDING_APPROVAL or APPROVED state.",
)
def cancel_campaign(
    campaign_id: str,
    merchant_id: Optional[str] = Query(None, description="Merchant ID"),
    reason: Optional[str] = Query(None, description="Cancellation reason"),
    db: Session = Depends(get_db),
) -> CampaignResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = CampaignService(db)
    return service.cancel_campaign(
        campaign_id=campaign_id, merchant_id=m_id, reason=reason
    )
