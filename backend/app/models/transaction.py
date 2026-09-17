"""
Transaction data model representing a payment or sales transaction.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone
from decimal import Decimal
import uuid
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant
    from app.models.customer import Customer


class Transaction(Base):
    """Payment transaction entity."""
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(
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
    customer_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("customers.customer_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), default="UPI", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False, index=True)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="transactions")
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="transactions")

    __table_args__ = (
        Index("idx_merchant_timestamp", "merchant_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<Transaction(id={self.transaction_id}, merchant={self.merchant_id}, amount={self.amount})>"
