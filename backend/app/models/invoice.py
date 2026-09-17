"""
Invoice data model representing vendor bills and supplier invoices.
"""

from typing import Optional, TYPE_CHECKING
from datetime import date
from decimal import Decimal
import uuid
from sqlalchemy import String, Numeric, Date, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant


class Invoice(Base):
    """Vendor invoice entity for bookkeeping and payable tracking."""
    __tablename__ = "invoices"

    invoice_id: Mapped[str] = mapped_column(
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
    vendor: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="invoices")

    __table_args__ = (
        Index("idx_merchant_invoice_status", "merchant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Invoice(id={self.invoice_id}, vendor={self.vendor}, amount={self.amount}, status={self.status})>"
