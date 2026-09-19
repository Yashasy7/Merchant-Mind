"""
Tests for Cognee Cloud memory client (app/ai/cognee_client.py).
Covers: remember, recall, unavailable fallback, merchant isolation, extract_context_text.
All external HTTP calls are mocked — no real Cognee credentials required.
"""

import pytest
from unittest.mock import patch, MagicMock

import httpx

from app.ai.cognee_client import CogneeClient, get_cognee_client, _merchant_dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_configured_client(**overrides) -> CogneeClient:
    """Build a CogneeClient that reports as enabled with test credentials."""
    with patch("app.ai.cognee_client.get_settings") as mock_settings:
        s = MagicMock()
        s.cognee_api_key = overrides.get("api_key", "test-api-key-abc123")
        s.cognee_base_url = overrides.get("base_url", "https://test-tenant.aws.cognee.ai")
        s.cognee_tenant_id = overrides.get("tenant_id", "test-tenant-uuid")
        s.cognee_user_id = overrides.get("user_id", "test-user-uuid")
        mock_settings.return_value = s
        client = CogneeClient()
    return client


def _make_unconfigured_client() -> CogneeClient:
    """Build a CogneeClient with empty credentials (disabled)."""
    return _make_configured_client(api_key="", base_url="https://your-tenant.aws.cognee.ai")


# ---------------------------------------------------------------------------
# 1. Merchant dataset isolation
# ---------------------------------------------------------------------------

class TestMerchantDatasetIsolation:

    def test_different_merchants_get_different_datasets(self):
        ds1 = _merchant_dataset("merchant-001")
        ds2 = _merchant_dataset("merchant-002")
        assert ds1 != ds2

    def test_same_merchant_always_same_dataset(self):
        assert _merchant_dataset("merchant-001") == _merchant_dataset("merchant-001")

    def test_dataset_includes_prefix(self):
        ds = _merchant_dataset("merchant-001")
        assert ds.startswith("merchantmind_merchant_")

    def test_dataset_normalises_hyphens(self):
        ds = _merchant_dataset("demo-merchant-001")
        assert "-" not in ds


# ---------------------------------------------------------------------------
# 2. CogneeClient — remember
# ---------------------------------------------------------------------------

class TestCogneeRemember:

    def test_remember_returns_true_on_200(self):
        client = _make_configured_client()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("app.ai.cognee_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
            result = client.remember("merchant-001", "Sales dropped 16% this week.")

        assert result is True

    def test_remember_returns_true_on_202(self):
        client = _make_configured_client()
        mock_response = MagicMock()
        mock_response.status_code = 202

        with patch("app.ai.cognee_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
            result = client.remember("merchant-001", "Test context.")

        assert result is True

    def test_remember_returns_false_on_non_2xx(self):
        client = _make_configured_client()
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("app.ai.cognee_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
            result = client.remember("merchant-001", "Test context.")

        assert result is False

    def test_remember_returns_false_on_timeout(self):
        client = _make_configured_client()

        with patch("app.ai.cognee_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException("timeout")
            result = client.remember("merchant-001", "Test context.")

        assert result is False  # Graceful degradation

    def test_remember_returns_false_on_network_error(self):
        client = _make_configured_client()

        with patch("app.ai.cognee_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.side_effect = Exception("connection refused")
            result = client.remember("merchant-001", "Test context.")

        assert result is False

    def test_remember_skips_empty_content(self):
        client = _make_configured_client()
        result = client.remember("merchant-001", "")
        assert result is False

    def test_remember_skips_whitespace_only_content(self):
        client = _make_configured_client()
        result = client.remember("merchant-001", "   ")
        assert result is False


# ---------------------------------------------------------------------------
# 3. CogneeClient — recall
# ---------------------------------------------------------------------------

class TestCogneeRecall:

    def test_recall_returns_list_on_200_list_response(self):
        client = _make_configured_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"text": "Merchant had 16% drop."}]

        with patch("app.ai.cognee_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
            results = client.recall("merchant-001", "sales trend")

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["text"] == "Merchant had 16% drop."

    def test_recall_returns_list_on_200_dict_response(self):
        client = _make_configured_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"text": "Context A"}, {"text": "Context B"}]}

        with patch("app.ai.cognee_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
            results = client.recall("merchant-001", "any query")

        assert len(results) == 2

    def test_recall_returns_empty_on_non_2xx(self):
        client = _make_configured_client()
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("app.ai.cognee_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.return_value = mock_response
            results = client.recall("merchant-001", "sales trend")

        assert results == []

    def test_recall_returns_empty_on_timeout(self):
        client = _make_configured_client()

        with patch("app.ai.cognee_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException("timeout")
            results = client.recall("merchant-001", "sales trend")

        assert results == []

    def test_recall_returns_empty_on_exception(self):
        client = _make_configured_client()

        with patch("app.ai.cognee_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.side_effect = RuntimeError("boom")
            results = client.recall("merchant-001", "query")

        assert results == []

    def test_recall_skips_empty_query(self):
        client = _make_configured_client()
        results = client.recall("merchant-001", "")
        assert results == []


# ---------------------------------------------------------------------------
# 4. Cognee unavailable fallback
# ---------------------------------------------------------------------------

class TestCogneeUnavailableFallback:

    def test_remember_returns_false_when_disabled(self):
        client = _make_unconfigured_client()
        assert client.remember("merchant-001", "Some context.") is False

    def test_recall_returns_empty_when_disabled(self):
        client = _make_unconfigured_client()
        assert client.recall("merchant-001", "any query") == []

    def test_client_disabled_when_api_key_empty(self):
        client = _make_unconfigured_client()
        assert client._enabled is False

    def test_client_disabled_when_placeholder_url(self):
        client = _make_configured_client(base_url="https://your-tenant.aws.cognee.ai")
        assert client._enabled is False

    def test_cognee_failure_does_not_raise(self):
        """Cognee failure must never propagate exceptions to callers."""
        client = _make_configured_client()
        with patch("app.ai.cognee_client.httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value.post.side_effect = RuntimeError("fatal error")
            # Neither of these should raise
            result_r = client.remember("merchant-001", "context")
            result_rc = client.recall("merchant-001", "query")

        assert result_r is False
        assert result_rc == []


# ---------------------------------------------------------------------------
# 5. extract_context_text
# ---------------------------------------------------------------------------

class TestExtractContextText:

    def test_empty_results_returns_empty_string(self):
        client = _make_configured_client()
        assert client.extract_context_text([]) == ""

    def test_extracts_text_field(self):
        client = _make_configured_client()
        result = client.extract_context_text([{"text": "Merchant context"}])
        assert "Merchant context" in result

    def test_extracts_content_field_fallback(self):
        client = _make_configured_client()
        result = client.extract_context_text([{"content": "Some content"}])
        assert "Some content" in result

    def test_handles_string_items(self):
        client = _make_configured_client()
        result = client.extract_context_text(["plain text item"])
        assert "plain text item" in result

    def test_joins_multiple_items(self):
        client = _make_configured_client()
        result = client.extract_context_text([{"text": "Item A"}, {"text": "Item B"}])
        assert "Item A" in result
        assert "Item B" in result


# ---------------------------------------------------------------------------
# 6. Singleton
# ---------------------------------------------------------------------------

def test_get_cognee_client_returns_same_instance():
    """Module-level singleton should return the same object on repeated calls."""
    import app.ai.cognee_client as mod
    mod._cognee_client = None  # Reset for clean test
    c1 = get_cognee_client()
    c2 = get_cognee_client()
    assert c1 is c2
