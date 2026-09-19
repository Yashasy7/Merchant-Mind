"""
Cognee Cloud Memory Client for MerchantMind.

Provides merchant-specific long-term AI memory using the Cognee Cloud REST API:
  - POST /api/v1/remember  — ingest merchant business context
  - POST /api/v1/recall    — retrieve relevant context before AI response

Design principles:
  - Merchant isolation enforced via per-merchant dataset names
  - Graceful degradation: Cognee failure NEVER crashes AI requests
  - No secrets stored or logged
  - No customer PII stored
  - All config read from environment via Settings
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.core.logging import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REMEMBER_TIMEOUT_SECONDS = 6.0
_RECALL_TIMEOUT_SECONDS = 6.0
_DATASET_PREFIX = "merchantmind_merchant_"


def _merchant_dataset(merchant_id: str) -> str:
    """
    Build a deterministic, isolated dataset name for a given merchant.
    Ensures memories from one merchant cannot be returned for another.
    """
    safe_id = merchant_id.strip().replace("-", "_").lower()
    return f"{_DATASET_PREFIX}{safe_id}"


# ---------------------------------------------------------------------------
# CogneeClient
# ---------------------------------------------------------------------------

class CogneeClient:
    """
    Thin HTTP wrapper around the Cognee Cloud REST API.

    Isolation strategy:
      Each merchant gets its own dataset (`merchantmind_merchant_<merchant_id>`).
      All remember/recall calls pass this dataset name, so data never leaks
      across merchant boundaries.

    Failure policy:
      Every public method returns a safe empty value on any error and logs a
      WARNING — it NEVER raises. Callers receive empty context and proceed
      normally.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key: str = settings.cognee_api_key
        self._base_url: str = settings.cognee_base_url.rstrip("/")
        self._tenant_id: str = settings.cognee_tenant_id
        self._user_id: str = settings.cognee_user_id

        # Determine whether Cognee is properly configured
        self._enabled: bool = bool(
            self._api_key
            and self._api_key not in {"", "your-cognee-api-key"}
            and self._base_url
            and self._base_url not in {"", "https://your-tenant.aws.cognee.ai"}
        )

        if not self._enabled:
            logger.warning(
                "CogneeClient: COGNEE_API_KEY or COGNEE_BASE_URL not configured. "
                "Memory layer disabled — AI requests will proceed without long-term context."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers. API key is never logged."""
        headers: Dict[str, str] = {
            "X-Api-Key": self._api_key,
            "Accept": "application/json",
        }
        if self._tenant_id:
            headers["X-Tenant-Id"] = self._tenant_id
        return headers

    def _is_available(self) -> bool:
        """Return True only when Cognee is fully configured."""
        return self._enabled

    # ------------------------------------------------------------------
    # Public API — remember
    # ------------------------------------------------------------------

    def remember(self, merchant_id: str, content: str) -> bool:
        """
        Ingest a text summary into Cognee memory for the given merchant.

        Args:
            merchant_id: Merchant's unique identifier (used to scope the dataset).
            content:     Plain-text business context to store (no PII, no secrets).

        Returns:
            True on success, False on any error (Cognee unavailable, timeout, etc.).
        """
        if not self._is_available():
            return False
        if not content or not content.strip():
            return False

        dataset = _merchant_dataset(merchant_id)
        url = f"{self._base_url}/api/v1/remember"

        try:
            with httpx.Client(timeout=_REMEMBER_TIMEOUT_SECONDS) as client:
                # Cognee Cloud /remember requires data as an uploaded file and datasetName
                response = client.post(
                    url,
                    headers=self._build_headers(),
                    files={"data": ("memory.txt", content.strip().encode("utf-8"), "text/plain")},
                    data={"datasetName": dataset, "run_in_background": "true"},
                )

            if response.status_code in (200, 201, 202):
                logger.info(
                    f"CogneeClient.remember: Successfully stored context for merchant "
                    f"'{merchant_id}' in dataset '{dataset}'."
                )
                return True
            else:
                logger.warning(
                    f"CogneeClient.remember: Non-2xx response {response.status_code} "
                    f"for merchant '{merchant_id}'. Continuing without memory storage."
                )
                return False

        except httpx.TimeoutException:
            logger.warning(
                f"CogneeClient.remember: Timeout after {_REMEMBER_TIMEOUT_SECONDS}s "
                f"for merchant '{merchant_id}'. Skipping memory storage."
            )
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"CogneeClient.remember: Unexpected error for merchant '{merchant_id}': "
                f"{type(exc).__name__}. Continuing without memory storage."
            )
            return False

    # ------------------------------------------------------------------
    # Public API — recall
    # ------------------------------------------------------------------

    def recall(self, merchant_id: str, query: str) -> List[Dict[str, Any]]:
        """
        Retrieve relevant business context from Cognee for the given merchant.

        Args:
            merchant_id: Merchant's unique identifier (scopes the search).
            query:       Natural-language question or search string.

        Returns:
            List of result dicts from Cognee, or [] on any failure.
            Each dict typically contains a ``text`` field with the recalled content.
        """
        if not self._is_available():
            return []
        if not query or not query.strip():
            return []

        dataset = _merchant_dataset(merchant_id)
        url = f"{self._base_url}/api/v1/recall"

        # Cognee Cloud OpenAPI specification:
        # - datasets: list of strings (e.g. [dataset]) scopes search to merchant's dataset
        # - searchType: "SUMMARIES" returns extracted knowledge facts fast
        # - onlyContext: True returns retrieval context directly without secondary LLM synthesis
        # - topK: 5
        payload: Dict[str, Any] = {
            "query": query.strip(),
            "datasets": [dataset],
            "searchType": "SUMMARIES",
            "onlyContext": True,
            "topK": 5,
        }

        try:
            with httpx.Client(timeout=_RECALL_TIMEOUT_SECONDS) as client:
                response = client.post(
                    url,
                    headers={**self._build_headers(), "Content-Type": "application/json"},
                    content=json.dumps(payload),
                )

            if response.status_code == 200:
                data = response.json()
                # Cognee may return a list or {"results": [...]}
                if isinstance(data, list):
                    results = data
                elif isinstance(data, dict):
                    results = data.get("results") or data.get("data") or []
                else:
                    results = []

                logger.info(
                    f"CogneeClient.recall: Retrieved {len(results)} memory items "
                    f"for merchant '{merchant_id}'."
                )
                return results

            else:
                logger.warning(
                    f"CogneeClient.recall: Non-2xx response {response.status_code} "
                    f"for merchant '{merchant_id}'. Returning empty context."
                )
                return []

        except httpx.TimeoutException:
            logger.warning(
                f"CogneeClient.recall: Timeout after {_RECALL_TIMEOUT_SECONDS}s "
                f"for merchant '{merchant_id}'. Using empty context."
            )
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"CogneeClient.recall: Unexpected error for merchant '{merchant_id}': "
                f"{type(exc).__name__}. Using empty context."
            )
            return []

    # ------------------------------------------------------------------
    # Convenience helpers used by the agent
    # ------------------------------------------------------------------

    def extract_context_text(self, recall_results: List[Dict[str, Any]]) -> str:
        """
        Flatten recall results into a single readable string for prompt injection.
        Returns empty string when results are empty.
        """
        if not recall_results:
            return ""
        parts: List[str] = []
        for item in recall_results:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("summary") or ""
            elif isinstance(item, str):
                text = item
            else:
                text = str(item)
            if text and text.strip():
                parts.append(text.strip())
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Module-level singleton (lazy-initialised)
# ---------------------------------------------------------------------------

_cognee_client: Optional[CogneeClient] = None


def get_cognee_client() -> CogneeClient:
    """Return the module-level CogneeClient singleton."""
    global _cognee_client
    if _cognee_client is None:
        _cognee_client = CogneeClient()
    return _cognee_client
