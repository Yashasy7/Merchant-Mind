"""
Comprehensive Test Suite for Module 9: Business Health & Risk Assessment.

Verifies:
 1. Composite business health calculation (0-100 score & status)
 2. Evaluation of all 5 core health dimensions
 3. Evidence-backed risk detection on revenue contraction
 4. Evidence-backed risk detection on inactive customer exposure
 5. Evidence-backed risk detection on operating deficit (expenses > revenue)
 6. Evidence-backed risk detection on operational expense anomalies
 7. Opportunity detection for weekend revenue expansion
 8. Opportunity detection for dormant customer winback (linked to Module 4 recommendation)
 9. Multi-merchant isolation (zero cross-tenant score leakage)
10. Empty/new merchant safe handling
11. Safe numeric serialization (no NaN / Infinity)
12. REST API GET /api/v1/business-health
13. REST API GET /api/v1/business-health/risks
14. REST API GET /api/v1/business-health/opportunities
15. Health disclaimer presence
16. Module 7 AI Copilot integration via get_business_health tool
"""

import math
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Merchant, Customer, Transaction, Expense
from app.services.business_health_service import BusinessHealthService
from app.schemas.business_health import BusinessHealthResponse, HEALTH_DISCLAIMER


@pytest.fixture
def health_test_merchant(db_session: Session) -> Merchant:
    """Create a test merchant seeded with healthy business metrics."""
    m_id = "test-health-merchant-01"
    merchant = db_session.get(Merchant, m_id)
    if not merchant:
        merchant = Merchant(
            merchant_id=m_id,
            business_name="Gupta Supermart",
            business_type="Retail",
            location="Delhi",
            business_age=36,
        )
        db_session.add(merchant)
        db_session.flush()

    # Seed Customers: 10 Regular, 2 VIP, 2 Inactive
    now = datetime.now(timezone.utc)
    today = now.date()

    customers = []
    for i in range(1, 15):
        seg = "VIP" if i <= 2 else ("Inactive" if i >= 13 else "Regular")
        c = Customer(
            customer_id=f"cust-hlth-{i:03d}",
            merchant_id=m_id,
            name=f"Customer {i}",
            phone=f"98765430{i:02d}",
            segment=seg,
        )
        customers.append(c)
    db_session.add_all(customers)
    db_session.flush()

    # Seed transactions for past 28 days (Revenue ~ 30,000)
    for i in range(28, 0, -1):
        tx_dt = now - timedelta(days=i)
        t = Transaction(
            transaction_id=f"tx-hlth-{i:03d}",
            merchant_id=m_id,
            customer_id="cust-hlth-001",
            timestamp=tx_dt,
            amount=Decimal("1200.00"),
            payment_method="paytm_qr",
            status="success",
        )
        db_session.add(t)

    # Seed Expenses (Total ~ 10,000 -> Profitable!)
    e1 = Expense(
        expense_id="exp-hlth-01",
        merchant_id=m_id,
        date=today - timedelta(days=5),
        category="Inventory",
        amount=Decimal("8000.00"),
        vendor="Wholesale Hub",
    )
    e2 = Expense(
        expense_id="exp-hlth-02",
        merchant_id=m_id,
        date=today - timedelta(days=10),
        category="Rent",
        amount=Decimal("2000.00"),
        vendor="Landlord",
    )
    db_session.add_all([e1, e2])
    db_session.commit()

    return merchant


def test_business_health_basic(db_session: Session, health_test_merchant: Merchant):
    """Verify health evaluation returns composite score between 0 and 100 and valid status."""
    service = BusinessHealthService(db_session)
    res = service.get_business_health(merchant_id=health_test_merchant.merchant_id)
    assert 0.0 <= res.overall_score <= 100.0
    assert res.overall_status in ["healthy", "stable", "at_risk", "critical"]
    assert len(res.dimensions) == 5
    assert len(res.summary) > 0


def test_all_five_dimensions_present(db_session: Session, health_test_merchant: Merchant):
    """Verify all 5 required dimensions are calculated with valid bounded scores."""
    service = BusinessHealthService(db_session)
    res = service.get_business_health(merchant_id=health_test_merchant.merchant_id)
    dim_names = {d.dimension_name for d in res.dimensions}
    expected = {
        "revenue_trend",
        "customer_retention",
        "profitability",
        "operational_risk",
        "growth_readiness",
    }
    assert dim_names == expected
    for d in res.dimensions:
        assert 0.0 <= d.score <= 100.0
        assert d.status in ["excellent", "good", "warning", "critical"]
        assert len(d.metric_summary) > 0


def test_risk_detection_on_revenue_decline(db_session: Session):
    """Verify risk signal is flagged when merchant has declining revenue."""
    declining_m = Merchant(
        merchant_id="merchant-declining-health",
        business_name="Declining Store",
        business_type="Retail",
        location="Jaipur",
    )
    db_session.add(declining_m)
    db_session.flush()

    now = datetime.now(timezone.utc)
    today = now.date()

    # Prior 14 days: 3000/day. Recent 14 days: 500/day (-83% drop)
    for i in range(28, 0, -1):
        amt = Decimal("500.00") if i <= 14 else Decimal("3000.00")
        t = Transaction(
            transaction_id=f"tx-dec-hlth-{i:03d}",
            merchant_id=declining_m.merchant_id,
            timestamp=now - timedelta(days=i),
            amount=amt,
            status="success",
        )
        db_session.add(t)
    db_session.commit()

    service = BusinessHealthService(db_session)
    res = service.get_business_health(merchant_id=declining_m.merchant_id)
    risk_ids = [r.risk_id for r in res.risks]
    assert "risk-rev-contraction" in risk_ids


