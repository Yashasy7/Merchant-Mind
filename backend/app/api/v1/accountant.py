"""
AI Accountant API endpoints under /api/v1/accountant.
Provides RESTful access to P&L statements, operational expense breakdowns,
income vs expense trends, period comparisons, vendor invoices, and financial insights.
Strictly merchant-isolated with deterministic calculations.
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.services.accountant_service import AccountantService
from app.schemas.accountant import (
    AccountantSummaryResponse,
    ProfitLossResponse,
    ExpensesBreakdownResponse,
    PeriodComparisonResponse,
    IncomeVsExpenseResponse,
    InvoiceSummaryResponse,
    FinancialInsightsResponse,
)

router = APIRouter(tags=["AI Accountant"])
settings = get_settings()


def resolve_merchant_id(merchant_id: Optional[str]) -> str:
    """Resolve merchant ID, defaulting to configured DEMO_MERCHANT_ID if omitted."""
    return (
        merchant_id.strip()
        if merchant_id and merchant_id.strip()
        else settings.demo_merchant_id
    )


def validate_date_range(start_date: Optional[date], end_date: Optional[date]) -> None:
    """Validate that start_date does not exceed end_date."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date range: start_date ({start_date}) cannot be after end_date ({end_date}).",
        )


@router.get(
    "/summary",
    response_model=AccountantSummaryResponse,
    summary="Get Unified Accountant Summary",
    description=(
        "Returns complete financial health summary for merchant Screen 7 and AI Copilot. "
        "Includes P&L, expense category breakdown, anomaly alerts, vendor invoices, and insights."
    ),
)
def get_accountant_summary(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> AccountantSummaryResponse:
    validate_date_range(start_date, end_date)
    m_id = resolve_merchant_id(merchant_id)
    service = AccountantService(db)
    return service.get_accountant_summary(merchant_id=m_id, start_date=start_date, end_date=end_date)


@router.get(
    "/profit-loss",
    response_model=ProfitLossResponse,
    summary="Get Profit and Loss Statement",
    description="Returns deterministic revenue, expenses, net operating profit, and operating margin %.",
)
def get_profit_loss(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> ProfitLossResponse:
    validate_date_range(start_date, end_date)
    m_id = resolve_merchant_id(merchant_id)
    service = AccountantService(db)
    return service.get_profit_loss(merchant_id=m_id, start_date=start_date, end_date=end_date)


@router.get(
    "/expenses",
    response_model=ExpensesBreakdownResponse,
    summary="Get Expenses Breakdown & Anomalies",
    description="Returns categorized operational expenses, top spending category, and anomaly alerts.",
)
def get_expenses_breakdown(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> ExpensesBreakdownResponse:
    validate_date_range(start_date, end_date)
    m_id = resolve_merchant_id(merchant_id)
    service = AccountantService(db)
    return service.get_expenses_breakdown(merchant_id=m_id, start_date=start_date, end_date=end_date)


@router.get(
    "/income-vs-expense",
    response_model=IncomeVsExpenseResponse,
    summary="Get Income vs Expense Trend",
    description="Returns periodic trend data comparing revenue vs expenses over time.",
)
def get_income_vs_expense(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    months: int = Query(3, ge=1, le=12, description="Number of lookback months"),
    db: Session = Depends(get_db),
) -> IncomeVsExpenseResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = AccountantService(db)
    return service.get_income_vs_expense(merchant_id=m_id, months=months)


@router.get(
    "/comparison",
    response_model=PeriodComparisonResponse,
    summary="Get Period-over-Period Comparison",
    description="Compares financial performance of the current period against the preceding equivalent period.",
)
def get_period_comparison(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    current_days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    db: Session = Depends(get_db),
) -> PeriodComparisonResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = AccountantService(db)
    return service.get_period_comparison(merchant_id=m_id, current_days=current_days)


@router.get(
    "/invoices",
    response_model=InvoiceSummaryResponse,
    summary="Get Vendor Invoices Summary",
    description="Returns vendor invoices, payment status (paid/pending), and payable commitments.",
)
def get_invoices_summary(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    status: Optional[str] = Query(None, description="Filter by invoice status: paid | pending"),
    db: Session = Depends(get_db),
) -> InvoiceSummaryResponse:
    m_id = resolve_merchant_id(merchant_id)
    service = AccountantService(db)
    return service.get_invoices_summary(merchant_id=m_id, status_filter=status)


@router.get(
    "/insights",
    response_model=FinancialInsightsResponse,
    summary="Get Financial Intelligence Insights",
    description="Returns actionable, deterministic insights on profitability, expenses, anomalies, and cash flow.",
)
def get_financial_insights(
    merchant_id: Optional[str] = Query(None, description="Merchant ID (defaults to demo merchant)"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> FinancialInsightsResponse:
    validate_date_range(start_date, end_date)
    m_id = resolve_merchant_id(merchant_id)
    service = AccountantService(db)
    return service.get_financial_insights(merchant_id=m_id, start_date=start_date, end_date=end_date)
