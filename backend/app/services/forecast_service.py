"""
Revenue Forecasting Service for Module 9.
Provides deterministic, reproducible statistical sales forecasting:
- 4-week rolling baseline daily average
- 2-week momentum trend multiplier
- Day-of-week seasonality (weekend lift adjustment)
- Lower (-10%), central, and upper (+10%) confidence range estimates
- Full historical + projected daily timeline
"""

from typing import Optional, List, Dict
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np

from app.services.base import BaseService
from app.repositories.transaction_repository import TransactionRepository
from app.services.sales_service import SalesService
from app.schemas.forecast import (
    FORECAST_DISCLAIMER,
    ForecastPoint,
    ForecastSummaryResponse,
)


class ForecastService(BaseService):
    """Business service handling statistical revenue projections and sales trend forecasts."""

    def __init__(self, db: Session):
        super().__init__(db)
        self.repo = TransactionRepository(db)
        self.sales_service = SalesService(db)

    def get_forecast_summary(
        self,
        merchant_id: str,
        historical_days: int = 28,
        horizon_days: int = 30,
    ) -> ForecastSummaryResponse:
        """
        Generate statistical sales forecast using 4-week rolling average and 2-week momentum.
        Incorporates day-of-week seasonality and confidence interval bounds.
        """
        if historical_days < 7 or historical_days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Historical period days must be between 7 and 365. Received: {historical_days}",
            )
        if horizon_days < 1 or horizon_days > 180:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Forecast horizon days must be between 1 and 180. Received: {horizon_days}",
            )

        now = datetime.now(timezone.utc)
        today = now.date()
        hist_start_dt = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=timezone.utc) - timedelta(days=historical_days)
        hist_end_dt = datetime(today.year, today.month, today.day, 23, 59, 59, 999999, tzinfo=timezone.utc)

        # 1. Fetch successful transactions
        df_tx = self.repo.get_transactions_df(
            merchant_id=merchant_id,
            start_date=hist_start_dt,
            end_date=hist_end_dt,
            status="success",
        )

        # 2. Check for sufficient historical observations
        if df_tx.empty or len(df_tx["date"].unique()) < 3:
            return ForecastSummaryResponse(
                merchant_id=merchant_id,
                historical_period_days=historical_days,
                forecast_horizon_days=horizon_days,
                historical_revenue=0.0,
                projected_revenue=0.0,
                lower_bound=0.0,
                upper_bound=0.0,
                trend_direction="stable",
                trend_factor_pct=0.0,
                is_sufficient_data=False,
                daily_points=[],
                disclaimer=FORECAST_DISCLAIMER,
            )

        # 3. Aggregate daily revenue series across full calendar span
        all_hist_dates = [today - timedelta(days=d) for d in range(historical_days - 1, -1, -1)]
        df_tx["amount"] = pd.to_numeric(df_tx["amount"], errors="coerce").fillna(0.0)
        daily_rev_series = df_tx.groupby("date")["amount"].sum().to_dict()

        hist_points: List[ForecastPoint] = []
        daily_amounts: List[float] = []
        dow_amounts: Dict[int, List[float]] = {d: [] for d in range(7)}

        for d in all_hist_dates:
            amt = round(float(daily_rev_series.get(d, 0.0)), 2)
            hist_points.append(
                ForecastPoint(
                    date=str(d),
                    amount=amt,
                    lower_bound=None,
                    upper_bound=None,
                    is_forecast=False,
                )
            )
            daily_amounts.append(amt)
            dow_amounts[d.weekday()].append(amt)

        total_hist_rev = round(float(sum(daily_amounts)), 2)
        base_daily_avg = total_hist_rev / float(len(daily_amounts)) if daily_amounts else 0.0

        # 4. Calculate 2-week momentum / trend factor
        half_span = max(historical_days // 2, 7)
        recent_half = daily_amounts[-half_span:]
        prior_half = daily_amounts[:-half_span]

        recent_rev = sum(recent_half)
        prior_rev = sum(prior_half) if prior_half else 0.0

        if prior_rev > 0:
            raw_trend_factor = (recent_rev - prior_rev) / prior_rev
            trend_factor_pct = round(raw_trend_factor * 100.0, 2)
        else:
            raw_trend_factor = 0.0
            trend_factor_pct = 0.0

        # Clamp trend dampener to avoid extreme extrapolations (-50% to +50%)
        clamped_trend_factor = float(np.clip(raw_trend_factor, -0.50, 0.50))

        if trend_factor_pct >= 5.0:
            trend_direction = "growing"
        elif trend_factor_pct <= -5.0:
            trend_direction = "declining"
        else:
            trend_direction = "stable"

        # 5. Day-of-week seasonality factors
        seasonality: Dict[int, float] = {}
        for dow, values in dow_amounts.items():
            dow_mean = float(np.mean(values)) if values else 0.0
            if base_daily_avg > 0:
                seasonality[dow] = dow_mean / base_daily_avg
            else:
                seasonality[dow] = 1.0

        # 6. Generate forecast daily points
        forecast_points: List[ForecastPoint] = []
        base_projected_daily = base_daily_avg * (1.0 + clamped_trend_factor)

        for step in range(1, horizon_days + 1):
            future_date = today + timedelta(days=step)
            dow = future_date.weekday()
            day_multiplier = seasonality.get(dow, 1.0)
            # Bound multiplier reasonably between 0.4 and 2.5
            day_multiplier = max(min(day_multiplier, 2.5), 0.4)

            projected_day_val = round(max(base_projected_daily * day_multiplier, 0.0), 2)
            lower_val = round(projected_day_val * 0.90, 2)
            upper_val = round(projected_day_val * 1.10, 2)

            forecast_points.append(
                ForecastPoint(
                    date=str(future_date),
                    amount=projected_day_val,
                    lower_bound=lower_val,
                    upper_bound=upper_val,
                    is_forecast=True,
                )
            )

        total_projected = round(float(sum(p.amount for p in forecast_points)), 2)
        total_lower = round(float(sum(p.lower_bound or 0.0 for p in forecast_points)), 2)
        total_upper = round(float(sum(p.upper_bound or 0.0 for p in forecast_points)), 2)

        return ForecastSummaryResponse(
            merchant_id=merchant_id,
            historical_period_days=historical_days,
            forecast_horizon_days=horizon_days,
            historical_revenue=total_hist_rev,
            projected_revenue=total_projected,
            lower_bound=total_lower,
            upper_bound=total_upper,
            trend_direction=trend_direction,
            trend_factor_pct=trend_factor_pct,
            is_sufficient_data=True,
            daily_points=hist_points + forecast_points,
            disclaimer=FORECAST_DISCLAIMER,
        )
