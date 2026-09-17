"""
Tests for Module 6 — Campaign / Approval / Action.

Verifies:
  1. Campaign creation (enters PENDING_APPROVAL)
  2. Audit logging for CREATE event
  3. Approval workflow (PENDING_APPROVAL -> APPROVED, sets approved_at, creates audit)
  4. Approval does NOT execute campaign
  5. Repeated approval rejected with 409 Conflict
  6. Rejection workflow (PENDING_APPROVAL -> REJECTED, reason persisted, creates audit)
  7. Repeated rejection rejected with 409 Conflict
  8. Safety boundary: PENDING_APPROVAL campaigns CANNOT execute (409 Conflict)
  9. Execution workflow: APPROVED -> VALIDATING -> EXECUTING -> COMPLETED
  10. Deterministic synthetic demo result generation (reusing Module 5 simulation)
  11. Completed campaigns cannot be executed twice (409 Conflict)
  12. Campaign result endpoint behavior (400 before execution, valid after)
  13. Campaign detail endpoint
  14. Campaign list endpoint with status filters and limits
  15. Audit history endpoint
  16. Merchant isolation across all operations (view, approve, reject, execute, audit)
  17. Invalid campaign parameters and validation checks (offer, segment, dates)
  18. Invalid state transitions (approve rejected, reject approved, execute draft)
  19. Financial correctness (finite values, non-negative bounds)
  20. Source recommendation / simulation merchant mismatch detection
  21. Database persistence and non-interference with transaction tables
  22. Optional cancellation workflow
  23. Route aliases (/campaigns vs /v1/campaigns)
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.campaign import Campaign, CampaignAuditLog
from app.models.transaction import Transaction
from app.schemas.campaign import CampaignStatus, CampaignAuditAction


def get_err(resp) -> str:
    """Extract error text from either 'detail' or unified ErrorResponse 'message'."""
    data = resp.json()
    if isinstance(data, dict):
        return str(data.get("detail") or data.get("message") or "")
    return str(data)


# -----------------------------------------------------------------------------
# 1. Campaign Creation Tests
# -----------------------------------------------------------------------------

def test_campaign_creation_enters_pending_approval(client: TestClient, db_session: Session):
    """Verify that newly created campaigns enter PENDING_APPROVAL and record CREATE audit."""
    payload = {
        "merchant_id": "demo-merchant-001",
        "name": "Weekend Cashback Festival",
        "description": "₹50 cashback on orders above ₹300 on weekends",
        "target_segment": "Inactive",
        "offer_type": "fixed_cashback",
        "cashback_amount": 50.0,
        "minimum_transaction_amount": 300.0,
        "target_days": "weekend",
        "target_hours": "evening",
    }
    response = client.post("/api/v1/campaigns", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    assert data["campaign_id"].startswith("cmp-")
    assert data["merchant_id"] == "demo-merchant-001"
    assert data["name"] == "Weekend Cashback Festival"
    assert data["target_segment"] == "Inactive"
    assert data["offer_type"] == "fixed_cashback"
    assert data["cashback_amount"] == 50.0
    assert data["minimum_transaction_amount"] == 300.0
    # Mandatory human-in-the-loop safety requirement:
    assert data["status"] == CampaignStatus.PENDING_APPROVAL.value
    assert data["approved_at"] is None
    assert data["executed_at"] is None

    # Verify CREATE audit log entry exists
    audit_resp = client.get(f"/api/v1/campaigns/{data['campaign_id']}/audit?merchant_id=demo-merchant-001")
    assert audit_resp.status_code == status.HTTP_200_OK
    audit_data = audit_resp.json()
    assert audit_data["total_events"] >= 1
    create_event = audit_data["events"][0]
    assert create_event["action"] == CampaignAuditAction.CREATE.value
    assert create_event["previous_status"] is None
    assert create_event["new_status"] == CampaignStatus.PENDING_APPROVAL.value


def test_campaign_creation_with_percentage_discount(client: TestClient):
    """Verify creation with percentage discount offer type and auto-simulation."""
    payload = {
        "merchant_id": "demo-merchant-001",
        "name": "VIP 10% Discount Campaign",
        "target_segment": "VIP",
        "offer_type": "percentage_discount",
        "discount_percent": 10.0,
        "minimum_transaction_amount": 200.0,
    }
    response = client.post("/api/v1/campaigns", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["status"] == CampaignStatus.PENDING_APPROVAL.value
    assert data["discount_percent"] == 10.0
    # Auto-computed projections from Module 5 should be finite numbers
    assert data["projected_revenue"] is not None
    assert data["projected_transactions"] is not None
    assert data["estimated_roi"] is not None


# -----------------------------------------------------------------------------
# 2. Approval Workflow Tests
# -----------------------------------------------------------------------------

def test_campaign_approval_succeeds_and_does_not_execute(client: TestClient):
    """Approval must transition status to APPROVED and record audit, but NOT execute."""
    # 1. Create campaign
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Approve Me Campaign",
            "target_segment": "Loyal",
            "offer_type": "fixed_cashback",
            "cashback_amount": 30.0,
        },
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    cid = create_resp.json()["campaign_id"]

    # 2. Approve campaign
    approve_resp = client.post(
        f"/api/v1/campaigns/{cid}/approve",
        json={"merchant_id": "demo-merchant-001", "actor": "owner-alice"},
    )
    assert approve_resp.status_code == status.HTTP_200_OK
    approved_data = approve_resp.json()

    assert approved_data["status"] == CampaignStatus.APPROVED.value
    assert approved_data["approved_at"] is not None
    assert approved_data["approved_by"] == "owner-alice"
    # Safety: execution must NOT have occurred
    assert approved_data["executed_at"] is None
    assert approved_data["simulated_revenue"] is None

    # 3. Check audit trail
    audit_resp = client.get(f"/api/v1/campaigns/{cid}/audit?merchant_id=demo-merchant-001")
    events = audit_resp.json()["events"]
    actions = [e["action"] for e in events]
    assert CampaignAuditAction.CREATE.value in actions
    assert CampaignAuditAction.APPROVE.value in actions


def test_repeated_approval_rejected_with_conflict_409(client: TestClient):
    """Repeated approval must return HTTP 409 Conflict."""
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Double Approve Campaign",
            "target_segment": "Regular",
            "offer_type": "fixed_cashback",
            "cashback_amount": 25.0,
        },
    )
    cid = create_resp.json()["campaign_id"]

    # First approval -> 200
    res1 = client.post(f"/api/v1/campaigns/{cid}/approve?merchant_id=demo-merchant-001")
    assert res1.status_code == status.HTTP_200_OK

    # Second approval -> 409 Conflict
    res2 = client.post(f"/api/v1/campaigns/{cid}/approve?merchant_id=demo-merchant-001")
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "already been approved" in get_err(res2).lower()



# -----------------------------------------------------------------------------
# 3. Rejection Workflow Tests
# -----------------------------------------------------------------------------

def test_campaign_rejection_succeeds_with_reason(client: TestClient):
    """Rejection sets status to REJECTED, records reason, and writes audit event."""
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Budget Too High Campaign",
            "target_segment": "All Customers",
            "offer_type": "percentage_discount",
            "discount_percent": 30.0,
        },
    )
    cid = create_resp.json()["campaign_id"]

    # Reject
    reject_resp = client.post(
        f"/api/v1/campaigns/{cid}/reject",
        json={
            "merchant_id": "demo-merchant-001",
            "reason": "Discount is too high for current margins",
            "actor": "manager-bob",
        },
    )
    assert reject_resp.status_code == status.HTTP_200_OK
    data = reject_resp.json()
    assert data["status"] == CampaignStatus.REJECTED.value
    assert data["rejected_at"] is not None
    assert data["rejection_reason"] == "Discount is too high for current margins"

    # Repeated rejection -> 409
    dup_resp = client.post(
        f"/api/v1/campaigns/{cid}/reject?merchant_id=demo-merchant-001",
        json={"reason": "Repeat reject"},
    )
    assert dup_resp.status_code == status.HTTP_409_CONFLICT


def test_cannot_approve_rejected_campaign(client: TestClient):
    """Cannot approve a campaign that was previously rejected (HTTP 409)."""
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Rejected First Campaign",
            "target_segment": "Regular",
            "offer_type": "fixed_cashback",
            "cashback_amount": 20.0,
        },
    )
    cid = create_resp.json()["campaign_id"]

    client.post(f"/api/v1/campaigns/{cid}/reject?merchant_id=demo-merchant-001")

    # Try to approve
    app_resp = client.post(f"/api/v1/campaigns/{cid}/approve?merchant_id=demo-merchant-001")
    assert app_resp.status_code == status.HTTP_409_CONFLICT
    assert "rejected" in get_err(app_resp).lower()


# -----------------------------------------------------------------------------
# 4. Execution Safety & Simulation Tests
# -----------------------------------------------------------------------------

def test_pending_campaign_cannot_execute(client: TestClient):
    """Safety boundary: campaigns in PENDING_APPROVAL cannot execute (HTTP 409)."""
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Premature Execution Test",
            "target_segment": "Loyal",
            "offer_type": "fixed_cashback",
            "cashback_amount": 40.0,
        },
    )
    cid = create_resp.json()["campaign_id"]

    exec_resp = client.post(f"/api/v1/campaigns/{cid}/execute?merchant_id=demo-merchant-001")
    assert exec_resp.status_code == status.HTTP_409_CONFLICT
    assert "pending approval" in get_err(exec_resp).lower()



def test_rejected_campaign_cannot_execute(client: TestClient):
    """Rejected campaigns cannot execute (HTTP 409)."""
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Reject Then Execute Test",
            "target_segment": "New",
            "offer_type": "fixed_cashback",
            "cashback_amount": 15.0,
        },
    )
    cid = create_resp.json()["campaign_id"]

    client.post(f"/api/v1/campaigns/{cid}/reject?merchant_id=demo-merchant-001")

    exec_resp = client.post(f"/api/v1/campaigns/{cid}/execute?merchant_id=demo-merchant-001")
    assert exec_resp.status_code == status.HTTP_409_CONFLICT


def test_approved_campaign_executes_safely_with_deterministic_simulation(client: TestClient):
    """
    Approved campaign executes cleanly through:
      APPROVED -> VALIDATING -> EXECUTING -> COMPLETED
    Produces synthetic demo results and full audit trail.
    """
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Full Execution Test",
            "target_segment": "At-Risk",
            "offer_type": "fixed_cashback",
            "cashback_amount": 50.0,
            "minimum_transaction_amount": 300.0,
            "target_days": "weekend",
        },
    )
    cid = create_resp.json()["campaign_id"]

    # Approve
    client.post(f"/api/v1/campaigns/{cid}/approve?merchant_id=demo-merchant-001")

    # Execute
    exec_resp = client.post(
        f"/api/v1/campaigns/{cid}/execute",
        json={"merchant_id": "demo-merchant-001", "actor": "operator-dan"},
    )
    assert exec_resp.status_code == status.HTTP_200_OK
    res = exec_resp.json()

    assert res["status"] == CampaignStatus.COMPLETED.value
    assert res["is_demo_result"] is True
    assert res["data_type"] == "SYNTHETIC_DEMO"
    assert "No real Paytm campaign APIs were called" in res["disclaimer"]
    assert res["simulated_transactions"] > 0
    assert res["simulated_revenue"] > 0
    assert res["simulated_cost"] >= 0
    assert res["simulated_net_impact"] is not None
    assert res["simulated_roi"] is not None
    assert res["executed_at"] is not None

    # Verify audit lifecycle events: CREATE, APPROVE, VALIDATE, EXECUTE, COMPLETE
    audit_resp = client.get(f"/api/v1/campaigns/{cid}/audit?merchant_id=demo-merchant-001")
    events = audit_resp.json()["events"]
    actions = [e["action"] for e in events]
    assert actions == [
        CampaignAuditAction.CREATE.value,
        CampaignAuditAction.APPROVE.value,
        CampaignAuditAction.VALIDATE.value,
        CampaignAuditAction.EXECUTE.value,
        CampaignAuditAction.COMPLETE.value,
    ]


def test_completed_campaign_cannot_execute_twice(client: TestClient):
    """Completed campaign cannot be re-executed (HTTP 409)."""
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Single Execution Only",
            "target_segment": "VIP",
            "offer_type": "percentage_discount",
            "discount_percent": 15.0,
        },
    )
    cid = create_resp.json()["campaign_id"]

    client.post(f"/api/v1/campaigns/{cid}/approve?merchant_id=demo-merchant-001")
    client.post(f"/api/v1/campaigns/{cid}/execute?merchant_id=demo-merchant-001")

    # Second execution attempt
    exec2 = client.post(f"/api/v1/campaigns/{cid}/execute?merchant_id=demo-merchant-001")
    assert exec2.status_code == status.HTTP_409_CONFLICT
    assert "already been executed" in get_err(exec2).lower()


# -----------------------------------------------------------------------------
# 5. Result & Query Endpoints Tests
# -----------------------------------------------------------------------------

def test_campaign_result_endpoint_before_and_after_execution(client: TestClient):
    """Result endpoint returns 400 before execution, and valid result after."""
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Result Endpoint Test",
            "target_segment": "Regular",
            "offer_type": "fixed_cashback",
            "cashback_amount": 20.0,
        },
    )
    cid = create_resp.json()["campaign_id"]

    # Before execution -> 400
    res_before = client.get(f"/api/v1/campaigns/{cid}/result?merchant_id=demo-merchant-001")
    assert res_before.status_code == status.HTTP_400_BAD_REQUEST
    assert "has not executed yet" in get_err(res_before).lower()


    # Approve & execute
    client.post(f"/api/v1/campaigns/{cid}/approve?merchant_id=demo-merchant-001")
    client.post(f"/api/v1/campaigns/{cid}/execute?merchant_id=demo-merchant-001")

    # After execution -> 200
    res_after = client.get(f"/api/v1/campaigns/{cid}/result?merchant_id=demo-merchant-001")
    assert res_after.status_code == status.HTTP_200_OK
    assert res_after.json()["status"] == CampaignStatus.COMPLETED.value
    assert res_after.json()["is_demo_result"] is True


def test_campaign_detail_and_list_endpoints(client: TestClient):
    """Verify GET /campaigns and GET /campaigns/{id} endpoints with status filtering."""
    # Ensure at least one campaign exists
    client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "List Fixture Campaign",
            "target_segment": "Regular",
            "offer_type": "fixed_cashback",
            "cashback_amount": 10.0,
        },
    )

    # List campaigns
    list_resp = client.get("/api/v1/campaigns?merchant_id=demo-merchant-001&limit=10")
    assert list_resp.status_code == status.HTTP_200_OK
    data = list_resp.json()
    assert data["merchant_id"] == "demo-merchant-001"
    assert "total_count" in data
    assert len(data["campaigns"]) > 0

    first_id = data["campaigns"][0]["campaign_id"]

    # Detail
    det_resp = client.get(f"/api/v1/campaigns/{first_id}?merchant_id=demo-merchant-001")
    assert det_resp.status_code == status.HTTP_200_OK
    assert det_resp.json()["campaign_id"] == first_id

    # Filter by status
    pend_resp = client.get(
        f"/api/v1/campaigns?merchant_id=demo-merchant-001&status={CampaignStatus.PENDING_APPROVAL.value}"
    )
    assert pend_resp.status_code == status.HTTP_200_OK
    for c in pend_resp.json()["campaigns"]:
        assert c["status"] == CampaignStatus.PENDING_APPROVAL.value



# -----------------------------------------------------------------------------
# 6. Merchant Isolation Tests (Mandatory)
# -----------------------------------------------------------------------------

def test_merchant_isolation_preventing_cross_merchant_access(client: TestClient):
    """
    Merchant A's campaigns cannot be viewed, approved, rejected, executed,
    or audited by Merchant B (must return HTTP 404).
    """
    # Create campaign belonging to merchant A
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Secret Merchant A Campaign",
            "target_segment": "VIP",
            "offer_type": "fixed_cashback",
            "cashback_amount": 50.0,
        },
    )
    cid = create_resp.json()["campaign_id"]

    other_merchant = "merchant-competitor-999"

    # Merchant B tries to GET campaign detail -> 404
    r_get = client.get(f"/api/v1/campaigns/{cid}?merchant_id={other_merchant}")
    assert r_get.status_code == status.HTTP_404_NOT_FOUND

    # Merchant B tries to approve -> 404
    r_app = client.post(f"/api/v1/campaigns/{cid}/approve?merchant_id={other_merchant}")
    assert r_app.status_code == status.HTTP_404_NOT_FOUND

    # Merchant B tries to reject -> 404
    r_rej = client.post(f"/api/v1/campaigns/{cid}/reject?merchant_id={other_merchant}")
    assert r_rej.status_code == status.HTTP_404_NOT_FOUND

    # Merchant B tries to execute -> 404
    r_exe = client.post(f"/api/v1/campaigns/{cid}/execute?merchant_id={other_merchant}")
    assert r_exe.status_code == status.HTTP_404_NOT_FOUND

    # Merchant B tries to view audit -> 404
    r_aud = client.get(f"/api/v1/campaigns/{cid}/audit?merchant_id={other_merchant}")
    assert r_aud.status_code == status.HTTP_404_NOT_FOUND

    # Merchant B listing does not contain Merchant A's campaign
    r_list = client.get(f"/api/v1/campaigns?merchant_id={other_merchant}")
    assert r_list.status_code == status.HTTP_200_OK
    b_ids = [c["campaign_id"] for c in r_list.json()["campaigns"]]
    assert cid not in b_ids


# -----------------------------------------------------------------------------
# 7. Validation & Financial Correctness Tests
# -----------------------------------------------------------------------------

def test_invalid_campaign_parameters_rejected(client: TestClient):
    """Verifies domain validation for invalid offers, dates, and segments."""
    # Invalid segment
    res1 = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Bad Segment",
            "target_segment": "NonExistentSegment",
            "offer_type": "fixed_cashback",
            "cashback_amount": 20.0,
        },
    )
    assert res1.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid target segment" in get_err(res1)

    # Invalid discount percent (> 100)
    res2 = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Excessive Discount",
            "target_segment": "Loyal",
            "offer_type": "percentage_discount",
            "discount_percent": 150.0,
        },
    )
    assert res2.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Negative minimum transaction
    res3 = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Negative Min Txn",
            "target_segment": "Loyal",
            "offer_type": "fixed_cashback",
            "cashback_amount": 10.0,
            "minimum_transaction_amount": -50.0,
        },
    )
    assert res3.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Inverted date range
    now = datetime.now(timezone.utc)
    res4 = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Inverted Dates",
            "target_segment": "Loyal",
            "offer_type": "fixed_cashback",
            "cashback_amount": 10.0,
            "start_date": (now + timedelta(days=10)).isoformat(),
            "end_date": (now + timedelta(days=2)).isoformat(),
        },
    )
    assert res4.status_code == status.HTTP_400_BAD_REQUEST
    assert "cannot be before start date" in get_err(res4).lower()


def test_source_recommendation_merchant_mismatch_rejected(client: TestClient):
    """Referencing a recommendation belonging to another merchant must be rejected."""
    res = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Mismatch Rec Campaign",
            "target_segment": "All Customers",
            "offer_type": "fixed_cashback",
            "cashback_amount": 25.0,
            "source_recommendation_id": "rec-other999-vip-retention",
        },
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "does not belong" in get_err(res).lower()



# -----------------------------------------------------------------------------
# 8. Database Safety & Non-Interference Tests
# -----------------------------------------------------------------------------

def test_campaign_execution_does_not_mutate_transaction_records(
    client: TestClient, db_session: Session
):
    """
    Section 22: Simulated execution must NOT modify the main transaction table
    or create fabricated historical transactions.
    """
    # Count initial transactions
    initial_tx_count = db_session.scalar(select(func.count()).select_from(Transaction))

    # Create, approve, and execute a campaign
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Safety Isolation Check",
            "target_segment": "Regular",
            "offer_type": "fixed_cashback",
            "cashback_amount": 35.0,
        },
    )
    cid = create_resp.json()["campaign_id"]
    client.post(f"/api/v1/campaigns/{cid}/approve?merchant_id=demo-merchant-001")
    client.post(f"/api/v1/campaigns/{cid}/execute?merchant_id=demo-merchant-001")

    # Verify transaction count is exactly identical
    post_tx_count = db_session.scalar(select(func.count()).select_from(Transaction))
    assert post_tx_count == initial_tx_count


# -----------------------------------------------------------------------------
# 9. Cancellation & Route Alias Tests
# -----------------------------------------------------------------------------

def test_campaign_cancellation_workflow(client: TestClient):
    """Campaign can be cancelled from PENDING_APPROVAL or APPROVED state."""
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Cancel Me Campaign",
            "target_segment": "Regular",
            "offer_type": "fixed_cashback",
            "cashback_amount": 10.0,
        },
    )
    cid = create_resp.json()["campaign_id"]

    cancel_resp = client.post(
        f"/api/v1/campaigns/{cid}/cancel?merchant_id=demo-merchant-001&reason=ChangedMind"
    )
    assert cancel_resp.status_code == status.HTTP_200_OK
    assert cancel_resp.json()["status"] == CampaignStatus.CANCELLED.value


def test_unversioned_campaign_route_aliases(client: TestClient):
    """Verify that unversioned /api/campaigns alias behaves identically to /api/v1/campaigns."""
    res_list = client.get("/api/campaigns?merchant_id=demo-merchant-001&limit=5")
    assert res_list.status_code == status.HTTP_200_OK
    assert res_list.json()["merchant_id"] == "demo-merchant-001"


# -----------------------------------------------------------------------------
# 10. Additional Edge Cases & State Transition Tests
# -----------------------------------------------------------------------------

def test_source_simulation_merchant_mismatch_rejected(client: TestClient):
    """Referencing a simulation belonging to another merchant must be rejected."""
    res = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Mismatch Sim Campaign",
            "target_segment": "All Customers",
            "offer_type": "fixed_cashback",
            "cashback_amount": 25.0,
            "source_simulation_id": "sim-merchant-other-scenario-01",
        },
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "does not belong" in get_err(res).lower()


def test_invalid_state_transitions_comprehensive(client: TestClient):
    """
    Verify complete state transition restrictions:
      - Cannot reject an APPROVED campaign
      - Cannot approve a COMPLETED campaign
      - Cannot reject a COMPLETED campaign
      - Cannot cancel a COMPLETED campaign
    """
    create_resp = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "State Matrix Test",
            "target_segment": "Regular",
            "offer_type": "fixed_cashback",
            "cashback_amount": 15.0,
        },
    )
    cid = create_resp.json()["campaign_id"]

    # 1. Approve
    client.post(f"/api/v1/campaigns/{cid}/approve?merchant_id=demo-merchant-001")

    # 2. Cannot reject an approved campaign -> 409
    rej_resp = client.post(f"/api/v1/campaigns/{cid}/reject?merchant_id=demo-merchant-001")
    assert rej_resp.status_code == status.HTTP_409_CONFLICT
    assert "approved" in get_err(rej_resp).lower()

    # 3. Execute to completion
    client.post(f"/api/v1/campaigns/{cid}/execute?merchant_id=demo-merchant-001")

    # 4. Cannot approve a completed campaign -> 409
    app_after = client.post(f"/api/v1/campaigns/{cid}/approve?merchant_id=demo-merchant-001")
    assert app_after.status_code == status.HTTP_409_CONFLICT

    # 5. Cannot reject a completed campaign -> 409
    rej_after = client.post(f"/api/v1/campaigns/{cid}/reject?merchant_id=demo-merchant-001")
    assert rej_after.status_code == status.HTTP_409_CONFLICT

    # 6. Cannot cancel a completed campaign -> 409
    canc_after = client.post(f"/api/v1/campaigns/{cid}/cancel?merchant_id=demo-merchant-001")
    assert canc_after.status_code == status.HTTP_409_CONFLICT


def test_zero_and_edge_financial_values(client: TestClient):
    """Verifies edge case handling for 0 minimum transaction and valid small cashback."""
    res = client.post(
        "/api/v1/campaigns",
        json={
            "merchant_id": "demo-merchant-001",
            "name": "Zero Min Transaction Campaign",
            "target_segment": "Regular",
            "offer_type": "fixed_cashback",
            "cashback_amount": 1.0,
            "minimum_transaction_amount": 0.0,
        },
    )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["minimum_transaction_amount"] == 0.0
    assert data["cashback_amount"] == 1.0


def test_nan_infinity_protection(client: TestClient, db_session: Session):
    """NaN or Inf values in projections or parameters are rejected cleanly."""
    from app.services.campaign_service import CampaignService
    from fastapi import HTTPException

    service = CampaignService(db_session)
    with pytest.raises(HTTPException):
        service._assert_finite_numbers(test_inf=float("inf"))
    with pytest.raises(HTTPException):
        service._assert_finite_numbers(test_nan=float("nan"))

    # Also test HTTP endpoint with raw non-compliant string representation
    res = client.post(
        "/api/v1/campaigns",
        content=b'{"merchant_id": "demo-merchant-001", "name": "Inf Campaign", "target_segment": "Regular", "offer_type": "fixed_cashback", "cashback_amount": "Infinity"}',
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY)

