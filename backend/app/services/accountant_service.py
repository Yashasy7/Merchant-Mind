"""
AI Accountant Service for Module 8.
Provides deterministic, authoritative financial calculations for:
- Revenue, Expenses, Net Operating Profit, and Margins
- Category breakdowns and anomaly detection
- Income vs expense periodic tracking
- Period over period comparisons
- Vendor supplier invoice summaries
- Structured financial intelligence insights

CRITICAL OPERATIONAL RULES:
- All authoritative financial figures are computed deterministically.
- Never returns NaN or Infinity; safe against division by zero and empty periods.
- Enforces multi-merchant isolation on every query.
- Does not replace a Chartered Accountant (CA); strictly assistance/intelligence.
"""

from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import pandas as pd

from app.services.base import BaseService
from app.services.sales_service import SalesService
from app.repositories.expense_repository import ExpenseRepository
from app.schemas.accountant import (
    ACCOUNTING_DISCLAIMER,
    ProfitLossResponse,
    ExpenseCategoryBreakdown,
    ExpenseAnomaly,
    ExpensesBreakdownResponse,
    PeriodComparisonResponse,
    IncomeVsExpensePoint,
    IncomeVsExpenseResponse,
    InvoiceItemResponse,
    InvoiceSummaryResponse,
    FinancialInsight,
    FinancialInsightsResponse,
    AccountantSummaryResponse,
)


