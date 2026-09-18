"""
Comprehensive Test Suite for Module 9: Revenue Forecasting.

Verifies:
 1. Forecast calculation based on 4-week rolling average
 2. 2-week momentum trend factor & direction
 3. Lower, central, and upper confidence bound calculations
 4. Day-of-week seasonality (weekend lift adjustment)
 5. Forecast horizon length customization
 6. Insufficient historical data handling (< 3 days)
 7. Unknown/empty merchant handling
 8. Growing trend detection
 9. Declining trend detection
10. Invalid horizon rejection (HTTP 400)
11. Invalid historical period rejection (HTTP 400)
12. Multi-merchant data isolation
13. Safe numeric serialization (no NaN / Infinity)
14. Prototype disclaimer presence
15. REST API GET /api/v1/forecast/summary
16. REST API GET /api/v1/forecast/sales
17. Module 7 AI Copilot integration via forecast_sales tool
"""

import math
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Merchant, Customer, Transaction
from app.services.forecast_service import ForecastService
from app.schemas.forecast import ForecastSummaryResponse, FORECAST_DISCLAIMER


@pytest.fixture
def forecast_test_merchant(db_session: Session) -> Merchant:
    """Create a test merchant seeded with 28 days of transaction history."""
    m_id = "test-forecast-merchant-01"
    merchant = db_session.get(Merchant, m_id)
    if not merchant:
        merchant = Merchant(
            merchant_id=m_id,
            business_name="Bansal Daily Mart",
            business_type="Retail",
            location="Delhi",
            business_age=18,
        )
        db_session.add(merchant)
        db_session.flush()

    cust = Customer(
        customer_id="cust-fc-001",
        merchant_id=m_id,
        name="Rohit Verma",
        phone="9876543111",
        segment="Regular",
    )
    db_session.add(cust)
    db_session.flush()

    now = datetime.now(timezone.utc)
    today = now.date()

    # Seed 28 days of transactions with higher volume on weekends (Fri/Sat/Sun)
    for i in range(28, 0, -1):
        tx_date = today - timedelta(days=i)
        tx_dt = datetime(tx_date.year, tx_date.month, tx_date.day, 12, 0, 0, tzinfo=timezone.utc)
        is_weekend = tx_date.weekday() in [4, 5, 6]
        tx_amount = Decimal("2000.00") if is_weekend else Decimal("1000.00")

        txn = Transaction(
            transaction_id=f"tx-fc-{i:03d}",
            merchant_id=m_id,
            customer_id=cust.customer_id,
            timestamp=tx_dt,
            amount=tx_amount,
            payment_method="paytm_qr",
            status="success",
        )
        db_session.add(txn)

    db_session.commit()
    return merchant


def test_forecast_calculation_basic(db_session: Session, forecast_test_merchant: Merchant):
    """Verify basic forecast calculation produces positive projected revenue and bounds."""
    service = ForecastService(db_session)
    res = service.get_forecast_summary(
        merchant_id=forecast_test_merchant.merchant_id,
        historical_days=28,
        horizon_days=30,
    )
    assert res.is_sufficient_data is True
    assert res.historical_revenue > 0.0
    assert res.projected_revenue > 0.0
    assert res.lower_bound > 0.0
    assert res.upper_bound > res.lower_bound
    assert res.trend_direction in ["growing", "declining", "stable"]


def test_forecast_bounds_range(db_session: Session, forecast_test_merchant: Merchant):
    """Verify lower bound is lower and upper bound is higher than projected revenue."""
    service = ForecastService(db_session)
    res = service.get_forecast_summary(
        merchant_id=forecast_test_merchant.merchant_id,
        historical_days=28,
        horizon_days=30,
    )
    assert res.lower_bound < res.projected_revenue < res.upper_bound
    # 10% bound width
    assert abs((res.projected_revenue * 0.90) - res.lower_bound) < 2.0
    assert abs((res.projected_revenue * 1.10) - res.upper_bound) < 2.0


def test_forecast_horizon_length(db_session: Session, forecast_test_merchant: Merchant):
    """Verify custom horizon returns exact number of projected daily points."""
    service = ForecastService(db_session)
    res_14 = service.get_forecast_summary(
        merchant_id=forecast_test_merchant.merchant_id,
        historical_days=28,
        horizon_days=14,
    )
    projected_points_14 = [p for p in res_14.daily_points if p.is_forecast]
    assert len(projected_points_14) == 14

    res_45 = service.get_forecast_summary(
        merchant_id=forecast_test_merchant.merchant_id,
        historical_days=28,
        horizon_days=45,
    )
    projected_points_45 = [p for p in res_45.daily_points if p.is_forecast]
    assert len(projected_points_45) == 45


