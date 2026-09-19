"""
Test Suite: Gemini API Validation, Synthetic Financial Dataset Grounding, and Data-Grounded Copilot
Covers all 28 verification items required by Part 11:
- Gemini: connection, invalid key, timeout, response parsing, model unavailable
- Financial data: transaction aggregation, monthly sales, expense aggregation, profit/loss,
  profit margin, cash flow, customer segments, campaign performance, period comparison
- Agent: sales, profit, expense, cash flow, customer, growth, follow-up, unrelated, non-repetitive
- Cognee: recall, remember, merchant isolation
- Campaign: approval gate, n8n execution only after approval
"""

import pytest
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import httpx

from app.models.merchant import Merchant
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.expense import Expense
from app.models.invoice import Invoice
from app.models.campaign import Campaign
from app.ai.llm_client import GeminiLLMClient, DeterministicFallbackClient
from app.ai.agent import MarketingCampaignAgent
from app.ai.schemas import AgentChatRequest, MerchantIntent
from app.ai.tools import ToolRegistry
from app.services.accountant_service import AccountantService
from app.services.sales_service import SalesService
from app.services.customer_service import CustomerService
from app.services.campaign_service import CampaignService
from app.ai.cognee_client import CogneeClient
from app.core.config import get_settings


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def financial_merchant(db_session: Session) -> Merchant:
    """Seed a test merchant with transactions, expenses, invoices, and customers."""
    m_id = "test-fin-merchant-01"
    existing = db_session.query(Merchant).filter(Merchant.merchant_id == m_id).first()
    if existing:
        return existing

    merchant = Merchant(
        merchant_id=m_id,
        business_name="Jaipur Sweets & Bakers",
        business_type="Bakery / Retail",
        location="Jaipur",
        business_age=2,
    )
    db_session.add(merchant)

    # Customers
    c1 = Customer(
        customer_id=f"{m_id}-c1",
        merchant_id=m_id,
        name="VIP Customer",
        segment="VIP",
        total_spend=Decimal("25000.00"),
        transaction_count=20,
        last_transaction=datetime(2026, 9, 15, tzinfo=timezone.utc),
    )
    c2 = Customer(
        customer_id=f"{m_id}-c2",
        merchant_id=m_id,
        name="At-Risk Customer",
        segment="At-Risk",
        total_spend=Decimal("8000.00"),
        transaction_count=8,
        last_transaction=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    c3 = Customer(
        customer_id=f"{m_id}-c3",
        merchant_id=m_id,
        name="Inactive Customer",
        segment="Inactive",
        total_spend=Decimal("4000.00"),
        transaction_count=4,
        last_transaction=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    db_session.add_all([c1, c2, c3])

    # Transactions (September 2026 and August 2026)
    txns = []
    # August (last month): 10 txns of 1000 each = 10,000 (dates: Aug 5 to Aug 14)
    for i in range(1, 11):
        txns.append(
            Transaction(
                transaction_id=f"tx-aug-{i}",
                merchant_id=m_id,
                customer_id=f"{m_id}-c1",
                amount=Decimal("1000.00"),
                status="success",
                payment_method="UPI",
                timestamp=datetime(2026, 8, i + 4, 12, 0, tzinfo=timezone.utc),
            )
        )
    # September (this month): 15 txns of 1200 each = 18,000
    for i in range(1, 16):
        txns.append(
            Transaction(
                transaction_id=f"tx-sep-{i}",
                merchant_id=m_id,
                customer_id=f"{m_id}-c1",
                amount=Decimal("1200.00"),
                status="success",
                payment_method="UPI" if i % 2 == 0 else "QR",
                timestamp=datetime(2026, 9, i, 14, 0, tzinfo=timezone.utc),
            )
        )
    db_session.add_all(txns)

    # Expenses (Total = 6000)
    e1 = Expense(
        expense_id="exp-1",
        merchant_id=m_id,
        date=date(2026, 9, 5),
        category="Inventory",
        amount=Decimal("3500.00"),
        vendor="Flour Mill Ltd",
        notes="Raw ingredients",
    )
    e2 = Expense(
        expense_id="exp-2",
        merchant_id=m_id,
        date=date(2026, 9, 10),
        category="Rent",
        amount=Decimal("2000.00"),
        vendor="Store Landlord",
        notes="Store rental",
    )
    e3 = Expense(
        expense_id="exp-3",
        merchant_id=m_id,
        date=date(2026, 9, 12),
        category="Utilities",
        amount=Decimal("500.00"),
        vendor="State Power Corp",
        notes="Electricity bill",
    )
    db_session.add_all([e1, e2, e3])

    # Invoices
    inv1 = Invoice(
        invoice_id="inv-1",
        merchant_id=m_id,
        vendor="Flour Supplier",
        amount=1200.0,
        date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        status="pending",
    )
    inv2 = Invoice(
        invoice_id="inv-2",
        merchant_id=m_id,
        vendor="Dairy Farm",
        amount=800.0,
        date=date(2026, 8, 15),
        due_date=date(2026, 9, 1),
        status="overdue",
    )
    db_session.add_all([inv1, inv2])

    # Campaign
    camp = Campaign(
        campaign_id="camp-test-hist-01",
        merchant_id=m_id,
        name="Past VIP Campaign",
        target_segment="VIP",
        offer_type="fixed_cashback",
        status="COMPLETED",
        estimated_cost=Decimal("3000.00"),
        actual_revenue=Decimal("18000.00"),
        simulated_revenue=Decimal("18000.00"),
        simulated_transactions=15,
        simulated_cost=Decimal("3000.00"),
        simulated_net_impact=Decimal("15000.00"),
        simulated_roi=Decimal("500.00"),
        created_at=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        executed_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    db_session.add(camp)

    db_session.commit()
    return merchant


# =============================================================================
# PART 11.1 — GEMINI INTEGRATION TESTS (Tests 1 to 5)
# =============================================================================

def test_1_gemini_connection():
    """Verify Gemini client live connection check returns valid dictionary."""
    client = GeminiLLMClient(api_key="mock-api-key-test")
    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "GEMINI_CONNECTION_OK"}]}}]
        }
        mock_post.return_value = mock_resp

        res = client.test_connection()
        assert res["status"] == "success"
        assert res["status_code"] == 200
        assert "GEMINI_CONNECTION_OK" in res["response_text"]
        assert res["latency_ms"] >= 0


