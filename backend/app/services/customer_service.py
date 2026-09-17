"""
Customer Intelligence Service.
Computes deterministic customer-level metrics, RFM scores, behavioral segmentation,
rankings, at-risk/inactive identification, individual profiles, and actionable insights.
Guarantees merchant isolation and zero LLM dependencies.
"""

from typing import Optional, List, Dict, Any
from datetime import date, datetime, timezone
import math
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.services.base import BaseService
from app.repositories.customer_repository import CustomerRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.customer import (
    CustomerSummaryResponse,
    RFMScore,
    CustomerSegmentStat,
    CustomerSegmentsResponse,
    CustomerRankingItem,
    TopCustomersResponse,
    AtRiskCustomerItem,
    AtRiskCustomersResponse,
    InactiveCustomerItem,
    InactiveCustomersResponse,
    CustomerTransactionSummary,
    CustomerDetailResponse,
    CustomerInsightItem,
    CustomerInsightsResponse,
)

SEGMENT_DESCRIPTIONS = {
    "VIP": "Top spenders with high transaction frequency and recent store activity",
    "Loyal": "Consistent regular shoppers with steady purchase frequency and spending",
    "New": "Recently acquired shoppers with 1-2 purchases within the last 30 days",
    "At-Risk": "Previously active customers who have not visited in 22-45 days",
    "Inactive": "Dormant customers with no successful visits for over 45 days",
    "Regular": "Standard customers with moderate visit frequency and spend",
}


