"""
Unit and integration tests for Module 2 — Sales Intelligence.
Covers all minimum testing requirements:
1. Sales summary
2. Daily trends
3. Period comparison
4. Revenue decline detection
5. Day-of-week aggregation
6. Hourly aggregation
7. Weekend analysis
8. Sales insights
9. Empty dataset
10. Zero previous-period revenue
11. Invalid date range
12. Successful vs failed transactions distinction
"""

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Merchant, Transaction
from app.services.sales_service import SalesService
from app.repositories.transaction_repository import TransactionRepository


@pytest.fixture
def sales_test_merchant(db_session: Session) -> Merchant:
    """Create a clean isolated merchant for sales tests."""
    m_id = "test-sales-merchant"
    merchant = db_session.get(Merchant, m_id)
    if not merchant:
        merchant = Merchant(
            merchant_id=m_id,
            business_name="Test Kirana Store",
            business_type="Grocery",
            location="Bengaluru",
            business_age=24
        )
        db_session.add(merchant)
        db_session.commit()
    return merchant


def test_sales_summary_with_transactions(client: TestClient, db_session: Session, sales_test_merchant: Merchant):
    """Verify sales summary calculates correct revenue, counts, min/max, and success rate."""
    m_id = sales_test_merchant.merchant_id
    now = datetime.now(timezone.utc)

    # Seed 3 successful and 1 failed transaction
    t1 = Transaction(transaction_id="tx-sum-1", merchant_id=m_id, timestamp=now - timedelta(days=2), amount=Decimal("100.00"), status="success")
    t2 = Transaction(transaction_id="tx-sum-2", merchant_id=m_id, timestamp=now - timedelta(days=1), amount=Decimal("200.00"), status="success")
    t3 = Transaction(transaction_id="tx-sum-3", merchant_id=m_id, timestamp=now, amount=Decimal("300.00"), status="success")
    t4 = Transaction(transaction_id="tx-sum-4", merchant_id=m_id, timestamp=now, amount=Decimal("500.00"), status="failed")
    db_session.add_all([t1, t2, t3, t4])
    db_session.commit()

    response = client.get(f"/api/v1/sales/summary?merchant_id={m_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["merchant_id"] == m_id
    assert data["total_revenue"] == 600.00  # Only successful: 100 + 200 + 300
    assert data["total_transactions"] == 4
    assert data["successful_transactions"] == 3
    assert data["failed_transactions"] == 1
    assert data["average_transaction_value"] == 200.00  # 600 / 3
    assert data["minimum_transaction_value"] == 100.00
    assert data["maximum_transaction_value"] == 300.00
    assert data["success_rate"] == 75.00  # 3/4 * 100


def test_sales_summary_empty_dataset(client: TestClient):
    """Verify that an empty transaction set returns zeroes without errors."""
    response = client.get("/api/v1/sales/summary?merchant_id=non-existent-merchant")
    assert response.status_code == 200
    data = response.json()

    assert data["total_revenue"] == 0.0
    assert data["total_transactions"] == 0
    assert data["successful_transactions"] == 0
    assert data["failed_transactions"] == 0
    assert data["average_transaction_value"] == 0.0
    assert data["success_rate"] == 0.0


def test_sales_daily_trends(client: TestClient, db_session: Session, sales_test_merchant: Merchant):
    """Verify daily trends aggregate transactions chronologically by calendar date."""
    m_id = "test-trend-merchant"
    db_session.add(Merchant(merchant_id=m_id, business_name="Trend Store", business_type="Retail", location="BLR", business_age=10))
    now = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)

    # 2 txns on Day 1, 1 txn on Day 2
    t1 = Transaction(transaction_id="tx-tr-1", merchant_id=m_id, timestamp=now - timedelta(days=1), amount=Decimal("150.00"), status="success")
    t2 = Transaction(transaction_id="tx-tr-2", merchant_id=m_id, timestamp=now - timedelta(days=1), amount=Decimal("250.00"), status="success")
    t3 = Transaction(transaction_id="tx-tr-3", merchant_id=m_id, timestamp=now, amount=Decimal("500.00"), status="success")
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    response = client.get(f"/api/v1/sales/trends?merchant_id={m_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["total_days"] == 2
    assert len(data["trends"]) == 2

    day1 = data["trends"][0]
    assert day1["revenue"] == 400.00
    assert day1["transaction_count"] == 2
    assert day1["average_transaction_value"] == 200.00

    day2 = data["trends"][1]
    assert day2["revenue"] == 500.00
    assert day2["transaction_count"] == 1


def test_sales_period_comparison(client: TestClient, db_session: Session):
    """Verify period-over-period comparison calculates accurate percentage changes."""
    m_id = "test-comp-merchant"
    db_session.add(Merchant(merchant_id=m_id, business_name="Comp Store", business_type="Retail", location="BLR", business_age=10))

    # Reference date: Sept 14, 2026.
    # Current period: Sept 8 to Sept 14 (7 days). Prev period: Sept 1 to Sept 7 (7 days).
    base_date = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

    # Previous period: Rs 1000 across 5 transactions (ATV = 200)
    for i in range(5):
        db_session.add(Transaction(
            transaction_id=f"tx-prev-{i}",
            merchant_id=m_id,
            timestamp=base_date - timedelta(days=10),
            amount=Decimal("200.00"),
            status="success"
        ))

    # Current period: Rs 800 across 4 transactions (ATV = 200) -> 20% drop
    for i in range(4):
        db_session.add(Transaction(
            transaction_id=f"tx-curr-{i}",
            merchant_id=m_id,
            timestamp=base_date - timedelta(days=2),
            amount=Decimal("200.00"),
            status="success"
        ))
    db_session.commit()

    response = client.get(f"/api/v1/sales/comparison?merchant_id={m_id}&current_days=7")
    assert response.status_code == 200
    data = response.json()

    assert data["current_period"]["revenue"] == 800.00
    assert data["previous_period"]["revenue"] == 1000.00
    assert data["revenue_change"] == -200.00
    assert data["revenue_change_percentage"] == -20.00
    assert data["transaction_change"] == -1
    assert data["transaction_change_percentage"] == -20.00
    assert data["average_transaction_value_change_percentage"] == 0.00


def test_sales_period_comparison_zero_previous_revenue(client: TestClient, db_session: Session):
    """Verify zero previous-period revenue handles safely without division by zero or NaN."""
    m_id = "test-zero-prev-merchant"
    db_session.add(Merchant(merchant_id=m_id, business_name="Zero Prev Store", business_type="Retail", location="BLR", business_age=5))

    now = datetime.now(timezone.utc)
    # Only current period has transactions
    db_session.add(Transaction(transaction_id="tx-zp-1", merchant_id=m_id, timestamp=now, amount=Decimal("500.00"), status="success"))
    db_session.commit()

    response = client.get(f"/api/v1/sales/comparison?merchant_id={m_id}&current_days=7")
    assert response.status_code == 200
    data = response.json()

    assert data["current_period"]["revenue"] == 500.00
    assert data["previous_period"]["revenue"] == 0.0
    assert data["revenue_change_percentage"] == 100.0  # Safe fallback to 100%
    assert not any(v in [float("nan"), float("inf"), float("-inf")] for v in [data["revenue_change_percentage"]])


def test_sales_decline_detection_and_insights(client: TestClient, db_session: Session):
    """Verify deterministic decline detection identifies volume-driven decline with structured insights."""
    m_id = "test-decline-merchant"
    db_session.add(Merchant(merchant_id=m_id, business_name="Decline Store", business_type="Retail", location="BLR", business_age=12))

    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)

    # Previous period (14 days ago): 20 transactions @ Rs 100 = Rs 2,000
    for i in range(20):
        db_session.add(Transaction(
            transaction_id=f"tx-dec-p-{i}",
            merchant_id=m_id,
            timestamp=now - timedelta(days=20),
            amount=Decimal("100.00"),
            status="success"
        ))

    # Current period (recent): 12 transactions @ Rs 100 = Rs 1,200 (40% decline in volume, stable ATV)
    for i in range(12):
        db_session.add(Transaction(
            transaction_id=f"tx-dec-c-{i}",
            merchant_id=m_id,
            timestamp=now - timedelta(days=2),
            amount=Decimal("100.00"),
            status="success"
        ))
    db_session.commit()

    response = client.get(f"/api/v1/sales/insights?merchant_id={m_id}&current_days=14")
    assert response.status_code == 200
    data = response.json()

    assert data["has_decline"] is True
    assert data["primary_driver"] == "volume_driven"

    insight_types = [ins["insight_type"] for ins in data["insights"]]
    assert "revenue_decline" in insight_types
    assert "volume_driver" in insight_types

    decline_ins = next(ins for ins in data["insights"] if ins["insight_type"] == "revenue_decline")
    assert decline_ins["severity"] == "critical"
    assert decline_ins["change_percentage"] == -40.0


