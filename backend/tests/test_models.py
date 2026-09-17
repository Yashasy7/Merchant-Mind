"""
Tests for SQLAlchemy data models and relationships.
"""

from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models import Merchant, Customer, Transaction, Expense, Invoice, Campaign


def test_create_merchant_and_related_entities(db_session: Session):
    """Verify that all entities can be persisted with proper foreign key relationships."""
    # 1. Create Merchant
    merchant = Merchant(
        merchant_id="test-merchant-001",
        business_name="Test Store Bengaluru",
        business_type="Retail",
        location="Indiranagar, Bengaluru",
        business_age=12
    )
    db_session.add(merchant)
    db_session.commit()

    saved_merchant = db_session.get(Merchant, "test-merchant-001")
    assert saved_merchant is not None
    assert saved_merchant.business_name == "Test Store Bengaluru"

    # 2. Create Customer
    customer = Customer(
        customer_id="test-cust-001",
        merchant_id=merchant.merchant_id,
        name="Ananya Rao",
        phone="+91 9876543210",
        transaction_count=5,
        total_spend=Decimal("4500.50"),
        average_transaction=Decimal("900.10"),
        segment="Loyal"
    )
    db_session.add(customer)
    db_session.commit()

    saved_customer = db_session.get(Customer, "test-cust-001")
    assert saved_customer is not None
    assert saved_customer.segment == "Loyal"
    assert saved_customer.total_spend == Decimal("4500.50")

    # 3. Create Transaction
    transaction = Transaction(
        transaction_id="test-tx-001",
        merchant_id=merchant.merchant_id,
        customer_id=customer.customer_id,
        timestamp=datetime.now(timezone.utc),
        amount=Decimal("850.00"),
        payment_method="UPI",
        status="success"
    )
    db_session.add(transaction)
    db_session.commit()

    saved_tx = db_session.get(Transaction, "test-tx-001")
    assert saved_tx is not None
    assert saved_tx.amount == Decimal("850.00")
    assert saved_tx.merchant.merchant_id == merchant.merchant_id

    # 4. Create Expense
    expense = Expense(
        expense_id="test-exp-001",
        merchant_id=merchant.merchant_id,
        date=date.today(),
        category="Inventory",
        amount=Decimal("15000.00"),
        vendor="Bangalore Wholesale Hub"
    )
    db_session.add(expense)
    db_session.commit()

    saved_exp = db_session.get(Expense, "test-exp-001")
    assert saved_exp is not None
    assert saved_exp.amount == Decimal("15000.00")

    # 5. Create Invoice
    invoice = Invoice(
        invoice_id="test-inv-001",
        merchant_id=merchant.merchant_id,
        vendor="Metro Cash & Carry",
        amount=Decimal("12500.00"),
        date=date.today(),
        due_date=date.today(),
        status="pending"
    )
    db_session.add(invoice)
    db_session.commit()

    saved_inv = db_session.get(Invoice, "test-inv-001")
    assert saved_inv is not None
    assert saved_inv.status == "pending"

    # 6. Create Campaign
    campaign = Campaign(
        campaign_id="test-camp-001",
        merchant_id=merchant.merchant_id,
        target_segment="At-Risk",
        offer_type="cashback",
        offer_value=Decimal("50.00"),
        min_transaction=Decimal("299.00"),
        status="pending",
        estimated_cost=Decimal("2000.00")
    )
    db_session.add(campaign)
    db_session.commit()

    saved_camp = db_session.get(Campaign, "test-camp-001")
    assert saved_camp is not None
    assert saved_camp.target_segment == "At-Risk"
    assert saved_camp.offer_value == Decimal("50.00")
