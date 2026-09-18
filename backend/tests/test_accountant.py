"""
Comprehensive Test Suite for Module 8: AI Accountant / Financial Intelligence.

Verifies:
 1. Revenue calculation derived strictly from successful transactions
 2. Expense calculation derived from operational expense records
 3. Profit calculation (Revenue - Expenses)
 4. Profit margin calculation with safe zero-revenue division protection
 5. Expense breakdown by category and percentage distribution
 6. Expense anomaly detection (e.g. utility spike over baseline)
 7. Income vs expense periodic time-series tracking
 8. Period-over-period comparison (growth & contraction deltas)
 9. Invoices summary with paid vs pending status aggregation
10. Empty data handling (returns clean zero values, no 500 error)
11. Negative profit (operating loss) scenario
12. Multi-merchant isolation (cross-tenant data leakage prevention)
13. Invalid date range validation (start_date > end_date returns HTTP 400)
14. API endpoint GET /api/v1/accountant/summary validation
15. API endpoint GET /api/v1/accountant/profit-loss validation
16. API endpoint GET /api/v1/accountant/expenses validation
17. API endpoint GET /api/v1/accountant/income-vs-expense validation
18. API endpoint GET /api/v1/accountant/comparison validation
19. API endpoint GET /api/v1/accountant/invoices validation
20. API endpoint GET /api/v1/accountant/insights validation
21. Accounting disclaimer presence (non-CA scope compliance)
22. Module 7 AI Copilot integration via analyze_financials tool
23. Safe numeric serialization (no NaN / Infinity)
"""

import math
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Merchant, Customer, Transaction, Expense, Invoice
from app.services.accountant_service import AccountantService
from app.schemas.accountant import (
    ACCOUNTING_DISCLAIMER,
    ProfitLossResponse,
    ExpensesBreakdownResponse,
    AccountantSummaryResponse,
)


@pytest.fixture
def accountant_test_merchant(db_session: Session) -> Merchant:
    """Create a test merchant populated with transactions, expenses, and invoices."""
    m_id = "test-accountant-merchant-01"
    merchant = db_session.get(Merchant, m_id)
    if not merchant:
        merchant = Merchant(
            merchant_id=m_id,
            business_name="Aggarwal Retail Mart",
            business_type="Retail",
            location="Delhi",
            business_age=24,
        )
        db_session.add(merchant)
        db_session.flush()

    # Seed Customer
    cust = Customer(
        customer_id="cust-acc-001",
        merchant_id=m_id,
        name="Vikram Singh",
        phone="9876543299",
        segment="Regular",
    )
    db_session.add(cust)
    db_session.flush()

    now = datetime.now(timezone.utc)
    today = now.date()

    # Seed successful transactions (Revenue = 10 * 500 = 5,000.00)
    for i in range(1, 11):
        txn = Transaction(
            transaction_id=f"tx-acc-{i:03d}",
            merchant_id=m_id,
            customer_id=cust.customer_id,
            timestamp=now - timedelta(days=i),
            amount=Decimal("500.00"),
            payment_method="paytm_qr",
            status="success",
        )
        db_session.add(txn)

    # Seed failed transaction (should NOT count toward revenue)
    failed_txn = Transaction(
        transaction_id="tx-acc-failed",
        merchant_id=m_id,
        customer_id=cust.customer_id,
        timestamp=now - timedelta(days=2),
        amount=Decimal("1500.00"),
        payment_method="paytm_qr",
        status="failed",
    )
    db_session.add(failed_txn)

    # Seed current period expenses (Total = 2,500.00)
    # Inventory: 1,500.00, Rent: 500.00, Utilities: 500.00
    e1 = Expense(
        expense_id="exp-acc-001",
        merchant_id=m_id,
        date=today - timedelta(days=5),
        category="Inventory",
        amount=Decimal("1500.00"),
        vendor="Metro Wholesale",
        notes="Restocking",
    )
    e2 = Expense(
        expense_id="exp-acc-002",
        merchant_id=m_id,
        date=today - timedelta(days=10),
        category="Rent",
        amount=Decimal("500.00"),
        vendor="Premises Landlord",
        notes="Rent part payment",
    )
    e3 = Expense(
        expense_id="exp-acc-003",
        merchant_id=m_id,
        date=today - timedelta(days=12),
        category="Utilities",
        amount=Decimal("500.00"),
        vendor="BSES Electricity",
        notes="Electric bill",
    )

    # Seed baseline prior period expense for Utilities: 300.00 (Current 500 vs 300 is a +66.7% spike -> Anomaly!)
    e_baseline = Expense(
        expense_id="exp-acc-004",
        merchant_id=m_id,
        date=today - timedelta(days=45),
        category="Utilities",
        amount=Decimal("300.00"),
        vendor="BSES Electricity",
        notes="Previous electric bill",
    )

    db_session.add_all([e1, e2, e3, e_baseline])

    # Seed Invoices (1 paid @ 2,000, 1 pending @ 1,000)
    inv1 = Invoice(
        invoice_id="inv-acc-001",
        merchant_id=m_id,
        vendor="Supplier A",
        amount=Decimal("2000.00"),
        date=today - timedelta(days=15),
        due_date=today + timedelta(days=5),
        status="paid",
    )
    inv2 = Invoice(
        invoice_id="inv-acc-002",
        merchant_id=m_id,
        vendor="Supplier B",
        amount=Decimal("1000.00"),
        date=today - timedelta(days=5),
        due_date=today + timedelta(days=10),
        status="pending",
    )
    db_session.add_all([inv1, inv2])
    db_session.commit()

    return merchant


