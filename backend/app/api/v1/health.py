"""
Health check route handler for monitoring system status and dependencies.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, status
from app.core.config import get_settings
from app.core.database import check_db_connection
from app.schemas.health import HealthResponse, DatabaseHealth

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health Diagnostics",
    description="Returns backend running state, environment info, and database connectivity."
)
async def get_health() -> HealthResponse:
    """Check and return system operational status."""
    db_status = check_db_connection()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version="1.0.0",
        environment=settings.app_env,
        database=DatabaseHealth(**db_status),
        timestamp=datetime.now(timezone.utc),
        data_notice="All data in this system is synthetic demo data. It does not represent real Paytm merchant data."
    )
