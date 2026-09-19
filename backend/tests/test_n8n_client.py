"""
Tests for n8n webhook client (app/services/n8n_client.py) and
campaign n8n-callback endpoint (POST /api/v1/campaigns/{id}/n8n-callback).

Covers:
  1. n8n webhook call success
  2. n8n unavailable fallback
  3. Approval gate: PENDING_APPROVAL MUST NOT trigger n8n
  4. APPROVED campaign CAN trigger n8n
  5. Callback endpoint — valid/invalid cases
  6. Callback merchant isolation
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Generator

import httpx

from app.services.n8n_client import N8nClient, get_n8n_client, N8nExecutionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_n8n_client(webhook_url: str = "https://n8n.example.com/webhook/test") -> N8nClient:
    with patch("app.services.n8n_client.get_settings") as mock_settings:
        s = MagicMock()
        s.n8n_webhook_url = webhook_url
        s.n8n_webhook_secret = ""
        mock_settings.return_value = s
        client = N8nClient()
    return client


def _make_unconfigured_n8n_client() -> N8nClient:
    return _make_n8n_client(webhook_url="")


def _trigger_kwargs(campaign_status: str = "APPROVED") -> dict:
    return dict(
        campaign_id="test-campaign-001",
        merchant_id="test-merchant-001",
        campaign_status=campaign_status,
        offer_type="fixed_cashback",
        target_segment="Inactive",
        cashback_amount=50.0,
        discount_percent=None,
        minimum_transaction_amount=0.0,
        target_count=120,
        campaign_name="Re-engagement Drive",
        campaign_description="Win back inactive customers",
        target_days="weekend",
        target_hours=None,
    )


# ---------------------------------------------------------------------------
# 1. N8n webhook call success
# ---------------------------------------------------------------------------

class TestN8nWebhookSuccess:

    def test_trigger_returns_success_on_200(self):
        client = _make_n8n_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "completed",
            "campaign_id": "test-campaign-001",
            "merchant_id": "test-merchant-001",
            "targeted": 120,
            "delivered": 115,
            "failed": 5,
            "execution_mode": "simulated_demo",
            "message": "Campaign delivered via n8n.",
        }

        with patch("app.services.n8n_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
            result = client.trigger_campaign(**_trigger_kwargs())

        assert result.success is True
        assert result.targeted == 120
        assert result.delivered == 115
        assert result.failed == 5
        assert result.execution_mode == "simulated_demo"

    def test_trigger_returns_success_on_202(self):
        client = _make_n8n_client()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {}

        with patch("app.services.n8n_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
            result = client.trigger_campaign(**_trigger_kwargs())

        assert result.success is True

    def test_result_contains_campaign_and_merchant_ids(self):
        client = _make_n8n_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "done"}

        with patch("app.services.n8n_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
            result = client.trigger_campaign(**_trigger_kwargs())

        assert result.campaign_id == "test-campaign-001"
        assert result.merchant_id == "test-merchant-001"


# ---------------------------------------------------------------------------
# 2. n8n unavailable fallback
# ---------------------------------------------------------------------------

class TestN8nUnavailableFallback:

    def test_trigger_returns_failure_on_non_2xx(self):
        client = _make_n8n_client()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("app.services.n8n_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
            result = client.trigger_campaign(**_trigger_kwargs())

        assert result.success is False
        assert "500" in (result.error or "")

    def test_trigger_returns_failure_on_timeout(self):
        client = _make_n8n_client()

        with patch("app.services.n8n_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException("timeout")
            result = client.trigger_campaign(**_trigger_kwargs())

        assert result.success is False
        assert result.error == "WEBHOOK_TIMEOUT"

    def test_trigger_returns_failure_on_connection_error(self):
        client = _make_n8n_client()

        with patch("app.services.n8n_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.side_effect = Exception("connection refused")
            result = client.trigger_campaign(**_trigger_kwargs())

        assert result.success is False
        assert result.error is not None

    def test_trigger_returns_skipped_when_not_configured(self):
        client = _make_unconfigured_n8n_client()
        result = client.trigger_campaign(**_trigger_kwargs())

        assert result.success is False
        assert result.error == "N8N_NOT_CONFIGURED"

    def test_n8n_failure_never_raises_exception(self):
        """n8n failures must be gracefully handled, never raise to callers."""
        client = _make_n8n_client()
        with patch("app.services.n8n_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.side_effect = RuntimeError("fatal")
            try:
                result = client.trigger_campaign(**_trigger_kwargs())
                assert result.success is False
            except Exception:
                pytest.fail("N8nClient.trigger_campaign() raised an unexpected exception")


# ---------------------------------------------------------------------------
# 3. Approval gate — PENDING_APPROVAL MUST NOT trigger n8n
# ---------------------------------------------------------------------------

class TestN8nApprovalGate:

    def test_pending_approval_campaign_is_blocked(self):
        client = _make_n8n_client()
        result = client.trigger_campaign(**_trigger_kwargs(campaign_status="PENDING_APPROVAL"))

        assert result.success is False
        assert result.status == "blocked"
        assert result.error == "APPROVAL_GATE_VIOLATION"

    def test_rejected_campaign_is_blocked(self):
        client = _make_n8n_client()
        result = client.trigger_campaign(**_trigger_kwargs(campaign_status="REJECTED"))

        assert result.success is False
        assert result.error == "APPROVAL_GATE_VIOLATION"

    def test_draft_campaign_is_blocked(self):
        client = _make_n8n_client()
        result = client.trigger_campaign(**_trigger_kwargs(campaign_status="DRAFT"))

        assert result.success is False
        assert result.error == "APPROVAL_GATE_VIOLATION"

    def test_blocked_campaign_does_not_call_webhook(self):
        """Blocked campaigns must never make HTTP calls to n8n."""
        client = _make_n8n_client()

        with patch("app.services.n8n_client.httpx.Client") as mock_httpx:
            client.trigger_campaign(**_trigger_kwargs(campaign_status="PENDING_APPROVAL"))
            mock_httpx.return_value.__enter__.return_value.post.assert_not_called()


# ---------------------------------------------------------------------------
# 4. APPROVED campaign CAN trigger n8n
# ---------------------------------------------------------------------------

class TestN8nApprovedTrigger:

    def test_approved_campaign_calls_webhook(self):
        client = _make_n8n_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "completed", "targeted": 50, "delivered": 48, "failed": 2}

        with patch("app.services.n8n_client.httpx.Client") as mock_httpx:
            post_mock = mock_httpx.return_value.__enter__.return_value.post
            post_mock.return_value = mock_response
            result = client.trigger_campaign(**_trigger_kwargs(campaign_status="APPROVED"))

        assert result.success is True
        assert mock_httpx.return_value.__enter__.return_value.post.called


# ---------------------------------------------------------------------------
# 5 & 6. n8n-callback endpoint — via FastAPI TestClient
# ---------------------------------------------------------------------------

class TestN8nCallbackEndpoint:

    def _create_and_approve_campaign(self, client, merchant_id: str) -> str:
        """Helper: create a campaign, approve, and execute it. Returns campaign_id."""
        # Create
        create_resp = client.post(
            "/api/v1/campaigns",
            json={
                "merchant_id": merchant_id,
                "name": "n8n Callback Test Campaign",
                "target_segment": "Inactive",
                "offer_type": "fixed_cashback",
                "cashback_amount": 30.0,
            },
            params={"merchant_id": merchant_id},
        )
        assert create_resp.status_code == 201, create_resp.text
        campaign_id = create_resp.json()["campaign_id"]

        # Approve
        approve_resp = client.post(
            f"/api/v1/campaigns/{campaign_id}/approve",
            params={"merchant_id": merchant_id},
        )
        assert approve_resp.status_code == 200, approve_resp.text

        # Execute (n8n client will be skipped/mocked in test env)
        execute_resp = client.post(
            f"/api/v1/campaigns/{campaign_id}/execute",
            params={"merchant_id": merchant_id},
        )
        assert execute_resp.status_code == 200, execute_resp.text

        return campaign_id

    def test_callback_accepted_for_completed_campaign(self, client):
        merchant_id = "test-merchant-callback-001"
        campaign_id = self._create_and_approve_campaign(client, merchant_id)

        resp = client.post(
            f"/api/v1/campaigns/{campaign_id}/n8n-callback",
            json={
                "campaign_id": campaign_id,
                "merchant_id": merchant_id,
                "status": "completed",
                "targeted": 100,
                "delivered": 95,
                "failed": 5,
                "execution_mode": "simulated_demo",
                "message": "All messages dispatched.",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["accepted"] is True
        assert data["campaign_id"] == campaign_id

    def test_callback_rejected_for_nonexistent_campaign(self, client):
        resp = client.post(
            "/api/v1/campaigns/nonexistent-campaign-xyz/n8n-callback",
            json={
                "campaign_id": "nonexistent-campaign-xyz",
                "merchant_id": "test-merchant-callback-001",
                "status": "completed",
            },
        )
        assert resp.status_code == 404

    def test_callback_merchant_isolation(self, client):
        """Callback with wrong merchant_id must be rejected (404)."""
        merchant_id = "test-merchant-callback-002"
        campaign_id = self._create_and_approve_campaign(client, merchant_id)

        # Send callback with WRONG merchant_id
        resp = client.post(
            f"/api/v1/campaigns/{campaign_id}/n8n-callback",
            json={
                "campaign_id": campaign_id,
                "merchant_id": "wrong-merchant-id",
                "status": "completed",
            },
        )
        # Campaign not found under wrong merchant = 404
        assert resp.status_code == 404

    def test_callback_rejected_for_pending_campaign(self, client):
        """n8n callback on PENDING_APPROVAL campaign must be 409."""
        merchant_id = "test-merchant-callback-003"

        # Only create, do NOT approve or execute
        create_resp = client.post(
            "/api/v1/campaigns",
            json={
                "merchant_id": merchant_id,
                "name": "Pending Only Campaign",
                "target_segment": "At-Risk",
                "offer_type": "fixed_cashback",
                "cashback_amount": 20.0,
            },
            params={"merchant_id": merchant_id},
        )
        assert create_resp.status_code == 201
        campaign_id = create_resp.json()["campaign_id"]

        resp = client.post(
            f"/api/v1/campaigns/{campaign_id}/n8n-callback",
            json={
                "campaign_id": campaign_id,
                "merchant_id": merchant_id,
                "status": "completed",
            },
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 7. Singleton
# ---------------------------------------------------------------------------

def test_get_n8n_client_returns_same_instance():
    import app.services.n8n_client as mod
    mod._n8n_client = None
    c1 = get_n8n_client()
    c2 = get_n8n_client()
    assert c1 is c2