# -----------------------------------------------------------------------------
# 1. Revenue Calculation
# -----------------------------------------------------------------------------

def test_revenue_calculation(db_session: Session, accountant_test_merchant: Merchant):
    """Verify revenue is derived strictly from successful transactions."""
    service = AccountantService(db_session)
    pl = service.get_profit_loss(merchant_id=accountant_test_merchant.merchant_id)
    # 10 successful transactions of 500 = 5,000. Failed 1,500 excluded.
    assert pl.total_revenue == 5000.0
    assert pl.transaction_count == 10


# -----------------------------------------------------------------------------
# 2. Expense Calculation
# -----------------------------------------------------------------------------

def test_expense_calculation(db_session: Session, accountant_test_merchant: Merchant):
    """Verify expenses are aggregated from expense records."""
    service = AccountantService(db_session)
    today = date.today()
    # Query current 30-day window
    pl = service.get_profit_loss(
        merchant_id=accountant_test_merchant.merchant_id,
        start_date=today - timedelta(days=30),
        end_date=today,
    )
    # e1 (1500) + e2 (500) + e3 (500) = 2500.0
    assert pl.total_expenses == 2500.0
    assert pl.expense_count == 3


# -----------------------------------------------------------------------------
# 3. Profit and Margin Calculation
# -----------------------------------------------------------------------------

def test_profit_and_margin_calculation(db_session: Session, accountant_test_merchant: Merchant):
    """Verify profit = revenue - expenses and margin = (profit / revenue) * 100."""
    service = AccountantService(db_session)
    today = date.today()
    pl = service.get_profit_loss(
        merchant_id=accountant_test_merchant.merchant_id,
        start_date=today - timedelta(days=30),
        end_date=today,
    )
    # Revenue = 5000.0, Expenses = 2500.0 -> Profit = 2500.0
    assert pl.net_profit == 2500.0
    # Margin = (2500 / 5000) * 100 = 50.0%
    assert pl.operating_margin_pct == 50.0
    assert pl.is_profitable is True


# -----------------------------------------------------------------------------
# 4. Zero Revenue Safe Margin Protection
# -----------------------------------------------------------------------------

def test_profit_margin_zero_revenue(db_session: Session):
    """Verify margin is 0.0% and no division-by-zero occurs when revenue is 0.0."""
    empty_m = Merchant(
        merchant_id="merchant-zero-rev",
        business_name="Zero Rev Store",
        business_type="Retail",
        location="Delhi",
    )
    db_session.add(empty_m)
    db_session.commit()

    service = AccountantService(db_session)
    pl = service.get_profit_loss(merchant_id=empty_m.merchant_id)
    assert pl.total_revenue == 0.0
    assert pl.operating_margin_pct == 0.0
    assert not math.isnan(pl.operating_margin_pct)
    assert not math.isinf(pl.operating_margin_pct)


# -----------------------------------------------------------------------------
# 5. Expense Breakdown by Category
# -----------------------------------------------------------------------------

