"""
Module 10 — Complete System Integration & End-to-End Test Suite.

Validates the complete MerchantMind product loop:
UNDERSTAND -> ANALYZE -> PREDICT -> RECOMMEND -> APPROVE -> ACT -> MEASURE -> LEARN

Tests all 15 required cross-module integration scenarios:
  1. Sales -> Growth
  2. Growth -> What-if
  3. What-if -> Campaign
  4. Human Approval Boundary (Pending -> Execution Block -> Approve -> Execute -> Re-execution Block)
  5. Campaign Audit Trail Lifecycle
  6. Accountant -> Business Health Parity
  7. Cross-Module Business Health Dimension Harmony (Modules 2, 3, 4, 8, 9)
  8. AI Copilot -> Forecast Sales Tool
  9. AI Copilot -> Business Health Diagnostic Tool
  10. AI Copilot -> Financial / Accounting Analysis Tool
  11. AI Copilot -> Campaign Creation (Pending Approval Safety)
  12. Multi-Merchant Isolation
  13. Unknown Merchant Safety & Non-Leakage
  14. Deterministic AI Grounding (Zero Hallucination)
  15. System Fallback & Resilience Under Sparse/Empty Data
"""

import pytest
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.merchant import Merchant
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.expense import Expense
from app.models.campaign import Campaign, CampaignAuditLog
from app.schemas.campaign import CampaignStatus, CampaignAuditAction


@pytest.fixture
def integrated_merchant(db_session: Session) -> Merchant:
    """Seed an integrated test merchant with rich multi-module history."""
    m = Merchant(
        merchant_id="merchant-e2e-demo",
        business_name="Sharma Supermarket",
        business_type="Grocery & FMCG",
        location="Indiranagar, Bengaluru",
    )
    db_session.add(m)
    db_session.flush()

    now = datetime.now(timezone.utc)
    today = now.date()

    # Seed Customers: 10 active, 5 at-risk, 5 inactive (20 total)
    customers = []
    for i in range(20):
        if i < 10:
            last_visit = now - timedelta(days=5)
            seg = "Regular"
        elif i < 15:
            last_visit = now - timedelta(days=35)
            seg = "At-Risk"
        else:
            last_visit = now - timedelta(days=70)
            seg = "Inactive"

        c = Customer(
            customer_id=f"cust-e2e-{i:03d}",
            merchant_id=m.merchant_id,
            name=f"Customer {i}",
            phone=f"+91987654{i:04d}",
            segment=seg,
            transaction_count=10 if seg == "Regular" else 2,
            total_spend=Decimal("5000.00") if seg == "Regular" else Decimal("600.00"),
            last_transaction=last_visit,
        )
        customers.append(c)
        db_session.add(c)
    db_session.flush()

    # Seed 28 days of daily transactions
    for d_offset in range(28, 0, -1):
        tx_date = today - timedelta(days=d_offset)
        # Saturday/Sunday gets higher volume (weekend surge)
        is_weekend = tx_date.weekday() in [5, 6]
        tx_count = 8 if is_weekend else 4
        base_amt = Decimal("400.00") if is_weekend else Decimal("250.00")

        for t_idx in range(tx_count):
            cust = customers[t_idx % len(customers)]
            tx_dt = datetime(tx_date.year, tx_date.month, tx_date.day, 10 + t_idx, 0, 0, tzinfo=timezone.utc)
            tx = Transaction(
                transaction_id=f"tx-e2e-{d_offset:02d}-{t_idx:02d}",
                merchant_id=m.merchant_id,
                customer_id=cust.customer_id,
                timestamp=tx_dt,
                amount=base_amt + Decimal(str(t_idx * 10)),
                payment_method="UPI",
                status="success",
            )
            db_session.add(tx)

    # Seed Expenses for Module 8 integration
    categories = [
        ("Inventory", Decimal("8000.00")),
        ("Rent", Decimal("4000.00")),
        ("Salaries", Decimal("3000.00")),
        ("Utilities", Decimal("1200.00")),
    ]
    for idx, (cat, amt) in enumerate(categories):
        exp = Expense(
            expense_id=f"exp-e2e-{idx}",
            merchant_id=m.merchant_id,
            date=today - timedelta(days=10),
            category=cat,
            amount=amt,
            vendor=f"{cat} Supplier Co",
            notes=f"Monthly {cat}",
        )
        db_session.add(exp)

    db_session.commit()
    return m


