"""
Expense data model for merchant operational expenses and accounting assistance.
"""

from typing import Optional, TYPE_CHECKING
from datetime import date
from decimal import Decimal
import uuid
from sqlalchemy import String, Numeric, Date, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.merchant import Merchant


class Expense(Base):
    """Expense entity for operational costs and financial tracking."""
    __tablename__ = "expenses"

    expense_id: Mapped[str] = mapped_column(
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
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vendor: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="expenses")

    __table_args__ = (
        Index("idx_merchant_date_category", "merchant_id", "date", "category"),
    )

    def __repr__(self) -> str:
        return f"<Expense(id={self.expense_id}, category={self.category}, amount={self.amount})>"