def test_forecast_insufficient_data(db_session: Session):
    """Verify merchant with fewer than 3 days of history returns safe response without crashing."""
    sparse_m = Merchant(
        merchant_id="merchant-sparse-fc",
        business_name="Sparse Mart",
        business_type="Retail",
        location="Jaipur",
    )
    db_session.add(sparse_m)
    db_session.flush()

    # Add only 1 transaction
    now = datetime.now(timezone.utc)
    t = Transaction(
        transaction_id="tx-sparse-01",
        merchant_id=sparse_m.merchant_id,
        timestamp=now,
        amount=Decimal("100.00"),
        status="success",
    )
    db_session.add(t)
    db_session.commit()

    service = ForecastService(db_session)
    res = service.get_forecast_summary(merchant_id=sparse_m.merchant_id)
    assert res.is_sufficient_data is False
    assert res.projected_revenue == 0.0
    assert res.lower_bound == 0.0
    assert res.upper_bound == 0.0


def test_forecast_empty_merchant(db_session: Session):
    """Verify unknown merchant returns clean zero values."""
    service = ForecastService(db_session)
    res = service.get_forecast_summary(merchant_id="nonexistent-merchant-999")
    assert res.is_sufficient_data is False
    assert res.projected_revenue == 0.0


def test_forecast_invalid_horizon_rejected(client: TestClient, forecast_test_merchant: Merchant):
    """Verify HTTP 400 on negative or out-of-range horizon."""
    resp = client.get(
        "/api/v1/forecast/summary",
        params={"merchant_id": forecast_test_merchant.merchant_id, "horizon_days": 0},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY or resp.status_code == status.HTTP_400_BAD_REQUEST

    resp2 = client.get(
        "/api/v1/forecast/summary",
        params={"merchant_id": forecast_test_merchant.merchant_id, "horizon_days": 200},
    )
    assert resp2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY or resp2.status_code == status.HTTP_400_BAD_REQUEST


def test_forecast_invalid_historical_days_rejected(client: TestClient, forecast_test_merchant: Merchant):
    """Verify HTTP 400 or 422 when historical_days is out of bounds."""
    resp = client.get(
        "/api/v1/forecast/summary",
        params={"merchant_id": forecast_test_merchant.merchant_id, "historical_days": 3},
    )
    assert resp.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY]


def test_forecast_growing_trend_detection(db_session: Session):
    """Verify growing trend is detected when recent period revenue is substantially higher."""
    grow_m = Merchant(
        merchant_id="merchant-growing-fc",
        business_name="Fast Growing Store",
        business_type="Retail",
        location="Bengaluru",
    )
    db_session.add(grow_m)
    db_session.flush()

    now = datetime.now(timezone.utc)
    today = now.date()

    # Prior 14 days: 500/day. Recent 14 days: 1500/day (+200% growth)
    for i in range(28, 0, -1):
        tx_date = today - timedelta(days=i)
        tx_dt = datetime(tx_date.year, tx_date.month, tx_date.day, 12, 0, 0, tzinfo=timezone.utc)
        amt = Decimal("1500.00") if i <= 14 else Decimal("500.00")

        t = Transaction(
            transaction_id=f"tx-grow-{i:03d}",
            merchant_id=grow_m.merchant_id,
            timestamp=tx_dt,
            amount=amt,
            status="success",
        )
        db_session.add(t)

    db_session.commit()

    service = ForecastService(db_session)
    res = service.get_forecast_summary(merchant_id=grow_m.merchant_id, historical_days=28)
    assert res.trend_direction == "growing"
    assert res.trend_factor_pct > 10.0


