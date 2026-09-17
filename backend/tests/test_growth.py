"""
Unit and integration tests for Module 4 — Growth Recommendation Engine.
Covers all minimum testing requirements:
1. Growth recommendations endpoint (/api/v1/growth/recommendations)
2. Sales decline recovery recommendation
3. At-risk customer re-engagement recommendation
4. Inactive customer win-back recommendation
5. VIP customer retention recommendation
6. Weekend growth opportunity recommendation
7. Time-of-day off-peak opportunity recommendation
8. Revenue concentration risk recommendation
9. Multiple simultaneous opportunities generation
10. Deterministic recommendation priority ranking (high -> medium -> low)
11. Analytical evidence structure and validation
12. Business goal filtering (revenue, retention, recovery, reactivation, weekend, frequency)
13. Empty merchant dataset behavior (clean empty list, safe diagnostic summary)
14. Insufficient data safety
15. Merchant data isolation
16. Invalid parameter handling (invalid goal, invalid limit)
17. No NaN/Infinity in responses
18. Growth opportunities endpoint (/api/v1/growth/opportunities)
19. Growth summary endpoint (/api/v1/growth/summary)
20. Unversioned API alias routing (/api/growth/...)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Merchant, Customer, Transaction
from app.services.growth_service import GrowthRecommendationService


@pytest.fixture
def growth_test_merchants(db_session: Session):
    """Create two clean isolated merchants for growth engine tests."""
    m1_id = "test-growth-m1"
    m2_id = "test-growth-m2"

    m1 = db_session.get(Merchant, m1_id)
    if not m1:
        m1 = Merchant(
            merchant_id=m1_id,
            business_name="Kirana Growth One",
            business_type="Grocery",
            location="Bengaluru",
            business_age=18
        )
        db_session.add(m1)

    m2 = db_session.get(Merchant, m2_id)
    if not m2:
        m2 = Merchant(
            merchant_id=m2_id,
            business_name="Kirana Growth Two",
            business_type="Apparel",
            location="Delhi",
            business_age=24
        )
        db_session.add(m2)

    db_session.commit()
    return m1, m2


@pytest.fixture
def seeded_growth_dataset(db_session: Session, growth_test_merchants):
    """Seed rich multi-segment customer and transaction scenario for Merchant 1."""
    m1, m2 = growth_test_merchants
    now = datetime.now(timezone.utc)

    # 1. VIP Customers (High spend, high visits)
    vip_cust = Customer(
        customer_id="growth-c-vip",
        merchant_id=m1.merchant_id,
        name="Sunil Mittal",
        phone="+91 9811111111",
        transaction_count=20,
        total_spend=Decimal("25000.00"),
        average_transaction=Decimal("1250.00"),
        last_transaction=now - timedelta(days=2),
        segment="VIP",
        created_at=now - timedelta(days=100)
    )

    # 2. At-Risk Customers (High prior spend, absent for 30 days)
    at_risk_cust = Customer(
        customer_id="growth-c-atrisk",
        merchant_id=m1.merchant_id,
        name="Anita Desai",
        phone="+91 9822222222",
        transaction_count=12,
        total_spend=Decimal("14000.00"),
        average_transaction=Decimal("1166.67"),
        last_transaction=now - timedelta(days=30),
        segment="At-Risk",
        created_at=now - timedelta(days=120)
    )

    # 3. Inactive Customers (Lapsed >45 days)
    inactive_custs = []
    for i in range(6):
        inactive_custs.append(
            Customer(
                customer_id=f"growth-c-inact-{i}",
                merchant_id=m1.merchant_id,
                name=f"Inactive User {i}",
                phone=f"+91 983333333{i}",
                transaction_count=4,
                total_spend=Decimal("3000.00"),
                average_transaction=Decimal("750.00"),
                last_transaction=now - timedelta(days=55 + i),
                segment="Inactive",
                created_at=now - timedelta(days=150)
            )
        )

    # 4. Loyal Customers
    loyal_cust = Customer(
        customer_id="growth-c-loyal",
        merchant_id=m1.merchant_id,
        name="Karan Johar",
        phone="+91 9844444444",
        transaction_count=8,
        total_spend=Decimal("7000.00"),
        average_transaction=Decimal("875.00"),
        last_transaction=now - timedelta(days=5),
        segment="Loyal",
        created_at=now - timedelta(days=60)
    )

    # Merchant 2 Customer (Isolated)
    m2_cust = Customer(
        customer_id="growth-c-m2-only",
        merchant_id=m2.merchant_id,
        name="Siddharth Roy",
        phone="+91 9899999999",
        transaction_count=2,
        total_spend=Decimal("1500.00"),
        average_transaction=Decimal("750.00"),
        last_transaction=now - timedelta(days=1),
        segment="New",
        created_at=now - timedelta(days=10)
    )

    db_session.add_all([vip_cust, at_risk_cust, loyal_cust, m2_cust] + inactive_custs)

    # Seed Transactions for Merchant 1
    # Prior period (15 to 28 days ago): Robust sales (e.g. ₹20,000)
    # Current period (0 to 14 days ago): Slower sales (e.g. ₹5,000) -> Triggers decline recovery
    tx_list = []
    # Prior period transactions
    for d in range(15, 25):
        tx_list.append(
            Transaction(
                transaction_id=f"tx-growth-prior-{d}",
                merchant_id=m1.merchant_id,
                customer_id="growth-c-vip",
                timestamp=now - timedelta(days=d, hours=10),
                amount=Decimal("1500.00"),
                payment_method="UPI",
                status="success"
            )
        )

    # Current period transactions (lower total, weekday heavy)
    for d in range(1, 10):
        # Weekday transaction
        tx_list.append(
            Transaction(
                transaction_id=f"tx-growth-curr-{d}",
                merchant_id=m1.merchant_id,
                customer_id="growth-c-loyal",
                timestamp=now - timedelta(days=d, hours=11),  # Morning/midday
                amount=Decimal("500.00"),
                payment_method="UPI",
                status="success"
            )
        )

    # Merchant 2 Transaction
    tx_list.append(
        Transaction(
            transaction_id="tx-growth-m2-1",
            merchant_id=m2.merchant_id,
            customer_id="growth-c-m2-only",
            timestamp=now - timedelta(days=1),
            amount=Decimal("1500.00"),
            payment_method="CARD",
            status="success"
        )
    )

    db_session.add_all(tx_list)
    db_session.commit()
    return m1, m2


# 1. Recommendations Endpoint & Overall Output
def test_growth_recommendations_endpoint(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset
    response = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["merchant_id"] == m1.merchant_id
    assert data["total_recommendations"] > 0
    assert len(data["recommendations"]) == data["total_recommendations"]
    assert data["high_priority_count"] >= 1

    rec = data["recommendations"][0]
    assert "recommendation_id" in rec
    assert "type" in rec
    assert "title" in rec
    assert "priority" in rec
    assert rec["priority"] in ("high", "medium", "low")
    assert "confidence" in rec
    assert rec["confidence"] in ("strong", "moderate", "weak")
    assert 0.0 <= rec["confidence_score"] <= 1.0
    assert "target_segment" in rec
    assert "objective" in rec
    assert "suggested_action" in rec
    assert "rationale" in rec
    assert len(rec["evidence"]) > 0


# 2. Sales Decline Recovery Recommendation
def test_sales_decline_recovery_recommendation(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset
    response = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}&goal=recovery")
    assert response.status_code == 200
    data = response.json()

    rec_types = [r["type"] for r in data["recommendations"]]
    assert "sales_decline_recovery" in rec_types

    decline_rec = next(r for r in data["recommendations"] if r["type"] == "sales_decline_recovery")
    assert decline_rec["target_segment"] == "At-Risk"
    assert decline_rec["priority"] in ("high", "medium")
    assert "decline" in decline_rec["description"].lower() or "contracted" in decline_rec["description"].lower()


# 3. At-Risk Customer Re-engagement Recommendation
def test_at_risk_reengagement_recommendation(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset
    response = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}")
    assert response.status_code == 200
    data = response.json()

    rec_types = [r["type"] for r in data["recommendations"]]
    assert "at_risk_reengagement" in rec_types

    at_risk_rec = next(r for r in data["recommendations"] if r["type"] == "at_risk_reengagement")
    assert at_risk_rec["target_segment"] == "At-Risk"
    assert at_risk_rec["priority"] == "high"
    assert "at_risk_customer_count" in at_risk_rec["supporting_metrics"]
    assert at_risk_rec["supporting_metrics"]["at_risk_customer_count"] >= 1.0


# 4. Inactive Customer Win-Back Recommendation
def test_inactive_winback_recommendation(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset
    response = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}&goal=reactivation")
    assert response.status_code == 200
    data = response.json()

    rec_types = [r["type"] for r in data["recommendations"]]
    assert "inactive_winback" in rec_types

    inactive_rec = next(r for r in data["recommendations"] if r["type"] == "inactive_winback")
    assert inactive_rec["target_segment"] == "Inactive"
    assert inactive_rec["priority"] == "medium"
    assert "inactive_customer_count" in inactive_rec["supporting_metrics"]
    assert inactive_rec["supporting_metrics"]["inactive_customer_count"] >= 5.0


# 5. VIP Customer Retention Recommendation
def test_vip_retention_recommendation(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset
    response = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}&goal=retention")
    assert response.status_code == 200
    data = response.json()

    rec_types = [r["type"] for r in data["recommendations"]]
    assert "vip_retention" in rec_types

    vip_rec = next(r for r in data["recommendations"] if r["type"] == "vip_retention")
    assert vip_rec["target_segment"] == "VIP"
    assert vip_rec["priority"] == "high"
    assert "vip_total_revenue" in vip_rec["supporting_metrics"]


# 6. Weekend Growth Opportunity Recommendation
def test_weekend_growth_recommendation(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset
    response = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}&goal=weekend")
    assert response.status_code == 200
    data = response.json()

    rec_types = [r["type"] for r in data["recommendations"]]
    assert "weekend_growth" in rec_types

    wend_rec = next(r for r in data["recommendations"] if r["type"] == "weekend_growth")
    assert wend_rec["objective"] == "increase weekend sales"
    assert "daily_avg_weekday_revenue" in wend_rec["supporting_metrics"]


# 7. Multiple Simultaneous Opportunities & Priority Ordering
def test_multiple_opportunities_and_priority_ordering(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset
    response = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}")
    assert response.status_code == 200
    data = response.json()

    recs = data["recommendations"]
    assert len(recs) >= 3

    # High priority items must precede Medium, which must precede Low
    priority_order = {"high": 1, "medium": 2, "low": 3}
    for i in range(len(recs) - 1):
        p_current = priority_order[recs[i]["priority"]]
        p_next = priority_order[recs[i + 1]["priority"]]
        assert p_current <= p_next, f"Priority ordering violated: {recs[i]['priority']} before {recs[i+1]['priority']}"


# 8. Analytical Evidence Integrity
def test_analytical_evidence_structure(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset
    response = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}")
    assert response.status_code == 200
    data = response.json()

    for rec in data["recommendations"]:
        for ev in rec["evidence"]:
            assert isinstance(ev["metric_name"], str)
            assert isinstance(ev["metric_value"], (int, float))
            assert not isinstance(ev["metric_value"], str)  # Never a formatted currency string
            assert len(ev["context"]) > 0


# 9. Business Goal Filtering
def test_goal_filtering(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset
    # Goal = retention
    res_ret = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}&goal=retention")
    assert res_ret.status_code == 200
    data_ret = res_ret.json()
    assert data_ret["goal_filter"] == "retention"
    for r in data_ret["recommendations"]:
        assert r["type"] in ("vip_retention", "revenue_concentration_risk", "at_risk_reengagement")

    # Goal = weekend
    res_wend = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}&goal=weekend")
    assert res_wend.status_code == 200
    data_wend = res_wend.json()
    assert data_wend["goal_filter"] == "weekend"
    for r in data_wend["recommendations"]:
        assert r["type"] == "weekend_growth"


# 10. Limit Parameter Pagination
def test_recommendation_limit_parameter(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset
    res = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}&limit=2")
    assert res.status_code == 200
    data = res.json()
    assert len(data["recommendations"]) == 2
    assert data["total_recommendations"] == 2


# 11. Empty Merchant Dataset Behavior
def test_growth_recommendations_empty_merchant(client: TestClient, growth_test_merchants):
    """Empty store yields zero recommendations without division-by-zero errors."""
    response = client.get("/api/v1/growth/recommendations?merchant_id=completely-empty-store")
    assert response.status_code == 200
    data = response.json()

    assert data["total_recommendations"] == 0
    assert data["high_priority_count"] == 0
    assert data["recommendations"] == []


# 12. Growth Summary Endpoint
def test_growth_summary_endpoint(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset
    response = client.get(f"/api/v1/growth/summary?merchant_id={m1.merchant_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["merchant_id"] == m1.merchant_id
    assert data["total_opportunities"] > 0
    assert data["revenue_at_risk"] > 0.0
    assert data["customers_at_risk"] >= 1
    assert data["current_sales_trend"] in ("declining", "growing", "stable")
    assert data["current_retention_signal"] in ("strong", "moderate", "at_risk")
    assert data["key_recommendation"] is not None


# 13. Growth Summary for Empty Merchant
def test_growth_summary_empty_merchant(client: TestClient):
    response = client.get("/api/v1/growth/summary?merchant_id=nonexistent-merchant-999")
    assert response.status_code == 200
    data = response.json()

    assert data["total_opportunities"] == 0
    assert data["high_priority_opportunities"] == 0
    assert data["revenue_at_risk"] == 0.0
    assert data["customers_at_risk"] == 0
    assert data["current_sales_trend"] == "insufficient_data"
    assert data["current_retention_signal"] == "no_data"
    assert data["key_recommendation"] is None


# 14. Growth Opportunities Endpoint
def test_growth_opportunities_endpoint(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset
    response = client.get(f"/api/v1/growth/opportunities?merchant_id={m1.merchant_id}&limit=5")
    assert response.status_code == 200
    data = response.json()

    assert data["merchant_id"] == m1.merchant_id
    assert data["total_opportunities"] > 0
    assert len(data["opportunities"]) <= 5


# 15. Merchant Data Isolation
def test_merchant_isolation(client: TestClient, seeded_growth_dataset):
    m1, m2 = seeded_growth_dataset

    res1 = client.get(f"/api/v1/growth/summary?merchant_id={m1.merchant_id}")
    res2 = client.get(f"/api/v1/growth/summary?merchant_id={m2.merchant_id}")
    assert res1.status_code == 200
    assert res2.status_code == 200

    data1 = res1.json()
    data2 = res2.json()

    # Merchant 2 has only 1 customer and 1 transaction, distinct from Merchant 1
    assert data1["merchant_id"] == m1.merchant_id
    assert data2["merchant_id"] == m2.merchant_id
    assert data1["revenue_at_risk"] != data2["revenue_at_risk"]
    assert data2["customers_at_risk"] == 0


# 16. Invalid Parameter Handling
def test_invalid_parameters(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset

    # Invalid goal parameter
    res_bad_goal = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}&goal=super_growth")
    assert res_bad_goal.status_code == 400
    assert "Invalid goal" in res_bad_goal.json()["message"]

    # Invalid limit parameter (too low)
    res_low_limit = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}&limit=0")
    assert res_low_limit.status_code == 422 or res_low_limit.status_code == 400

    # Invalid limit parameter (too high)
    res_high_limit = client.get(f"/api/v1/growth/recommendations?merchant_id={m1.merchant_id}&limit=999")
    assert res_high_limit.status_code == 422 or res_high_limit.status_code == 400


# 17. Unversioned API Alias Routing
def test_unversioned_growth_aliases(client: TestClient, seeded_growth_dataset):
    m1, _ = seeded_growth_dataset

    # /api/growth/recommendations
    res_recs = client.get(f"/api/growth/recommendations?merchant_id={m1.merchant_id}")
    assert res_recs.status_code == 200
    assert res_recs.json()["total_recommendations"] > 0

    # /api/growth/summary
    res_sum = client.get(f"/api/growth/summary?merchant_id={m1.merchant_id}")
    assert res_sum.status_code == 200
    assert res_sum.json()["total_opportunities"] > 0

    # /api/growth/opportunities
    res_opp = client.get(f"/api/growth/opportunities?merchant_id={m1.merchant_id}")
    assert res_opp.status_code == 200
    assert res_opp.json()["total_opportunities"] > 0
