"""
Campaign repository for database operations on campaigns and audit logs.
Ensures strict merchant isolation and transaction safety.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.core.logging import logger
from app.repositories.base import BaseRepository
from app.models.campaign import Campaign, CampaignAuditLog


class CampaignRepository(BaseRepository[Campaign]):
    """Repository handling Campaign and CampaignAuditLog operations."""

    def __init__(self, db: Session):
        super().__init__(Campaign, db)

    def create_campaign(self, campaign: Campaign) -> Campaign:
        """Persist a new campaign record."""
        return self.add(campaign)

    def get_campaign(
        self, campaign_id: str, merchant_id: Optional[str] = None
    ) -> Optional[Campaign]:
        """
        Fetch a campaign by its unique campaign_id.
        If merchant_id is provided, enforces strict merchant ownership.
        """
        conditions = [Campaign.campaign_id == campaign_id]
        if merchant_id is not None:
            conditions.append(Campaign.merchant_id == merchant_id)

        stmt = select(Campaign).where(and_(*conditions))
        return self.db.scalars(stmt).first()

    def list_campaigns(
        self,
        merchant_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Campaign]:
        """
        List campaigns for a specific merchant, optionally filtered by status.
        Ordered by created_at descending.
        """
        conditions = [Campaign.merchant_id == merchant_id]
        if status:
            conditions.append(Campaign.status == status)

        stmt = (
            select(Campaign)
            .where(and_(*conditions))
            .order_by(Campaign.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def update_campaign(self, campaign: Campaign) -> Campaign:
        """Flush and refresh an updated campaign record."""
        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def create_audit_log(
        self,
        campaign_id: str,
        merchant_id: str,
        action: str,
        previous_status: Optional[str],
        new_status: str,
        actor: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> CampaignAuditLog:
        """Record an immutable audit log entry for a campaign lifecycle transition."""
        audit_entry = CampaignAuditLog(
            campaign_id=campaign_id,
            merchant_id=merchant_id,
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            actor=actor or "merchant",
            reason=reason,
        )
        self.db.add(audit_entry)
        self.db.commit()
        self.db.refresh(audit_entry)
        logger.info(
            f"Recorded audit log for campaign '{campaign_id}': "
            f"{previous_status} -> {new_status} (action: {action})"
        )
        return audit_entry

    def get_audit_logs(
        self, campaign_id: str, merchant_id: Optional[str] = None
    ) -> List[CampaignAuditLog]:
        """
        Fetch chronological audit history for a campaign.
        Enforces merchant isolation if merchant_id is supplied.
        """
        conditions = [CampaignAuditLog.campaign_id == campaign_id]
        if merchant_id is not None:
            conditions.append(CampaignAuditLog.merchant_id == merchant_id)

        stmt = (
            select(CampaignAuditLog)
            .where(and_(*conditions))
            .order_by(CampaignAuditLog.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())
