"""
Unit and integration tests for Module 5 — What-if Simulator.
Covers all 22 required testing dimensions:
1. baseline calculation
2. no-offer scenario
3. percentage discount scenario
4. cashback scenario
5. comparison endpoint
6. projected transactions calculation
7. projected revenue calculation
8. incentive cost calculation
9. incremental revenue and net impact calculation
10. ROI calculation
11. zero incentive cost ROI handling (null, finite)
12. invalid negative discount validation
13. invalid negative cashback validation
14. invalid target segment handling
15. insufficient data safe handling
16. merchant isolation
17. deterministic repeated results
18. recommended scenario selection
19. finite numeric outputs (no NaN, Infinity)
20. API response schema completeness
21. route aliases (/api/what-if/* and /api/campaign/*)
22. target segment and time window filtering
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Merchant, Customer, Transaction
from app.services.what_if_service import WhatIfSimulationService
from app.schemas.what_if import SimulationRequest, WhatIfCompareRequest


@pytest.fixture
def whatif_merchants(db_session: Session):
    """Seed two distinct isolated merchants for What-if simulator testing."""
    m1_id = "test-whatif-m1"
    m2_id = "test-whatif-m2"

    m1 = db_session.get(Merchant, m1_id)
    if not m1:
        m1 = Merchant(
            merchant_id=m1_id,
            business_name="What-if Grocers 1",
            business_type="Grocery",
            location="Bengaluru",
            business_age=12,
        )
        db_session.add(m1)

    m2 = db_session.get(Merchant, m2_id)
    if not m2:
        m2 = Merchant(
            merchant_id=m2_id,
            business_name="What-if Retail 2",
            business_type="Fashion",
            location="Mumbai",
            business_age=24,
        )
        db_session.add(m2)

    db_session.commit()
    return m1, m2


@pytest.fixture
def seeded_whatif_dataset(db_session: Session, whatif_merchants):
    """Seed representative transactions and customers for Merchant 1."""
    m1, m2 = whatif_merchants
    now = datetime.now(timezone.utc)

    # 1. Customers
    c_vip = Customer(
        customer_id="whatif-c-vip",
        merchant_id=m1.merchant_id,
        name="Vikram Seth",
        phone="+91 9900000001",
        transaction_count=15,
        total_spend=Decimal("15000.00"),
        average_transaction=Decimal("1000.00"),
        last_transaction=now - timedelta(days=2),
        segment="VIP",
        created_at=now - timedelta(days=60),
    )
    c_atrisk = Customer(
        customer_id="whatif-c-atrisk",
        merchant_id=m1.merchant_id,
        name="Pooja Sharma",
        phone="+91 9900000002",
        transaction_count=8,
        total_spend=Decimal("4000.00"),
        average_transaction=Decimal("500.00"),
        last_transaction=now - timedelta(days=25),
        segment="At-Risk",
        created_at=now - timedelta(days=90),
    )
    db_session.add_all([c_vip, c_atrisk])

    # 2. Historical transactions for Merchant 1 (total 30 txns, ~₹12,000 revenue, ATV ~₹400)
    txns = []
    for i in range(30):
        # 10 weekend txns, 20 weekday txns
        txn_time = now - timedelta(days=i)
        txns.append(
            Transaction(
                transaction_id=f"whatif-t1-{i}",
                merchant_id=m1.merchant_id,
                customer_id=c_vip.customer_id if i % 2 == 0 else c_atrisk.customer_id,
                amount=Decimal("400.00"),
                payment_method="UPI",
                status="success",
                timestamp=txn_time,
            )
        )

    # Only 2 transactions for Merchant 2 (total ₹500 revenue)
    m2_txns = [
        Transaction(
            transaction_id="whatif-t2-0",
            merchant_id=m2.merchant_id,
            amount=Decimal("250.00"),
            payment_method="CARD",
            status="success",
            timestamp=now - timedelta(days=1),
        ),
        Transaction(
            transaction_id="whatif-t2-1",
            merchant_id=m2.merchant_id,
            amount=Decimal("250.00"),
            payment_method="UPI",
            status="success",
            timestamp=now - timedelta(days=2),
        ),
    ]

    db_session.add_all(txns + m2_txns)
    db_session.commit()
    return m1, m2


# 1. Baseline Calculation
def test_baseline_calculation(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    resp = client.get(f"/api/v1/what-if/baseline?merchant_id={m1.merchant_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["merchant_id"] == m1.merchant_id
    assert data["has_sufficient_data"] is True
    assert data["baseline_transactions"] == 30
    assert data["baseline_revenue"] == 12000.0
    assert data["baseline_average_order_value"] == 400.0
    assert data["is_demo_projection"] is True


# 2. No-offer Scenario
def test_no_offer_scenario(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    req = {
        "merchant_id": m1.merchant_id,
        "scenario_type": "no_offer",
        "scenario_name": "Baseline Status Quo",
    }
    resp = client.post("/api/v1/what-if/simulate", json=req)
    assert resp.status_code == 200
    data = resp.json()

    assert data["scenario_type"] == "no_offer"
    assert data["projected_transactions"] == data["baseline_transactions"]
    assert data["projected_revenue"] == data["baseline_revenue"]
    assert data["estimated_incentive_cost"] == 0.0
    assert data["gross_incremental_revenue"] == 0.0
    assert data["net_incremental_impact"] == 0.0
    assert data["estimated_roi"] is None
    assert data["roi_multiplier_label"] == "N/A"
    assert data["is_demo_projection"] is True


# 3. Percentage Discount Scenario
def test_percentage_discount_scenario(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    req = {
        "merchant_id": m1.merchant_id,
        "scenario_type": "percentage_discount",
        "discount_percent": 10.0,
        "uplift_assumption": 20.0,
        "participation_rate": 80.0,
    }
    resp = client.post("/api/v1/what-if/simulate", json=req)
    assert resp.status_code == 200
    data = resp.json()

    assert data["scenario_type"] == "percentage_discount"
    # 30 baseline * 20% uplift = 6 incremental txns -> 36 projected txns
    assert data["projected_transactions"] == 36
    assert data["incremental_transactions"] == 6
    # Gross GMV = 36 * 400 = ₹14,400.00
    assert data["gross_projected_revenue"] == 14400.0
    # 80% participation -> 14,400 * 0.80 = 11,520 eligible * 10% = ₹1,152 cost
    assert data["estimated_incentive_cost"] == 1152.0
    # Net revenue after discount = 14,400 - 1,152 = ₹13,248.00
    assert data["projected_revenue"] == 13248.0
    # Gross incremental = 14,400 - 12,000 = ₹2,400.00
    assert data["gross_incremental_revenue"] == 2400.0
    # Net impact = 2,400 - 1,152 = ₹1,248.00
    assert data["net_incremental_impact"] == 1248.0
    # ROI = 1,248 / 1,152 = 1.08x
    assert data["estimated_roi"] == 1.08
    assert "1.1x" in data["roi_multiplier_label"]


# 4. Cashback Scenario
def test_cashback_scenario(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    req = {
        "merchant_id": m1.merchant_id,
        "scenario_type": "fixed_cashback",
        "cashback_amount": 50.0,
        "uplift_assumption": 25.0,
        "participation_rate": 80.0,
    }
    resp = client.post("/api/v1/what-if/simulate", json=req)
    assert resp.status_code == 200
    data = resp.json()

    assert data["scenario_type"] == "fixed_cashback"
    # 30 * 25% uplift = 7.5 -> 8 incremental txns -> 38 projected txns
    assert data["projected_transactions"] == 38
    assert data["incremental_transactions"] == 8
    # Gross GMV = 38 * 400 = ₹15,200.00
    assert data["gross_projected_revenue"] == 15200.0
    # 80% eligible txns = 38 * 0.8 = 30.4 -> 30.4 * 50 = ₹1,520 cost
    assert data["estimated_incentive_cost"] == 1520.0
    # Gross incremental = 15,200 - 12,000 = ₹3,200.00
    assert data["gross_incremental_revenue"] == 3200.0
    # Net impact = 3,200 - 1,520 = ₹1,680.00
    assert data["net_incremental_impact"] == 1680.0
    # ROI = 1,680 / 1,520 = 1.11x
    assert data["estimated_roi"] == 1.11


# 5. Comparison Endpoint
def test_comparison_endpoint(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    resp = client.post("/api/v1/what-if/compare", json={"merchant_id": m1.merchant_id})
    assert resp.status_code == 200
    data = resp.json()

    assert data["merchant_id"] == m1.merchant_id
    assert data["status"] == "success"
    assert len(data["scenarios"]) == 4

    names = [s["scenario_name"] for s in data["scenarios"]]
    assert "No Offer (Baseline)" in names
    assert "5% Discount" in names
    assert "10% Discount" in names
    assert "₹50 Cashback" in names

    assert data["recommended_scenario_id"] is not None
    assert data["recommended_scenario_name"] is not None
    assert "highest estimated" in data["recommendation_reason"].lower()
    assert data["is_demo_projection"] is True
    assert data["data_type"] == "SYNTHETIC_DEMO"


# 6. Projected Transactions Calculation
def test_projected_transactions_calculation(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    req = {
        "merchant_id": m1.merchant_id,
        "scenario_type": "percentage_discount",
        "discount_percent": 5.0,
        "uplift_assumption": 10.0,
    }
    resp = client.post("/api/v1/what-if/simulate", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["projected_transactions"] == data["baseline_transactions"] + data["incremental_transactions"]


# 7. Projected Revenue Calculation
def test_projected_revenue_calculation(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    req = {
        "merchant_id": m1.merchant_id,
        "scenario_type": "percentage_discount",
        "discount_percent": 10.0,
    }
    resp = client.post("/api/v1/what-if/simulate", json=req)
    assert resp.status_code == 200
    data = resp.json()
    # Projected revenue = gross_projected_revenue - estimated_incentive_cost
    assert round(data["projected_revenue"], 2) == round(data["gross_projected_revenue"] - data["estimated_incentive_cost"], 2)


# 8. Incentive Cost Calculation
def test_incentive_cost_calculation(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    # Test that No Offer costs 0
    resp_no_offer = client.post("/api/v1/what-if/simulate", json={"merchant_id": m1.merchant_id, "scenario_type": "no_offer"})
    assert resp_no_offer.json()["estimated_incentive_cost"] == 0.0

    # Test that Cashback scales with transaction count and cashback amount
    resp_cb = client.post("/api/v1/what-if/simulate", json={
        "merchant_id": m1.merchant_id,
        "scenario_type": "fixed_cashback",
        "cashback_amount": 100.0,
        "participation_rate": 100.0,
        "uplift_assumption": 0.0,
    })
    # 30 txns * 100 = 3000.0
    assert resp_cb.json()["estimated_incentive_cost"] == 3000.0


# 9. Incremental Revenue and Net Impact
def test_incremental_revenue_and_net_impact(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    req = {
        "merchant_id": m1.merchant_id,
        "scenario_type": "percentage_discount",
        "discount_percent": 5.0,
    }
    resp = client.post("/api/v1/what-if/simulate", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert round(data["gross_incremental_revenue"], 2) == round(data["gross_projected_revenue"] - data["baseline_revenue"], 2)
    assert round(data["net_incremental_impact"], 2) == round(data["gross_incremental_revenue"] - data["estimated_incentive_cost"], 2)


# 10. ROI Calculation
def test_roi_calculation(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    req = {
        "merchant_id": m1.merchant_id,
        "scenario_type": "percentage_discount",
        "discount_percent": 5.0,
    }
    resp = client.post("/api/v1/what-if/simulate", json=req)
    data = resp.json()
    expected_roi = round(data["net_incremental_impact"] / data["estimated_incentive_cost"], 2)
    assert data["estimated_roi"] == expected_roi


# 11. Zero Incentive Cost ROI Handling
def test_zero_incentive_cost_roi_null(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    req = {
        "merchant_id": m1.merchant_id,
        "scenario_type": "no_offer",
    }
    resp = client.post("/api/v1/what-if/simulate", json=req)
    data = resp.json()
    assert data["estimated_incentive_cost"] == 0.0
    assert data["estimated_roi"] is None
    assert data["roi_multiplier_label"] == "N/A"


# 12. Invalid Negative Discount Validation
def test_invalid_negative_discount_validation(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    req = {
        "merchant_id": m1.merchant_id,
        "scenario_type": "percentage_discount",
        "discount_percent": -5.0,
    }
    resp = client.post("/api/v1/what-if/simulate", json=req)
    assert resp.status_code in [400, 422]


# 13. Invalid Negative Cashback Validation
def test_invalid_negative_cashback_validation(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    req = {
        "merchant_id": m1.merchant_id,
        "scenario_type": "fixed_cashback",
        "cashback_amount": -100.0,
    }
    resp = client.post("/api/v1/what-if/simulate", json=req)
    assert resp.status_code in [400, 422]


# 14. Invalid Target Segment Handling
def test_invalid_segment_returns_400(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    req = {

        "merchant_id": m1.merchant_id,
        "scenario_type": "percentage_discount",
        "target_segment": "NonExistentCohort",
    }
    resp = client.post("/api/v1/what-if/simulate", json=req)
    assert resp.status_code == 400
    err_msg = resp.json().get("detail") or resp.json().get("message", "")
    assert "invalid target segment" in str(err_msg).lower()





# 15. Insufficient Data Safe Handling
def test_insufficient_data_safe_response(client: TestClient, db_session: Session):
    empty_m_id = "test-whatif-empty"
    empty_m = db_session.get(Merchant, empty_m_id)
    if not empty_m:
        empty_m = Merchant(
            merchant_id=empty_m_id,
            business_name="Empty Store",
            business_type="Retail",
            location="Pune",
            business_age=1,
        )
        db_session.add(empty_m)
        db_session.commit()

    resp = client.post("/api/v1/what-if/compare", json={"merchant_id": empty_m_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "insufficient_data"
    assert data["baseline"]["has_sufficient_data"] is False
    assert len(data["scenarios"]) == 0
    assert data["recommended_scenario_id"] is None


# 16. Merchant Isolation
def test_merchant_isolation(client: TestClient, seeded_whatif_dataset):
    m1, m2 = seeded_whatif_dataset
    resp1 = client.get(f"/api/v1/what-if/baseline?merchant_id={m1.merchant_id}")
    resp2 = client.get(f"/api/v1/what-if/baseline?merchant_id={m2.merchant_id}")

    data1 = resp1.json()
    data2 = resp2.json()

    assert data1["baseline_transactions"] == 30
    assert data1["baseline_revenue"] == 12000.0

    assert data2["baseline_transactions"] == 2
    assert data2["baseline_revenue"] == 500.0


# 17. Deterministic Repeated Results
def test_deterministic_repeated_results(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    req = {
        "merchant_id": m1.merchant_id,
        "scenario_type": "fixed_cashback",
        "cashback_amount": 50.0,
    }
    resp1 = client.post("/api/v1/what-if/simulate", json=req).json()
    resp2 = client.post("/api/v1/what-if/simulate", json=req).json()

    assert resp1["projected_revenue"] == resp2["projected_revenue"]
    assert resp1["estimated_incentive_cost"] == resp2["estimated_incentive_cost"]
    assert resp1["net_incremental_impact"] == resp2["net_incremental_impact"]
    assert resp1["estimated_roi"] == resp2["estimated_roi"]


# 18. Recommended Scenario Selection
def test_recommended_scenario_selection(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    resp = client.post("/api/v1/what-if/compare", json={"merchant_id": m1.merchant_id})
    assert resp.status_code == 200
    data = resp.json()

    rec_id = data["recommended_scenario_id"]
    rec_scenario = next(s for s in data["scenarios"] if s["scenario_id"] == rec_id)

    # Must produce positive net yield
    assert rec_scenario["net_incremental_impact"] > 0
    # Must be top net impact among simulated promotional scenarios
    for s in data["scenarios"]:
        if s["scenario_type"] != "no_offer":
            assert rec_scenario["net_incremental_impact"] >= s["net_incremental_impact"] or math.isclose(rec_scenario["net_incremental_impact"], s["net_incremental_impact"], abs_tol=1e-2)


# 19. Finite Numeric Outputs (No NaN or Inf)
def test_finite_numeric_outputs_no_nan_or_inf(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    resp = client.post("/api/v1/what-if/compare", json={"merchant_id": m1.merchant_id})
    data = resp.json()

    for s in data["scenarios"]:
        assert math.isfinite(s["baseline_revenue"])
        assert math.isfinite(s["projected_revenue"])
        assert math.isfinite(s["estimated_incentive_cost"])
        assert math.isfinite(s["gross_incremental_revenue"])
        assert math.isfinite(s["net_incremental_impact"])
        if s["estimated_roi"] is not None:
            assert math.isfinite(s["estimated_roi"])


# 20. API Response Schema Completeness
def test_api_response_schema_completeness(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    resp = client.post("/api/v1/what-if/compare", json={"merchant_id": m1.merchant_id})
    data = resp.json()

    assert "baseline" in data
    assert "scenarios" in data
    assert "recommended_scenario_id" in data
    assert "recommended_scenario_name" in data
    assert "comparison_summary" in data
    assert "assumptions_notice" in data
    assert "disclaimer" in data
    assert data["is_demo_projection"] is True
    assert data["data_type"] == "SYNTHETIC_DEMO"


# 21. Route Aliases
def test_route_aliases(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    # /api/what-if/baseline
    resp_alias_baseline = client.get(f"/api/what-if/baseline?merchant_id={m1.merchant_id}")
    assert resp_alias_baseline.status_code == 200

    # /api/what-if/compare
    resp_alias_compare = client.post("/api/what-if/compare", json={"merchant_id": m1.merchant_id})
    assert resp_alias_compare.status_code == 200

    # /api/campaign/simulate (Blueprint line 3064 alias)
    resp_campaign_sim = client.post("/api/campaign/simulate", json={"merchant_id": m1.merchant_id, "scenario_type": "fixed_cashback"})
    assert resp_campaign_sim.status_code == 200
    assert resp_campaign_sim.json()["scenario_type"] == "fixed_cashback"


# 22. Target Segment and Window Filtering
def test_target_segment_and_window_filtering(client: TestClient, seeded_whatif_dataset):
    m1, _ = seeded_whatif_dataset
    # Test segment filtering (VIP)
    resp_vip = client.get(f"/api/v1/what-if/baseline?merchant_id={m1.merchant_id}&target_segment=VIP")
    assert resp_vip.status_code == 200
    data_vip = resp_vip.json()
    assert data_vip["target_segment"] == "VIP"
    assert data_vip["target_segment_size"] >= 1

    # Test weekend filtering
    resp_wknd = client.get(f"/api/v1/what-if/baseline?merchant_id={m1.merchant_id}&target_days=weekend")
    assert resp_wknd.status_code == 200
    data_wknd = resp_wknd.json()
    assert "weekend" in data_wknd["baseline_window"].lower()