class AccountantService(BaseService):
    """Business service handling all AI Accountant calculations and financial analysis."""

    def __init__(self, db: Session):
        super().__init__(db)
        self.sales_service = SalesService(db)
        self.expense_repo = ExpenseRepository(db)

    @staticmethod
    def _safe_pct_change(current: float, previous: float) -> float:
        """Calculate percentage change safely avoiding division by zero or NaN."""
        if previous > 0:
            return round(((current - previous) / previous) * 100.0, 2)
        elif previous == 0 and current > 0:
            return 100.0
        elif previous == 0 and current == 0:
            return 0.0
        return 0.0

    @staticmethod
    def _validate_date_range(start_date: Optional[date], end_date: Optional[date]) -> None:
        """Validate date ordering to reject invalid chronological ranges."""
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Start date ({start_date}) cannot be after end date ({end_date})."
            )

    def get_profit_loss(
        self,
        merchant_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ProfitLossResponse:
        """
        Calculate authoritative Net Operating Profit & Profit Margin.
        Revenue is derived from successful transactions in Module 2.
        Expenses are derived from operational records in ExpenseRepository.
        """
        self._validate_date_range(start_date, end_date)

        # 1. Authoritative revenue from Module 2 SalesService
        sales_summary = self.sales_service.get_summary(
            merchant_id=merchant_id,
            start_date=start_date,
            end_date=end_date,
        )
        total_revenue = round(float(sales_summary.total_revenue), 2)
        txn_count = sales_summary.successful_transactions

        # 2. Authoritative expenses from ExpenseRepository
        df_exp = self.expense_repo.get_expenses_df(
            merchant_id=merchant_id,
            start_date=start_date,
            end_date=end_date,
        )
        total_expenses = round(float(df_exp["amount"].sum()), 2) if not df_exp.empty else 0.0
        exp_count = len(df_exp)

        # 3. Core profit metrics: profit = revenue - expenses
        net_profit = round(total_revenue - total_expenses, 2)
        operating_margin = round((net_profit / total_revenue) * 100.0, 2) if total_revenue > 0 else 0.0
        is_profitable = net_profit > 0

        return ProfitLossResponse(
            merchant_id=merchant_id,
            total_revenue=total_revenue,
            total_expenses=total_expenses,
            net_profit=net_profit,
            operating_margin_pct=operating_margin,
            transaction_count=txn_count,
            expense_count=exp_count,
            is_profitable=is_profitable,
            start_date=str(start_date) if start_date else sales_summary.start_date,
            end_date=str(end_date) if end_date else sales_summary.end_date,
            disclaimer=ACCOUNTING_DISCLAIMER,
        )

    def get_expenses_breakdown(
        self,
        merchant_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ExpensesBreakdownResponse:
        """
        Calculate grouped category expenses, identify the top category,
        and detect operational spending anomalies (e.g. utility spike over baseline).
        """
        self._validate_date_range(start_date, end_date)

        df_exp = self.expense_repo.get_expenses_df(
            merchant_id=merchant_id,
            start_date=start_date,
            end_date=end_date,
        )

        total_expenses = round(float(df_exp["amount"].sum()), 2) if not df_exp.empty else 0.0
        expense_count = len(df_exp)

        if df_exp.empty:
            return ExpensesBreakdownResponse(
                merchant_id=merchant_id,
                total_expenses=0.0,
                expense_count=0,
                top_category=None,
                categories=[],
                anomalies=[],
                start_date=str(start_date) if start_date else None,
                end_date=str(end_date) if end_date else None,
            )

        # Group by category
        categories: List[ExpenseCategoryBreakdown] = []
        for cat_name, cat_group in df_exp.groupby("category"):
            cat_sum = round(float(cat_group["amount"].sum()), 2)
            cat_pct = round((cat_sum / total_expenses) * 100.0, 2) if total_expenses > 0 else 0.0
            categories.append(
                ExpenseCategoryBreakdown(
                    category=str(cat_name),
                    total_amount=cat_sum,
                    percentage_of_total=cat_pct,
                    expense_count=len(cat_group),
                )
            )

        categories.sort(key=lambda c: c.total_amount, reverse=True)
        top_cat = categories[0].category if categories else None

        # Detect category anomalies: compare current period vs baseline lookback
        anomalies: List[ExpenseAnomaly] = []
        days_span = (end_date - start_date).days if (start_date and end_date) else 30
        days_span = max(days_span, 7)

        ref_end = start_date or date.today()
        ref_start = ref_end - timedelta(days=days_span)

        df_prev = self.expense_repo.get_expenses_df(
            merchant_id=merchant_id,
            start_date=ref_start,
            end_date=ref_end - timedelta(days=1),
        )

        for cat in categories:
            prev_sum = 0.0
            if not df_prev.empty:
                prev_cat_df = df_prev[df_prev["category"] == cat.category]
                if not prev_cat_df.empty:
                    prev_sum = round(float(prev_cat_df["amount"].sum()), 2)

            # Anomaly trigger: expense increases by >= 14% over baseline (e.g. electricity/utility spike)
            if prev_sum > 0:
                pct_change = self._safe_pct_change(cat.total_amount, prev_sum)
                if pct_change >= 14.0:
                    anomalies.append(
                        ExpenseAnomaly(
                            category=cat.category,
                            current_amount=cat.total_amount,
                            baseline_amount=prev_sum,
                            change_percentage=pct_change,
                            is_anomaly=True,
                            message=(
                                f"{cat.category} expenses surged by {pct_change}% "
                                f"(₹{cat.total_amount:,.2f} vs ₹{prev_sum:,.2f} baseline). "
                                "Inspect energy consumption or vendor pricing."
                            ),
                        )
                    )

        return ExpensesBreakdownResponse(
            merchant_id=merchant_id,
            total_expenses=total_expenses,
            expense_count=expense_count,
            top_category=top_cat,
            categories=categories,
            anomalies=anomalies,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
        )

    def get_period_comparison(
        self,
        merchant_id: str,
        current_days: int = 30,
    ) -> PeriodComparisonResponse:
        """
        Compare current N-day financial performance with the previous equivalent N-day period.
        """
        current_days = max(current_days, 1)
        today = date.today()

        current_end = today
        current_start = today - timedelta(days=current_days)

        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=current_days)

        curr_pl = self.get_profit_loss(merchant_id, current_start, current_end)
        prev_pl = self.get_profit_loss(merchant_id, previous_start, previous_end)

        rev_delta = self._safe_pct_change(curr_pl.total_revenue, prev_pl.total_revenue)
        exp_delta = self._safe_pct_change(curr_pl.total_expenses, prev_pl.total_expenses)
        profit_delta = self._safe_pct_change(curr_pl.net_profit, prev_pl.net_profit)
        margin_delta = round(curr_pl.operating_margin_pct - prev_pl.operating_margin_pct, 2)

        return PeriodComparisonResponse(
            merchant_id=merchant_id,
            current_period=curr_pl,
            previous_period=prev_pl,
            revenue_change_pct=rev_delta,
            expense_change_pct=exp_delta,
            profit_change_pct=profit_delta,
            margin_change_pct=margin_delta,
            disclaimer=ACCOUNTING_DISCLAIMER,
        )

    def get_income_vs_expense(
        self,
        merchant_id: str,
        months: int = 3,
    ) -> IncomeVsExpenseResponse:
        """
        Generate monthly comparative buckets of income, expense, and net profit.
        """
        months = max(min(months, 12), 1)
        now = datetime.now(timezone.utc)
        points: List[IncomeVsExpensePoint] = []

        total_income = 0.0
        total_expense = 0.0

        for i in range(months - 1, -1, -1):
            target_date = now - timedelta(days=i * 30)
            month_start = date(target_date.year, target_date.month, 1)

            # End of month
            if target_date.month == 12:
                next_month = date(target_date.year + 1, 1, 1)
            else:
                next_month = date(target_date.year, target_date.month + 1, 1)
            month_end = next_month - timedelta(days=1)

            pl = self.get_profit_loss(merchant_id, month_start, month_end)
            label = month_start.strftime("%b %Y")

            points.append(
                IncomeVsExpensePoint(
                    period=label,
                    income=pl.total_revenue,
                    expense=pl.total_expenses,
                    net_profit=pl.net_profit,
                )
            )
            total_income += pl.total_revenue
            total_expense += pl.total_expenses

        net_profit = round(total_income - total_expense, 2)

        return IncomeVsExpenseResponse(
            merchant_id=merchant_id,
            total_income=round(total_income, 2),
            total_expense=round(total_expense, 2),
            net_profit=net_profit,
            points=points,
            disclaimer=ACCOUNTING_DISCLAIMER,
        )

    def get_invoices_summary(
        self,
        merchant_id: str,
        status_filter: Optional[str] = None,
    ) -> InvoiceSummaryResponse:
        """
        Retrieve vendor supplier invoices and calculate paid vs pending cash flow obligations.
        """
        invoices_data = self.expense_repo.get_invoices(merchant_id=merchant_id, status=status_filter)

        total_invoices = len(invoices_data)
        total_amount = 0.0
        paid_amount = 0.0
        pending_amount = 0.0
        paid_count = 0
        pending_count = 0

        items: List[InvoiceItemResponse] = []
        for inv in invoices_data:
            amt = float(inv.get("amount", 0.0))
            total_amount += amt
            inv_status = str(inv.get("status", "pending")).lower()

            if inv_status == "paid":
                paid_amount += amt
                paid_count += 1
            else:
                pending_amount += amt
                pending_count += 1

            items.append(
                InvoiceItemResponse(
                    invoice_id=inv.get("invoice_id", ""),
                    merchant_id=inv.get("merchant_id", merchant_id),
                    vendor=inv.get("vendor", ""),
                    amount=round(amt, 2),
                    date=inv.get("date"),
                    due_date=inv.get("due_date"),
                    status=inv_status,
                )
            )

        return InvoiceSummaryResponse(
            merchant_id=merchant_id,
            total_invoices=total_invoices,
            total_amount=round(total_amount, 2),
            paid_amount=round(paid_amount, 2),
            pending_amount=round(pending_amount, 2),
            paid_count=paid_count,
            pending_count=pending_count,
            invoices=items,
            disclaimer=ACCOUNTING_DISCLAIMER,
        )

    def get_financial_insights(
        self,
        merchant_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> FinancialInsightsResponse:
        """
        Generate grounded, deterministic financial intelligence insights based on actual metrics.
        """
        pl = self.get_profit_loss(merchant_id, start_date, end_date)
        exp_breakdown = self.get_expenses_breakdown(merchant_id, start_date, end_date)
        invoices = self.get_invoices_summary(merchant_id)

        insights: List[FinancialInsight] = []

        # 1. Profitability & Margin Insight
        if pl.is_profitable:
            if pl.operating_margin_pct >= 20.0:
                insights.append(
                    FinancialInsight(
                        insight_type="profitability",
                        observation=(
                            f"Strong operating profitability: Net profit is ₹{pl.net_profit:,.2f} "
                            f"with an operating margin of {pl.operating_margin_pct}%."
                        ),
                        impact_level="high",
                        recommendation="Reinvest a portion of operating profit into high-ROI promotional campaigns.",
                    )
                )
            else:
                insights.append(
                    FinancialInsight(
                        insight_type="profitability",
                        observation=(
                            f"Moderate profitability: Net profit of ₹{pl.net_profit:,.2f} "
                            f"with a {pl.operating_margin_pct}% margin."
                        ),
                        impact_level="medium",
                        recommendation="Focus on driving higher basket size (ATV) to expand profit margins.",
                    )
                )
        else:
            insights.append(
                FinancialInsight(
                    insight_type="profitability",
                    observation=(
                        f"Operating loss detected: Expenses (₹{pl.total_expenses:,.2f}) exceed revenue "
                        f"(₹{pl.total_revenue:,.2f}), resulting in net deficit of ₹{abs(pl.net_profit):,.2f}."
                    ),
                    impact_level="high",
                    recommendation="Review discretionary operational overhead and prioritize high-margin inventory items.",
                )
            )

        # 2. Expense Concentration Insight
        if exp_breakdown.top_category and exp_breakdown.categories:
            top_cat = exp_breakdown.categories[0]
            if top_cat.percentage_of_total >= 40.0:
                insights.append(
                    FinancialInsight(
                        insight_type="expense_concentration",
                        observation=(
                            f"High expense concentration: '{top_cat.category}' accounts for "
                            f"{top_cat.percentage_of_total}% of total operating expenditures (₹{top_cat.total_amount:,.2f})."
                        ),
                        impact_level="medium",
                        recommendation=f"Negotiate supplier volume discounts or bulk payment terms for {top_cat.category}.",
                    )
                )

        # 3. Anomaly Insight
        for anom in exp_breakdown.anomalies:
            insights.append(
                FinancialInsight(
                    insight_type="expense_anomaly",
                    observation=anom.message,
                    impact_level="high",
                    recommendation="Audit meter readings and check for equipment inefficiencies or tariff escalations.",
                )
            )

        # 4. Invoices / Cash Flow Commitment
        if invoices.pending_amount > 0:
            insights.append(
                FinancialInsight(
                    insight_type="cash_flow",
                    observation=(
                        f"Pending vendor obligations: {invoices.pending_count} unpaid supplier invoices "
                        f"totaling ₹{invoices.pending_amount:,.2f}."
                    ),
                    impact_level="medium",
                    recommendation="Plan payment schedules around peak weekend cash inflow to protect liquidity.",
                )
            )

        summary_text = (
            f"Business generated ₹{pl.total_revenue:,.2f} revenue against ₹{pl.total_expenses:,.2f} expenses, "
            f"yielding ₹{pl.net_profit:,.2f} net operating profit ({pl.operating_margin_pct}% margin)."
        )

        return FinancialInsightsResponse(
            merchant_id=merchant_id,
            insights=insights,
            summary=summary_text,
            disclaimer=ACCOUNTING_DISCLAIMER,
        )

    def get_accountant_summary(
        self,
        merchant_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AccountantSummaryResponse:
        """
        Unified financial health snapshot powering Screen 7 and Module 7 AI Copilot.
        """
        pl = self.get_profit_loss(merchant_id, start_date, end_date)
        exp = self.get_expenses_breakdown(merchant_id, start_date, end_date)
        inv = self.get_invoices_summary(merchant_id)
        ins = self.get_financial_insights(merchant_id, start_date, end_date)

        narrative = (
            f"Over the selected period, your store recorded total revenue of ₹{pl.total_revenue:,.2f} "
            f"from {pl.transaction_count} transactions, while operating expenses totaled ₹{pl.total_expenses:,.2f}. "
            f"Your estimated operating profit is ₹{pl.net_profit:,.2f} (operating margin: {pl.operating_margin_pct}%). "
            f"Largest expense category is '{exp.top_category or 'N/A'}'. "
            f"You have ₹{inv.pending_amount:,.2f} in pending supplier invoices."
        )

        return AccountantSummaryResponse(
            merchant_id=merchant_id,
            profit_loss=pl,
            expenses=exp,
            invoices=inv,
            insights=ins.insights,
            ai_narrative=narrative,
            disclaimer=ACCOUNTING_DISCLAIMER,
        )
