"""
Customer data model representing a merchant's customer profile and segment.
"""

from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, timezone
from decimal import Decimal
import uuid
from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.transaction import Transaction


class Customer(Base):
    """Customer entity with spend aggregations and segmentation tags."""
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(
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
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    transaction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    last_transaction: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    average_transaction: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    segment: Mapped[str] = mapped_column(String(30), default="New", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="customers")
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        back_populates="customer",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Customer(id={self.customer_id}, merchant={self.merchant_id}, segment={self.segment})>"