def test_sales_day_of_week_aggregation(client: TestClient, db_session: Session):
    """Verify sales are properly grouped into all 7 days of the week."""
    m_id = "test-dow-merchant"
    db_session.add(Merchant(merchant_id=m_id, business_name="DOW Store", business_type="Retail", location="BLR", business_age=8))

    # Add transactions across specific dates
    # 2026-09-07 is Monday, 2026-09-12 is Saturday
    monday_dt = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)
    saturday_dt = datetime(2026, 9, 12, 18, 0, tzinfo=timezone.utc)

    db_session.add(Transaction(transaction_id="tx-dow-1", merchant_id=m_id, timestamp=monday_dt, amount=Decimal("1000.00"), status="success"))
    db_session.add(Transaction(transaction_id="tx-dow-2", merchant_id=m_id, timestamp=saturday_dt, amount=Decimal("300.00"), status="success"))
    db_session.commit()

    response = client.get(f"/api/v1/sales/day-of-week?merchant_id={m_id}")
    assert response.status_code == 200
    data = response.json()

    assert len(data["days"]) == 7
    day_names = [d["day_name"] for d in data["days"]]
    assert day_names == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    assert data["strongest_day"] == "Monday"
    assert data["weakest_day"] in ["Tuesday", "Wednesday", "Thursday", "Friday", "Sunday"]  # Days with 0 revenue