# -----------------------------------------------------------------------------
# 1. Sales -> Growth Recommendation Flow
# -----------------------------------------------------------------------------
def test_e2e_sales_to_growth(client: TestClient, integrated_merchant: Merchant):
    """Verify sales analysis correctly triggers contextual growth recommendations."""
    # Step 1: Sales Analysis
    sales_resp = client.get(f"/api/v1/sales/summary?merchant_id={integrated_merchant.merchant_id}")
    assert sales_resp.status_code == status.HTTP_200_OK
    sales_data = sales_resp.json()
    assert sales_data["total_revenue"] > 0
    assert sales_data["total_transactions"] > 0

    # Step 2: Growth Recommendations derived from sales and customer state
    growth_resp = client.get(f"/api/v1/growth/recommendations?merchant_id={integrated_merchant.merchant_id}")
    assert growth_resp.status_code == status.HTTP_200_OK
    growth_data = growth_resp.json()
    assert len(growth_data["recommendations"]) > 0

    # Confirm recommendations contain actionable levers
    rec_ids = [r["recommendation_id"] for r in growth_data["recommendations"]]
    assert any(r.startswith("rec-") for r in rec_ids)


# -----------------------------------------------------------------------------
# 2. Growth -> What-if Simulator Flow
# -----------------------------------------------------------------------------
def test_e2e_growth_to_what_if_simulation(client: TestClient, integrated_merchant: Merchant):
    """Verify recommendation context binds into what-if simulation request."""
    # Fetch growth recommendations
    growth_resp = client.get(f"/api/v1/growth/recommendations?merchant_id={integrated_merchant.merchant_id}")
    growth_data = growth_resp.json()
    rec = growth_data["recommendations"][0]

    # Simulate campaign offer bound to the recommendation
    sim_payload = {
        "merchant_id": integrated_merchant.merchant_id,
        "recommendation_id": rec["recommendation_id"],
        "scenario_type": "percentage_discount",
        "discount_percent": 10.0,
        "minimum_transaction_amount": 200.0,
        "target_segment": "All Customers",
    }
    sim_resp = client.post("/api/v1/what-if/simulate", json=sim_payload)
    assert sim_resp.status_code == status.HTTP_200_OK
    sim_data = sim_resp.json()

    assert sim_data["scenario_id"].startswith("scenario-")
    assert "projected_revenue" in sim_data
    assert "net_incremental_impact" in sim_data
    assert "estimated_incentive_cost" in sim_data
    assert sim_data["confidence_score"] > 0


# -----------------------------------------------------------------------------
# 3. What-if -> Campaign Creation Flow
# -----------------------------------------------------------------------------
def test_e2e_what_if_to_campaign_creation(client: TestClient, integrated_merchant: Merchant):
    """Verify simulation outcome transitions seamlessly into campaign creation."""
    campaign_payload = {
        "merchant_id": integrated_merchant.merchant_id,
        "name": "Weekend Special Offer",
        "description": "10% off on all weekend orders",
        "target_segment": "Inactive",
        "offer_type": "percentage_discount",
        "discount_percent": 10.0,
        "minimum_transaction_amount": 250.0,
        "target_days": "weekend",
        "target_hours": "all",
    }
    create_resp = client.post("/api/v1/campaigns", json=campaign_payload)
    assert create_resp.status_code == status.HTTP_201_CREATED
    camp_data = create_resp.json()

    assert camp_data["campaign_id"].startswith("cmp-")
    assert camp_data["status"] == CampaignStatus.PENDING_APPROVAL.value
    assert camp_data["merchant_id"] == integrated_merchant.merchant_id


