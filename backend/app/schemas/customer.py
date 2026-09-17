"""
Customer and Transaction foundational validation schemas.
"""

from datetime import datetime
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class CustomerResponse(BaseModel):
    customer_id: str
    merchant_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    transaction_count: int
    total_spend: Decimal
    last_transaction: Optional[datetime] = None
    average_transaction: Decimal
    segment: str

    model_config = ConfigDict(from_attributes=True)


class TransactionResponse(BaseModel):
    transaction_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    timestamp: datetime
    amount: Decimal
    payment_method: str
    status: str

    model_config = ConfigDict(from_attributes=True)