def test_expense_breakdown_by_category(db_session: Session, accountant_test_merchant: Merchant):
    """Verify expense breakdown groups by category and computes accurate percentages."""
    service = AccountantService(db_session)
    today = date.today()
    exp_resp = service.get_expenses_breakdown(
        merchant_id=accountant_test_merchant.merchant_id,
        start_date=today - timedelta(days=30),
        end_date=today,
    )
    assert exp_resp.total_expenses == 2500.0
    assert exp_resp.top_category == "Inventory"
    assert len(exp_resp.categories) == 3

    cat_map = {c.category: c for c in exp_resp.categories}
    assert cat_map["Inventory"].total_amount == 1500.0
    assert cat_map["Inventory"].percentage_of_total == 60.0
    assert cat_map["Rent"].total_amount == 500.0
    assert cat_map["Rent"].percentage_of_total == 20.0
    assert cat_map["Utilities"].total_amount == 500.0
    assert cat_map["Utilities"].percentage_of_total == 20.0

    # Sum of percentages should be 100.0
    total_pct = sum(c.percentage_of_total for c in exp_resp.categories)
    assert abs(total_pct - 100.0) < 0.1


# -----------------------------------------------------------------------------
# 6. Expense Anomaly Detection
# -----------------------------------------------------------------------------

def test_expense_anomaly_detection(db_session: Session, accountant_test_merchant: Merchant):
    """Verify that utility bill increase (+66.7% vs baseline) is flagged as an anomaly."""
    service = AccountantService(db_session)
    today = date.today()
    exp_resp = service.get_expenses_breakdown(
        merchant_id=accountant_test_merchant.merchant_id,
        start_date=today - timedelta(days=30),
        end_date=today,
    )
    assert len(exp_resp.anomalies) >= 1
    anom = exp_resp.anomalies[0]
    assert anom.category == "Utilities"
    assert anom.is_anomaly is True
    assert anom.change_percentage > 15.0
    assert "surged" in anom.message.lower() or "increase" in anom.message.lower()


# -----------------------------------------------------------------------------
# 7. Income vs Expense Periodic Tracking
# -----------------------------------------------------------------------------

def test_income_vs_expense_trends(db_session: Session, accountant_test_merchant: Merchant):
    """Verify monthly comparative buckets of income vs expense."""
    service = AccountantService(db_session)
    res = service.get_income_vs_expense(merchant_id=accountant_test_merchant.merchant_id, months=3)
    assert len(res.points) == 3
    assert res.total_income >= 0.0
    assert res.total_expense >= 0.0
    for p in res.points:
        assert isinstance(p.period, str)
        assert isinstance(p.income, float)
        assert isinstance(p.expense, float)
        assert isinstance(p.net_profit, float)


# -----------------------------------------------------------------------------
# 8. Period-over-Period Comparison
# -----------------------------------------------------------------------------

def test_period_comparison(db_session: Session, accountant_test_merchant: Merchant):
    """Verify delta calculation between current and previous period."""
    service = AccountantService(db_session)
    comp = service.get_period_comparison(merchant_id=accountant_test_merchant.merchant_id, current_days=30)
    assert isinstance(comp.revenue_change_pct, float)
    assert isinstance(comp.expense_change_pct, float)
    assert isinstance(comp.profit_change_pct, float)
    assert isinstance(comp.margin_change_pct, float)
    assert not math.isnan(comp.revenue_change_pct)


# -----------------------------------------------------------------------------
# 9. Invoices Summary
# -----------------------------------------------------------------------------

def test_invoices_summary(db_session: Session, accountant_test_merchant: Merchant):
    """Verify total invoices, paid vs pending amount and count aggregation."""
    service = AccountantService(db_session)
    inv = service.get_invoices_summary(merchant_id=accountant_test_merchant.merchant_id)
    assert inv.total_invoices == 2
    assert inv.total_amount == 3000.0
    assert inv.paid_amount == 2000.0
    assert inv.pending_amount == 1000.0
    assert inv.paid_count == 1
    assert inv.pending_count == 1


# -----------------------------------------------------------------------------
# 10. Empty Data Handling
# -----------------------------------------------------------------------------