def test_sales_hourly_aggregation(client: TestClient, db_session: Session):
    """Verify hourly distribution and operating time windows (Morning, Afternoon, Evening, Night)."""
    m_id = "test-hourly-merchant"
    db_session.add(Merchant(merchant_id=m_id, business_name="Hourly Store", business_type="Retail", location="BLR", business_age=6))

    now = datetime(2026, 9, 10, 0, 0, tzinfo=timezone.utc)
    # 1 transaction at 9 AM (Morning) and 1 transaction at 7 PM (Evening, hour 19)
    morning_tx = Transaction(transaction_id="tx-h-1", merchant_id=m_id, timestamp=now.replace(hour=9), amount=Decimal("200.00"), status="success")
    evening_tx = Transaction(transaction_id="tx-h-2", merchant_id=m_id, timestamp=now.replace(hour=19), amount=Decimal("800.00"), status="success")
    db_session.add_all([morning_tx, evening_tx])
    db_session.commit()

    response = client.get(f"/api/v1/sales/hourly?merchant_id={m_id}")
    assert response.status_code == 200
    data = response.json()

    assert len(data["hourly_metrics"]) == 24
    assert data["peak_hour"] == 19

    window_names = [w["window_name"] for w in data["time_windows"]]
    assert "Morning" in window_names
    assert "Evening" in window_names

    evening_w = next(w for w in data["time_windows"] if w["window_name"] == "Evening")
    assert evening_w["revenue"] == 800.00
    assert evening_w["revenue_share_percentage"] == 80.00


def test_sales_weekend_analysis(client: TestClient, db_session: Session):
    """Verify weekday vs weekend sales comparison and underperformance detection."""
    m_id = "test-wend-merchant"
    db_session.add(Merchant(merchant_id=m_id, business_name="Weekend Store", business_type="Retail", location="BLR", business_age=12))

    # Weekday: Mon Sept 7 (Rs 1,000)
    wday_dt = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    # Weekend: Sat Sept 12 (Rs 200)
    wend_dt = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)

    db_session.add(Transaction(transaction_id="tx-we-1", merchant_id=m_id, timestamp=wday_dt, amount=Decimal("1000.00"), status="success"))
    db_session.add(Transaction(transaction_id="tx-we-2", merchant_id=m_id, timestamp=wend_dt, amount=Decimal("200.00"), status="success"))
    db_session.commit()

    response = client.get(f"/api/v1/sales/weekend?merchant_id={m_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["weekday_revenue"] == 1000.00
    assert data["weekend_revenue"] == 200.00
    assert data["daily_avg_weekday_revenue"] == 1000.00
    assert data["daily_avg_weekend_revenue"] == 200.00
    assert data["is_weekend_underperforming"] is True
    assert data["weekend_revenue_share_percentage"] == 16.67  # 200 / 1200 * 100


def test_sales_invalid_date_range(client: TestClient):
    """Verify that start_date > end_date returns HTTP 400 Bad Request with unified error message."""
    response = client.get("/api/v1/sales/summary?start_date=2026-09-25&end_date=2026-09-10")
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert data["error_code"] == "HTTP_400"
    assert "start_date" in data["message"]
    assert "end_date" in data["message"]


def test_sales_fallback_data_mode(monkeypatch: pytest.MonkeyPatch, client: TestClient):
    """Verify that DATA_MODE=memory loads fallback JSON data properly."""
    from app.core import config
    monkeypatch.setattr(config.get_settings(), "data_mode", "memory")

    response = client.get("/api/v1/sales/summary?merchant_id=demo-merchant-001")
    assert response.status_code == 200
    data = response.json()
    assert data["merchant_id"] == "demo-merchant-001"
    assert data["total_revenue"] > 0.0
    assert data["total_transactions"] > 1000
    assert data["successful_transactions"] > 0
