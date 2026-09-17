"""
Tests for the synthetic data generator foundation.
"""

from scripts.generate_synthetic_data import (
    generate_full_synthetic_dataset,
    generate_merchant_data,
    generate_customers_data,
    generate_expenses_data,
    generate_invoices_data,
    generate_campaigns_data,
)


def test_synthetic_data_generation_structure():
    """Verify that synthetic dataset produces all required entity tables with metadata."""
    dataset = generate_full_synthetic_dataset(merchant_id="demo-merchant-001", seed=42)

    assert "metadata" in dataset
    assert "merchant" in dataset
    assert "customers" in dataset
    assert "transactions" in dataset
    assert "expenses" in dataset
    assert "invoices" in dataset
    assert "campaigns" in dataset

    # Validate merchant
    m = dataset["merchant"]
    assert m["merchant_id"] == "demo-merchant-001"
    assert m["business_name"] == "Sharma General Store"

    # Validate customers
    custs = dataset["customers"]
    assert len(custs) >= 250
    segments = {c["segment"] for c in custs}
    assert "VIP" in segments
    assert "Loyal" in segments
    assert "New" in segments
    assert "At-Risk" in segments
    assert "Inactive" in segments

    # Validate transactions
    txns = dataset["transactions"]
    assert len(txns) >= 2000
    first_tx = txns[0]
    assert "amount" in first_tx
    assert "payment_method" in first_tx
    assert "timestamp" in first_tx

    # Validate expenses and invoices
    assert len(dataset["expenses"]) > 0
    assert len(dataset["invoices"]) > 0
    assert len(dataset["campaigns"]) > 0
