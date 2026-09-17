"""
Campaign data models for promotional growth strategies, merchant-approved campaigns,
state machine lifecycles, and audit trails.
"""

from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, timezone
from decimal import Decimal
import uuid
from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant


class Campaign(Base):
    """Marketing and re-engagement campaign entity with strict human-in-the-loop lifecycle."""
    __tablename__ = "campaigns"

    campaign_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("merchants.merchant_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    target_segment: Mapped[str] = mapped_column(String(50), nullable=False)
    offer_type: Mapped[str] = mapped_column(String(50), default="fixed_cashback", nullable=False)
    offer_value: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"), nullable=False)
    discount_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    cashback_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    min_transaction: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"), nullable=False)
    minimum_transaction_amount: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"), nullable=True)
    target_days: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_hours: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # State machine lifecycle: DRAFT, PENDING_APPROVAL, APPROVED, REJECTED, VALIDATING, EXECUTING, COMPLETED, FAILED
    status: Mapped[str] = mapped_column(String(30), default="PENDING_APPROVAL", nullable=False, index=True)

    # Source references to Module 4 & 5
    source_recommendation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    source_simulation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Pre-execution projections (Module 5)
    projected_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=True)
    projected_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    estimated_incentive_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=True)
    estimated_roi: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)

    # Post-execution simulated results
    actual_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    actual_txn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    simulated_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=True)
    simulated_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    simulated_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=True)
    simulated_net_impact: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=True)
    simulated_roi: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)

    # Lifecycle Timestamps & Actors
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), default="Merchant", nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="campaigns")
    audit_logs: Mapped[List["CampaignAuditLog"]] = relationship(
        "CampaignAuditLog",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignAuditLog.created_at"
    )

    __table_args__ = (
        Index("idx_merchant_campaign_status", "merchant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Campaign(id={self.campaign_id}, target={self.target_segment}, status={self.status})>"


class CampaignAuditLog(Base):
    """Immutable audit log tracking all sensitive state transitions and merchant actions."""
    __tablename__ = "campaign_audit_logs"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    campaign_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("campaigns.campaign_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    merchant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("merchants.merchant_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), default="Merchant", nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="audit_logs")
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="campaign_audit_logs")

    __table_args__ = (
        Index("idx_campaign_audit_time", "campaign_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<CampaignAuditLog(campaign={self.campaign_id}, action={self.action}, {self.previous_status}->{self.new_status})>"
