"""
Campaign Service implementing Module 6: Campaign / Approval / Action.

Enforces human-in-the-loop lifecycle:
  DRAFT -> PENDING_APPROVAL -> APPROVED / REJECTED -> VALIDATING -> EXECUTING -> COMPLETED

Safety boundary:
  - Execution is strictly forbidden unless campaign has been explicitly APPROVED.
  - Generates deterministic synthetic demo execution results without contacting real Paytm APIs
    or dispatching real SMS/WhatsApp messages.
  - Strictly merchant-isolated across all operations and audit logs.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.services.base import BaseService
from app.repositories.campaign_repository import CampaignRepository
from app.services.growth_service import GrowthRecommendationService
from app.services.what_if_service import WhatIfSimulationService
from app.models.campaign import Campaign, CampaignAuditLog
from app.schemas.campaign import (
    CampaignStatus,
    CampaignOfferType,
    CampaignAuditAction,
    CampaignCreateRequest,
    CampaignApproveRequest,
    CampaignRejectRequest,
    CampaignExecuteRequest,
    CampaignResponse,
    CampaignListResponse,
    CampaignResultResponse,
    CampaignAuditLogResponse,
    CampaignAuditHistoryResponse,
)
from app.schemas.what_if import SimulationRequest
from app.services.n8n_client import get_n8n_client

VALID_SEGMENTS = {
    "all customers": "All Customers",
    "all": "All Customers",
    "vip": "VIP",
    "loyal": "Loyal",
    "new": "New",
    "at-risk": "At-Risk",
    "at risk": "At-Risk",
    "inactive": "Inactive",
    "regular": "Regular",
}

VALID_OFFER_TYPES = {
    "percentage_discount",
    "fixed_cashback",
    "free_delivery",
    "custom",
}


class CampaignService(BaseService):
    """
    Business service orchestrating campaign creation, validation, human approval,
    simulated action, result measurement, and immutable audit logging.
    """

    def __init__(self, db: Session):
        super().__init__(db)
        self.campaign_repo = CampaignRepository(db)
        self.growth_service = GrowthRecommendationService(db)
        self.what_if_service = WhatIfSimulationService(db)

    # -------------------------------------------------------------------------
    # Helper Validation Methods
    # -------------------------------------------------------------------------

    def _canonicalize_segment(self, segment: Optional[str]) -> str:
        """Normalize customer segment or raise HTTP 400."""
        if not segment or not segment.strip():
            return "All Customers"
        cleaned = segment.strip().lower()
        if cleaned not in VALID_SEGMENTS:
            valid_list = ", ".join(
                ["All Customers", "VIP", "Loyal", "New", "At-Risk", "Inactive", "Regular"]
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target segment '{segment}'. Valid options: {valid_list}.",
            )
        return VALID_SEGMENTS[cleaned]

    def _assert_finite_numbers(self, **kwargs: Any) -> None:
        """Ensure all provided numerical values are finite and non-NaN, supporting Decimal, float, int."""
        from decimal import Decimal

        for key, val in kwargs.items():
            if val is not None:
                if not isinstance(val, (int, float, Decimal)):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Malformed financial value for '{key}': value must be a finite number.",
                    )
                try:
                    f_val = float(val)
                    if not math.isfinite(f_val):
                        raise ValueError()
                except (ValueError, OverflowError):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Malformed financial value for '{key}': value must be a finite number.",
                    )


    def _validate_campaign_business_rules(
        self,
        merchant_id: str,
        target_segment: str,
        offer_type: str,
        discount_percent: Optional[float] = None,
        cashback_amount: Optional[float] = None,
        minimum_transaction_amount: Optional[float] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> None:
        """Perform comprehensive business domain validation."""
        if not merchant_id or not merchant_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Merchant ID cannot be empty.",
            )

        if offer_type not in VALID_OFFER_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid offer type '{offer_type}'. Allowed: {', '.join(sorted(VALID_OFFER_TYPES))}.",
            )

        if offer_type == "percentage_discount":
            if discount_percent is None or discount_percent <= 0 or discount_percent > 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Percentage discount must be greater than 0% and at most 100%.",
                )

        if offer_type == "fixed_cashback":
            if cashback_amount is None or cashback_amount <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cashback amount must be greater than 0.",
                )

        if minimum_transaction_amount is not None and minimum_transaction_amount < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Minimum transaction amount cannot be negative.",
            )

        if start_date and end_date and end_date < start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign end date cannot be before start date.",
            )

        self._assert_finite_numbers(
            discount_percent=discount_percent,
            cashback_amount=cashback_amount,
            minimum_transaction_amount=minimum_transaction_amount,
        )

    # -------------------------------------------------------------------------
    # 1. Campaign Creation (Always Enters PENDING_APPROVAL)
    # -------------------------------------------------------------------------

    def create_campaign(
        self, merchant_id: str, request: CampaignCreateRequest
    ) -> CampaignResponse:
        """
        Create a new campaign draft and place it immediately in PENDING_APPROVAL state.
        Validates business parameters and ensures human-in-the-loop safety.
        Reuses Module 4 (Recommendations) and Module 5 (What-If Simulator) if linked.
        """
        # 1. Enforce merchant parameter consistency
        if request.merchant_id and request.merchant_id != merchant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Route merchant_id '{merchant_id}' does not match payload merchant_id '{request.merchant_id}'.",
            )

        target_segment = self._canonicalize_segment(request.target_segment)
        offer_type_str = (
            request.offer_type.value
            if hasattr(request.offer_type, "value")
            else str(request.offer_type)
        )

        # 2. Validate business rules
        self._validate_campaign_business_rules(
            merchant_id=merchant_id,
            target_segment=target_segment,
            offer_type=offer_type_str,
            discount_percent=request.discount_percent,
            cashback_amount=request.cashback_amount,
            minimum_transaction_amount=request.minimum_transaction_amount,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        # 3. Validate source recommendation ownership if provided (Module 4 reuse)
        if request.source_recommendation_id:
            # Check if prefix belongs to another merchant
            rec_id = request.source_recommendation_id.strip()
            merchant_prefix = f"rec-{merchant_id[:8]}"
            if rec_id.startswith("rec-") and not rec_id.startswith(merchant_prefix):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Source recommendation '{rec_id}' does not belong to merchant '{merchant_id}'.",
                )
            try:
                recs_resp = self.growth_service.generate_recommendations(merchant_id=merchant_id)
                known_ids = {r.recommendation_id for r in recs_resp.recommendations}
                if rec_id not in known_ids and not rec_id.startswith(merchant_prefix):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Source recommendation '{rec_id}' not found for merchant '{merchant_id}'.",
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Could not verify recommendation id {rec_id}: {e}")

        # 4. Validate source simulation ownership if provided (Module 5 reuse)
        if request.source_simulation_id:
            sim_id = request.source_simulation_id.strip()
            # If simulation id embeds a merchant prefix, verify it matches
            if "merchant" in sim_id and merchant_id not in sim_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Source simulation '{sim_id}' does not belong to merchant '{merchant_id}'.",
                )

        # 5. Determine or compute projections using Module 5 (What-If Simulator)
        proj_rev = request.projected_revenue
        proj_txns = request.projected_transactions
        est_cost = request.estimated_incentive_cost
        est_roi = request.estimated_roi

        # If projections are not supplied, compute them deterministically using WhatIfSimulationService
        if proj_rev is None or proj_txns is None or est_cost is None or est_roi is None:
            try:
                sim_req = SimulationRequest(
                    target_segment=target_segment,
                    scenario_type=offer_type_str,
                    discount_percent=request.discount_percent or 0.0,
                    cashback_amount=request.cashback_amount or 0.0,
                    minimum_transaction_amount=request.minimum_transaction_amount or 0.0,
                    target_days=request.target_days,
                    target_hours=request.target_hours,
                )

                sim_result = self.what_if_service.simulate_scenario(merchant_id=merchant_id, request=sim_req)
                proj_rev = proj_rev if proj_rev is not None else float(sim_result.projected_revenue)
                proj_txns = proj_txns if proj_txns is not None else int(sim_result.projected_transactions)
                est_cost = est_cost if est_cost is not None else float(sim_result.estimated_incentive_cost)
                est_roi = est_roi if est_roi is not None else sim_result.estimated_roi

            except Exception as e:
                logger.warning(f"Could not auto-simulate baseline projections: {e}")
                proj_rev = proj_rev or 0.0
                proj_txns = proj_txns or 0.0
                est_cost = est_cost or 0.0
                est_roi = est_roi or 0.0


        self._assert_finite_numbers(
            projected_revenue=proj_rev,
            projected_transactions=proj_txns,
            estimated_incentive_cost=est_cost,
            estimated_roi=est_roi,
        )

        # 6. Construct and persist Campaign model
        campaign_id = f"cmp-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        initial_status = CampaignStatus.PENDING_APPROVAL.value

        campaign = Campaign(
            campaign_id=campaign_id,
            merchant_id=merchant_id,
            name=request.name.strip(),
            description=request.description.strip() if request.description else None,
            target_segment=target_segment,
            offer_type=offer_type_str,
            offer_value=request.discount_percent or request.cashback_amount or 0.0,
            discount_percent=request.discount_percent,
            cashback_amount=request.cashback_amount,
            minimum_transaction_amount=request.minimum_transaction_amount,
            min_transaction=request.minimum_transaction_amount,
            target_days=request.target_days,
            target_hours=request.target_hours,
            start_date=request.start_date,
            end_date=request.end_date,
            status=initial_status,
            source_recommendation_id=request.source_recommendation_id,
            source_simulation_id=request.source_simulation_id,
            projected_revenue=proj_rev,
            projected_transactions=proj_txns,
            estimated_incentive_cost=est_cost,
            estimated_cost=est_cost,
            estimated_roi=est_roi,
            created_by=request.created_by or "merchant",
            created_at=now,
        )

        persisted = self.campaign_repo.create_campaign(campaign)

        # 7. Record CREATE audit log
        self.campaign_repo.create_audit_log(
            campaign_id=campaign_id,
            merchant_id=merchant_id,
            action=CampaignAuditAction.CREATE.value,
            previous_status=None,
            new_status=initial_status,
            actor=request.created_by or "merchant",
            reason="Campaign draft created and queued for merchant approval.",
        )

        logger.info(f"Created campaign '{campaign_id}' in PENDING_APPROVAL for merchant '{merchant_id}'.")
        return self._to_campaign_response(persisted)


    # -------------------------------------------------------------------------
    # 2. Campaign Approval (Human-in-the-Loop)
    # -------------------------------------------------------------------------

    def approve_campaign(
        self,
        campaign_id: str,
        merchant_id: str,
        request: Optional[CampaignApproveRequest] = None,
    ) -> CampaignResponse:
        """
        Explicitly approve a campaign in PENDING_APPROVAL state.
        Transitions state: PENDING_APPROVAL -> APPROVED.
        Approval DOES NOT execute the campaign.
        """
        campaign = self.campaign_repo.get_campaign(campaign_id=campaign_id, merchant_id=merchant_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign '{campaign_id}' not found for merchant '{merchant_id}'.",
            )

        # State transition validation
        if campaign.status == CampaignStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Campaign '{campaign_id}' has already been approved.",
            )
        if campaign.status == CampaignStatus.REJECTED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot approve campaign '{campaign_id}' because it has already been rejected.",
            )
        if campaign.status in (
            CampaignStatus.EXECUTING.value,
            CampaignStatus.COMPLETED.value,
            CampaignStatus.VALIDATING.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot approve campaign '{campaign_id}' with active or completed execution status '{campaign.status}'.",
            )
        if campaign.status != CampaignStatus.PENDING_APPROVAL.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot approve campaign in state '{campaign.status}'. Must be in PENDING_APPROVAL state.",
            )

        # Pre-approval business validation
        self._validate_campaign_business_rules(
            merchant_id=campaign.merchant_id,
            target_segment=campaign.target_segment,
            offer_type=campaign.offer_type,
            discount_percent=campaign.discount_percent,
            cashback_amount=campaign.cashback_amount,
            minimum_transaction_amount=campaign.minimum_transaction_amount,
            start_date=campaign.start_date,
            end_date=campaign.end_date,
        )

        prev_status = campaign.status
        actor = (
            request.actor
            if request and request.actor
            else (request.approved_by if request and request.approved_by else None)
        ) or "merchant"
        now = datetime.now(timezone.utc)

        campaign.status = CampaignStatus.APPROVED.value
        campaign.approved_at = now
        campaign.approved_by = actor

        updated = self.campaign_repo.update_campaign(campaign)

        # Record APPROVE audit log
        self.campaign_repo.create_audit_log(
            campaign_id=campaign_id,
            merchant_id=merchant_id,
            action=CampaignAuditAction.APPROVE.value,
            previous_status=prev_status,
            new_status=CampaignStatus.APPROVED.value,
            actor=actor,
            reason="Merchant verified and explicitly approved campaign.",
        )

        logger.info(f"Campaign '{campaign_id}' successfully approved by '{actor}'. Ready for safe execution.")
        return self._to_campaign_response(updated)

    # -------------------------------------------------------------------------
    # 3. Campaign Rejection
    # -------------------------------------------------------------------------

    def reject_campaign(
        self,
        campaign_id: str,
        merchant_id: str,
        request: Optional[CampaignRejectRequest] = None,
    ) -> CampaignResponse:
        """
        Reject a campaign in PENDING_APPROVAL state.
        Transitions state: PENDING_APPROVAL -> REJECTED.
        Persists rejection reason and audit entry.
        """
        campaign = self.campaign_repo.get_campaign(campaign_id=campaign_id, merchant_id=merchant_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign '{campaign_id}' not found for merchant '{merchant_id}'.",
            )

        if campaign.status == CampaignStatus.REJECTED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Campaign '{campaign_id}' has already been rejected.",
            )
        if campaign.status == CampaignStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot reject campaign '{campaign_id}' because it has already been approved.",
            )
        if campaign.status in (
            CampaignStatus.EXECUTING.value,
            CampaignStatus.COMPLETED.value,
            CampaignStatus.VALIDATING.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot reject campaign '{campaign_id}' with status '{campaign.status}'.",
            )
        if campaign.status != CampaignStatus.PENDING_APPROVAL.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot reject campaign in state '{campaign.status}'. Must be in PENDING_APPROVAL state.",
            )

        prev_status = campaign.status
        actor = (request.actor if request else None) or "merchant"
        reason = (request.reason if request else None) or "Rejected by merchant."
        now = datetime.now(timezone.utc)

        campaign.status = CampaignStatus.REJECTED.value
        campaign.rejected_at = now
        campaign.rejection_reason = reason

        updated = self.campaign_repo.update_campaign(campaign)

        # Record REJECT audit log
        self.campaign_repo.create_audit_log(
            campaign_id=campaign_id,
            merchant_id=merchant_id,
            action=CampaignAuditAction.REJECT.value,
            previous_status=prev_status,
            new_status=CampaignStatus.REJECTED.value,
            actor=actor,
            reason=reason,
        )

        logger.info(f"Campaign '{campaign_id}' rejected by '{actor}'. Reason: {reason}")
        return self._to_campaign_response(updated)

    # -------------------------------------------------------------------------
    # 4. Campaign Execution (Safe Simulated Action)
    # -------------------------------------------------------------------------

    def execute_campaign(
        self,
        campaign_id: str,
        merchant_id: str,
        request: Optional[CampaignExecuteRequest] = None,
    ) -> CampaignResultResponse:
        """
        Execute an approved campaign in a safe simulated manner.
        Allowed ONLY when status is APPROVED.
        Transitions:
          APPROVED -> VALIDATING -> EXECUTING -> COMPLETED
        Does NOT contact real Paytm APIs or external messaging services.
        Generates deterministic synthetic demo results.
        """
        campaign = self.campaign_repo.get_campaign(campaign_id=campaign_id, merchant_id=merchant_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign '{campaign_id}' not found for merchant '{merchant_id}'.",
            )

        # Safety boundary checks
        if campaign.status == CampaignStatus.PENDING_APPROVAL.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Campaign '{campaign_id}' is pending approval and cannot be executed without merchant approval.",
            )
        if campaign.status == CampaignStatus.REJECTED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot execute rejected campaign '{campaign_id}'.",
            )
        if campaign.status == CampaignStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Campaign '{campaign_id}' has already been executed and completed.",
            )
        if campaign.status != CampaignStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Campaign '{campaign_id}' must be in APPROVED state to execute. Current status: '{campaign.status}'.",
            )

        actor = (request.actor if request else None) or "merchant"
        now = datetime.now(timezone.utc)

        # 1. Transition to VALIDATING
        campaign.status = CampaignStatus.VALIDATING.value
        self.campaign_repo.update_campaign(campaign)
        self.campaign_repo.create_audit_log(
            campaign_id=campaign_id,
            merchant_id=merchant_id,
            action=CampaignAuditAction.VALIDATE.value,
            previous_status=CampaignStatus.APPROVED.value,
            new_status=CampaignStatus.VALIDATING.value,
            actor=actor,
            reason="Pre-execution integrity validation initiated.",
        )

        # 2. Re-validate parameters before execution
        self._validate_campaign_business_rules(
            merchant_id=campaign.merchant_id,
            target_segment=campaign.target_segment,
            offer_type=campaign.offer_type,
            discount_percent=campaign.discount_percent,
            cashback_amount=campaign.cashback_amount,
            minimum_transaction_amount=campaign.minimum_transaction_amount,
            start_date=campaign.start_date,
            end_date=campaign.end_date,
        )

        # 2b. Trigger n8n workflow (best-effort; does NOT override simulation results)
        #     Safety invariant: only APPROVED campaigns reach this point.
        n8n_result = None
        try:
            n8n = get_n8n_client()
            # Determine approximate target count from segment (rough estimate for payload)
            from app.services.customer_service import CustomerService
            _cs = CustomerService(self.db)
            try:
                _seg_data = _cs.get_segment_summary(merchant_id=merchant_id)
                _seg_counts = {s.get("segment", ""): s.get("count", 0) for s in (_seg_data.get("segments") or [])}
                _target_count = _seg_counts.get(campaign.target_segment, 0) or 0
            except Exception:
                _target_count = 0

            n8n_result = n8n.trigger_campaign(
                campaign_id=campaign_id,
                merchant_id=merchant_id,
                campaign_status=CampaignStatus.APPROVED.value,  # Safety: always pass literal APPROVED
                offer_type=campaign.offer_type,
                target_segment=campaign.target_segment,
                cashback_amount=float(campaign.cashback_amount) if campaign.cashback_amount else None,
                discount_percent=float(campaign.discount_percent) if campaign.discount_percent else None,
                minimum_transaction_amount=float(campaign.minimum_transaction_amount or 0),
                target_count=_target_count,
                campaign_name=campaign.name or "",
                campaign_description=campaign.description,
                target_days=campaign.target_days,
                target_hours=campaign.target_hours,
                marketing_copy_headline=getattr(campaign, "marketing_copy_headline", None),
                marketing_copy_body=getattr(campaign, "marketing_copy_body", None),
            )
            if n8n_result.success:
                logger.info(
                    f"n8n workflow triggered for campaign '{campaign_id}': "
                    f"targeted={n8n_result.targeted}, delivered={n8n_result.delivered}."
                )
            else:
                logger.warning(
                    f"n8n trigger failed for campaign '{campaign_id}': {n8n_result.error}. "
                    f"Continuing with internal simulation."
                )
        except Exception as _n8n_err:  # noqa: BLE001
            logger.warning(
                f"n8n integration error for campaign '{campaign_id}' (non-fatal): {_n8n_err}. "
                f"Proceeding with internal simulation."
            )


        # 3. Transition to EXECUTING
        campaign.status = CampaignStatus.EXECUTING.value
        self.campaign_repo.update_campaign(campaign)
        self.campaign_repo.create_audit_log(
            campaign_id=campaign_id,
            merchant_id=merchant_id,
            action=CampaignAuditAction.EXECUTE.value,
            previous_status=CampaignStatus.VALIDATING.value,
            new_status=CampaignStatus.EXECUTING.value,
            actor=actor,
            reason="Campaign execution triggered in safe simulated environment.",
        )

        # 4. Generate deterministic simulated execution results based on Module 5 projections
        sim_txns = float(campaign.projected_transactions or 0.0)
        sim_rev = float(campaign.projected_revenue or 0.0)
        sim_cost = float(campaign.estimated_incentive_cost or campaign.estimated_cost or 0.0)
        sim_roi = float(campaign.estimated_roi) if campaign.estimated_roi is not None else None

        # If campaign lacked projections, run WhatIfSimulationService to compute exact numbers
        if sim_rev == 0.0 and sim_txns == 0.0:
            try:
                sim_req = SimulationRequest(
                    target_segment=campaign.target_segment,
                    scenario_type=campaign.offer_type,
                    discount_percent=float(campaign.discount_percent or 0.0),
                    cashback_amount=float(campaign.cashback_amount or 0.0),
                    minimum_transaction_amount=float(campaign.minimum_transaction_amount or 0.0),
                    target_days=campaign.target_days,
                    target_hours=campaign.target_hours,
                )
                sim_scenario = self.what_if_service.simulate_scenario(
                    merchant_id=merchant_id, request=sim_req
                )

                sim_txns = float(sim_scenario.projected_transactions)
                sim_rev = float(sim_scenario.projected_revenue)
                sim_cost = float(sim_scenario.estimated_incentive_cost)
                sim_roi = sim_scenario.estimated_roi
            except Exception as e:
                logger.warning(f"Failed to calculate simulation scenario for execution: {e}")

        # Compute net impact and incremental values
        sim_net_impact = float(sim_rev) - float(sim_cost)
        inc_rev = max(0.0, float(sim_rev) * 0.15) if sim_rev > 0 else 0.0  # Synthetic incremental bump


        self._assert_finite_numbers(
            sim_txns=sim_txns,
            sim_rev=sim_rev,
            sim_cost=sim_cost,
            sim_roi=sim_roi,
            sim_net_impact=sim_net_impact,
        )

        # 5. Transition to COMPLETED and persist results
        campaign.status = CampaignStatus.COMPLETED.value
        campaign.executed_at = now
        campaign.simulated_transactions = round(float(sim_txns), 1)
        campaign.simulated_revenue = round(float(sim_rev), 2)
        campaign.simulated_cost = round(float(sim_cost), 2)
        campaign.simulated_net_impact = round(float(sim_net_impact), 2)
        campaign.simulated_roi = round(float(sim_roi), 2) if sim_roi is not None else None


        # Populate legacy columns for backward compatibility
        campaign.actual_txn_count = int(sim_txns)
        campaign.actual_revenue = round(float(sim_rev), 2)
        campaign.estimated_cost = round(float(sim_cost), 2)

        updated = self.campaign_repo.update_campaign(campaign)

        # Record COMPLETE audit log
        self.campaign_repo.create_audit_log(
            campaign_id=campaign_id,
            merchant_id=merchant_id,
            action=CampaignAuditAction.COMPLETE.value,
            previous_status=CampaignStatus.EXECUTING.value,
            new_status=CampaignStatus.COMPLETED.value,
            actor="system",
            reason="Safe simulated campaign action executed successfully. Performance recorded.",
        )

        logger.info(
            f"Simulated execution for campaign '{campaign_id}' completed. "
            f"Revenue: INR {updated.simulated_revenue:,.2f}, Transactions: {updated.simulated_transactions}"
        )


        return self._to_campaign_result_response(updated, inc_rev)

    # -------------------------------------------------------------------------
    # 5. Campaign Query & Result Endpoints
    # -------------------------------------------------------------------------

    def get_campaign(self, campaign_id: str, merchant_id: str) -> CampaignResponse:
        """Fetch campaign details for a specific merchant."""
        campaign = self.campaign_repo.get_campaign(campaign_id=campaign_id, merchant_id=merchant_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign '{campaign_id}' not found for merchant '{merchant_id}'.",
            )
        return self._to_campaign_response(campaign)

    def get_campaign_result(self, campaign_id: str, merchant_id: str) -> CampaignResultResponse:
        """
        Fetch execution results for a campaign.
        Raises HTTP 400 if campaign has not completed execution yet.
        """
        campaign = self.campaign_repo.get_campaign(campaign_id=campaign_id, merchant_id=merchant_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign '{campaign_id}' not found for merchant '{merchant_id}'.",
            )

        if campaign.status != CampaignStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Campaign '{campaign_id}' has not executed yet. Current status: '{campaign.status}'.",
            )

        inc_rev = max(0.0, float(campaign.simulated_revenue or 0.0) * 0.15)
        return self._to_campaign_result_response(campaign, inc_rev)


    def list_campaigns(
        self,
        merchant_id: str,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> CampaignListResponse:
        """List campaigns belonging exclusively to the specified merchant."""
        if not merchant_id or not merchant_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Merchant ID cannot be empty.",
            )

        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be between 1 and 100.",
            )

        campaigns = self.campaign_repo.list_campaigns(
            merchant_id=merchant_id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )

        items = [self._to_campaign_response(c) for c in campaigns]
        return CampaignListResponse(
            merchant_id=merchant_id,
            total_campaigns=len(items),
            total_count=len(items),
            status_filter=status_filter,
            campaigns=items,
        )

    def get_audit_history(
        self, campaign_id: str, merchant_id: str
    ) -> CampaignAuditHistoryResponse:
        """
        Fetch chronological audit history for a campaign, enforcing merchant isolation.
        """
        # First verify campaign belongs to merchant
        campaign = self.campaign_repo.get_campaign(campaign_id=campaign_id, merchant_id=merchant_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign '{campaign_id}' not found for merchant '{merchant_id}'.",
            )

        logs = self.campaign_repo.get_audit_logs(campaign_id=campaign_id, merchant_id=merchant_id)
        events = [
            CampaignAuditLogResponse(
                id=log.id,
                campaign_id=log.campaign_id,
                merchant_id=log.merchant_id,
                action=log.action,
                previous_status=log.previous_status,
                new_status=log.new_status,
                actor=log.actor,
                reason=log.reason,
                created_at=log.created_at,
            )
            for log in logs
        ]

        return CampaignAuditHistoryResponse(
            campaign_id=campaign_id,
            merchant_id=merchant_id,
            total_audit_events=len(events),
            total_events=len(events),
            events=events,
            audit_logs=events,
        )

    def cancel_campaign(
        self,
        campaign_id: str,
        merchant_id: str,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> CampaignResponse:
        """
        Cancel a campaign that is in PENDING_APPROVAL or APPROVED state.
        Transitions state to CANCELLED.
        """
        campaign = self.campaign_repo.get_campaign(campaign_id=campaign_id, merchant_id=merchant_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign '{campaign_id}' not found for merchant '{merchant_id}'.",
            )

        if campaign.status in (
            CampaignStatus.COMPLETED.value,
            CampaignStatus.EXECUTING.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel campaign '{campaign_id}' with status '{campaign.status}'.",
            )

        if campaign.status == CampaignStatus.CANCELLED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Campaign '{campaign_id}' has already been cancelled.",
            )

        prev_status = campaign.status
        campaign.status = CampaignStatus.CANCELLED.value
        updated = self.campaign_repo.update_campaign(campaign)

        self.campaign_repo.create_audit_log(
            campaign_id=campaign_id,
            merchant_id=merchant_id,
            action=CampaignAuditAction.CANCEL.value,
            previous_status=prev_status,
            new_status=CampaignStatus.CANCELLED.value,
            actor=actor or "merchant",
            reason=reason or "Campaign cancelled by merchant.",
        )

        return self._to_campaign_response(updated)

    # -------------------------------------------------------------------------
    # Schema Conversion Helpers
    # -------------------------------------------------------------------------

    def _to_campaign_response(self, c: Campaign) -> CampaignResponse:
        """Convert a Campaign SQLAlchemy model to CampaignResponse schema."""
        is_completed = (c.status == CampaignStatus.COMPLETED.value)
        sim_txns = (
            int(c.simulated_transactions)
            if (is_completed and c.simulated_transactions is not None)
            else (int(c.actual_txn_count) if (is_completed and c.actual_txn_count is not None) else None)
        )
        sim_rev = (
            float(c.simulated_revenue)
            if (is_completed and c.simulated_revenue is not None)
            else (float(c.actual_revenue) if (is_completed and c.actual_revenue is not None) else None)
        )
        sim_cost = (
            float(c.simulated_cost)
            if (is_completed and c.simulated_cost is not None)
            else (float(c.estimated_cost) if (is_completed and c.estimated_cost is not None) else None)
        )
        sim_net = float(c.simulated_net_impact) if (is_completed and c.simulated_net_impact is not None) else None
        sim_roi = float(c.simulated_roi) if (is_completed and c.simulated_roi is not None) else None

        return CampaignResponse(
            campaign_id=c.campaign_id,
            merchant_id=c.merchant_id,
            name=c.name or f"Campaign {c.campaign_id}",
            description=c.description,
            target_segment=c.target_segment,
            offer_type=c.offer_type,
            discount_percent=c.discount_percent,
            cashback_amount=c.cashback_amount,
            minimum_transaction_amount=float(c.minimum_transaction_amount or c.min_transaction or 0.0),
            target_days=c.target_days,
            target_hours=c.target_hours,
            start_date=c.start_date,
            end_date=c.end_date,
            status=c.status,
            source_recommendation_id=c.source_recommendation_id,
            source_simulation_id=c.source_simulation_id,
            projected_revenue=float(c.projected_revenue or 0.0),
            projected_transactions=int(c.projected_transactions or 0),
            estimated_incentive_cost=float(c.estimated_incentive_cost or c.estimated_cost or 0.0),
            estimated_roi=c.estimated_roi,
            simulated_transactions=sim_txns,
            simulated_revenue=sim_rev,
            simulated_cost=sim_cost,
            simulated_net_impact=sim_net,
            simulated_roi=sim_roi,
            created_at=c.created_at,
            approved_at=c.approved_at,
            executed_at=c.executed_at,
            rejected_at=c.rejected_at,
            rejection_reason=c.rejection_reason,
            created_by=c.created_by or "Merchant",
            approved_by=c.approved_by,
        )



    def _to_campaign_result_response(
        self, c: Campaign, inc_rev: float = 0.0
    ) -> CampaignResultResponse:
        """Convert an executed Campaign model to CampaignResultResponse schema."""
        sim_txns = int(c.simulated_transactions or c.actual_txn_count or 0)
        sim_rev = float(c.simulated_revenue or c.actual_revenue or 0.0)
        sim_cost = float(c.simulated_cost or c.estimated_cost or 0.0)
        sim_net = float(c.simulated_net_impact or (sim_rev - sim_cost))
        roi_val = c.simulated_roi or c.estimated_roi
        roi_label = f"{roi_val:.2f}x" if roi_val is not None else None
        summary_text = (
            f"Synthetic simulation achieved {sim_txns} transactions "
            f"generating ₹{sim_rev:,.2f} revenue with estimated incentive cost "
            f"of ₹{sim_cost:,.2f}."
        )

        return CampaignResultResponse(
            campaign_id=c.campaign_id,
            merchant_id=c.merchant_id,
            status=c.status,
            executed_at=c.executed_at,
            target_segment=c.target_segment,
            offer_type=c.offer_type,
            simulated_transactions=sim_txns,
            simulated_revenue=sim_rev,
            simulated_cost=sim_cost,
            simulated_incremental_revenue=round(inc_rev, 2),
            simulated_net_impact=sim_net,
            simulated_roi=roi_val,
            roi_multiplier_label=roi_label,
            result_summary=summary_text,
            execution_summary=summary_text,
            is_demo_result=True,
            data_type="SYNTHETIC_DEMO",
            disclaimer=(
                "Synthetic / Illustrative Demo Result — Simulated campaign outcome for demonstration only. "
                "No real Paytm campaign APIs were called, and no actual messages or coupons were sent."
            ),
        )

    # -------------------------------------------------------------------------
    # n8n Callback Handler
    # -------------------------------------------------------------------------

    def handle_n8n_callback(
        self,
        campaign_id: str,
        merchant_id: str,
        n8n_status: Optional[str],
        targeted: Optional[int],
        delivered: Optional[int],
        failed: Optional[int],
        execution_mode: Optional[str],
        message: Optional[str],
    ) -> None:
        """
        Process execution-result callback POSTed by the n8n workflow.

        Validates:
          - Campaign exists and belongs to merchant (isolation gate).
          - Campaign is in EXECUTING or COMPLETED state (no state is overridden
            by n8n alone — financial figures remain deterministic).

        Records an informational audit log entry with n8n delivery summary.
        """
        campaign = self.campaign_repo.get_campaign(campaign_id=campaign_id, merchant_id=merchant_id)
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign '{campaign_id}' not found for merchant '{merchant_id}'.",
            )

        # Only accept callback for campaigns that passed through execution
        if campaign.status not in (
            CampaignStatus.COMPLETED.value,
            CampaignStatus.EXECUTING.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot accept n8n callback for campaign '{campaign_id}' "
                    f"with status '{campaign.status}'. Must be EXECUTING or COMPLETED."
                ),
            )

        # Build informational audit note (no financial data modified)
        note_parts = [f"n8n callback received (mode={execution_mode or 'unknown'})."]
        if targeted is not None:
            note_parts.append(f"Targeted: {targeted}.")
        if delivered is not None:
            note_parts.append(f"Delivered: {delivered}.")
        if failed is not None:
            note_parts.append(f"Failed: {failed}.")
        if message:
            note_parts.append(f"n8n message: {message[:200]}")

        self.campaign_repo.create_audit_log(
            campaign_id=campaign_id,
            merchant_id=merchant_id,
            action="N8N_CALLBACK",
            previous_status=campaign.status,
            new_status=campaign.status,
            actor="n8n",
            reason=" ".join(note_parts),
        )

        logger.info(
            f"n8n callback processed for campaign '{campaign_id}' "
            f"(merchant '{merchant_id}'): "
            f"targeted={targeted}, delivered={delivered}, failed={failed}."
        )