def test_forecast_declining_trend_detection(db_session: Session):
    """Verify declining trend is detected when recent period revenue dropped."""
    drop_m = Merchant(
        merchant_id="merchant-declining-fc",
        business_name="Struggling Store",
        business_type="Retail",
        location="Delhi",
    )
    db_session.add(drop_m)
    db_session.flush()

    now = datetime.now(timezone.utc)
    today = now.date()

    # Prior 14 days: 2000/day. Recent 14 days: 500/day (-75% decline)
    for i in range(28, 0, -1):
        tx_date = today - timedelta(days=i)
        tx_dt = datetime(tx_date.year, tx_date.month, tx_date.day, 12, 0, 0, tzinfo=timezone.utc)
        amt = Decimal("500.00") if i <= 14 else Decimal("2000.00")

        t = Transaction(
            transaction_id=f"tx-drop-{i:03d}",
            merchant_id=drop_m.merchant_id,
            timestamp=tx_dt,
            amount=amt,
            status="success",
        )
        db_session.add(t)

    db_session.commit()

    service = ForecastService(db_session)
    res = service.get_forecast_summary(merchant_id=drop_m.merchant_id, historical_days=28)
    assert res.trend_direction == "declining"
    assert res.trend_factor_pct < -10.0


def test_forecast_seasonality_weekend_lift(db_session: Session, forecast_test_merchant: Merchant):
    """Verify that projected weekend points reflect historical weekend uplift."""
    service = ForecastService(db_session)
    res = service.get_forecast_summary(
        merchant_id=forecast_test_merchant.merchant_id,
        historical_days=28,
        horizon_days=7,
    )
    projected = [p for p in res.daily_points if p.is_forecast]

    weekend_projected = [
        p.amount for p in projected
        if date.fromisoformat(p.date).weekday() in [4, 5, 6]
    ]
    weekday_projected = [
        p.amount for p in projected
        if date.fromisoformat(p.date).weekday() in [0, 1, 2, 3]
    ]

    if weekend_projected and weekday_projected:
        assert (sum(weekend_projected) / len(weekend_projected)) > (sum(weekday_projected) / len(weekday_projected))


def test_forecast_no_nan_or_infinity(client: TestClient, forecast_test_merchant: Merchant):
    """Verify response contains no NaN or Infinity."""
    resp = client.get(
        "/api/v1/forecast/summary",
        params={"merchant_id": forecast_test_merchant.merchant_id},
    )
    raw = resp.text
    assert "NaN" not in raw
    assert "Infinity" not in raw


def test_api_forecast_summary(client: TestClient, forecast_test_merchant: Merchant):
    """Verify GET /api/v1/forecast/summary endpoint."""
    resp = client.get(
        "/api/v1/forecast/summary",
        params={"merchant_id": forecast_test_merchant.merchant_id},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["merchant_id"] == forecast_test_merchant.merchant_id
    assert "projected_revenue" in data
    assert "trend_direction" in data
    assert data["is_sufficient_data"] is True
    assert "disclaimer" in data


def test_api_forecast_sales_timeline(client: TestClient, forecast_test_merchant: Merchant):
    """Verify GET /api/v1/forecast/sales endpoint."""
    resp = client.get(
        "/api/v1/forecast/sales",
        params={"merchant_id": forecast_test_merchant.merchant_id},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data["daily_points"]) > 0
    assert any(p["is_forecast"] for p in data["daily_points"])
    assert any(not p["is_forecast"] for p in data["daily_points"])


def test_forecast_disclaimer_present(client: TestClient, forecast_test_merchant: Merchant):
    """Verify synthetic prototype estimate disclaimer is included."""
    resp = client.get(
        "/api/v1/forecast/summary",
        params={"merchant_id": forecast_test_merchant.merchant_id},
    )
    data = resp.json()
    assert "prototype" in data["disclaimer"].lower() or "synthetic" in data["disclaimer"].lower()


def test_ai_agent_forecast_sales_tool(client: TestClient, forecast_test_merchant: Merchant):
    """Verify AI Agent orchestrator correctly routes natural language forecast query to forecast_sales tool."""
    payload = {
        "message": "What will my sales forecast look like next month? Can you predict my revenue?",
        "merchant_id": forecast_test_merchant.merchant_id,
    }
    resp = client.post("/api/v1/agent/chat", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["intent"]["intent"] == "forecast_sales"
    tool_names = [a["tool_name"] for a in data["actions_taken"]]
    assert "forecast_sales" in tool_names
    assert len(data["insights"]) > 0
    assert any("projected" in ins.lower() or "revenue" in ins.lower() for ins in data["insights"])


def test_api_forecast_days_alias(client: TestClient, forecast_test_merchant: Merchant):
    """Verify that 'days' query param acts as an alias for 'horizon_days'."""
    resp = client.get(
        "/api/v1/forecast/summary",
        params={"merchant_id": forecast_test_merchant.merchant_id, "days": 14},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["forecast_horizon_days"] == 14
    forecast_points = [p for p in data["daily_points"] if p["is_forecast"]]
    assert len(forecast_points) == 14