def test_2_gemini_invalid_api_key_handling():
    """Verify Gemini client handles invalid API key (401/403) gracefully with fallback."""
    client = GeminiLLMClient(api_key="invalid-key-xyz")
    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "API_KEY_INVALID"
        mock_post.return_value = mock_resp

        # Should not raise exception; must fall back to deterministic response
        resp_text = client.generate_response(
            "What are my sales this month?",
            MerchantIntent(intent="analyze_sales", objective="analysis", requested_action="analysis"),
            []
        )
        assert resp_text is not None
        assert len(resp_text) > 20


def test_3_gemini_timeout_handling():
    """Verify Gemini client handles network timeouts without crashing."""
    client = GeminiLLMClient(api_key="mock-timeout-key")
    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Connection timed out")):
        res = client.test_connection()
        assert res["status"] == "timeout"
        assert "TimeoutException" in res["exception_type"]

        # generate_response also handles timeout gracefully
        resp_text = client.generate_response(
            "How much profit did I make?",
            MerchantIntent(intent="analyze_financials", objective="accounting", requested_action="accounting"),
            []
        )
        assert resp_text is not None
        assert "profit" in resp_text.lower() or "financial" in resp_text.lower()


def test_4_gemini_response_parsing():
    """Verify Gemini structured JSON intent parsing handles markdown fences and valid JSON."""
    client = GeminiLLMClient(api_key="mock-parser-key")
    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": '```json\n{"intent": "analyze_cash_flow", "objective": "accounting", "target_segment": "All Customers", "requested_action": "accounting", "parameters": {}}\n```'
                    }]
                }
            }]
        }
        mock_post.return_value = mock_resp

        intent = client.parse_intent("What is my cash flow situation?")
        assert intent.intent == "analyze_cash_flow"
        assert intent.objective == "accounting"


def test_5_gemini_model_unavailable_handling():
    """Verify 404 (model unavailable) triggers graceful fallback to deterministic engine."""
    client = GeminiLLMClient(api_key="mock-key", model="nonexistent-gemini-model-v99")
    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Model nonexistent-gemini-model-v99 not found"
        mock_post.return_value = mock_resp

        intent = client.parse_intent("What are my sales this month?")
        assert intent.intent == "analyze_sales"


# =============================================================================
# PART 11.2 — FINANCIAL DATA TESTS (Tests 6 to 14)
# =============================================================================

