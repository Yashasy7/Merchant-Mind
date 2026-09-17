"""
Merchant request and response validation schemas.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MerchantBase(BaseModel):
    business_name: str
    business_type: str
    location: str
    business_age: int


class MerchantCreate(MerchantBase):
    pass


class MerchantResponse(MerchantBase):
    merchant_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