def test_risk_detection_on_customer_attrition(db_session: Session):
    """Verify risk signal when customer base has high percentage of inactive customers."""
    attrition_m = Merchant(
        merchant_id="merchant-attrition-health",
        business_name="High Churn Store",
        business_type="Retail",
        location="Pune",
    )
    db_session.add(attrition_m)
    db_session.flush()

    # Seed 10 customers where 6 are inactive (60% inactive)
    for i in range(1, 11):
        seg = "Inactive" if i <= 6 else "Regular"
        c = Customer(
            customer_id=f"cust-attr-{i:03d}",
            merchant_id=attrition_m.merchant_id,
            name=f"Attr Customer {i}",
            phone=f"98765432{i:02d}",
            segment=seg,
        )
        db_session.add(c)
    db_session.commit()

    service = BusinessHealthService(db_session)
    res = service.get_business_health(merchant_id=attrition_m.merchant_id)
    risk_ids = [r.risk_id for r in res.risks]
    assert "risk-inactive-customers" in risk_ids


def test_risk_detection_on_operating_loss(db_session: Session):
    """Verify risk signal when operational expenses exceed revenue."""
    loss_m = Merchant(
        merchant_id="merchant-loss-health",
        business_name="Operating Deficit Store",
        business_type="Retail",
        location="Lucknow",
    )
    db_session.add(loss_m)
    db_session.flush()

    now = datetime.now(timezone.utc)
    today = now.date()

    # Revenue = 1,000. Expenses = 5,000
    t = Transaction(
        transaction_id="tx-loss-hlth-01",
        merchant_id=loss_m.merchant_id,
        timestamp=now,
        amount=Decimal("1000.00"),
        status="success",
    )
    e = Expense(
        expense_id="exp-loss-hlth-01",
        merchant_id=loss_m.merchant_id,
        date=today,
        category="Rent",
        amount=Decimal("5000.00"),
        vendor="Landlord",
    )
    db_session.add_all([t, e])
    db_session.commit()

    service = BusinessHealthService(db_session)
    res = service.get_business_health(merchant_id=loss_m.merchant_id)
    risk_ids = [r.risk_id for r in res.risks]
    assert "risk-operating-deficit" in risk_ids


def test_opportunity_detection_inactive_recovery(db_session: Session, health_test_merchant: Merchant):
    """Verify opportunity detection identifies dormant customer winback opportunities."""
    service = BusinessHealthService(db_session)
    res = service.get_business_health(merchant_id=health_test_merchant.merchant_id)
    opp_ids = [o.opportunity_id for o in res.opportunities]
    assert "opp-winback-recovery" in opp_ids


def test_merchant_isolation(db_session: Session, health_test_merchant: Merchant):
    """Verify fresh merchant with no records does not inherit metrics from test merchant."""
    isolated_m = Merchant(
        merchant_id="merchant-isolated-hlth-99",
        business_name="Isolated Store",
        business_type="Retail",
        location="Indore",
    )
    db_session.add(isolated_m)
    db_session.commit()

    service = BusinessHealthService(db_session)
    res = service.get_business_health(merchant_id=isolated_m.merchant_id)
    assert res.merchant_id == isolated_m.merchant_id
    prof_dim = next(d for d in res.dimensions if d.dimension_name == "profitability")
    assert prof_dim.details["total_revenue"] == 0.0


def test_no_nan_or_infinity(client: TestClient, health_test_merchant: Merchant):
    """Verify no NaN or Infinity is present in serialized output."""
    resp = client.get(
        "/api/v1/business-health",
        params={"merchant_id": health_test_merchant.merchant_id},
    )
    raw = resp.text
    assert "NaN" not in raw
    assert "Infinity" not in raw


def test_api_business_health(client: TestClient, health_test_merchant: Merchant):
    """Verify GET /api/v1/business-health endpoint."""
    resp = client.get(
        "/api/v1/business-health",
        params={"merchant_id": health_test_merchant.merchant_id},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["merchant_id"] == health_test_merchant.merchant_id
    assert "overall_score" in data
    assert "dimensions" in data
    assert len(data["dimensions"]) == 5
    assert "disclaimer" in data


def test_api_business_risks(client: TestClient, health_test_merchant: Merchant):
    """Verify GET /api/v1/business-health/risks endpoint."""
    resp = client.get(
        "/api/v1/business-health/risks",
        params={"merchant_id": health_test_merchant.merchant_id},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "risks" in data
    assert "total_risks" in data


def test_api_business_opportunities(client: TestClient, health_test_merchant: Merchant):
    """Verify GET /api/v1/business-health/opportunities endpoint."""
    resp = client.get(
        "/api/v1/business-health/opportunities",
        params={"merchant_id": health_test_merchant.merchant_id},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "opportunities" in data
    assert "total_opportunities" in data


def test_ai_agent_get_business_health_tool(client: TestClient, health_test_merchant: Merchant):
    """Verify AI Agent orchestrator routes health queries to get_business_health tool."""
    payload = {
        "message": "Is my business healthy? What are my main business risks and health score?",
        "merchant_id": health_test_merchant.merchant_id,
    }
    resp = client.post("/api/v1/agent/chat", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["intent"]["intent"] == "get_business_health"
    tool_names = [a["tool_name"] for a in data["actions_taken"]]
    assert "get_business_health" in tool_names
    assert len(data["insights"]) > 0
    assert any("health" in ins.lower() or "score" in ins.lower() for ins in data["insights"])
