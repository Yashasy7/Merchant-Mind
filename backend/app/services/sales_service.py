"""
Sales Intelligence Service.
Computes deterministic business metrics, trends, period comparisons, day/hour distributions,
weekend analysis, and structured machine-readable insights.
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import date, datetime, timedelta, timezone
import pandas as pd
from sqlalchemy.orm import Session

from app.services.base import BaseService
from app.repositories.transaction_repository import TransactionRepository
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


class SalesService(BaseService):
    """Business service handling all Sales Intelligence calculations."""

    def __init__(self, db: Session):
        super().__init__(db)
        self.repo = TransactionRepository(db)

    def _to_utc_datetime(self, d: Optional[date], is_end: bool = False) -> Optional[datetime]:
        """Convert a date object to UTC datetime start-of-day or end-of-day."""
        if d is None:
            return None
        if is_end:
            return datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=timezone.utc)
        return datetime(d.year, d.month, d.day, 0, 0, 0, 0, tzinfo=timezone.utc)

    def _safe_pct_change(self, current: float, previous: float) -> float:
        """Calculate percentage change safely without division by zero or NaN."""
        if previous > 0:
            return round(((current - previous) / previous) * 100.0, 2)
        elif previous == 0 and current > 0:
            return 100.0
        elif previous == 0 and current == 0:
            return 0.0
        return 0.0

    def get_summary(
        self,
        merchant_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> SalesSummaryResponse:
        """Calculate comprehensive sales KPIs for the specified merchant and date range."""
        start_dt = self._to_utc_datetime(start_date, is_end=False)
        end_dt = self._to_utc_datetime(end_date, is_end=True)

        df = self.repo.get_transactions_df(
            merchant_id=merchant_id,
            start_date=start_dt,
            end_date=end_dt
        )

        total_txns = len(df)
        if df.empty:
            return SalesSummaryResponse(
                merchant_id=merchant_id,
                total_revenue=0.0,
                total_transactions=0,
                average_transaction_value=0.0,
                minimum_transaction_value=0.0,
                maximum_transaction_value=0.0,
                successful_transactions=0,
                failed_transactions=0,
                success_rate=0.0,
                start_date=str(start_date) if start_date else None,
                end_date=str(end_date) if end_date else None
            )

        df_success = df[df["status"] == "success"]
        df_failed = df[df["status"] != "success"]

        successful_txns = len(df_success)
        failed_txns = len(df_failed)
        total_revenue = round(float(df_success["amount"].sum()), 2) if not df_success.empty else 0.0
        avg_tv = round(total_revenue / successful_txns, 2) if successful_txns > 0 else 0.0
        min_tv = round(float(df_success["amount"].min()), 2) if not df_success.empty else 0.0
        max_tv = round(float(df_success["amount"].max()), 2) if not df_success.empty else 0.0
        success_rate = round((successful_txns / total_txns) * 100.0, 2) if total_txns > 0 else 0.0

        resolved_start = str(start_date) if start_date else str(df["date"].min())
        resolved_end = str(end_date) if end_date else str(df["date"].max())

        return SalesSummaryResponse(
            merchant_id=merchant_id,
            total_revenue=total_revenue,
            total_transactions=total_txns,
            average_transaction_value=avg_tv,
            minimum_transaction_value=min_tv,
            maximum_transaction_value=max_tv,
            successful_transactions=successful_txns,
            failed_transactions=failed_txns,
            success_rate=success_rate,
            start_date=resolved_start,
            end_date=resolved_end
        )

    def get_daily_trends(
        self,
        merchant_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> SalesTrendsResponse:
        """Aggregate successful sales by calendar day, returning chronological time series."""
        start_dt = self._to_utc_datetime(start_date, is_end=False)
        end_dt = self._to_utc_datetime(end_date, is_end=True)

        df = self.repo.get_transactions_df(
            merchant_id=merchant_id,
            start_date=start_dt,
            end_date=end_dt,
            status="success"
        )

        if df.empty:
            return SalesTrendsResponse(
                merchant_id=merchant_id,
                start_date=str(start_date) if start_date else None,
                end_date=str(end_date) if end_date else None,
                total_days=0,
                trends=[]
            )

        grouped = df.groupby("date").agg(
            revenue=("amount", "sum"),
            transaction_count=("amount", "count")
        ).reset_index().sort_values("date")

        trend_points: List[SalesTrendPoint] = []
        for _, row in grouped.iterrows():
            rev = round(float(row["revenue"]), 2)
            cnt = int(row["transaction_count"])
            atv = round(rev / cnt, 2) if cnt > 0 else 0.0
            trend_points.append(SalesTrendPoint(
                date=str(row["date"]),
                revenue=rev,
                transaction_count=cnt,
                average_transaction_value=atv
            ))

        return SalesTrendsResponse(
            merchant_id=merchant_id,
            start_date=str(grouped["date"].min()),
            end_date=str(grouped["date"].max()),
            total_days=len(trend_points),
            trends=trend_points
        )

    def get_period_comparison(
        self,
        merchant_id: str,
        current_days: int = 14,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> SalesComparisonResponse:
        """Compare current period against the immediately preceding period of equivalent length."""
        all_df = self.repo.get_transactions_df(merchant_id=merchant_id, status="success")

        if start_date and end_date:
            curr_start_d = start_date
            curr_end_d = end_date
            num_days = max((curr_end_d - curr_start_d).days + 1, 1)
        else:
            if not all_df.empty:
                max_date = all_df["date"].max()
            else:
                max_date = datetime.now(timezone.utc).date()
            curr_end_d = max_date
            curr_start_d = curr_end_d - timedelta(days=max(current_days - 1, 0))
            num_days = current_days

        prev_end_d = curr_start_d - timedelta(days=1)
        prev_start_d = prev_end_d - timedelta(days=num_days - 1)

        # Slice current
        c_start_dt = self._to_utc_datetime(curr_start_d, is_end=False)
        c_end_dt = self._to_utc_datetime(curr_end_d, is_end=True)
        curr_df = self.repo.get_transactions_df(
            merchant_id=merchant_id,
            start_date=c_start_dt,
            end_date=c_end_dt,
            status="success"
        )

        # Slice previous
        p_start_dt = self._to_utc_datetime(prev_start_d, is_end=False)
        p_end_dt = self._to_utc_datetime(prev_end_d, is_end=True)
        prev_df = self.repo.get_transactions_df(
            merchant_id=merchant_id,
            start_date=p_start_dt,
            end_date=p_end_dt,
            status="success"
        )

        # Current metrics
        curr_rev = round(float(curr_df["amount"].sum()), 2) if not curr_df.empty else 0.0
        curr_cnt = len(curr_df)
        curr_atv = round(curr_rev / curr_cnt, 2) if curr_cnt > 0 else 0.0

        # Previous metrics
        prev_rev = round(float(prev_df["amount"].sum()), 2) if not prev_df.empty else 0.0
        prev_cnt = len(prev_df)
        prev_atv = round(prev_rev / prev_cnt, 2) if prev_cnt > 0 else 0.0

        # Differences
        rev_change = round(curr_rev - prev_rev, 2)
        rev_change_pct = self._safe_pct_change(curr_rev, prev_rev)

        cnt_change = curr_cnt - prev_cnt
        cnt_change_pct = self._safe_pct_change(float(curr_cnt), float(prev_cnt))

        atv_change = round(curr_atv - prev_atv, 2)
        atv_change_pct = self._safe_pct_change(curr_atv, prev_atv)

        return SalesComparisonResponse(
            merchant_id=merchant_id,
            current_period=PeriodMetrics(
                start_date=str(curr_start_d),
                end_date=str(curr_end_d),
                revenue=curr_rev,
                transaction_count=curr_cnt,
                average_transaction_value=curr_atv
            ),
            previous_period=PeriodMetrics(
                start_date=str(prev_start_d),
                end_date=str(prev_end_d),
                revenue=prev_rev,
                transaction_count=prev_cnt,
                average_transaction_value=prev_atv
            ),
            revenue_change=rev_change,
            revenue_change_percentage=rev_change_pct,
            transaction_change=cnt_change,
            transaction_change_percentage=cnt_change_pct,
            average_transaction_value_change=atv_change,
            average_transaction_value_change_percentage=atv_change_pct
        )

    def get_day_of_week_analysis(
        self,
        merchant_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> DayOfWeekAnalysisResponse:
        """Analyze sales distribution across Monday through Sunday."""
        start_dt = self._to_utc_datetime(start_date, is_end=False)
        end_dt = self._to_utc_datetime(end_date, is_end=True)

        df = self.repo.get_transactions_df(
            merchant_id=merchant_id,
            start_date=start_dt,
            end_date=end_dt,
            status="success"
        )

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        total_rev = float(df["amount"].sum()) if not df.empty else 0.0

        metrics_list: List[DayOfWeekMetric] = []
        for idx, name in enumerate(day_names):
            if not df.empty:
                sub = df[df["day_index"] == idx]
                rev = round(float(sub["amount"].sum()), 2)
                cnt = len(sub)
                atv = round(rev / cnt, 2) if cnt > 0 else 0.0
                share = round((rev / total_rev) * 100.0, 2) if total_rev > 0 else 0.0
            else:
                rev, cnt, atv, share = 0.0, 0, 0.0, 0.0

            metrics_list.append(DayOfWeekMetric(
                day_name=name,
                day_index=idx,
                revenue=rev,
                transaction_count=cnt,
                average_transaction_value=atv,
                revenue_share_percentage=share
            ))

        # Find strongest and weakest days
        if metrics_list and total_rev > 0:
            strongest = max(metrics_list, key=lambda x: x.revenue).day_name
            weakest = min(metrics_list, key=lambda x: x.revenue).day_name
        else:
            strongest, weakest = "N/A", "N/A"

        return DayOfWeekAnalysisResponse(
            merchant_id=merchant_id,
            days=metrics_list,
            strongest_day=strongest,
            weakest_day=weakest
        )

    def get_hourly_analysis(
        self,
        merchant_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> HourlyAnalysisResponse:
        """Analyze sales by hour of day (0-23) and operating time windows."""
        start_dt = self._to_utc_datetime(start_date, is_end=False)
        end_dt = self._to_utc_datetime(end_date, is_end=True)

        df = self.repo.get_transactions_df(
            merchant_id=merchant_id,
            start_date=start_dt,
            end_date=end_dt,
            status="success"
        )

        total_rev = float(df["amount"].sum()) if not df.empty else 0.0

        # Hourly metrics (0..23)
        hourly_list: List[HourlyMetric] = []
        for h in range(24):
            if not df.empty:
                sub = df[df["hour"] == h]
                rev = round(float(sub["amount"].sum()), 2)
                cnt = len(sub)
                atv = round(rev / cnt, 2) if cnt > 0 else 0.0
            else:
                rev, cnt, atv = 0.0, 0, 0.0

            hourly_list.append(HourlyMetric(
                hour=h,
                hour_label=f"{h:02d}:00 - {(h+1)%24:02d}:00",
                revenue=rev,
                transaction_count=cnt,
                average_transaction_value=atv
            ))

        # Broad time windows: Morning (6-12), Afternoon (12-17), Evening (17-21), Night (21-6)
        windows_def = [
            ("Morning", "06:00 - 12:00", list(range(6, 12))),
            ("Afternoon", "12:00 - 17:00", list(range(12, 17))),
            ("Evening", "17:00 - 21:00", list(range(17, 21))),
            ("Night", "21:00 - 06:00", [21, 22, 23, 0, 1, 2, 3, 4, 5]),
        ]

        windows_list: List[TimeWindowMetric] = []
        for w_name, w_hours_str, h_list in windows_def:
            if not df.empty:
                w_sub = df[df["hour"].isin(h_list)]
                w_rev = round(float(w_sub["amount"].sum()), 2)
                w_cnt = len(w_sub)
                w_atv = round(w_rev / w_cnt, 2) if w_cnt > 0 else 0.0
                w_share = round((w_rev / total_rev) * 100.0, 2) if total_rev > 0 else 0.0
            else:
                w_rev, w_cnt, w_atv, w_share = 0.0, 0, 0.0, 0.0

            windows_list.append(TimeWindowMetric(
                window_name=w_name,
                hours_range=w_hours_str,
                revenue=w_rev,
                transaction_count=w_cnt,
                average_transaction_value=w_atv,
                revenue_share_percentage=w_share
            ))

        peak_hour = max(hourly_list, key=lambda x: x.revenue).hour if total_rev > 0 else 0
        lowest_hour = min(hourly_list, key=lambda x: x.revenue).hour if total_rev > 0 else 0

        return HourlyAnalysisResponse(
            merchant_id=merchant_id,
            hourly_metrics=hourly_list,
            time_windows=windows_list,
            peak_hour=peak_hour,
            lowest_hour=lowest_hour
        )

    def get_weekend_analysis(
        self,
        merchant_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> WeekendAnalysisResponse:
        """Compare aggregate weekday (Mon-Fri) vs weekend (Sat-Sun) performance."""
        start_dt = self._to_utc_datetime(start_date, is_end=False)
        end_dt = self._to_utc_datetime(end_date, is_end=True)

        df = self.repo.get_transactions_df(
            merchant_id=merchant_id,
            start_date=start_dt,
            end_date=end_dt,
            status="success"
        )

        if df.empty:
            return WeekendAnalysisResponse(
                merchant_id=merchant_id,
                weekday_revenue=0.0,
                weekend_revenue=0.0,
                weekday_transactions=0,
                weekend_transactions=0,
                weekday_average_transaction_value=0.0,
                weekend_average_transaction_value=0.0,
                weekend_revenue_share_percentage=0.0,
                daily_avg_weekday_revenue=0.0,
                daily_avg_weekend_revenue=0.0,
                weekend_to_weekday_revenue_ratio=0.0,
                is_weekend_underperforming=False
            )

        weekday_df = df[df["day_index"].isin([0, 1, 2, 3, 4])]
        weekend_df = df[df["day_index"].isin([5, 6])]

        wday_rev = round(float(weekday_df["amount"].sum()), 2) if not weekday_df.empty else 0.0
        wend_rev = round(float(weekend_df["amount"].sum()), 2) if not weekend_df.empty else 0.0

        wday_tx = len(weekday_df)
        wend_tx = len(weekend_df)

        wday_atv = round(wday_rev / wday_tx, 2) if wday_tx > 0 else 0.0
        wend_atv = round(wend_rev / wend_tx, 2) if wend_tx > 0 else 0.0

        total_rev = wday_rev + wend_rev
        wend_share = round((wend_rev / total_rev) * 100.0, 2) if total_rev > 0 else 0.0

        wday_days_count = max(weekday_df["date"].nunique(), 1) if not weekday_df.empty else 5
        wend_days_count = max(weekend_df["date"].nunique(), 1) if not weekend_df.empty else 2

        daily_avg_wday = round(wday_rev / wday_days_count, 2)
        daily_avg_wend = round(wend_rev / wend_days_count, 2)

        ratio = round(daily_avg_wend / daily_avg_wday, 2) if daily_avg_wday > 0 else 0.0
        is_underperforming = daily_avg_wend < daily_avg_wday

        return WeekendAnalysisResponse(
            merchant_id=merchant_id,
            weekday_revenue=wday_rev,
            weekend_revenue=wend_rev,
            weekday_transactions=wday_tx,
            weekend_transactions=wend_tx,
            weekday_average_transaction_value=wday_atv,
            weekend_average_transaction_value=wend_atv,
            weekend_revenue_share_percentage=wend_share,
            daily_avg_weekday_revenue=daily_avg_wday,
            daily_avg_weekend_revenue=daily_avg_wend,
            weekend_to_weekday_revenue_ratio=ratio,
            is_weekend_underperforming=is_underperforming
        )

    def get_sales_insights(
        self,
        merchant_id: str,
        current_days: int = 14
    ) -> SalesInsightsResponse:
        """
        Synthesize deterministic business insights across trends, drivers, and timing.
        No LLM used — entirely structured rules and mathematical thresholds.
        """
        insights: List[SalesInsight] = []
        comparison = self.get_period_comparison(merchant_id=merchant_id, current_days=current_days)
        weekend_analysis = self.get_weekend_analysis(merchant_id=merchant_id)
        dow_analysis = self.get_day_of_week_analysis(merchant_id=merchant_id)
        hourly_analysis = self.get_hourly_analysis(merchant_id=merchant_id)

        rev_pct = comparison.revenue_change_percentage
        tx_pct = comparison.transaction_change_percentage
        atv_pct = comparison.average_transaction_value_change_percentage

        has_decline = rev_pct < -5.0
        primary_driver = "none"

        # 1. Revenue Trajectory Insight
        if rev_pct <= -20.0:
            insights.append(SalesInsight(
                insight_type="revenue_decline",
                severity="critical",
                metric="revenue",
                current_value=comparison.current_period.revenue,
                previous_value=comparison.previous_period.revenue,
                change_percentage=rev_pct,
                title="Critical Revenue Decline",
                explanation=f"Revenue fell sharply by {abs(rev_pct):.1f}% (Rs {abs(comparison.revenue_change):,.2f}) compared to the previous {current_days}-day period."
            ))
        elif rev_pct <= -10.0:
            insights.append(SalesInsight(
                insight_type="revenue_decline",
                severity="warning",
                metric="revenue",
                current_value=comparison.current_period.revenue,
                previous_value=comparison.previous_period.revenue,
                change_percentage=rev_pct,
                title="Moderate Revenue Contraction",
                explanation=f"Revenue decreased by {abs(rev_pct):.1f}% (Rs {abs(comparison.revenue_change):,.2f}) compared to the previous {current_days}-day period."
            ))
        elif rev_pct >= 10.0:
            insights.append(SalesInsight(
                insight_type="revenue_growth",
                severity="positive",
                metric="revenue",
                current_value=comparison.current_period.revenue,
                previous_value=comparison.previous_period.revenue,
                change_percentage=rev_pct,
                title="Healthy Revenue Growth",
                explanation=f"Revenue increased by {rev_pct:.1f}% (Rs {comparison.revenue_change:,.2f}) compared to the previous {current_days}-day period."
            ))
        else:
            insights.append(SalesInsight(
                insight_type="revenue_stable",
                severity="info",
                metric="revenue",
                current_value=comparison.current_period.revenue,
                previous_value=comparison.previous_period.revenue,
                change_percentage=rev_pct,
                title="Stable Revenue Trajectory",
                explanation=f"Revenue is holding steady ({'+' if rev_pct >= 0 else ''}{rev_pct:.1f}% change) compared to the prior period."
            ))

        # 2. Driver Root Cause Diagnosis
        if has_decline:
            if tx_pct <= -5.0 and abs(atv_pct) <= 5.0:
                primary_driver = "volume_driven"
                insights.append(SalesInsight(
                    insight_type="volume_driver",
                    severity="warning",
                    metric="transactions",
                    current_value=float(comparison.current_period.transaction_count),
                    previous_value=float(comparison.previous_period.transaction_count),
                    change_percentage=tx_pct,
                    title="Volume-Driven Decline (Footfall Drop)",
                    explanation=(
                        f"Transaction count dropped by {abs(tx_pct):.1f}%, while average basket size remained steady "
                        f"at Rs {comparison.current_period.average_transaction_value:.2f} ({atv_pct:+.1f}%). "
                        "This confirms fewer customer visits rather than smaller purchases per visit."
                    )
                ))
            elif abs(tx_pct) <= 5.0 and atv_pct <= -5.0:
                primary_driver = "basket_driven"
                insights.append(SalesInsight(
                    insight_type="basket_driver",
                    severity="warning",
                    metric="average_transaction_value",
                    current_value=comparison.current_period.average_transaction_value,
                    previous_value=comparison.previous_period.average_transaction_value,
                    change_percentage=atv_pct,
                    title="Basket-Driven Decline (Lower Spend per Visit)",
                    explanation=(
                        f"Average transaction value fell by {abs(atv_pct):.1f}%, while customer visit volume was stable "
                        f"({tx_pct:+.1f}%). Customers are visiting as often but buying fewer or cheaper items."
                    )
                ))
            elif tx_pct <= -5.0 and atv_pct <= -5.0:
                primary_driver = "volume_and_basket_driven"
                insights.append(SalesInsight(
                    insight_type="compound_driver",
                    severity="critical",
                    metric="compound",
                    current_value=comparison.current_period.revenue,
                    previous_value=comparison.previous_period.revenue,
                    change_percentage=rev_pct,
                    title="Compound Volume and Basket Contraction",
                    explanation=(
                        f"Both transaction volume ({tx_pct:.1f}%) and average basket value ({atv_pct:.1f}%) declined, "
                        "indicating simultaneously lower footfall and smaller purchase values."
                    )
                ))

        # 3. Weekend Analysis Insight
        if weekend_analysis.is_weekend_underperforming:
            gap_pct = round((1.0 - weekend_analysis.weekend_to_weekday_revenue_ratio) * 100.0, 1)
            insights.append(SalesInsight(
                insight_type="weekend_gap",
                severity="warning",
                metric="timing",
                current_value=weekend_analysis.daily_avg_weekend_revenue,
                previous_value=weekend_analysis.daily_avg_weekday_revenue,
                change_percentage=-gap_pct,
                title="Weekend Underperformance Opportunity",
                explanation=(
                    f"Weekends generate only {weekend_analysis.weekend_revenue_share_percentage:.1f}% of total sales. "
                    f"Daily weekend revenue (Rs {weekend_analysis.daily_avg_weekend_revenue:,.2f}) is {gap_pct:.1f}% lower "
                    f"than weekday average (Rs {weekend_analysis.daily_avg_weekday_revenue:,.2f})."
                )
            ))
        else:
            insights.append(SalesInsight(
                insight_type="weekend_strength",
                severity="positive",
                metric="timing",
                current_value=weekend_analysis.daily_avg_weekend_revenue,
                previous_value=weekend_analysis.daily_avg_weekday_revenue,
                change_percentage=round((weekend_analysis.weekend_to_weekday_revenue_ratio - 1.0) * 100.0, 1),
                title="Strong Weekend Performance",
                explanation=f"Weekends perform strongly, generating {weekend_analysis.weekend_revenue_share_percentage:.1f}% of total revenue."
            ))

        # 4. Weakest Day Insight
        if dow_analysis.weakest_day != "N/A":
            weak_day_obj = next((d for d in dow_analysis.days if d.day_name == dow_analysis.weakest_day), None)
            if weak_day_obj:
                insights.append(SalesInsight(
                    insight_type="weakest_day",
                    severity="info",
                    metric="timing",
                    current_value=weak_day_obj.revenue,
                    change_percentage=weak_day_obj.revenue_share_percentage,
                    title=f"Lowest Volume Day: {dow_analysis.weakest_day}",
                    explanation=(
                        f"{dow_analysis.weakest_day} is historically the slowest sales day, contributing only "
                        f"{weak_day_obj.revenue_share_percentage:.1f}% of weekly volume (Rs {weak_day_obj.revenue:,.2f})."
                    )
                ))

        # 5. Operating Window Insight
        evening_window = next((w for w in hourly_analysis.time_windows if w.window_name == "Evening"), None)
        if evening_window and evening_window.revenue_share_percentage > 0:
            insights.append(SalesInsight(
                insight_type="prime_window",
                severity="info",
                metric="timing",
                current_value=evening_window.revenue,
                change_percentage=evening_window.revenue_share_percentage,
                title="Core Business Window: Evening (5 PM - 9 PM)",
                explanation=(
                    f"Evening hours represent the primary trade window, driving {evening_window.revenue_share_percentage:.1f}% "
                    f"of total sales (Rs {evening_window.revenue:,.2f} across {evening_window.transaction_count} transactions)."
                )
            ))

        return SalesInsightsResponse(
            merchant_id=merchant_id,
            has_decline=has_decline,
            primary_driver=primary_driver,
            insights=insights
        )
