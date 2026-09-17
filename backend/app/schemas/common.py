"""
Common response envelope schemas and standard error structures.
"""

from typing import Generic, TypeVar, Optional, Any, List
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    """Standard unified response wrapper for API endpoints."""
    success: bool = Field(default=True)
    message: str = Field(default="Operation completed successfully")
    data: Optional[DataT] = None


class ErrorDetail(BaseModel):
    """Detailed error item for validation and business logic exceptions."""
    loc: Optional[List[str]] = None
    msg: str
    type: Optional[str] = None


class ErrorResponse(BaseModel):
    """Unified error response model preventing sensitive stack trace leaks."""
    success: bool = Field(default=False)
    error_code: str
    message: str
    details: Optional[List[Any]] = None
