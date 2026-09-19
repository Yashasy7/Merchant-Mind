"""
Comprehensive regression test suite for Paytm MerchantMind AI Copilot.
Verifies all 10 independent merchant queries, distinct responses,
hero multi-turn flow with human-in-the-loop approval gates,
and security/safety invariants.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Merchant, Customer, Transaction, Expense


@pytest.fixture
def agent_test_merchant(db_session: Session) -> Merchant:
    """Create a populated merchant with customers, expenses, and transactions for agent testing."""
    m_id = "test-agent-reg-01"
    merchant = db_session.get(Merchant, m_id)
    if not merchant:
        merchant = Merchant(
            merchant_id=m_id,
            business_name="Sharma Supermarket",
            business_type="Retail",
            location="Delhi",
            business_age=24,
        )
        db_session.add(merchant)
        db_session.flush()

    # Seed customers across cohorts
    c_inactive = Customer(
        customer_id=f"cust-inact-{m_id}",
        merchant_id=m_id,
        name="Rohan Sharma",
        phone="9876543210",
        transaction_count=2,
        total_spend=Decimal("600.00"),
        segment="Inactive",
        last_transaction=datetime.now(timezone.utc) - timedelta(days=60),
    )
    c_at_risk = Customer(
        customer_id=f"cust-risk-{m_id}",
        merchant_id=m_id,
        name="Priya Patel",
        phone="9876543211",
        transaction_count=4,
        total_spend=Decimal("1200.00"),
        segment="At-Risk",
        last_transaction=datetime.now(timezone.utc) - timedelta(days=35),
    )
    c_vip = Customer(
        customer_id=f"cust-vip-{m_id}",
        merchant_id=m_id,
        name="Amit Kumar",
        phone="9876543212",
        transaction_count=15,
        total_spend=Decimal("8500.00"),
        segment="VIP",
        last_transaction=datetime.now(timezone.utc) - timedelta(days=2),
    )
    db_session.add_all([c_inactive, c_at_risk, c_vip])
    db_session.flush()

    # Seed transactions for sales baseline
    now = datetime.now(timezone.utc)
    txns = []
    for i in range(1, 25):
        txns.append(
            Transaction(
                transaction_id=f"tx-reg-{i}-{m_id}",
                merchant_id=m_id,
                customer_id=f"cust-vip-{m_id}" if i % 2 == 0 else f"cust-risk-{m_id}",
                amount=Decimal(str(200 + i * 15)),
                timestamp=now - timedelta(days=i % 14, hours=(i * 3) % 12),
                status="success",
                payment_method="UPI",
            )
        )
    db_session.add_all(txns)

    # Seed expenses for profit/loss and expense breakdown
    exp1 = Expense(
        expense_id=f"exp-1-{m_id}",
        merchant_id=m_id,
        category="Procurement",
        amount=Decimal("12000.00"),
        vendor="Wholesale Supplies Ltd",
        notes="Weekly inventory replenishment",
        date=now.date(),
    )
    exp2 = Expense(
        expense_id=f"exp-2-{m_id}",
        merchant_id=m_id,
        category="Rent",
        amount=Decimal("5000.00"),
        vendor="Commercial Property Trust",
        notes="Store monthly lease allocation",
        date=now.date(),
    )
    db_session.add_all([exp1, exp2])
    db_session.commit()
    return merchant


def test_10_distinct_questions_return_distinct_grounded_responses(client: TestClient, agent_test_merchant: Merchant):
    """
    Verify all 10 independent questions produce distinct, grounded responses
    and do NOT repeat identical answers or fallback to general guidance.
    """
    questions = [
        ("q1_why_falling", "Why are my sales falling?"),
        ("q2_profit", "How much profit did I make this month?"),
        ("q3_best_customers", "Who are my best customers?"),
        ("q4_expenses", "What are my biggest expenses?"),
        ("q5_increase_weekend", "How can I increase weekend sales?"),
        ("q6_transactions", "How many transactions did I have this week?"),
        ("q7_atv", "What is my average transaction value?"),
        ("q8_peak_time", "Which time of day performs best?"),
        ("q9_inactive", "How many inactive customers do I have?"),
        ("q10_forecast", "Can you forecast my sales for next month?"),
    ]

    responses = {}
    intents = {}

    for q_id, q_text in questions:
        res = client.post(
            "/api/v1/agent/chat",
            json={
                "message": q_text,
                "merchant_id": agent_test_merchant.merchant_id,
                "conversation_id": f"conv-{q_id}",
            }
        )
        assert res.status_code == status.HTTP_200_OK, f"Query '{q_text}' failed: {res.text}"
        data = res.json()
        responses[q_id] = data["message"]
        intents[q_id] = data["intent"]["intent"]

    # Invariant 1: All 10 responses must be completely non-empty and non-identical
    unique_responses = set(responses.values())
    assert len(unique_responses) == 10, f"Expected 10 unique responses, got {len(unique_responses)}"

    # Invariant 2: Grounding and domain-specific keywords check for each response
    # Q1: Sales falling -> decline diagnosis
    assert any(w in responses["q1_why_falling"].lower() for w in ["decline", "down", "revenue", "drop", "%"])
    assert intents["q1_why_falling"] == "analyze_sales"

    # Q2: Profit -> net profit figures + CA disclaimer
    assert any(w in responses["q2_profit"].lower() for w in ["profit", "margin", "revenue", "₹"])
    assert "ca" in responses["q2_profit"].lower() or "chartered accountant" in responses["q2_profit"].lower()
    assert intents["q2_profit"] == "analyze_financials"

    # Q3: Best customers -> VIP customers
    assert any(w in responses["q3_best_customers"].lower() for w in ["vip", "top", "patron", "spenders", "highest"])
    assert intents["q3_best_customers"] == "analyze_customers"

    # Q4: Expenses -> breakdown / categories + CA disclaimer
    assert any(w in responses["q4_expenses"].lower() for w in ["expense", "operating", "cost", "inventory", "rent", "wages"])
    assert "ca" in responses["q4_expenses"].lower() or "chartered accountant" in responses["q4_expenses"].lower()
    assert intents["q4_expenses"] == "analyze_financials"

    # Q5: Increase weekend -> weekend campaign or revenue proposal
    assert any(w in responses["q5_increase_weekend"].lower() for w in ["weekend", "campaign", "revenue", "cashback", "offer"])
    assert intents["q5_increase_weekend"] == "increase_weekend_revenue"

    # Q6: Transactions count -> successful transaction count
    assert any(w in responses["q6_transactions"].lower() for w in ["transaction", "transactions", "recorded", "success"])
    assert intents["q6_transactions"] == "analyze_sales"

    # Q7: ATV -> average transaction value
    assert any(w in responses["q7_atv"].lower() for w in ["average transaction", "atv", "ticket size", "₹"])
    assert intents["q7_atv"] == "analyze_sales"

    # Q8: Peak time -> hourly breakdown or peak window
    assert any(w in responses["q8_peak_time"].lower() for w in ["peak", "hour", "window", "afternoon", "12:", "13:", "footfall"])
    assert intents["q8_peak_time"] == "analyze_sales"

    # Q9: Inactive customers -> inactive count
    assert any(w in responses["q9_inactive"].lower() for w in ["inactive", "reactivat", "dormant", "days"])
    assert intents["q9_inactive"] == "analyze_customers"

    # Q10: Forecast -> projected revenue + synthetic disclaimer
    assert any(w in responses["q10_forecast"].lower() for w in ["project", "forecast", "next-month", "month", "₹"])
    assert any(w in responses["q10_forecast"].lower() for w in ["prototype", "statistical", "synthetic", "estimate"])
    assert intents["q10_forecast"] == "forecast_sales"


def test_hero_multi_turn_flow_and_approval_gates(client: TestClient, agent_test_merchant: Merchant):
    """
    Test the complete 5-turn hero conversational flow:
    Turn 1: 'Why are my sales falling?' (Diagnosis)
    Turn 2: 'Show me growth opportunities.' (Recommendations)
    Turn 3: 'Simulate a ₹50 cashback campaign for inactive customers.' (Draft + Simulation)
    Turn 4: 'Approve this campaign.' (Human-in-the-loop Gate)
    Turn 5: 'Execute the campaign.' (Simulated Execution)
    """
    conv_id = f"conv-hero-{agent_test_merchant.merchant_id}"

    # Turn 1: Why are my sales falling?
    res1 = client.post(
        "/api/v1/agent/chat",
        json={
            "message": "Why are my sales falling?",
            "merchant_id": agent_test_merchant.merchant_id,
            "conversation_id": conv_id,
        }
    )
    assert res1.status_code == status.HTTP_200_OK
    d1 = res1.json()
    assert d1["intent"]["intent"] == "analyze_sales"
    assert len(d1["insights"]) > 0

    # Turn 2: Show me growth opportunities.
    res2 = client.post(
        "/api/v1/agent/chat",
        json={
            "message": "Show me growth opportunities.",
            "merchant_id": agent_test_merchant.merchant_id,
            "conversation_id": conv_id,
        }
    )
    assert res2.status_code == status.HTTP_200_OK
    d2 = res2.json()
    assert d2["intent"]["intent"] in ("get_growth_recommendations", "analyze_business")

    # Turn 3: Simulate a ₹50 cashback campaign for inactive customers.
    res3 = client.post(
        "/api/v1/agent/chat",
        json={
            "message": "Simulate a ₹50 cashback campaign for inactive customers.",
            "merchant_id": agent_test_merchant.merchant_id,
            "conversation_id": conv_id,
        }
    )
    assert res3.status_code == status.HTTP_200_OK
    d3 = res3.json()
    assert d3["simulation"] is not None
    assert d3["simulation"]["projected_revenue"] > 0
    assert d3["simulation"].get("estimated_roi") is not None
    # Invariant: Campaign created must be strictly PENDING_APPROVAL
    if d3.get("campaign"):
        assert d3["campaign"]["status"] == "PENDING_APPROVAL"
        camp_id = d3["campaign"]["campaign_id"]
    else:
        # If simulated first, request draft
        res3b = client.post(
            "/api/v1/agent/chat",
            json={
                "message": "Create this campaign draft for inactive customers.",
                "merchant_id": agent_test_merchant.merchant_id,
                "conversation_id": conv_id,
            }
        )
        assert res3b.status_code == status.HTTP_200_OK
        d3b = res3b.json()
        assert d3b["campaign"] is not None
        assert d3b["campaign"]["status"] == "PENDING_APPROVAL"
        camp_id = d3b["campaign"]["campaign_id"]

    # Negative Safety Invariant: Autonomous or premature execution MUST fail before approval
    unapproved_exec = client.post(
        f"/api/v1/campaigns/{camp_id}/execute",
        params={"merchant_id": agent_test_merchant.merchant_id},
        headers={"Content-Type": "application/json"}
    )
    assert unapproved_exec.status_code == status.HTTP_409_CONFLICT, (
        f"Unapproved campaign execution should return 409 Conflict, got {unapproved_exec.status_code}"
    )

    # Turn 4: Approve this campaign
    res4 = client.post(
        "/api/v1/agent/chat",
        json={
            "message": "Approve this campaign.",
            "merchant_id": agent_test_merchant.merchant_id,
            "conversation_id": conv_id,
        }
    )
    assert res4.status_code == status.HTTP_200_OK
    d4 = res4.json()
    assert d4["intent"]["intent"] == "approve_campaign"
    assert d4["campaign"] is not None
    assert d4["campaign"]["status"] == "APPROVED"

    # Turn 5: Execute the campaign
    res5 = client.post(
        "/api/v1/agent/chat",
        json={
            "message": f"Execute campaign {camp_id}.",
            "merchant_id": agent_test_merchant.merchant_id,
            "conversation_id": conv_id,
        }
    )
    assert res5.status_code == status.HTTP_200_OK
    d5 = res5.json()
    assert d5["intent"]["intent"] == "execute_campaign"
    assert d5["execution_result"] is not None
    assert d5["execution_result"]["campaign_id"] == camp_id
    assert d5["execution_result"]["simulated_revenue"] > 0


def test_customer_cohort_differentiation(client: TestClient, agent_test_merchant: Merchant):
    """Verify VIP vs Inactive vs At-Risk customer questions yield distinct cohort data."""
    res_vip = client.post(
        "/api/v1/agent/chat",
        json={
            "message": "Who are my top customers?",
            "merchant_id": agent_test_merchant.merchant_id,
            "conversation_id": "conv-cohort-vip",
        }
    )
    res_inactive = client.post(
        "/api/v1/agent/chat",
        json={
            "message": "How many inactive customers do I have?",
            "merchant_id": agent_test_merchant.merchant_id,
            "conversation_id": "conv-cohort-inactive",
        }
    )
    res_at_risk = client.post(
        "/api/v1/agent/chat",
        json={
            "message": "Which customers are at risk of churning?",
            "merchant_id": agent_test_merchant.merchant_id,
            "conversation_id": "conv-cohort-at-risk",
        }
    )

    assert res_vip.status_code == status.HTTP_200_OK
    assert res_inactive.status_code == status.HTTP_200_OK
    assert res_at_risk.status_code == status.HTTP_200_OK

    msg_vip = res_vip.json()["message"]
    msg_inactive = res_inactive.json()["message"]
    msg_at_risk = res_at_risk.json()["message"]

    assert msg_vip != msg_inactive
    assert msg_vip != msg_at_risk
    assert msg_inactive != msg_at_risk

    assert "vip" in msg_vip.lower() or "top" in msg_vip.lower()
    assert "inactive" in msg_inactive.lower()
    assert "at-risk" in msg_at_risk.lower() or "at risk" in msg_at_risk.lower()