class CustomerService(BaseService):
    """Business service handling all Customer Intelligence calculations."""

    def __init__(self, db: Session):
        super().__init__(db)
        self.customer_repo = CustomerRepository(db)
        self.transaction_repo = TransactionRepository(db)

    def _resolve_reference_date(self, df: pd.DataFrame, as_of_date: Optional[date] = None) -> datetime:
        """
        Determine deterministic reference datetime for recency calculations.
        If as_of_date is provided, use end-of-day UTC.
        Otherwise, use the latest customer last_transaction date, or current UTC time as fallback.
        """
        if as_of_date:
            return datetime(as_of_date.year, as_of_date.month, as_of_date.day, 23, 59, 59, 999999, tzinfo=timezone.utc)

        if not df.empty and "last_transaction" in df.columns:
            valid_dates = df["last_transaction"].dropna()
            if not valid_dates.empty:
                max_dt = valid_dates.max()
                if isinstance(max_dt, pd.Timestamp):
                    return max_dt.to_pydatetime()
                elif isinstance(max_dt, datetime):
                    return max_dt if max_dt.tzinfo else max_dt.replace(tzinfo=timezone.utc)

        return datetime.now(timezone.utc)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """Sanitize floats to avoid NaN or Infinity values."""
        if value is None:
            return default
        try:
            val = float(value)
            if math.isnan(val) or math.isinf(val):
                return default
            return round(val, 2)
        except (ValueError, TypeError):
            return default

    def _calculate_rfm_score(self, recency_days: int, frequency: int, monetary: float) -> RFMScore:
        """
        Deterministic RFM scoring on a 1-5 scale.
        Recency: 5 (<=7d), 4 (8-14d), 3 (15-30d), 2 (31-60d), 1 (>60d)
        Frequency: 5 (>=15), 4 (8-14), 3 (4-7), 2 (2-3), 1 (<=1)
        Monetary: 5 (>=10k), 4 (5k-10k), 3 (2k-5k), 2 (500-2k), 1 (<500)
        """
        # Recency score
        if recency_days <= 7:
            r_score = 5
        elif recency_days <= 14:
            r_score = 4
        elif recency_days <= 30:
            r_score = 3
        elif recency_days <= 60:
            r_score = 2
        else:
            r_score = 1

        # Frequency score
        if frequency >= 15:
            f_score = 5
        elif frequency >= 8:
            f_score = 4
        elif frequency >= 4:
            f_score = 3
        elif frequency >= 2:
            f_score = 2
        else:
            f_score = 1

        # Monetary score
        if monetary >= 10000.0:
            m_score = 5
        elif monetary >= 5000.0:
            m_score = 4
        elif monetary >= 2000.0:
            m_score = 3
        elif monetary >= 500.0:
            m_score = 2
        else:
            m_score = 1

        rfm_code = f"{r_score}{f_score}{m_score}"
        return RFMScore(
            recency_days=recency_days,
            frequency=frequency,
            monetary=round(monetary, 2),
            r_score=r_score,
            f_score=f_score,
            m_score=m_score,
            rfm_code=rfm_code,
        )

    def get_summary(
        self,
        merchant_id: str,
        as_of_date: Optional[date] = None
    ) -> CustomerSummaryResponse:
        """
        Calculate merchant-level customer KPIs:
        total, active, inactive, at-risk, new, repeat, spend & transaction averages.
        """
        df = self.customer_repo.get_customers_df(merchant_id=merchant_id)

        if df.empty:
            return CustomerSummaryResponse(
                merchant_id=merchant_id,
                total_customers=0,
                active_customers=0,
                inactive_customers=0,
                at_risk_customers=0,
                new_customers=0,
                repeat_customers=0,
                repeat_customer_rate=0.0,
                average_customer_spend=0.0,
                average_transactions_per_customer=0.0,
                total_customer_revenue=0.0,
            )

        ref_dt = self._resolve_reference_date(df, as_of_date)
        total_customers = len(df)

        # Calculate recency in days for each customer
        recency_days_list = []
        for _, row in df.iterrows():
            last_tx = row.get("last_transaction")
            if pd.notnull(last_tx):
                if isinstance(last_tx, pd.Timestamp):
                    tx_dt = last_tx.to_pydatetime()
                elif isinstance(last_tx, datetime):
                    tx_dt = last_tx if last_tx.tzinfo else last_tx.replace(tzinfo=timezone.utc)
                else:
                    tx_dt = ref_dt
                diff = (ref_dt - tx_dt).total_seconds() / 86400.0
                recency_days_list.append(max(0, int(diff)))
            else:
                recency_days_list.append(999)

        df["recency_days"] = recency_days_list

        # Deterministic Cohort Classifications
        active_count = int((df["recency_days"] <= 30).sum())
        inactive_count = int(((df["recency_days"] > 45) | (df["segment"] == "Inactive")).sum())
        at_risk_count = int(
            (((df["recency_days"] >= 22) & (df["recency_days"] <= 45) & (df["transaction_count"] >= 3)) | (df["segment"] == "At-Risk")).sum()
        )
        new_count = int(
            (((df["transaction_count"] <= 2) & (df["recency_days"] <= 30)) | (df["segment"] == "New")).sum()
        )
        repeat_count = int((df["transaction_count"] >= 2).sum())

        repeat_rate = self._safe_float((repeat_count / total_customers) * 100.0) if total_customers > 0 else 0.0
        total_revenue = self._safe_float(df["total_spend"].sum())
        total_txns = int(df["transaction_count"].sum())

        avg_spend = self._safe_float(total_revenue / total_customers) if total_customers > 0 else 0.0
        avg_txns = self._safe_float(total_txns / total_customers) if total_customers > 0 else 0.0

        return CustomerSummaryResponse(
            merchant_id=merchant_id,
            total_customers=total_customers,
            active_customers=active_count,
            inactive_customers=inactive_count,
            at_risk_customers=at_risk_count,
            new_customers=new_count,
            repeat_customers=repeat_count,
            repeat_customer_rate=repeat_rate,
            average_customer_spend=avg_spend,
            average_transactions_per_customer=avg_txns,
            total_customer_revenue=total_revenue,
        )

    def get_segments(self, merchant_id: str) -> CustomerSegmentsResponse:
        """
        Aggregate customer statistics across behavioral segments.
        Calculates counts, revenue contributions, and percentages.
        """
        df = self.customer_repo.get_customers_df(merchant_id=merchant_id)

        if df.empty:
            return CustomerSegmentsResponse(
                merchant_id=merchant_id,
                total_customers=0,
                total_revenue=0.0,
                segments=[]
            )

        total_customers = len(df)
        grand_total_revenue = self._safe_float(df["total_spend"].sum())

        known_segments = ["VIP", "Loyal", "New", "At-Risk", "Inactive"]
        segments_in_df = df["segment"].dropna().unique().tolist()
        all_segments = [s for s in known_segments if s in segments_in_df]
        for s in segments_in_df:
            if s not in all_segments:
                all_segments.append(s)

        segment_stats: List[CustomerSegmentStat] = []

        for seg_name in all_segments:
            seg_df = df[df["segment"] == seg_name]
            seg_count = len(seg_df)
            seg_revenue = self._safe_float(seg_df["total_spend"].sum())
            seg_avg_spend = self._safe_float(seg_revenue / seg_count) if seg_count > 0 else 0.0
            seg_avg_txns = self._safe_float(seg_df["transaction_count"].mean()) if seg_count > 0 else 0.0
            pct_cust = self._safe_float((seg_count / total_customers) * 100.0) if total_customers > 0 else 0.0
            pct_rev = self._safe_float((seg_revenue / grand_total_revenue) * 100.0) if grand_total_revenue > 0 else 0.0

            segment_stats.append(
                CustomerSegmentStat(
                    segment=seg_name,
                    customer_count=seg_count,
                    total_revenue=seg_revenue,
                    average_revenue_per_customer=seg_avg_spend,
                    average_transaction_count=seg_avg_txns,
                    percentage_of_customers=pct_cust,
                    percentage_of_revenue=pct_rev,
                    description=SEGMENT_DESCRIPTIONS.get(seg_name, "Behavioral customer segment"),
                )
            )

        # Sort segments logically: VIP -> Loyal -> New -> At-Risk -> Inactive
        def segment_sort_key(item: CustomerSegmentStat) -> int:
            order = {"VIP": 1, "Loyal": 2, "New": 3, "At-Risk": 4, "Inactive": 5}
            return order.get(item.segment, 10)

        segment_stats.sort(key=segment_sort_key)

        return CustomerSegmentsResponse(
            merchant_id=merchant_id,
            total_customers=total_customers,
            total_revenue=grand_total_revenue,
            segments=segment_stats,
        )

    def get_top_customers(
        self,
        merchant_id: str,
        by: str = "revenue",
        limit: int = 10
    ) -> TopCustomersResponse:
        """
        Rank top customers by spend (revenue) or transaction frequency.
        """
        if by not in ("revenue", "frequency"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sorting criterion '{by}'. Allowed values: 'revenue', 'frequency'."
            )
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid limit {limit}. Limit must be between 1 and 100."
            )

        df = self.customer_repo.get_customers_df(merchant_id=merchant_id)

        if df.empty:
            return TopCustomersResponse(
                merchant_id=merchant_id,
                ranked_by=by,
                count=0,
                customers=[]
            )

        if by == "revenue":
            sorted_df = df.sort_values(by=["total_spend", "transaction_count"], ascending=[False, False])
        else:
            sorted_df = df.sort_values(by=["transaction_count", "total_spend"], ascending=[False, False])

        top_df = sorted_df.head(limit)
        items: List[CustomerRankingItem] = []

        for rank_idx, (_, row) in enumerate(top_df.iterrows(), start=1):
            last_tx_val = row.get("last_transaction")
            last_tx_str = None
            if pd.notnull(last_tx_val):
                last_tx_str = last_tx_val.isoformat() if hasattr(last_tx_val, "isoformat") else str(last_tx_val)

            items.append(
                CustomerRankingItem(
                    rank=rank_idx,
                    customer_id=str(row["customer_id"]),
                    name=str(row["name"]) if pd.notnull(row.get("name")) else None,
                    phone=str(row["phone"]) if pd.notnull(row.get("phone")) else None,
                    total_spend=self._safe_float(row["total_spend"]),
                    transaction_count=int(row["transaction_count"]),
                    average_transaction_value=self._safe_float(row["average_transaction"]),
                    last_transaction_date=last_tx_str,
                    segment=str(row.get("segment", "Regular")),
                )
            )

        return TopCustomersResponse(
            merchant_id=merchant_id,
            ranked_by=by,
            count=len(items),
            customers=items,
        )

    def get_at_risk_customers(
        self,
        merchant_id: str,
        limit: int = 50
    ) -> AtRiskCustomersResponse:
        """
        Retrieve customers who are becoming inactive and at risk of churning.
        """
        if limit < 1 or limit > 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid limit {limit}. Limit must be between 1 and 200."
            )

        df = self.customer_repo.get_customers_df(merchant_id=merchant_id)

        if df.empty:
            return AtRiskCustomersResponse(
                merchant_id=merchant_id,
                total_at_risk=0,
                total_at_risk_revenue=0.0,
                customers=[]
            )

        ref_dt = self._resolve_reference_date(df)

        # Calculate recency
        recency_list = []
        for _, row in df.iterrows():
            last_tx = row.get("last_transaction")
            if pd.notnull(last_tx):
                if isinstance(last_tx, pd.Timestamp):
                    tx_dt = last_tx.to_pydatetime()
                elif isinstance(last_tx, datetime):
                    tx_dt = last_tx if last_tx.tzinfo else last_tx.replace(tzinfo=timezone.utc)
                else:
                    tx_dt = ref_dt
                diff = (ref_dt - tx_dt).total_seconds() / 86400.0
                recency_list.append(max(0, int(diff)))
            else:
                recency_list.append(999)

        df["recency_days"] = recency_list

        # Filter at-risk: either segment == "At-Risk" or (22 <= recency <= 45 and tx_count >= 3)
        at_risk_df = df[
            (df["segment"] == "At-Risk") |
            ((df["recency_days"] >= 22) & (df["recency_days"] <= 45) & (df["transaction_count"] >= 3))
        ].copy()

        if at_risk_df.empty:
            return AtRiskCustomersResponse(
                merchant_id=merchant_id,
                total_at_risk=0,
                total_at_risk_revenue=0.0,
                customers=[]
            )

        # Sort descending by total_spend
        at_risk_df = at_risk_df.sort_values(by="total_spend", ascending=False)
        total_at_risk = len(at_risk_df)
        total_at_risk_revenue = self._safe_float(at_risk_df["total_spend"].sum())

        cohort_slice = at_risk_df.head(limit)
        items: List[AtRiskCustomerItem] = []

        for _, row in cohort_slice.iterrows():
            spend = self._safe_float(row["total_spend"])
            tx_count = int(row["transaction_count"])
            rec_days = int(row["recency_days"])
            atv = self._safe_float(row["average_transaction"])

            risk_level = "high" if spend >= 5000.0 or tx_count >= 8 else "medium"
            risk_reason = (
                f"No purchases in {rec_days} days despite {tx_count} previous orders totaling ₹{spend:,.2f}."
            )

            last_tx_val = row.get("last_transaction")
            last_tx_str = None
            if pd.notnull(last_tx_val):
                last_tx_str = last_tx_val.isoformat() if hasattr(last_tx_val, "isoformat") else str(last_tx_val)

            items.append(
                AtRiskCustomerItem(
                    customer_id=str(row["customer_id"]),
                    name=str(row["name"]) if pd.notnull(row.get("name")) else None,
                    phone=str(row["phone"]) if pd.notnull(row.get("phone")) else None,
                    last_transaction_date=last_tx_str,
                    days_since_last_transaction=rec_days,
                    historical_spend=spend,
                    transaction_count=tx_count,
                    average_transaction_value=atv,
                    segment=str(row.get("segment", "At-Risk")),
                    risk_level=risk_level,
                    risk_reason=risk_reason,
                )
            )

        return AtRiskCustomersResponse(
            merchant_id=merchant_id,
            total_at_risk=total_at_risk,
            total_at_risk_revenue=total_at_risk_revenue,
            customers=items,
        )

    def get_inactive_customers(
        self,
        merchant_id: str,
        limit: int = 50
    ) -> InactiveCustomersResponse:
        """
        Retrieve dormant customers who have not visited in >45 days.
        """
        if limit < 1 or limit > 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid limit {limit}. Limit must be between 1 and 200."
            )

        df = self.customer_repo.get_customers_df(merchant_id=merchant_id)

        if df.empty:
            return InactiveCustomersResponse(
                merchant_id=merchant_id,
                total_inactive=0,
                total_inactive_historical_revenue=0.0,
                customers=[]
            )

        ref_dt = self._resolve_reference_date(df)

        recency_list = []
        for _, row in df.iterrows():
            last_tx = row.get("last_transaction")
            if pd.notnull(last_tx):
                if isinstance(last_tx, pd.Timestamp):
                    tx_dt = last_tx.to_pydatetime()
                elif isinstance(last_tx, datetime):
                    tx_dt = last_tx if last_tx.tzinfo else last_tx.replace(tzinfo=timezone.utc)
                else:
                    tx_dt = ref_dt
                diff = (ref_dt - tx_dt).total_seconds() / 86400.0
                recency_list.append(max(0, int(diff)))
            else:
                recency_list.append(999)

        df["recency_days"] = recency_list

        inactive_df = df[
            (df["segment"] == "Inactive") | (df["recency_days"] > 45)
        ].copy()

        if inactive_df.empty:
            return InactiveCustomersResponse(
                merchant_id=merchant_id,
                total_inactive=0,
                total_inactive_historical_revenue=0.0,
                customers=[]
            )

        inactive_df = inactive_df.sort_values(by="total_spend", ascending=False)
        total_inactive = len(inactive_df)
        total_inactive_revenue = self._safe_float(inactive_df["total_spend"].sum())

        cohort_slice = inactive_df.head(limit)
        items: List[InactiveCustomerItem] = []

        for _, row in cohort_slice.iterrows():
            spend = self._safe_float(row["total_spend"])
            tx_count = int(row["transaction_count"])
            rec_days = int(row["recency_days"])
            atv = self._safe_float(row["average_transaction"])

            dormancy_reason = (
                f"Inactive for {rec_days} days. Prior spend was ₹{spend:,.2f} across {tx_count} orders."
            )

            last_tx_val = row.get("last_transaction")
            last_tx_str = None
            if pd.notnull(last_tx_val):
                last_tx_str = last_tx_val.isoformat() if hasattr(last_tx_val, "isoformat") else str(last_tx_val)

            items.append(
                InactiveCustomerItem(
                    customer_id=str(row["customer_id"]),
                    name=str(row["name"]) if pd.notnull(row.get("name")) else None,
                    phone=str(row["phone"]) if pd.notnull(row.get("phone")) else None,
                    last_transaction_date=last_tx_str,
                    days_since_last_transaction=rec_days,
                    historical_spend=spend,
                    transaction_count=tx_count,
                    average_transaction_value=atv,
                    segment=str(row.get("segment", "Inactive")),
                    dormancy_reason=dormancy_reason,
                )
            )

        return InactiveCustomersResponse(
            merchant_id=merchant_id,
            total_inactive=total_inactive,
            total_inactive_historical_revenue=total_inactive_revenue,
            customers=items,
        )

    def get_customer_detail(
        self,
        customer_id: str,
        merchant_id: str
    ) -> CustomerDetailResponse:
        """
        Fetch individual customer profile, RFM score, and recent transaction history.
        Strictly enforces merchant isolation.
        """
        cust = self.customer_repo.get_by_customer_id(customer_id=customer_id, merchant_id=merchant_id)

        if not cust:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer '{customer_id}' not found for merchant '{merchant_id}'."
            )

        # Reference date from recent transactions or customer record
        last_tx = cust.get("last_transaction")
        ref_dt = datetime.now(timezone.utc)
        rec_days = None

        if last_tx:
            if isinstance(last_tx, pd.Timestamp):
                tx_dt = last_tx.to_pydatetime()
            elif isinstance(last_tx, datetime):
                tx_dt = last_tx if last_tx.tzinfo else last_tx.replace(tzinfo=timezone.utc)
            elif isinstance(last_tx, str):
                try:
                    tx_dt = datetime.fromisoformat(last_tx)
                    if tx_dt.tzinfo is None:
                        tx_dt = tx_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    tx_dt = ref_dt
            else:
                tx_dt = ref_dt

            diff = (ref_dt - tx_dt).total_seconds() / 86400.0
            rec_days = max(0, int(diff))

        spend = self._safe_float(cust.get("total_spend"))
        tx_count = int(cust.get("transaction_count", 0))
        atv = self._safe_float(cust.get("average_transaction"))

        rfm = None
        if rec_days is not None:
            rfm = self._calculate_rfm_score(
                recency_days=rec_days,
                frequency=tx_count,
                monetary=spend
            )

        # Recent transactions
        recent_txs = self.customer_repo.get_recent_transactions(
            customer_id=customer_id,
            merchant_id=merchant_id,
            limit=5
        )
        tx_summaries = [
            CustomerTransactionSummary(
                transaction_id=str(t.get("transaction_id")),
                timestamp=str(t.get("timestamp")),
                amount=self._safe_float(t.get("amount")),
                payment_method=str(t.get("payment_method", "UPI")),
                status=str(t.get("status", "success")),
            )
            for t in recent_txs
        ]

        first_tx_str = None
        first_tx = cust.get("created_at")
        if first_tx:
            first_tx_str = first_tx.isoformat() if hasattr(first_tx, "isoformat") else str(first_tx)

        last_tx_str = None
        if last_tx:
            last_tx_str = last_tx.isoformat() if hasattr(last_tx, "isoformat") else str(last_tx)

        return CustomerDetailResponse(
            customer_id=str(cust["customer_id"]),
            merchant_id=merchant_id,
            name=cust.get("name"),
            phone=cust.get("phone"),
            total_spend=spend,
            transaction_count=tx_count,
            average_transaction_value=atv,
            first_transaction_date=first_tx_str,
            last_transaction_date=last_tx_str,
            days_since_last_transaction=rec_days,
            segment=str(cust.get("segment", "Regular")),
            rfm=rfm,
            recent_transactions=tx_summaries,
        )

    def get_insights(self, merchant_id: str) -> CustomerInsightsResponse:
        """
        Generate deterministic, rule-based customer intelligence insights.
        Zero LLM invocations. Formats observations with severity and recommendation context.
        """
        df = self.customer_repo.get_customers_df(merchant_id=merchant_id)

        if df.empty:
            return CustomerInsightsResponse(
                merchant_id=merchant_id,
                insights=[
                    CustomerInsightItem(
                        type="no_customer_data",
                        severity="info",
                        title="No Customer History Found",
                        message="There is no customer transaction history recorded for this merchant.",
                        metric=0.0,
                        recommendation_context="Record customer-linked transactions at checkout to unlock customer intelligence."
                    )
                ]
            )

        total_customers = len(df)
        total_revenue = self._safe_float(df["total_spend"].sum())
        insights: List[CustomerInsightItem] = []

        # 1. Revenue Concentration (Pareto observation)
        sorted_by_spend = df.sort_values(by="total_spend", ascending=False)
        top_10_pct_count = max(1, int(math.ceil(total_customers * 0.10)))
        top_10_spend = self._safe_float(sorted_by_spend.head(top_10_pct_count)["total_spend"].sum())
        concentration_pct = self._safe_float((top_10_spend / total_revenue) * 100.0) if total_revenue > 0 else 0.0

        if concentration_pct >= 40.0:
            severity = "warning" if concentration_pct >= 55.0 else "info"
            insights.append(
                CustomerInsightItem(
                    type="revenue_concentration",
                    severity=severity,
                    title="High Revenue Concentration",
                    message=(
                        f"Top 10% of customers ({top_10_pct_count} shoppers) generate "
                        f"{concentration_pct:.1f}% (₹{top_10_spend:,.2f}) of total merchant revenue."
                    ),
                    metric=concentration_pct,
                    recommendation_context="Nurture top-tier customers with exclusive VIP perks and personalized service."
                )
            )

        # 2. At-Risk Revenue Alert
        at_risk_df = df[df["segment"] == "At-Risk"]
        at_risk_count = len(at_risk_df)
        at_risk_rev = self._safe_float(at_risk_df["total_spend"].sum())

        if at_risk_count > 0 and total_revenue > 0:
            pct_at_risk_rev = self._safe_float((at_risk_rev / total_revenue) * 100.0)
            severity = "critical" if pct_at_risk_rev >= 20.0 else "warning"
            insights.append(
                CustomerInsightItem(
                    type="at_risk_revenue",
                    severity=severity,
                    title="Substantial Revenue at Risk",
                    message=(
                        f"{at_risk_count} customers representing ₹{at_risk_rev:,.2f} "
                        f"({pct_at_risk_rev:.1f}% of revenue) haven't visited in 22-45 days."
                    ),
                    metric=at_risk_rev,
                    recommendation_context="Trigger timely personalized WhatsApp win-back campaigns before these customers lapse completely."
                )
            )

        # 3. Dormancy Scale (Inactive cohort)
        inactive_df = df[df["segment"] == "Inactive"]
        inactive_count = len(inactive_df)
        inactive_pct = self._safe_float((inactive_count / total_customers) * 100.0)

        if inactive_pct >= 25.0:
            insights.append(
                CustomerInsightItem(
                    type="dormancy_scale",
                    severity="warning",
                    title="High Customer Dormancy",
                    message=(
                        f"{inactive_count} customers ({inactive_pct:.1f}% of total base) "
                        f"have had no activity for over 45 days."
                    ),
                    metric=inactive_pct,
                    recommendation_context="Re-engage dormant customers with targeted reactivation incentives and product updates."
                )
            )

        # 4. Loyalty Strength (Repeat customer rate)
        repeat_count = int((df["transaction_count"] >= 2).sum())
        repeat_pct = self._safe_float((repeat_count / total_customers) * 100.0)

        if repeat_pct >= 45.0:
            insights.append(
                CustomerInsightItem(
                    type="loyalty_strength",
                    severity="positive",
                    title="Solid Customer Retention",
                    message=(
                        f"Repeat customer rate is {repeat_pct:.1f}% ({repeat_count} return shoppers), "
                        f"demonstrating strong merchant loyalty."
                    ),
                    metric=repeat_pct,
                    recommendation_context="Introduce a tiered rewards or milestone points program to accelerate purchase frequency."
                )
            )
        elif repeat_pct < 30.0:
            one_time_pct = round(100.0 - repeat_pct, 2)
            insights.append(
                CustomerInsightItem(
                    type="one_time_customer_ratio",
                    severity="info",
                    title="Second Purchase Opportunity",
                    message=(
                        f"{one_time_pct:.1f}% of customers have only purchased once. "
                        f"Converting first-time shoppers to repeat visits presents significant upside."
                    ),
                    metric=one_time_pct,
                    recommendation_context="Send immediate post-purchase discounts valid on next visit within 7 days."
                )
            )

        # 5. VIP Segment Contribution
        vip_df = df[df["segment"] == "VIP"]
        vip_count = len(vip_df)
        if vip_count > 0 and total_revenue > 0:
            vip_rev = self._safe_float(vip_df["total_spend"].sum())
            vip_pct_rev = self._safe_float((vip_rev / total_revenue) * 100.0)
            vip_avg = self._safe_float(vip_df["average_transaction"].mean())

            if vip_pct_rev >= 15.0:
                insights.append(
                    CustomerInsightItem(
                        type="vip_contribution",
                        severity="positive",
                        title="High VIP Spending Impact",
                        message=(
                            f"{vip_count} VIP customers account for {vip_pct_rev:.1f}% of revenue "
                            f"(₹{vip_rev:,.2f}) with an average order value of ₹{vip_avg:,.2f}."
                        ),
                        metric=vip_pct_rev,
                        recommendation_context="Offer bespoke merchant services, priority booking, and sneak peeks at new stock."
                    )
                )

        return CustomerInsightsResponse(
            merchant_id=merchant_id,
            insights=insights,
        )