def test_empty_data_handling(db_session: Session):
    """Verify clean zero values when merchant has no transaction or expense records."""
    fresh_m = Merchant(
        merchant_id="merchant-empty-acc-01",
        business_name="Fresh Store",
        business_type="Retail",
        location="Pune",
    )
    db_session.add(fresh_m)
    db_session.commit()

    service = AccountantService(db_session)
    summary = service.get_accountant_summary(merchant_id=fresh_m.merchant_id)
    assert summary.profit_loss.total_revenue == 0.0
    assert summary.profit_loss.total_expenses == 0.0
    assert summary.profit_loss.net_profit == 0.0
    assert summary.profit_loss.operating_margin_pct == 0.0
    assert summary.expenses.total_expenses == 0.0
    assert summary.invoices.total_amount == 0.0


# -----------------------------------------------------------------------------
# 11. Negative Profit Scenario (Operating Loss)
# -----------------------------------------------------------------------------

def test_negative_profit_operating_loss(db_session: Session):
    """Verify operating deficit when expenses exceed revenue."""
    loss_m = Merchant(
        merchant_id="merchant-loss-acc-01",
        business_name="Struggling Store",
        business_type="Retail",
        location="Jaipur",
    )
    db_session.add(loss_m)
    db_session.flush()

    today = date.today()
    now = datetime.now(timezone.utc)

    # Revenue = 100.0
    t = Transaction(
        transaction_id="tx-loss-01",
        merchant_id=loss_m.merchant_id,
        timestamp=now,
        amount=Decimal("100.00"),
        status="success",
    )
    # Expenses = 500.0
    e = Expense(
        expense_id="exp-loss-01",
        merchant_id=loss_m.merchant_id,
        date=today,
        category="Rent",
        amount=Decimal("500.00"),
        vendor="Landlord",
    )
    db_session.add_all([t, e])
    db_session.commit()

    service = AccountantService(db_session)
    pl = service.get_profit_loss(merchant_id=loss_m.merchant_id)
    assert pl.net_profit == -400.0
    assert pl.is_profitable is False
    assert pl.operating_margin_pct == -400.0


# -----------------------------------------------------------------------------
# 12. Multi-Merchant Isolation
# -----------------------------------------------------------------------------

def test_merchant_isolation(db_session: Session, accountant_test_merchant: Merchant):
    """Verify Merchant B cannot view Merchant A's financial records."""
    other_m = Merchant(
        merchant_id="other-merchant-acc-99",
        business_name="Other Shop",
        business_type="Retail",
        location="Chennai",
    )
    db_session.add(other_m)
    db_session.commit()

    service = AccountantService(db_session)
    other_pl = service.get_profit_loss(merchant_id=other_m.merchant_id)
    # Must be 0.0, not contaminated by accountant_test_merchant's 5,000.0 revenue
    assert other_pl.total_revenue == 0.0
    assert other_pl.total_expenses == 0.0
    assert other_pl.net_profit == 0.0

    other_invoices = service.get_invoices_summary(merchant_id=other_m.merchant_id)
    assert other_invoices.total_invoices == 0
    assert other_invoices.total_amount == 0.0


# -----------------------------------------------------------------------------
# 13. Invalid Date Range Validation
# -----------------------------------------------------------------------------

