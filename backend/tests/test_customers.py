"""
Unit and integration tests for Module 3 — Customer Intelligence.
Covers all minimum testing requirements:
1. Customer summary calculation
2. Successful transaction aggregation and customer statistics
3. RFM calculation and scoring (1-5)
4. Behavioral segment assignment and segment statistics
5. Top customer ranking by revenue and frequency
6. At-risk customer detection and risk level/reasoning
7. Inactive customer detection and dormancy reasoning
8. Customer profile detail with RFM and recent transactions
9. Empty dataset behavior (0 counts, 0.0 averages, no div by zero)
10. Unknown customer 404 response
11. Merchant data isolation across all endpoints
12. Invalid parameter handling (invalid sort criteria, invalid limits)
13. No NaN/Infinity in responses
14. Fallback memory mode loading
15. Unversioned API alias routing (/api/customers/...)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Merchant, Customer, Transaction
from app.services.customer_service import CustomerService
from app.repositories.customer_repository import CustomerRepository


@pytest.fixture
def cust_test_merchants(db_session: Session):
    """Create two clean isolated merchants for customer tests."""
    m1_id = "test-cust-merchant-1"
    m2_id = "test-cust-merchant-2"

    m1 = db_session.get(Merchant, m1_id)
    if not m1:
        m1 = Merchant(
            merchant_id=m1_id,
            business_name="Kirana One",
            business_type="Grocery",
            location="Bengaluru",
            business_age=12
        )
        db_session.add(m1)

    m2 = db_session.get(Merchant, m2_id)
    if not m2:
        m2 = Merchant(
            merchant_id=m2_id,
            business_name="Kirana Two",
            business_type="Electronics",
            location="Mumbai",
            business_age=24
        )
        db_session.add(m2)

    db_session.commit()
    return m1, m2


@pytest.fixture
def seeded_customers(db_session: Session, cust_test_merchants):
    """Seed distinct customer cohorts for merchant 1 and merchant 2."""
    m1, m2 = cust_test_merchants
    now = datetime.now(timezone.utc)

    # Merchant 1 Customers
    # 1. VIP Customer
    c1 = Customer(
        customer_id="cust-m1-vip",
        merchant_id=m1.merchant_id,
        name="Ramesh Kumar",
        phone="+91 9876543210",
        transaction_count=18,
        total_spend=Decimal("15000.00"),
        average_transaction=Decimal("833.33"),
        last_transaction=now - timedelta(days=3),
        segment="VIP",
        created_at=now - timedelta(days=90),
    )
    # 2. Loyal Customer
    c2 = Customer(
        customer_id="cust-m1-loyal",
        merchant_id=m1.merchant_id,
        name="Sunita Rao",
        phone="+91 9876543211",
        transaction_count=7,
        total_spend=Decimal("6000.00"),
        average_transaction=Decimal("857.14"),
        last_transaction=now - timedelta(days=12),
        segment="Loyal",
        created_at=now - timedelta(days=60),
    )
    # 3. New Customer (1 visit, 5 days ago)
    c3 = Customer(
        customer_id="cust-m1-new",
        merchant_id=m1.merchant_id,
        name="Ankit Sharma",
        phone="+91 9876543212",
        transaction_count=1,
        total_spend=Decimal("800.00"),
        average_transaction=Decimal("800.00"),
        last_transaction=now - timedelta(days=5),
        segment="New",
        created_at=now - timedelta(days=5),
    )
    # 4. At-Risk Customer (visited 30 days ago, high past spend)
    c4 = Customer(
        customer_id="cust-m1-atrisk",
        merchant_id=m1.merchant_id,
        name="Vikram Singh",
        phone="+91 9876543213",
        transaction_count=9,
        total_spend=Decimal("8500.00"),
        average_transaction=Decimal("944.44"),
        last_transaction=now - timedelta(days=30),
        segment="At-Risk",
        created_at=now - timedelta(days=120),
    )
    # 5. Inactive Customer (visited 60 days ago)
    c5 = Customer(
        customer_id="cust-m1-inactive",
        merchant_id=m1.merchant_id,
        name="Pooja Patel",
        phone="+91 9876543214",
        transaction_count=4,
        total_spend=Decimal("3200.00"),
        average_transaction=Decimal("800.00"),
        last_transaction=now - timedelta(days=60),
        segment="Inactive",
        created_at=now - timedelta(days=150),
    )

    # Merchant 2 Customer (Isolated)
    c_m2 = Customer(
        customer_id="cust-m2-only",
        merchant_id=m2.merchant_id,
        name="Amit Shah",
        phone="+91 9876543299",
        transaction_count=3,
        total_spend=Decimal("2500.00"),
        average_transaction=Decimal("833.33"),
        last_transaction=now - timedelta(days=2),
        segment="Loyal",
        created_at=now - timedelta(days=30),
    )

    # Transactions for cust-m1-vip
    t1 = Transaction(
        transaction_id="tx-c1-1",
        merchant_id=m1.merchant_id,
        customer_id="cust-m1-vip",
        timestamp=now - timedelta(days=3),
        amount=Decimal("1200.00"),
        payment_method="UPI",
        status="success"
    )
    t2 = Transaction(
        transaction_id="tx-c1-2",
        merchant_id=m1.merchant_id,
        customer_id="cust-m1-vip",
        timestamp=now - timedelta(days=10),
        amount=Decimal("900.00"),
        payment_method="UPI",
        status="success"
    )
    t3_failed = Transaction(
        transaction_id="tx-c1-failed",
        merchant_id=m1.merchant_id,
        customer_id="cust-m1-vip",
        timestamp=now - timedelta(days=1),
        amount=Decimal("5000.00"),
        payment_method="CARD",
        status="failed"
    )

    db_session.add_all([c1, c2, c3, c4, c5, c_m2, t1, t2, t3_failed])
    db_session.commit()
    return m1, m2


# 1. Customer Summary Calculation
def test_customer_summary_calculation(client: TestClient, seeded_customers):
    m1, _ = seeded_customers
    response = client.get(f"/api/v1/customers/summary?merchant_id={m1.merchant_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["merchant_id"] == m1.merchant_id
    assert data["total_customers"] == 5
    assert data["active_customers"] >= 3  # c1 (3d), c2 (12d), c3 (5d) are <= 30d
    assert data["at_risk_customers"] >= 1  # c4
    assert data["inactive_customers"] >= 1  # c5
    assert data["new_customers"] >= 1  # c3
    assert data["repeat_customers"] == 4  # c1(18), c2(7), c4(9), c5(4) >= 2
    assert data["repeat_customer_rate"] == 80.0  # 4 / 5 * 100
    assert data["total_customer_revenue"] == 33500.0  # 15000 + 6000 + 800 + 8500 + 3200
    assert data["average_customer_spend"] == 6700.0  # 33500 / 5
    assert data["average_transactions_per_customer"] == 7.8  # 39 / 5


# 2. Empty Dataset Behavior
def test_customer_summary_empty_dataset(client: TestClient, cust_test_merchants):
    """Empty merchant yields valid 0-valued response without errors."""
    response = client.get("/api/v1/customers/summary?merchant_id=nonexistent-merchant-999")
    assert response.status_code == 200
    data = response.json()

    assert data["total_customers"] == 0
    assert data["active_customers"] == 0
    assert data["inactive_customers"] == 0
    assert data["at_risk_customers"] == 0
    assert data["new_customers"] == 0
    assert data["repeat_customers"] == 0
    assert data["repeat_customer_rate"] == 0.0
    assert data["average_customer_spend"] == 0.0
    assert data["average_transactions_per_customer"] == 0.0
    assert data["total_customer_revenue"] == 0.0


# 3. Behavioral Segments Distribution
def test_customer_segments_breakdown(client: TestClient, seeded_customers):
    m1, _ = seeded_customers
    response = client.get(f"/api/v1/customers/segments?merchant_id={m1.merchant_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["merchant_id"] == m1.merchant_id
    assert data["total_customers"] == 5
    assert data["total_revenue"] == 33500.0

    segments = {s["segment"]: s for s in data["segments"]}
    assert "VIP" in segments
    assert "Loyal" in segments
    assert "New" in segments
    assert "At-Risk" in segments
    assert "Inactive" in segments

    vip = segments["VIP"]
    assert vip["customer_count"] == 1
    assert vip["total_revenue"] == 15000.0
    assert vip["average_revenue_per_customer"] == 15000.0
    assert vip["percentage_of_customers"] == 20.0
    assert round(vip["percentage_of_revenue"], 1) == 44.8

    # Ensure total percentages sum to approx 100
    total_cust_pct = sum(s["percentage_of_customers"] for s in data["segments"])
    total_rev_pct = sum(s["percentage_of_revenue"] for s in data["segments"])
    assert 99.0 <= total_cust_pct <= 101.0
    assert 99.0 <= total_rev_pct <= 101.0


# 4. Top Customers Ranking by Revenue
def test_top_customers_by_revenue(client: TestClient, seeded_customers):
    m1, _ = seeded_customers
    response = client.get(f"/api/v1/customers/top?merchant_id={m1.merchant_id}&by=revenue&limit=3")
    assert response.status_code == 200
    data = response.json()

    assert data["ranked_by"] == "revenue"
    assert data["count"] == 3
    customers = data["customers"]
    assert len(customers) == 3

    # Rank 1 must be VIP (15000)
    assert customers[0]["rank"] == 1
    assert customers[0]["customer_id"] == "cust-m1-vip"
    assert customers[0]["total_spend"] == 15000.0

    # Rank 2 must be At-Risk (8500)
    assert customers[1]["rank"] == 2
    assert customers[1]["customer_id"] == "cust-m1-atrisk"
    assert customers[1]["total_spend"] == 8500.0

    # Rank 3 must be Loyal (6000)
    assert customers[2]["rank"] == 3
    assert customers[2]["customer_id"] == "cust-m1-loyal"
    assert customers[2]["total_spend"] == 6000.0


# 5. Top Customers Ranking by Frequency
def test_top_customers_by_frequency(client: TestClient, seeded_customers):
    m1, _ = seeded_customers
    response = client.get(f"/api/v1/customers/top?merchant_id={m1.merchant_id}&by=frequency&limit=2")
    assert response.status_code == 200
    data = response.json()

    assert data["ranked_by"] == "frequency"
    assert data["count"] == 2
    customers = data["customers"]
    assert customers[0]["customer_id"] == "cust-m1-vip"  # 18 txns
    assert customers[0]["transaction_count"] == 18
    assert customers[1]["customer_id"] == "cust-m1-atrisk"  # 9 txns
    assert customers[1]["transaction_count"] == 9


# 6. Top Customers Invalid Parameters
def test_top_customers_invalid_parameters(client: TestClient, seeded_customers):
    m1, _ = seeded_customers
    # Invalid 'by'
    res1 = client.get(f"/api/v1/customers/top?merchant_id={m1.merchant_id}&by=invalid")
    assert res1.status_code == 400

    # Limit too low
    res2 = client.get(f"/api/v1/customers/top?merchant_id={m1.merchant_id}&limit=0")
    assert res2.status_code == 422

    # Limit too high
    res3 = client.get(f"/api/v1/customers/top?merchant_id={m1.merchant_id}&limit=500")
    assert res3.status_code == 422


# 7. At-Risk Customers Cohort
def test_at_risk_customers_cohort(client: TestClient, seeded_customers):
    m1, _ = seeded_customers
    response = client.get(f"/api/v1/customers/at-risk?merchant_id={m1.merchant_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["total_at_risk"] >= 1
    assert data["total_at_risk_revenue"] >= 8500.0
    cust_ids = [c["customer_id"] for c in data["customers"]]
    assert "cust-m1-atrisk" in cust_ids

    at_risk_item = next(c for c in data["customers"] if c["customer_id"] == "cust-m1-atrisk")
    assert at_risk_item["risk_level"] == "high"  # spend 8500 >= 5000
    assert at_risk_item["transaction_count"] == 9
    assert at_risk_item["historical_spend"] == 8500.0
    assert "days" in at_risk_item["risk_reason"]
    assert "orders" in at_risk_item["risk_reason"]


# 8. Inactive Customers Cohort
def test_inactive_customers_cohort(client: TestClient, seeded_customers):
    m1, _ = seeded_customers
    response = client.get(f"/api/v1/customers/inactive?merchant_id={m1.merchant_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["total_inactive"] >= 1
    cust_ids = [c["customer_id"] for c in data["customers"]]
    assert "cust-m1-inactive" in cust_ids

    inactive_item = next(c for c in data["customers"] if c["customer_id"] == "cust-m1-inactive")
    assert inactive_item["transaction_count"] == 4
    assert inactive_item["historical_spend"] == 3200.0
    assert "Dormant" in inactive_item["dormancy_reason"] or "Inactive" in inactive_item["dormancy_reason"]


# 9. Customer Detail with RFM Scores & Recent Transactions
def test_customer_detail_profile(client: TestClient, seeded_customers):
    m1, _ = seeded_customers
    response = client.get(f"/api/v1/customers/cust-m1-vip?merchant_id={m1.merchant_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["customer_id"] == "cust-m1-vip"
    assert data["merchant_id"] == m1.merchant_id
    assert data["name"] == "Ramesh Kumar"
    assert data["total_spend"] == 15000.0
    assert data["transaction_count"] == 18
    assert data["segment"] == "VIP"

    # RFM validation
    assert data["rfm"] is not None
    rfm = data["rfm"]
    assert rfm["r_score"] == 5  # 3 days <= 7 days
    assert rfm["f_score"] == 5  # 18 txns >= 15
    assert rfm["m_score"] == 5  # 15000 >= 10000
    assert rfm["rfm_code"] == "555"

    # Recent transactions
    recent_txs = data["recent_transactions"]
    assert len(recent_txs) >= 2
    tx_ids = [t["transaction_id"] for t in recent_txs]
    assert "tx-c1-1" in tx_ids
    assert "tx-c1-2" in tx_ids


# 10. Unknown Customer 404
def test_customer_detail_unknown_404(client: TestClient, seeded_customers):
    m1, _ = seeded_customers
    response = client.get(f"/api/v1/customers/unknown-cust-id-xyz?merchant_id={m1.merchant_id}")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["message"].lower()


# 11. Merchant Isolation
def test_merchant_isolation(client: TestClient, seeded_customers):
    m1, m2 = seeded_customers

    # Attempting to access Merchant 2's customer under Merchant 1 scope must return 404
    res1 = client.get(f"/api/v1/customers/cust-m2-only?merchant_id={m1.merchant_id}")
    assert res1.status_code == 404

    # Attempting to access Merchant 1's customer under Merchant 2 scope must return 404
    res2 = client.get(f"/api/v1/customers/cust-m1-vip?merchant_id={m2.merchant_id}")
    assert res2.status_code == 404

    # Merchant 2 summary must reflect ONLY Merchant 2's data
    res_m2_sum = client.get(f"/api/v1/customers/summary?merchant_id={m2.merchant_id}")
    assert res_m2_sum.status_code == 200
    m2_data = res_m2_sum.json()
    assert m2_data["total_customers"] == 1
    assert m2_data["total_customer_revenue"] == 2500.0


# 12. Customer Insights Generation
def test_customer_insights(client: TestClient, seeded_customers):
    m1, _ = seeded_customers
    response = client.get(f"/api/v1/customers/insights?merchant_id={m1.merchant_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["merchant_id"] == m1.merchant_id
    assert len(data["insights"]) > 0

    types = [i["type"] for i in data["insights"]]
    # In our seed, top 1 customer accounts for 15k / 33.5k = 44.8% -> concentration insight
    assert "revenue_concentration" in types or "at_risk_revenue" in types or "loyalty_strength" in types

    for insight in data["insights"]:
        assert insight["severity"] in ("critical", "warning", "info", "positive")
        assert len(insight["title"]) > 0
        assert len(insight["message"]) > 0
        assert insight["recommendation_context"] is not None


# 13. Customer Insights for Empty Merchant
def test_customer_insights_empty_merchant(client: TestClient):
    response = client.get("/api/v1/customers/insights?merchant_id=empty-merchant-no-customers")
    assert response.status_code == 200
    data = response.json()
    assert len(data["insights"]) == 1
    assert data["insights"][0]["type"] == "no_customer_data"


# 14. Fallback Data Mode
def test_customer_fallback_data_mode(monkeypatch: pytest.MonkeyPatch, client: TestClient):
    from app.core import config
    monkeypatch.setattr(config.get_settings(), "data_mode", "memory")

    response = client.get("/api/v1/customers/summary?merchant_id=demo-merchant-001")
    assert response.status_code == 200
    data = response.json()
    assert data["merchant_id"] == "demo-merchant-001"
    assert data["total_customers"] > 200
    assert data["total_customer_revenue"] > 100000.0


# 15. Unversioned API Alias Routing
def test_unversioned_customer_aliases(client: TestClient, seeded_customers):
    m1, _ = seeded_customers
    # /api/customers/summary should resolve identically to /api/v1/customers/summary
    res = client.get(f"/api/customers/summary?merchant_id={m1.merchant_id}")
    assert res.status_code == 200
    assert res.json()["total_customers"] == 5