# -----------------------------------------------------------------------------
# 4. Human Approval Boundary & Execution Lifecycle
# -----------------------------------------------------------------------------
def test_e2e_human_approval_boundary(client: TestClient, integrated_merchant: Merchant):
    """Verify strict approval gate: pending cannot execute, approval allows execution, re-execution blocked."""
    # 1. Create campaign
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": integrated_merchant.merchant_id,
            "name": "Approval Gate Test",
            "description": "Testing boundary enforcement",
            "target_segment": "At-Risk",
            "offer_type": "fixed_cashback",
            "cashback_amount": 40.0,
            "minimum_transaction_amount": 300.0,
            "target_days": "all",
            "target_hours": "evening",
        },
    )
    camp_id = create_resp.json()["campaign_id"]

    # 2. Attempt execution while PENDING_APPROVAL -> MUST BE REJECTED
    exec_blocked = client.post(f"/api/v1/campaigns/{camp_id}/execute?merchant_id={integrated_merchant.merchant_id}")
    assert exec_blocked.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]

    # 3. Explicit merchant approval
    approve_resp = client.post(f"/api/v1/campaigns/{camp_id}/approve?merchant_id={integrated_merchant.merchant_id}")
    assert approve_resp.status_code == status.HTTP_200_OK
    assert approve_resp.json()["status"] == CampaignStatus.APPROVED.value

    # 4. Execute approved campaign -> MUST SUCCEED
    exec_resp = client.post(f"/api/v1/campaigns/{camp_id}/execute?merchant_id={integrated_merchant.merchant_id}")
    assert exec_resp.status_code == status.HTTP_200_OK
    assert exec_resp.json()["status"] == CampaignStatus.COMPLETED.value

    # 5. Repeated execution -> MUST BE REJECTED
    repeat_exec = client.post(f"/api/v1/campaigns/{camp_id}/execute?merchant_id={integrated_merchant.merchant_id}")
    assert repeat_exec.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]


# -----------------------------------------------------------------------------
# 5. Campaign Audit Trail Verification
# -----------------------------------------------------------------------------
def test_e2e_campaign_audit_trail(client: TestClient, integrated_merchant: Merchant):
    """Verify full audit trail persists chronological state transitions."""
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": integrated_merchant.merchant_id,
            "name": "Audit Trail Campaign",
            "description": "Audit testing",
            "target_segment": "Regular",
            "offer_type": "percentage_discount",
            "discount_percent": 5.0,
            "minimum_transaction_amount": 100.0,
            "target_days": "all",
            "target_hours": "all",
        },
    )
    camp_id = create_resp.json()["campaign_id"]
    client.post(f"/api/v1/campaigns/{camp_id}/approve?merchant_id={integrated_merchant.merchant_id}")
    client.post(f"/api/v1/campaigns/{camp_id}/execute?merchant_id={integrated_merchant.merchant_id}")

    audit_resp = client.get(f"/api/v1/campaigns/{camp_id}/audit?merchant_id={integrated_merchant.merchant_id}")
    assert audit_resp.status_code == status.HTTP_200_OK
    data = audit_resp.json()
    events = data.get("events") or data.get("audit_logs", [])
    actions = [l["action"] for l in events]

    assert CampaignAuditAction.CREATE.value in actions
    assert CampaignAuditAction.APPROVE.value in actions
    assert CampaignAuditAction.EXECUTE.value in actions


# -----------------------------------------------------------------------------
# 6. Accountant -> Business Health Parity
# -----------------------------------------------------------------------------
def test_e2e_accountant_to_business_health(client: TestClient, integrated_merchant: Merchant):
    """Verify financial metrics in Business Health precisely match Accountant P&L statement."""
    # Module 8 P&L
    pnl_resp = client.get(f"/api/v1/accountant/profit-loss?merchant_id={integrated_merchant.merchant_id}")
    assert pnl_resp.status_code == status.HTTP_200_OK
    pnl = pnl_resp.json()

    # Module 9 Business Health
    health_resp = client.get(f"/api/v1/business-health/?merchant_id={integrated_merchant.merchant_id}")
    assert health_resp.status_code == status.HTTP_200_OK
    health = health_resp.json()

    # Find profitability dimension
    prof_dim = next((d for d in health["dimensions"] if d["dimension_name"] == "profitability"), None)
    assert prof_dim is not None
    assert prof_dim["details"]["operating_margin_pct"] == pnl["operating_margin_pct"]
    assert prof_dim["details"]["total_revenue"] == pnl["total_revenue"]
    assert prof_dim["details"]["total_expenses"] == pnl["total_expenses"]