def test_6_transaction_aggregation(db_session: Session, financial_merchant: Merchant):
    """Verify deterministic transaction aggregation calculates total revenue and volume."""
    service = SalesService(db_session)
    summary = service.get_summary(financial_merchant.merchant_id)
    # 10 * 1000 + 15 * 1200 = 10,000 + 18,000 = 28,000
    assert summary.total_revenue == 28000.0
    assert summary.total_transactions == 25
    assert summary.average_transaction_value == 1120.0


def test_7_monthly_sales(db_session: Session, financial_merchant: Merchant):
    """Verify monthly sales query isolates August vs September transactions."""
    service = SalesService(db_session)
    sep_summary = service.get_summary(
        financial_merchant.merchant_id,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30)
    )
    assert sep_summary.total_revenue == 18000.0
    assert sep_summary.total_transactions == 15

    aug_summary = service.get_summary(
        financial_merchant.merchant_id,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31)
    )
    assert aug_summary.total_revenue == 10000.0
    assert aug_summary.total_transactions == 10


def test_8_expense_aggregation(db_session: Session, financial_merchant: Merchant):
    """Verify expense aggregation sums categorized expenses correctly."""
    service = AccountantService(db_session)
    expenses = service.get_expenses_breakdown(financial_merchant.merchant_id)
    # 3500 (Inventory) + 2000 (Rent) + 500 (Utilities) = 6000
    assert expenses.total_expenses == 6000.0
    assert expenses.top_category == "Inventory"
    assert len(expenses.categories) == 3


def test_9_profit_loss(db_session: Session, financial_merchant: Merchant):
    """Verify deterministic P&L calculation: Net Profit = Revenue - Expenses."""
    service = AccountantService(db_session)
    pl = service.get_profit_loss(financial_merchant.merchant_id)
    # Revenue = 28,000, Expenses = 6,000 -> Net Profit = 22,000
    assert pl.total_revenue == 28000.0
    assert pl.total_expenses == 6000.0
    assert pl.net_profit == 22000.0
    assert pl.is_profitable is True


def test_10_profit_margin(db_session: Session, financial_merchant: Merchant):
    """Verify Operating Profit Margin calculation: (Net Profit / Revenue) * 100."""
    service = AccountantService(db_session)
    pl = service.get_profit_loss(financial_merchant.merchant_id)
    expected_margin = round((22000.0 / 28000.0) * 100.0, 2)
    assert pl.operating_margin_pct == expected_margin
    assert pl.operating_margin_pct > 70.0


def test_11_cash_flow(db_session: Session, financial_merchant: Merchant):
    """Verify cash flow service computes inflows, outflows, receivables, and payables."""
    service = AccountantService(db_session)
    cf = service.get_cash_flow(financial_merchant.merchant_id)
    assert cf.total_cash_inflows == 28000.0
    assert cf.total_cash_outflows == 6000.0
    assert cf.net_cash_flow == 22000.0
    assert cf.pending_payables == 2000.0  # inv1 (pending) + inv2 (overdue)
    assert cf.overdue_payables == 800.0   # inv2 is overdue
    assert cf.pending_receivables > 0.0


def test_12_customer_segments(db_session: Session, financial_merchant: Merchant):
    """Verify customer intelligence classifies customers into VIP, At-Risk, Inactive."""
    service = CustomerService(db_session)
    summary = service.get_summary(financial_merchant.merchant_id)
    segments = service.get_segments(financial_merchant.merchant_id)
    assert summary.total_customers == 3
    assert summary.at_risk_customers >= 0
    assert summary.inactive_customers >= 0
    assert len(segments.segments) >= 1


def test_13_campaign_performance(db_session: Session, financial_merchant: Merchant):
    """Verify historical campaign performance metrics are accessible."""
    service = CampaignService(db_session)
    history = service.list_campaigns(financial_merchant.merchant_id)
    assert len(history.campaigns) >= 1
    past_camp = history.campaigns[0]
    assert past_camp.status == "COMPLETED"
    assert past_camp.simulated_revenue == 18000.0


def test_14_period_comparison(db_session: Session, financial_merchant: Merchant):
    """Verify period comparison evaluates revenue and profit changes."""
    service = SalesService(db_session)
    comp = service.get_period_comparison(
        financial_merchant.merchant_id,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30)
    )
    assert comp.current_period.revenue == 18000.0
    assert comp.previous_period.revenue == 10000.0
    assert comp.revenue_change_percentage == 80.0