def test_invalid_date_range_rejected(client: TestClient, accountant_test_merchant: Merchant):
    """Verify HTTP 400 when start_date > end_date."""
    response = client.get(
        "/api/v1/accountant/profit-loss",
        params={
            "merchant_id": accountant_test_merchant.merchant_id,
            "start_date": "2026-09-20",
            "end_date": "2026-09-10",
        }
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert "start_date" in str(data).lower() or "start date" in str(data).lower()


# -----------------------------------------------------------------------------
# 14–20. REST API Endpoints Validation
# -----------------------------------------------------------------------------

def test_api_accountant_summary(client: TestClient, accountant_test_merchant: Merchant):
    """Verify GET /api/v1/accountant/summary returns complete structured envelope."""
    response = client.get(
        "/api/v1/accountant/summary",
        params={"merchant_id": accountant_test_merchant.merchant_id}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "profit_loss" in data
    assert "expenses" in data
    assert "invoices" in data
    assert "insights" in data
    assert "disclaimer" in data
    assert data["profit_loss"]["total_revenue"] == 5000.0


def test_api_profit_loss(client: TestClient, accountant_test_merchant: Merchant):
    """Verify GET /api/v1/accountant/profit-loss."""
    response = client.get(
        "/api/v1/accountant/profit-loss",
        params={"merchant_id": accountant_test_merchant.merchant_id}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_revenue"] == 5000.0
    assert "net_profit" in data
    assert "operating_margin_pct" in data


def test_api_expenses(client: TestClient, accountant_test_merchant: Merchant):
    """Verify GET /api/v1/accountant/expenses."""
    response = client.get(
        "/api/v1/accountant/expenses",
        params={"merchant_id": accountant_test_merchant.merchant_id}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_expenses"] > 0.0
    assert data["top_category"] is not None
    assert len(data["categories"]) > 0


def test_api_income_vs_expense(client: TestClient, accountant_test_merchant: Merchant):
    """Verify GET /api/v1/accountant/income-vs-expense."""
    response = client.get(
        "/api/v1/accountant/income-vs-expense",
        params={"merchant_id": accountant_test_merchant.merchant_id, "months": 3}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["points"]) == 3


def test_api_comparison(client: TestClient, accountant_test_merchant: Merchant):
    """Verify GET /api/v1/accountant/comparison."""
    response = client.get(
        "/api/v1/accountant/comparison",
        params={"merchant_id": accountant_test_merchant.merchant_id, "current_days": 30}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "current_period" in data
    assert "previous_period" in data
    assert "profit_change_pct" in data


def test_api_invoices(client: TestClient, accountant_test_merchant: Merchant):
    """Verify GET /api/v1/accountant/invoices."""
    response = client.get(
        "/api/v1/accountant/invoices",
        params={"merchant_id": accountant_test_merchant.merchant_id}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_invoices"] == 2
    assert data["pending_amount"] == 1000.0


def test_api_insights(client: TestClient, accountant_test_merchant: Merchant):
    """Verify GET /api/v1/accountant/insights."""
    response = client.get(
        "/api/v1/accountant/insights",
        params={"merchant_id": accountant_test_merchant.merchant_id}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["insights"]) >= 1
    assert "summary" in data


# -----------------------------------------------------------------------------
# 21. Non-CA Accounting Safety Disclaimer
# -----------------------------------------------------------------------------

def test_accounting_disclaimer_present(client: TestClient, accountant_test_merchant: Merchant):
    """Verify visible non-CA disclaimer is included on all responses."""
    endpoints = [
        "/api/v1/accountant/summary",
        "/api/v1/accountant/profit-loss",
        "/api/v1/accountant/expenses",
        "/api/v1/accountant/invoices",
        "/api/v1/accountant/insights",
    ]
    for ep in endpoints:
        resp = client.get(ep, params={"merchant_id": accountant_test_merchant.merchant_id})
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "disclaimer" in data
        assert "Chartered Accountant" in data["disclaimer"] or "CA" in data["disclaimer"]


# -----------------------------------------------------------------------------
# 22. Module 7 AI Copilot Integration via analyze_financials
# -----------------------------------------------------------------------------

def test_ai_agent_analyze_financials_tool(client: TestClient, accountant_test_merchant: Merchant):
    """
    Verify merchant can ask 'How much profit did I make this month?'
    Agent invokes analyze_financials tool and returns validated financial metrics.
    """
    payload = {
        "message": "How much profit did I make this month? What are my expenses?",
        "merchant_id": accountant_test_merchant.merchant_id,
    }
    response = client.post("/api/v1/agent/chat", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["intent"]["intent"] == "analyze_financials"
    actions = [a["tool_name"] for a in data["actions_taken"]]
    assert "analyze_financials" in actions
    assert len(data["insights"]) > 0
    # Response must mention profit or margin
    assert any("profit" in ins.lower() for ins in data["insights"])


# -----------------------------------------------------------------------------
# 23. Safe Numeric Serialization (No NaN / Infinity)
# -----------------------------------------------------------------------------

def test_no_nan_or_infinity(client: TestClient, accountant_test_merchant: Merchant):
    """Verify that all numerical responses are finite numbers."""
    resp = client.get(
        "/api/v1/accountant/summary",
        params={"merchant_id": accountant_test_merchant.merchant_id}
    )
    raw_text = resp.text
    assert "NaN" not in raw_text
    assert "Infinity" not in raw_text
    assert "-Infinity" not in raw_text
