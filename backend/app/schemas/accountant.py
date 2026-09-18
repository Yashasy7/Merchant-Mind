"""
Pydantic schemas for Module 8: AI Accountant / Financial Intelligence.
Provides strongly-typed, Decimal-safe models for P&L, expense breakdowns,
anomalies, income vs expenses, invoices, and financial insights.
"""

from typing import List, Optional
from datetime import date
from pydantic import BaseModel, Field, ConfigDict


ACCOUNTING_DISCLAIMER = (
    "MerchantMind AI Accountant provides financial organization and decision assistance. "
    "It does not replace a Certified Accountant or Chartered Accountant (CA). "
    "All figures are calculated deterministically from synthetic demo records."
)


class ExpenseItemResponse(BaseModel):
    """Individual operational expense record."""
    expense_id: str
    merchant_id: str
    date: date
    category: str
    amount: float
    vendor: str
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ExpenseCategoryBreakdown(BaseModel):
    """Breakdown of expenses for a specific category."""
    category: str
    total_amount: float
    percentage_of_total: float
    expense_count: int

    model_config = ConfigDict(from_attributes=True)


class ExpenseAnomaly(BaseModel):
    """Detected expense anomaly (e.g. utility spike over baseline)."""
    category: str
    current_amount: float
    baseline_amount: float
    change_percentage: float
    is_anomaly: bool
    message: str

    model_config = ConfigDict(from_attributes=True)


class ExpensesBreakdownResponse(BaseModel):
    """Categorized operational expenses breakdown and anomaly alerts."""
    merchant_id: str
    total_expenses: float
    expense_count: int
    top_category: Optional[str] = None
    categories: List[ExpenseCategoryBreakdown] = Field(default_factory=list)
    anomalies: List[ExpenseAnomaly] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    disclaimer: str = Field(default=ACCOUNTING_DISCLAIMER)

    model_config = ConfigDict(from_attributes=True)


class ProfitLossResponse(BaseModel):
    """Core P&L statement metrics and operating profit margin."""
    merchant_id: str
    total_revenue: float
    total_expenses: float
    net_profit: float
    operating_margin_pct: float
    transaction_count: int
    expense_count: int
    is_profitable: bool
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    disclaimer: str = Field(default=ACCOUNTING_DISCLAIMER)

    model_config = ConfigDict(from_attributes=True)


class PeriodComparisonResponse(BaseModel):
    """Comparison between current period and equivalent previous period."""
    merchant_id: str
    current_period: ProfitLossResponse
    previous_period: ProfitLossResponse
    revenue_change_pct: float
    expense_change_pct: float
    profit_change_pct: float
    margin_change_pct: float
    disclaimer: str = Field(default=ACCOUNTING_DISCLAIMER)

    model_config = ConfigDict(from_attributes=True)


class IncomeVsExpensePoint(BaseModel):
    """Periodic bucket comparing income and expenses."""
    period: str
    income: float
    expense: float
    net_profit: float

    model_config = ConfigDict(from_attributes=True)


class IncomeVsExpenseResponse(BaseModel):
    """Time-series comparative analysis of revenue vs expenses."""
    merchant_id: str
    total_income: float
    total_expense: float
    net_profit: float
    points: List[IncomeVsExpensePoint] = Field(default_factory=list)
    disclaimer: str = Field(default=ACCOUNTING_DISCLAIMER)

    model_config = ConfigDict(from_attributes=True)


class InvoiceItemResponse(BaseModel):
    """Vendor invoice record."""
    invoice_id: str
    merchant_id: str
    vendor: str
    amount: float
    date: Optional[str] = None
    due_date: Optional[str] = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class InvoiceSummaryResponse(BaseModel):
    """Summary of vendor supplier invoices and payment statuses."""
    merchant_id: str
    total_invoices: int
    total_amount: float
    paid_amount: float
    pending_amount: float
    paid_count: int
    pending_count: int
    invoices: List[InvoiceItemResponse] = Field(default_factory=list)
    disclaimer: str = Field(default=ACCOUNTING_DISCLAIMER)

    model_config = ConfigDict(from_attributes=True)


class FinancialInsight(BaseModel):
    """Structured deterministic financial observation and recommendation."""
    insight_type: str
    observation: str
    impact_level: str = "medium"  # low | medium | high
    recommendation: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FinancialInsightsResponse(BaseModel):
    """List of actionable financial intelligence insights."""
    merchant_id: str
    insights: List[FinancialInsight] = Field(default_factory=list)
    summary: str
    disclaimer: str = Field(default=ACCOUNTING_DISCLAIMER)

    model_config = ConfigDict(from_attributes=True)


class AccountantSummaryResponse(BaseModel):
    """Unified financial dashboard summary for merchant Screen 7 and AI Copilot."""
    merchant_id: str
    profit_loss: ProfitLossResponse
    expenses: ExpensesBreakdownResponse
    invoices: InvoiceSummaryResponse
    insights: List[FinancialInsight] = Field(default_factory=list)
    ai_narrative: Optional[str] = None
    disclaimer: str = Field(default=ACCOUNTING_DISCLAIMER)

    model_config = ConfigDict(from_attributes=True)
