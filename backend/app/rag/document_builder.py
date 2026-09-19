"""
RAG Document Builder — MerchantMind.

Generates meaningful, aggregated text documents from the existing SQLAlchemy
database for use in the RAG pipeline.

CRITICAL RULES:
  - All content is derived from REAL database records for the merchant.
  - NO hardcoded financial values.
  - NO per-row embeddings — only aggregated, meaningful summaries.
  - NO customer PII (names/phones are excluded; only counts and segments).
  - Every document carries full metadata for filtering and source tracing.
  - Merchant isolation: merchant_id is always checked before any query.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, List, Optional
from decimal import Decimal

from sqlalchemy import func, case, and_, extract
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.merchant import Merchant
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.expense import Expense
from app.models.campaign import Campaign


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doc_id(merchant_id: str, doc_type: str, suffix: str = "") -> str:
    """Deterministic document ID — prevents duplicate embeddings on re-index."""
    raw = f"{merchant_id}:{doc_type}:{suffix}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _fmt_inr(amount: Any) -> str:
    """Format amount as Indian Rupee string."""
    try:
        val = float(amount or 0)
        return f"₹{val:,.2f}"
    except Exception:
        return "₹0.00"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _month_range(months_ago: int = 0) -> tuple[date, date]:
    """Return (first_day, last_day) for a calendar month relative to today."""
    today = date.today()
    # First day of target month
    first = (today.replace(day=1) - timedelta(days=months_ago * 28)).replace(day=1)
    # Last day of target month
    if first.month == 12:
        last = first.replace(year=first.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = first.replace(month=first.month + 1, day=1) - timedelta(days=1)
    return first, last


# ---------------------------------------------------------------------------
# Document Builder
# ---------------------------------------------------------------------------

class DocumentBuilder:
    """
    Builds aggregated RAG documents from live database data.
    All documents are merchant-scoped and contain no PII.
    """

    def __init__(self, db: Session):
        self.db = db

    def build_all(self, merchant_id: str) -> List[Dict[str, Any]]:
        """
        Build the complete document set for a merchant.
        Returns list of document dicts ready for embedding and storage.
        """
        docs: List[Dict[str, Any]] = []
        mid = merchant_id.strip()

        # Verify merchant exists
        merchant = self.db.query(Merchant).filter(Merchant.merchant_id == mid).first()
        if not merchant:
            logger.warning(f"DocumentBuilder: merchant '{mid}' not found — skipping build.")
            return []

        try:
            docs.append(self._build_merchant_profile(mid, merchant))
        except Exception as exc:
            logger.warning(f"RAG doc error (merchant_profile): {exc}")

        try:
            docs.extend(self._build_monthly_sales_summaries(mid))
        except Exception as exc:
            logger.warning(f"RAG doc error (monthly_sales): {exc}")

        try:
            docs.append(self._build_sales_patterns(mid))
        except Exception as exc:
            logger.warning(f"RAG doc error (sales_patterns): {exc}")

        try:
            docs.append(self._build_customer_segments(mid))
        except Exception as exc:
            logger.warning(f"RAG doc error (customer_segments): {exc}")

        try:
            docs.append(self._build_at_risk_customers(mid))
        except Exception as exc:
            logger.warning(f"RAG doc error (at_risk_customers): {exc}")

        try:
            docs.extend(self._build_monthly_expense_summaries(mid))
        except Exception as exc:
            logger.warning(f"RAG doc error (monthly_expenses): {exc}")

        try:
            docs.extend(self._build_campaign_history(mid))
        except Exception as exc:
            logger.warning(f"RAG doc error (campaign_history): {exc}")

        try:
            docs.append(self._build_business_observations(mid))
        except Exception as exc:
            logger.warning(f"RAG doc error (business_observations): {exc}")

        # Filter out None/empty docs
        valid_docs = [d for d in docs if d and d.get("content", "").strip()]
        logger.info(f"DocumentBuilder: built {len(valid_docs)} documents for merchant '{mid}'.")
        return valid_docs

    # ------------------------------------------------------------------
    # Merchant Profile
    # ------------------------------------------------------------------

    def _build_merchant_profile(self, merchant_id: str, merchant: Merchant) -> Dict[str, Any]:
        today = date.today()
        content = (
            f"Merchant Business Profile\n\n"
            f"Business Name: {merchant.business_name}\n"
            f"Business Type: {merchant.business_type}\n"
            f"Location: {merchant.location}\n"
            f"Business Age: {merchant.business_age} months ({merchant.business_age // 12} years, {merchant.business_age % 12} months)\n"
            f"Profile Generated: {today.strftime('%B %Y')}\n\n"
            f"This is a {merchant.business_type.lower()} store located in {merchant.location}. "
            f"The business has been operating for approximately {merchant.business_age} months. "
            f"MerchantMind is monitoring this merchant's sales, customers, expenses, and campaigns."
        )
        return {
            "doc_id": _doc_id(merchant_id, "merchant_profile"),
            "merchant_id": merchant_id,
            "doc_type": "merchant_profile",
            "topic": "merchant_context",
            "date_from": None,
            "date_to": None,
            "source_tables": ["merchants"],
            "content": content,
            "created_at": _now_utc().isoformat(),
        }

    # ------------------------------------------------------------------
    # Monthly Sales Summaries
    # ------------------------------------------------------------------

    def _build_monthly_sales_summaries(self, merchant_id: str) -> List[Dict[str, Any]]:
        docs = []
        for months_ago in range(3):  # Current month + 2 prior months
            first, last = _month_range(months_ago)
            doc = self._build_sales_summary_for_period(merchant_id, first, last)
            if doc:
                docs.append(doc)
        return docs

    def _build_sales_summary_for_period(
        self, merchant_id: str, date_from: date, date_to: date
    ) -> Optional[Dict[str, Any]]:
        from_dt = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
        to_dt = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc)

        result = (
            self.db.query(
                func.count(Transaction.transaction_id).label("total_txn"),
                func.sum(Transaction.amount).label("total_rev"),
                func.avg(Transaction.amount).label("avg_txn"),
                func.sum(case((Transaction.status == "success", 1), else_=0)).label("success_count"),
                func.count(func.distinct(Transaction.customer_id)).label("unique_customers"),
            )
            .filter(
                Transaction.merchant_id == merchant_id,
                Transaction.timestamp >= from_dt,
                Transaction.timestamp <= to_dt,
            )
            .first()
        )

        if not result or not result.total_txn:
            return None

        total_txn = int(result.total_txn or 0)
        total_rev = float(result.total_rev or 0)
        avg_txn = float(result.avg_txn or 0)
        success_rate = round(float(result.success_count or 0) / max(total_txn, 1) * 100, 1)
        unique_customers = int(result.unique_customers or 0)

        period_label = date_from.strftime("%B %Y")

        # Payment method breakdown
        pm_rows = (
            self.db.query(
                Transaction.payment_method,
                func.count(Transaction.transaction_id).label("cnt"),
            )
            .filter(
                Transaction.merchant_id == merchant_id,
                Transaction.timestamp >= from_dt,
                Transaction.timestamp <= to_dt,
                Transaction.status == "success",
            )
            .group_by(Transaction.payment_method)
            .order_by(func.count(Transaction.transaction_id).desc())
            .limit(3)
            .all()
        )
        pm_lines = [f"  - {r.payment_method}: {r.cnt} transactions" for r in pm_rows]
        pm_text = "\n".join(pm_lines) if pm_lines else "  - Not available"

        content = (
            f"Sales Summary — {period_label}\n\n"
            f"Period: {date_from.strftime('%d %b %Y')} to {date_to.strftime('%d %b %Y')}\n"
            f"Total Transactions: {total_txn:,}\n"
            f"Total Revenue: {_fmt_inr(total_rev)}\n"
            f"Average Transaction Value: {_fmt_inr(avg_txn)}\n"
            f"Payment Success Rate: {success_rate}%\n"
            f"Unique Customers Served: {unique_customers:,}\n\n"
            f"Payment Method Breakdown:\n{pm_text}\n\n"
            f"This data covers the sales performance of the merchant for {period_label}. "
            f"The figures above are derived from the transactions database and represent "
            f"actual recorded payment activity. (Synthetic / Illustrative Demo Data)"
        )

        return {
            "doc_id": _doc_id(merchant_id, "sales_summary_monthly", f"{date_from.year}-{date_from.month:02d}"),
            "merchant_id": merchant_id,
            "doc_type": "sales_summary_monthly",
            "topic": "sales_performance",
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "source_tables": ["transactions"],
            "content": content,
            "created_at": _now_utc().isoformat(),
        }

    # ------------------------------------------------------------------
    # Sales Patterns (peak hours, weekday/weekend, payment methods)
    # ------------------------------------------------------------------

    def _build_sales_patterns(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        cutoff = _now_utc() - timedelta(days=90)

        # Hourly pattern
        hourly = (
            self.db.query(
                extract("hour", Transaction.timestamp).label("hour"),
                func.count(Transaction.transaction_id).label("cnt"),
                func.avg(Transaction.amount).label("avg_amt"),
            )
            .filter(
                Transaction.merchant_id == merchant_id,
                Transaction.timestamp >= cutoff,
                Transaction.status == "success",
            )
            .group_by(extract("hour", Transaction.timestamp))
            .order_by(func.count(Transaction.transaction_id).desc())
            .all()
        )

        if not hourly:
            return None

        peak_hours = hourly[:3]
        slow_hours = sorted(hourly, key=lambda r: r.cnt)[:3]

        def _hour_label(h: Any) -> str:
            h = int(h)
            return f"{h:02d}:00–{h+1:02d}:00"

        peak_text = ", ".join([f"{_hour_label(r.hour)} ({r.cnt} txns)" for r in peak_hours])
        slow_text = ", ".join([f"{_hour_label(r.hour)} ({r.cnt} txns)" for r in slow_hours])

        # Weekday vs weekend
        dow_rows = (
            self.db.query(
                extract("dow", Transaction.timestamp).label("dow"),
                func.count(Transaction.transaction_id).label("cnt"),
            )
            .filter(
                Transaction.merchant_id == merchant_id,
                Transaction.timestamp >= cutoff,
                Transaction.status == "success",
            )
            .group_by(extract("dow", Transaction.timestamp))
            .all()
        )
        weekday_total = sum(int(r.cnt) for r in dow_rows if int(r.dow) not in (0, 6))
        weekend_total = sum(int(r.cnt) for r in dow_rows if int(r.dow) in (0, 6))
        total_all = weekday_total + weekend_total or 1
        weekday_pct = round(weekday_total / total_all * 100, 1)
        weekend_pct = round(weekend_total / total_all * 100, 1)

        # Payment method popularity
        pm_all = (
            self.db.query(
                Transaction.payment_method,
                func.count(Transaction.transaction_id).label("cnt"),
            )
            .filter(
                Transaction.merchant_id == merchant_id,
                Transaction.timestamp >= cutoff,
                Transaction.status == "success",
            )
            .group_by(Transaction.payment_method)
            .order_by(func.count(Transaction.transaction_id).desc())
            .limit(4)
            .all()
        )
        pm_text = "; ".join([f"{r.payment_method} ({r.cnt} txns)" for r in pm_all])

        content = (
            f"Sales Patterns & Operating Insights — Last 90 Days\n\n"
            f"Peak Hours (highest transaction volume):\n  {peak_text}\n\n"
            f"Slow Hours (lowest transaction volume):\n  {slow_text}\n\n"
            f"Weekday vs Weekend Split:\n"
            f"  - Weekday: {weekday_pct}% of total transactions\n"
            f"  - Weekend: {weekend_pct}% of total transactions\n\n"
            f"Payment Method Popularity:\n  {pm_text}\n\n"
            f"These patterns show when the store is busiest and which payment methods "
            f"customers prefer. The evening hours typically show lower volumes, which "
            f"may represent a targeting opportunity. (Synthetic / Illustrative Demo Data)"
        )

        return {
            "doc_id": _doc_id(merchant_id, "sales_patterns"),
            "merchant_id": merchant_id,
            "doc_type": "sales_patterns",
            "topic": "sales_patterns",
            "date_from": cutoff.date().isoformat(),
            "date_to": date.today().isoformat(),
            "source_tables": ["transactions"],
            "content": content,
            "created_at": _now_utc().isoformat(),
        }

    # ------------------------------------------------------------------
    # Customer Segments
    # ------------------------------------------------------------------

    def _build_customer_segments(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        rows = (
            self.db.query(
                Customer.segment,
                func.count(Customer.customer_id).label("count"),
                func.avg(Customer.total_spend).label("avg_spend"),
                func.avg(Customer.transaction_count).label("avg_txns"),
            )
            .filter(Customer.merchant_id == merchant_id)
            .group_by(Customer.segment)
            .all()
        )

        if not rows:
            return None

        total_customers = sum(int(r.count) for r in rows)
        segment_lines = []
        for r in sorted(rows, key=lambda x: -x.count):
            pct = round(int(r.count) / max(total_customers, 1) * 100, 1)
            segment_lines.append(
                f"  - {r.segment}: {int(r.count)} customers ({pct}%) | "
                f"avg spend {_fmt_inr(r.avg_spend)} | avg {float(r.avg_txns or 0):.1f} transactions"
            )

        content = (
            f"Customer Segmentation Summary\n\n"
            f"Total Customers on Record: {total_customers:,}\n\n"
            f"Segment Breakdown:\n" + "\n".join(segment_lines) + "\n\n"
            f"Customer segments are computed based on recency, frequency, and spend. "
            f"VIP customers have the highest lifetime value. At-Risk customers were "
            f"previously active but have not transacted in 25–45 days. Inactive customers "
            f"have been absent for more than 45 days. (Synthetic / Illustrative Demo Data)"
        )

        return {
            "doc_id": _doc_id(merchant_id, "customer_segments"),
            "merchant_id": merchant_id,
            "doc_type": "customer_segments",
            "topic": "customer_intelligence",
            "date_from": None,
            "date_to": None,
            "source_tables": ["customers"],
            "content": content,
            "created_at": _now_utc().isoformat(),
        }

    # ------------------------------------------------------------------
    # At-Risk Customers
    # ------------------------------------------------------------------

    def _build_at_risk_customers(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        at_risk = (
            self.db.query(func.count(Customer.customer_id))
            .filter(Customer.merchant_id == merchant_id, Customer.segment == "At-Risk")
            .scalar()
        ) or 0

        inactive = (
            self.db.query(func.count(Customer.customer_id))
            .filter(Customer.merchant_id == merchant_id, Customer.segment == "Inactive")
            .scalar()
        ) or 0

        at_risk_spend = (
            self.db.query(func.avg(Customer.total_spend))
            .filter(Customer.merchant_id == merchant_id, Customer.segment == "At-Risk")
            .scalar()
        ) or 0

        inactive_spend = (
            self.db.query(func.avg(Customer.total_spend))
            .filter(Customer.merchant_id == merchant_id, Customer.segment == "Inactive")
            .scalar()
        ) or 0

        if not at_risk and not inactive:
            return None

        content = (
            f"At-Risk & Inactive Customer Analysis\n\n"
            f"At-Risk Customers: {int(at_risk)} customers\n"
            f"  - Definition: Previously active, absent for 25–45 days.\n"
            f"  - Average Historical Spend: {_fmt_inr(at_risk_spend)}\n"
            f"  - Recovery Opportunity: These customers have demonstrated purchase intent "
            f"    and may respond to a targeted win-back offer.\n\n"
            f"Inactive Customers: {int(inactive)} customers\n"
            f"  - Definition: Absent for more than 45 days.\n"
            f"  - Average Historical Spend: {_fmt_inr(inactive_spend)}\n"
            f"  - Recovery Opportunity: Re-engagement campaigns with cashback or discount "
            f"    offers may bring a portion back.\n\n"
            f"Churn Prevention Strategy: Running re-engagement campaigns for the {int(at_risk)} "
            f"at-risk customers before they become fully inactive is the highest-priority "
            f"retention opportunity. (Synthetic / Illustrative Demo Data)"
        )

        return {
            "doc_id": _doc_id(merchant_id, "customer_at_risk"),
            "merchant_id": merchant_id,
            "doc_type": "customer_at_risk",
            "topic": "customer_retention",
            "date_from": None,
            "date_to": None,
            "source_tables": ["customers"],
            "content": content,
            "created_at": _now_utc().isoformat(),
        }

    # ------------------------------------------------------------------
    # Monthly Expense Summaries
    # ------------------------------------------------------------------

    def _build_monthly_expense_summaries(self, merchant_id: str) -> List[Dict[str, Any]]:
        docs = []
        for months_ago in range(3):
            first, last = _month_range(months_ago)
            doc = self._build_expense_summary_for_period(merchant_id, first, last)
            if doc:
                docs.append(doc)
        return docs

    def _build_expense_summary_for_period(
        self, merchant_id: str, date_from: date, date_to: date
    ) -> Optional[Dict[str, Any]]:
        total = (
            self.db.query(func.sum(Expense.amount))
            .filter(
                Expense.merchant_id == merchant_id,
                Expense.date >= date_from,
                Expense.date <= date_to,
            )
            .scalar()
        )

        if not total:
            return None

        # Category breakdown
        cat_rows = (
            self.db.query(
                Expense.category,
                func.sum(Expense.amount).label("total"),
                func.count(Expense.expense_id).label("count"),
            )
            .filter(
                Expense.merchant_id == merchant_id,
                Expense.date >= date_from,
                Expense.date <= date_to,
            )
            .group_by(Expense.category)
            .order_by(func.sum(Expense.amount).desc())
            .all()
        )

        total_f = float(total)
        cat_lines = []
        for r in cat_rows:
            pct = round(float(r.total) / max(total_f, 1) * 100, 1)
            cat_lines.append(
                f"  - {r.category}: {_fmt_inr(r.total)} ({pct}% of total, {r.count} entries)"
            )

        period_label = date_from.strftime("%B %Y")
        largest = cat_rows[0] if cat_rows else None

        content = (
            f"Expense Summary — {period_label}\n\n"
            f"Period: {date_from.strftime('%d %b %Y')} to {date_to.strftime('%d %b %Y')}\n"
            f"Total Expenses: {_fmt_inr(total_f)}\n"
            f"Largest Expense Category: {largest.category if largest else 'N/A'} "
            f"({_fmt_inr(largest.total) if largest else ''})\n\n"
            f"Expense Category Breakdown:\n" + "\n".join(cat_lines) + "\n\n"
            f"Monitoring expense trends helps identify cost optimization opportunities. "
            f"The largest expense driver represents the most significant operational cost. "
            f"(Synthetic / Illustrative Demo Data)"
        )

        return {
            "doc_id": _doc_id(merchant_id, "expense_summary_monthly", f"{date_from.year}-{date_from.month:02d}"),
            "merchant_id": merchant_id,
            "doc_type": "expense_summary_monthly",
            "topic": "expense_analysis",
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "source_tables": ["expenses"],
            "content": content,
            "created_at": _now_utc().isoformat(),
        }

    # ------------------------------------------------------------------
    # Campaign History
    # ------------------------------------------------------------------

    def _build_campaign_history(self, merchant_id: str) -> List[Dict[str, Any]]:
        campaigns = (
            self.db.query(Campaign)
            .filter(
                Campaign.merchant_id == merchant_id,
                Campaign.status.in_(["COMPLETED", "APPROVED", "EXECUTING"]),
            )
            .order_by(Campaign.created_at.desc())
            .limit(5)
            .all()
        )

        if not campaigns:
            # Build a "no campaigns yet" doc
            content = (
                "Campaign History\n\n"
                "No completed campaigns have been recorded yet for this merchant. "
                "MerchantMind can help create targeted campaigns for customer segments "
                "such as VIP customers, at-risk customers, or weekend revenue boosts. "
                "All campaign proposals require explicit merchant approval before execution. "
                "(Synthetic / Illustrative Demo Data)"
            )
            return [{
                "doc_id": _doc_id(merchant_id, "campaign_history", "empty"),
                "merchant_id": merchant_id,
                "doc_type": "campaign_history",
                "topic": "campaign_performance",
                "date_from": None,
                "date_to": None,
                "source_tables": ["campaigns"],
                "content": content,
                "created_at": _now_utc().isoformat(),
            }]

        docs = []
        for c in campaigns:
            roi = float(c.simulated_roi or c.estimated_roi or 0)
            net_impact = float(c.simulated_net_impact or 0)
            projected_rev = float(c.projected_revenue or c.simulated_revenue or 0)
            cost = float(c.estimated_cost or c.simulated_cost or 0)

            content = (
                f"Campaign Record — {c.name or 'Unnamed Campaign'}\n\n"
                f"Campaign ID: {c.campaign_id[:12]}...\n"
                f"Target Segment: {c.target_segment}\n"
                f"Offer Type: {c.offer_type}\n"
                f"Offer Value: {_fmt_inr(c.offer_value)}\n"
                f"Status: {c.status}\n"
                f"Created: {c.created_at.strftime('%d %b %Y') if c.created_at else 'N/A'}\n"
                f"Projected Revenue: {_fmt_inr(projected_rev)}\n"
                f"Estimated Cost: {_fmt_inr(cost)}\n"
                f"Simulated Net Impact: {_fmt_inr(net_impact)}\n"
                f"Simulated ROI: {roi:.1f}x\n\n"
                f"This campaign targeted the '{c.target_segment}' customer segment "
                f"with a {c.offer_type} offer. "
                f"{'The projected ROI suggests this was a viable strategy.' if roi > 1 else 'The campaign was created for merchant review.'} "
                f"(Synthetic / Illustrative Demo Data)"
            )

            docs.append({
                "doc_id": _doc_id(merchant_id, "campaign_history", str(c.campaign_id)),
                "merchant_id": merchant_id,
                "doc_type": "campaign_history",
                "topic": "campaign_performance",
                "date_from": c.created_at.date().isoformat() if c.created_at else None,
                "date_to": c.executed_at.date().isoformat() if c.executed_at else None,
                "source_tables": ["campaigns"],
                "content": content,
                "created_at": _now_utc().isoformat(),
            })

        return docs

    # ------------------------------------------------------------------
    # Business Observations (derived qualitative insights)
    # ------------------------------------------------------------------

    def _build_business_observations(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        today = date.today()
        cutoff_30 = _now_utc() - timedelta(days=30)
        cutoff_60 = _now_utc() - timedelta(days=60)

        # Revenue comparison: last 30 vs prior 30
        rev_30 = float(
            self.db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.merchant_id == merchant_id,
                Transaction.timestamp >= cutoff_30,
                Transaction.status == "success",
            )
            .scalar() or 0
        )
        rev_30_60 = float(
            self.db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.merchant_id == merchant_id,
                Transaction.timestamp >= cutoff_60,
                Transaction.timestamp < cutoff_30,
                Transaction.status == "success",
            )
            .scalar() or 0
        )

        trend_direction = "stable"
        trend_pct = 0.0
        if rev_30_60 > 0:
            trend_pct = round((rev_30 - rev_30_60) / rev_30_60 * 100, 1)
            if trend_pct > 5:
                trend_direction = "growing"
            elif trend_pct < -5:
                trend_direction = "declining"

        # Customer health
        total_cust = self.db.query(func.count(Customer.customer_id)).filter(Customer.merchant_id == merchant_id).scalar() or 0
        at_risk = self.db.query(func.count(Customer.customer_id)).filter(Customer.merchant_id == merchant_id, Customer.segment == "At-Risk").scalar() or 0
        inactive = self.db.query(func.count(Customer.customer_id)).filter(Customer.merchant_id == merchant_id, Customer.segment == "Inactive").scalar() or 0
        churn_pct = round((int(at_risk) + int(inactive)) / max(int(total_cust), 1) * 100, 1)

        # Peak day of week
        dow_best = (
            self.db.query(
                extract("dow", Transaction.timestamp).label("dow"),
                func.count(Transaction.transaction_id).label("cnt"),
            )
            .filter(Transaction.merchant_id == merchant_id, Transaction.status == "success")
            .group_by(extract("dow", Transaction.timestamp))
            .order_by(func.count(Transaction.transaction_id).desc())
            .first()
        )
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        best_day = day_names[int(dow_best.dow)] if dow_best else "weekday"

        content = (
            f"Business Health Observations — as of {today.strftime('%d %b %Y')}\n\n"
            f"Revenue Trend (Last 30 Days vs Prior 30 Days):\n"
            f"  Revenue is currently {trend_direction}. "
            f"{'Revenue increased by' if trend_pct >= 0 else 'Revenue declined by'} "
            f"{abs(trend_pct):.1f}% compared to the prior period.\n\n"
            f"Customer Health:\n"
            f"  Total customers: {int(total_cust):,}\n"
            f"  At-risk + inactive: {int(at_risk) + int(inactive):,} ({churn_pct}% of base)\n"
            f"  Churn risk is {'HIGH' if churn_pct > 40 else 'MODERATE' if churn_pct > 20 else 'LOW'}.\n\n"
            f"Peak Trading:\n"
            f"  {best_day} is historically the strongest trading day.\n\n"
            f"Key Observations:\n"
            f"  1. Revenue trend is {trend_direction} — {'monitor for further decline.' if trend_direction == 'declining' else 'maintain momentum.'}\n"
            f"  2. {int(at_risk)} customers are at risk of churning — a targeted offer could retain them.\n"
            f"  3. {int(inactive)} customers have already gone inactive — win-back campaigns may recover a portion.\n"
            f"  4. {best_day} appears to be the best day for high-volume promotions.\n\n"
            f"(Synthetic / Illustrative Demo Data — not a certified business assessment)"
        )

        return {
            "doc_id": _doc_id(merchant_id, "business_observations"),
            "merchant_id": merchant_id,
            "doc_type": "business_observations",
            "topic": "business_health",
            "date_from": cutoff_60.date().isoformat(),
            "date_to": today.isoformat(),
            "source_tables": ["transactions", "customers"],
            "content": content,
            "created_at": _now_utc().isoformat(),
        }
