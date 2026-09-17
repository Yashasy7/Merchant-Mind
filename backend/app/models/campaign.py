"""
Campaign data model for growth strategies, merchant-approved promotions, and simulated results.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone
from decimal import Decimal
import uuid
from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant


class Campaign(Base):
    """Marketing and re-engagement campaign entity."""
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
    target_segment: Mapped[str] = mapped_column(String(50), nullable=False)
    offer_type: Mapped[str] = mapped_column(String(50), default="cashback", nullable=False)
    offer_value: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    min_transaction: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"), nullable=False)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    actual_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    actual_txn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="campaigns")

    __table_args__ = (
        Index("idx_merchant_campaign_status", "merchant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Campaign(id={self.campaign_id}, target={self.target_segment}, status={self.status})>"