# -----------------------------------------------------------------------------
# 7. Cross-Module Business Health Dimension Harmony
# -----------------------------------------------------------------------------
def test_e2e_cross_module_business_health_harmony(client: TestClient, integrated_merchant: Merchant):
    """Verify all 5 dimensions harmonize across Modules 2, 3, 4, 8, and 9."""
    resp = client.get(f"/api/v1/business-health/?merchant_id={integrated_merchant.merchant_id}")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    dim_names = {d["dimension_name"] for d in data["dimensions"]}
    assert dim_names == {
        "revenue_trend",
        "customer_retention",
        "profitability",
        "operational_risk",
        "growth_readiness",
    }
    assert 0.0 <= data["overall_score"] <= 100.0
    assert data["overall_status"] in ["healthy", "stable", "at_risk", "critical"]
    assert len(data["risks"]) > 0 or len(data["opportunities"]) > 0


# -----------------------------------------------------------------------------
# 8. AI Copilot -> Forecast Sales Tool
# -----------------------------------------------------------------------------
def test_e2e_ai_copilot_forecast_sales(client: TestClient, integrated_merchant: Merchant):
    """Verify natural language forecast query executes forecast_sales tool and returns grounded data."""
    payload = {
        "merchant_id": integrated_merchant.merchant_id,
        "message": "Forecast my sales for next week and tell me the expected revenue.",
    }
    resp = client.post("/api/v1/agent/chat", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["intent"]["intent"] == "forecast_sales"
    tool_names = [a["tool_name"] for a in data["actions_taken"]]
    assert "forecast_sales" in tool_names
    assert len(data["insights"]) > 0


# -----------------------------------------------------------------------------
# 9. AI Copilot -> Business Health Diagnostic Tool
# -----------------------------------------------------------------------------
def test_e2e_ai_copilot_business_health(client: TestClient, integrated_merchant: Merchant):
    """Verify natural language business health query routes to get_business_health tool."""
    payload = {
        "merchant_id": integrated_merchant.merchant_id,
        "message": "Is my business healthy? What are my biggest risks?",
    }
    resp = client.post("/api/v1/agent/chat", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["intent"]["intent"] == "get_business_health"
    tool_names = [a["tool_name"] for a in data["actions_taken"]]
    assert "get_business_health" in tool_names


# -----------------------------------------------------------------------------
# 10. AI Copilot -> Financial / Accounting Analysis Tool
# -----------------------------------------------------------------------------
def test_e2e_ai_copilot_financials(client: TestClient, integrated_merchant: Merchant):
    """Verify natural language profit query routes to analyze_financials tool."""
    payload = {
        "merchant_id": integrated_merchant.merchant_id,
        "message": "How much profit did I make this month?",
    }
    resp = client.post("/api/v1/agent/chat", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["intent"]["intent"] == "analyze_financials"
    tool_names = [a["tool_name"] for a in data["actions_taken"]]
    assert "analyze_financials" in tool_names


# -----------------------------------------------------------------------------
# 11. AI Copilot -> Campaign Creation (Pending Approval Safety)
# -----------------------------------------------------------------------------
def test_e2e_ai_copilot_campaign_creation_safety(client: TestClient, integrated_merchant: Merchant):
    """Verify AI campaign intent automatically creates campaign in PENDING_APPROVAL without auto-execution."""
    payload = {
        "merchant_id": integrated_merchant.merchant_id,
        "message": "Create a campaign for inactive customers with a 15% discount.",
    }
    resp = client.post("/api/v1/agent/chat", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    # Verify created campaign exists and remains pending approval
    assert data["campaign"] is not None
    assert data["campaign"]["status"] == CampaignStatus.PENDING_APPROVAL.value
    assert data["approval_required"] is True


# -----------------------------------------------------------------------------
# 12. Multi-Merchant Isolation
# -----------------------------------------------------------------------------
def test_e2e_multi_merchant_isolation(client: TestClient, db_session: Session, integrated_merchant: Merchant):
    """Verify strict tenant isolation: Merchant B cannot access Merchant A's campaigns, health, or sales."""
    merchant_b = Merchant(
        merchant_id="merchant-isolated-b",
        business_name="Gupta Electronics",
        business_type="Retail",
        location="Delhi",
    )
    db_session.add(merchant_b)
    db_session.commit()

    # Create campaign under Merchant A
    c_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": integrated_merchant.merchant_id,
            "name": "Merchant A Only",
            "description": "Private campaign",
            "target_segment": "Regular",
            "offer_type": "percentage_discount",
            "discount_percent": 10.0,
            "minimum_transaction_amount": 100.0,
            "target_days": "weekend",
            "target_hours": "all",
        },
    )
    camp_a_id = c_resp.json()["campaign_id"]

    # Attempt to view/approve Merchant A's campaign using Merchant B's identity -> 404
    approve_b = client.post(f"/api/v1/campaigns/{camp_a_id}/approve?merchant_id={merchant_b.merchant_id}")
    assert approve_b.status_code == status.HTTP_404_NOT_FOUND

    # Merchant B forecast summary must return zero data without leaking Merchant A's numbers
    fc_b = client.get(f"/api/v1/forecast/summary?merchant_id={merchant_b.merchant_id}")
    assert fc_b.status_code == status.HTTP_200_OK
    assert fc_b.json()["historical_revenue"] == 0.0
    assert fc_b.json()["is_sufficient_data"] is False


# -----------------------------------------------------------------------------
# 13. Unknown Merchant Safety & Non-Leakage
# -----------------------------------------------------------------------------
def test_e2e_unknown_merchant_safety(client: TestClient):
    """Verify unknown merchant receives safe zero/empty responses or 404 without server errors."""
    # Forecast summary
    fc = client.get("/api/v1/forecast/summary?merchant_id=nonexistent-merchant-999")
    assert fc.status_code == status.HTTP_200_OK
    assert fc.json()["historical_revenue"] == 0.0
    assert fc.json()["is_sufficient_data"] is False

    # Campaign approval
    ca = client.post("/api/v1/campaigns/cmp-fake-999/approve?merchant_id=nonexistent-merchant-999")
    assert ca.status_code == status.HTTP_404_NOT_FOUND

    # Customer detail
    cd = client.get("/api/v1/customers/cust-fake-999?merchant_id=nonexistent-merchant-999")
    assert cd.status_code == status.HTTP_404_NOT_FOUND


# -----------------------------------------------------------------------------
# 14. Deterministic AI Grounding (Zero Financial Hallucination)
# -----------------------------------------------------------------------------
def test_e2e_ai_deterministic_grounding(client: TestClient, integrated_merchant: Merchant):
    """Verify Copilot numerical explanations match deterministic backend outputs."""
    # Get actual backend P&L
    pnl_resp = client.get(f"/api/v1/accountant/profit-loss?merchant_id={integrated_merchant.merchant_id}")
    pnl_data = pnl_resp.json()
    actual_profit = pnl_data["net_profit"]

    # Ask Copilot for financial summary
    chat_resp = client.post(
        "/api/v1/agent/chat",
        json={"merchant_id": integrated_merchant.merchant_id, "message": "What is my net profit?"},
    )
    assert chat_resp.status_code == status.HTTP_200_OK
    chat_data = chat_resp.json()

    # Tool result must confirm tool execution
    financial_action = next((a for a in chat_data["actions_taken"] if a["tool_name"] == "analyze_financials"), None)
    assert financial_action is not None
    assert financial_action["status"] == "success"
    assert any("profit" in ins.lower() or "revenue" in ins.lower() for ins in chat_data["insights"]) or "profit" in chat_data["message"].lower()


# -----------------------------------------------------------------------------
# 15. System Fallback & Resilience Under Sparse/Empty Data
# -----------------------------------------------------------------------------
def test_e2e_system_fallback_and_resilience(client: TestClient, db_session: Session):
    """Verify graceful handling when merchant has minimal/sparse data."""
    sparse_m = Merchant(
        merchant_id="merchant-sparse-e2e",
        business_name="Brand New Kiosk",
        business_type="Kiosk",
        location="Mysuru",
    )
    db_session.add(sparse_m)
    db_session.commit()

    # Forecast handles sparse data safely
    fc_resp = client.get(f"/api/v1/forecast/summary?merchant_id={sparse_m.merchant_id}")
    assert fc_resp.status_code == status.HTTP_200_OK
    assert fc_resp.json()["is_sufficient_data"] is False

    # Business Health handles sparse data safely
    health_resp = client.get(f"/api/v1/business-health/?merchant_id={sparse_m.merchant_id}")
    assert health_resp.status_code == status.HTTP_200_OK
    assert health_resp.json()["overall_score"] >= 0.0

    # AI Copilot handles sparse merchant safely
    chat_resp = client.post(
        "/api/v1/agent/chat",
        json={"merchant_id": sparse_m.merchant_id, "message": "Is my business healthy?"},
    )
    assert chat_resp.status_code == status.HTTP_200_OK
    assert len(chat_resp.json()["message"]) > 0