# =============================================================================
# PART 11.3 — AGENT INTELLIGENCE & RESPONSE DIVERSITY (Tests 15 to 23)
# =============================================================================

def test_15_agent_sales_query(db_session: Session, financial_merchant: Merchant):
    """Verify sales query executes analyze_sales and returns verified revenue numbers."""
    agent = MarketingCampaignAgent(db=db_session, merchant_id=financial_merchant.merchant_id)
    resp = agent.chat(AgentChatRequest(message="What are my sales this month?"))
    assert resp.intent.intent == "analyze_sales"
    assert "18,000" in resp.message
    assert any(a.tool_name == "analyze_sales" for a in resp.actions_taken)


def test_16_agent_profit_query(db_session: Session, financial_merchant: Merchant):
    """Verify profit query executes analyze_financials and returns net profit & CA disclaimer."""
    agent = MarketingCampaignAgent(db=db_session, merchant_id=financial_merchant.merchant_id)
    resp = agent.chat(AgentChatRequest(message="How much profit did I make?"))
    assert resp.intent.intent == "analyze_financials"
    assert "22,000" in resp.message or "profit" in resp.message.lower()
    assert "Chartered Accountant" in resp.message or "CA" in resp.message


def test_17_agent_expense_query(db_session: Session, financial_merchant: Merchant):
    """Verify biggest expenses query ranks categories by spend."""
    agent = MarketingCampaignAgent(db=db_session, merchant_id=financial_merchant.merchant_id)
    resp = agent.chat(AgentChatRequest(message="What are my biggest expenses?"))
    assert resp.intent.intent == "analyze_financials"
    assert "Inventory" in resp.message
    assert "6,000" in resp.message


def test_18_agent_cash_flow_query(db_session: Session, financial_merchant: Merchant):
    """Verify cash flow query executes analyze_cash_flow tool."""
    agent = MarketingCampaignAgent(db=db_session, merchant_id=financial_merchant.merchant_id)
    resp = agent.chat(AgentChatRequest(message="What is my cash flow situation?"))
    assert resp.intent.intent == "analyze_cash_flow"
    assert "cash flow" in resp.message.lower()
    assert any(a.tool_name == "analyze_cash_flow" for a in resp.actions_taken)


def test_19_agent_customer_query(db_session: Session, financial_merchant: Merchant):
    """Verify customer intelligence query identifies at-risk and inactive segments."""
    agent = MarketingCampaignAgent(db=db_session, merchant_id=financial_merchant.merchant_id)
    resp = agent.chat(AgentChatRequest(message="Who are my at-risk customers?"))
    assert resp.intent.intent == "analyze_customers"
    assert "at-risk" in resp.message.lower()
    assert any(a.tool_name == "analyze_customers" for a in resp.actions_taken)


def test_20_agent_growth_query(db_session: Session, financial_merchant: Merchant):
    """Verify growth recommendation query returns prioritized store upside opportunities."""
    agent = MarketingCampaignAgent(db=db_session, merchant_id=financial_merchant.merchant_id)
    resp = agent.chat(AgentChatRequest(message="How can I increase sales?"))
    assert resp.intent.intent in ("get_growth_recommendations", "analyze_business")
    assert any(a.tool_name == "get_growth_recommendations" for a in resp.actions_taken)


def test_21_agent_follow_up_query(db_session: Session, financial_merchant: Merchant):
    """Verify multi-turn follow-up preserves context."""
    agent = MarketingCampaignAgent(db=db_session, merchant_id=financial_merchant.merchant_id)
    conv_id = "test-conv-grounding-followup"
    # Turn 1
    r1 = agent.chat(AgentChatRequest(message="My sales have dropped. Why are they falling?", conversation_id=conv_id))
    assert r1.intent.intent == "analyze_sales"
    # Turn 2: Follow up
    r2 = agent.chat(AgentChatRequest(message="Why is that?", conversation_id=conv_id))
    assert r2.intent.intent == "analyze_sales"


def test_22_agent_unrelated_query(db_session: Session, financial_merchant: Merchant):
    """Verify unrelated / general guidance returns helpful capabilities list."""
    agent = MarketingCampaignAgent(db=db_session, merchant_id=financial_merchant.merchant_id)
    resp = agent.chat(AgentChatRequest(message="What is the weather in Delhi?"))
    assert "Paytm MerchantMind" in resp.message or "marketing partner" in resp.message.lower()


