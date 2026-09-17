"""
Health check schemas for system diagnostics and monitoring.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    """Database connectivity status schema."""
    status: str
    dialect: str
    connected: bool
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Overall system health check response schema."""
    status: str = Field(default="ok", description="Overall health status")
    app_name: str
    version: str
    environment: str
    database: DatabaseHealth
    timestamp: datetime
    data_notice: str = Field(
        default="All data in this system is synthetic demo data. It does not represent real Paytm merchant data."
    )
