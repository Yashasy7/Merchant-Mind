"""
Models package initialization.
Exports all SQLAlchemy models for metadata registration and clean imports.
"""

from app.core.database import Base
from app.models.base import TimestampMixin, utc_now
from app.models.merchant import Merchant
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.expense import Expense
from app.models.invoice import Invoice
from app.models.campaign import Campaign

__all__ = [
    "Base",
    "TimestampMixin",
    "utc_now",
    "Merchant",
    "Customer",
    "Transaction",
    "Expense",
    "Invoice",
    "Campaign",
]
