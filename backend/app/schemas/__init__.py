"""
Schemas package initialization.
Exports all Pydantic schemas for data transfer and validation.
"""

from app.schemas.health import HealthResponse, DatabaseHealth
from app.schemas.common import APIResponse, ErrorDetail, ErrorResponse
from app.schemas.merchant import MerchantBase, MerchantCreate, MerchantResponse
from app.schemas.customer import CustomerResponse, TransactionResponse
from app.schemas.sales import (
    SalesSummaryResponse,
    SalesTrendPoint,
    SalesTrendsResponse,
    PeriodMetrics,
    SalesComparisonResponse,
    DayOfWeekMetric,
    DayOfWeekAnalysisResponse,
    HourlyMetric,
    TimeWindowMetric,
    HourlyAnalysisResponse,
    WeekendAnalysisResponse,
    SalesInsight,
    SalesInsightsResponse,
)

__all__ = [
    "HealthResponse",
    "DatabaseHealth",
    "APIResponse",
    "ErrorDetail",
    "ErrorResponse",
    "MerchantBase",
    "MerchantCreate",
    "MerchantResponse",
    "CustomerResponse",
    "TransactionResponse",
    "SalesSummaryResponse",
    "SalesTrendPoint",
    "SalesTrendsResponse",
    "PeriodMetrics",
    "SalesComparisonResponse",
    "DayOfWeekMetric",
    "DayOfWeekAnalysisResponse",
    "HourlyMetric",
    "TimeWindowMetric",
    "HourlyAnalysisResponse",
    "WeekendAnalysisResponse",
    "SalesInsight",
    "SalesInsightsResponse",
]
