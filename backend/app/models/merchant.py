"""
Merchant data model representing a registered Paytm merchant.
"""

from typing import List, TYPE_CHECKING
from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.transaction import Transaction
    from app.models.expense import Expense
    from app.models.invoice import Invoice
    from app.models.campaign import Campaign


class Merchant(Base):
    """Merchant entity representing store owner profile."""
    __tablename__ = "merchants"

    merchant_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    business_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    business_age: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    customers: Mapped[List["Customer"]] = relationship(
        "Customer",
        back_populates="merchant",
        cascade="all, delete-orphan"
    )
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        back_populates="merchant",
        cascade="all, delete-orphan"
    )
    expenses: Mapped[List["Expense"]] = relationship(
        "Expense",
        back_populates="merchant",
        cascade="all, delete-orphan"
    )
    invoices: Mapped[List["Invoice"]] = relationship(
        "Invoice",
        back_populates="merchant",
        cascade="all, delete-orphan"
    )
    campaigns: Mapped[List["Campaign"]] = relationship(
        "Campaign",
        back_populates="merchant",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Merchant(id={self.merchant_id}, name={self.business_name}, type={self.business_type})>"