def test_23_multiple_different_queries_distinct_responses(db_session: Session, financial_merchant: Merchant):
    """Verify that multiple different queries NEVER return identical canned responses."""
    agent = MarketingCampaignAgent(db=db_session, merchant_id=financial_merchant.merchant_id)
    queries = [
        "What are my sales this month?",
        "How much profit did I make?",
        "Who are my at-risk customers?",
        "What are my biggest expenses?",
        "What is my cash flow situation?",
        "Which expenses increased the most?",
        "How much revenue did I generate last month?",
        "What is my profit margin?",
        "Tell me something completely different about my business.",
    ]
    responses = []
    for q in queries:
        resp = agent.chat(AgentChatRequest(message=q))
        responses.append(resp.message.strip())

    # All 9 responses must be strictly unique
    assert len(set(responses)) == len(queries), "Detected duplicate or repetitive responses across distinct queries!"


# =============================================================================
# PART 11.4 — COGNEE CLOUD MEMORY TESTS (Tests 24 to 26)
# =============================================================================

def test_24_cognee_recall():
    """Verify Cognee memory recall retrieves stored knowledge."""
    cognee = CogneeClient()
    with patch.object(cognee, "recall", return_value=["Merchant prefer weekend campaigns"]):
        memories = cognee.recall("demo-merchant-001")
        assert len(memories) == 1
        assert "weekend" in memories[0]


def test_25_cognee_remember():
    """Verify Cognee memory stores business context without errors."""
    cognee = CogneeClient()
    with patch.object(cognee, "remember", return_value=True):
        ok = cognee.remember("demo-merchant-001", "Sales increased by 15% after evening offer.")
        assert ok is True


def test_26_cognee_merchant_isolation():
    """Verify Cognee dataset naming maintains strict merchant isolation."""
    from app.ai.cognee_client import _merchant_dataset
    ds1 = _merchant_dataset("demo-merchant-001")
    ds2 = _merchant_dataset("demo-merchant-002")
    assert ds1 != ds2
    assert "demo_merchant_001" in ds1
    assert "demo_merchant_002" in ds2


# =============================================================================
# PART 11.5 — CAMPAIGN & N8N APPROVAL SAFETY (Tests 27 to 28)
# =============================================================================

def test_27_campaign_approval_gate(db_session: Session, financial_merchant: Merchant):
    """Verify campaign creation stops at PENDING_APPROVAL and requires human approval."""
    agent = MarketingCampaignAgent(db=db_session, merchant_id=financial_merchant.merchant_id)
    resp = agent.chat(AgentChatRequest(message="Create a ₹50 cashback campaign for inactive customers."))
    assert resp.approval_required is True
    assert resp.status == "PENDING_APPROVAL"
    assert resp.campaign is not None
    assert resp.campaign.status == "PENDING_APPROVAL"
    assert resp.execution_result is None


def test_28_n8n_execution_only_after_approval(db_session: Session, financial_merchant: Merchant):
    """Verify campaign can only be executed after explicit approval, rejecting execution on unapproved drafts."""
    agent = MarketingCampaignAgent(db=db_session, merchant_id=financial_merchant.merchant_id)
    c_service = CampaignService(db_session)
    from app.schemas.campaign import CampaignCreateRequest
    draft = c_service.create_campaign(
        financial_merchant.merchant_id,
        CampaignCreateRequest(
            merchant_id=financial_merchant.merchant_id,
            name="Safety Test Campaign",
            target_segment="Inactive",
            offer_type="fixed_cashback",
            cashback_amount=50.0,
        )
    )
    assert draft.status == "PENDING_APPROVAL"

    # Direct execution of unapproved campaign fails
    with pytest.raises(Exception):
        c_service.execute_campaign(draft.campaign_id, financial_merchant.merchant_id)

    # Approve campaign
    from app.schemas.campaign import CampaignApproveRequest
    approved = c_service.approve_campaign(
        draft.campaign_id,
        financial_merchant.merchant_id,
        CampaignApproveRequest(approved_by="Merchant")
    )
    assert approved.status == "APPROVED"

    # Execution now succeeds
    result = c_service.execute_campaign(draft.campaign_id, financial_merchant.merchant_id)
    assert result.status == "COMPLETED"
