"""
n8n Webhook Client for MerchantMind Campaign Delivery.

Sends an HTTP POST to the configured n8n webhook when an APPROVED campaign
is executed. The n8n workflow processes target customers and returns a
structured delivery result.

Design principles:
  - N8N_WEBHOOK_URL read from environment — never hard-coded
  - Optional N8N_WEBHOOK_SECRET header (only sent when configured)
  - Graceful degradation: n8n failure returns a structured error result
    and NEVER silently marks a campaign as successfully executed
  - Human approval gate is NEVER bypassed — only APPROVED campaigns
    may trigger this client
  - No credentials logged or stored
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

_WEBHOOK_TIMEOUT_SECONDS = 15.0
_N8N_EXECUTION_MODE_DEMO = "simulated_demo"
_N8N_EXECUTION_MODE_LIVE = "live"


# ---------------------------------------------------------------------------
# Result data class (plain dict based, no ORM dependency)
# ---------------------------------------------------------------------------

class N8nExecutionResult:
    """
    Structured result returned from an n8n webhook call.
    Always populated — even on failure — so callers can safely read it.
    """

    __slots__ = (
        "success",
        "campaign_id",
        "merchant_id",
        "status",
        "targeted",
        "delivered",
        "failed",
        "execution_mode",
        "message",
        "raw_response",
        "error",
    )

    def __init__(
        self,
        *,
        success: bool,
        campaign_id: str,
        merchant_id: str,
        status: str = "unknown",
        targeted: int = 0,
        delivered: int = 0,
        failed: int = 0,
        execution_mode: str = _N8N_EXECUTION_MODE_DEMO,
        message: str = "",
        raw_response: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        self.success = success
        self.campaign_id = campaign_id
        self.merchant_id = merchant_id
        self.status = status
        self.targeted = targeted
        self.delivered = delivered
        self.failed = failed
        self.execution_mode = execution_mode
        self.message = message
        self.raw_response = raw_response or {}
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "campaign_id": self.campaign_id,
            "merchant_id": self.merchant_id,
            "status": self.status,
            "targeted": self.targeted,
            "delivered": self.delivered,
            "failed": self.failed,
            "execution_mode": self.execution_mode,
            "message": self.message,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# N8nClient
# ---------------------------------------------------------------------------

class N8nClient:
    """
    HTTP client that POSTs campaign execution payloads to the n8n webhook.

    Safety invariant (enforced by caller, asserted here for defence):
      Only campaigns with status == "APPROVED" may be sent to n8n.
      PENDING_APPROVAL campaigns MUST NEVER reach this client.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._webhook_url: str = settings.n8n_webhook_url.strip()
        # Secret is optional — only sent when explicitly configured
        self._webhook_secret: str = settings.n8n_webhook_secret.strip()

        self._enabled: bool = bool(
            self._webhook_url
            and self._webhook_url not in {"", "https://your-n8n-instance/webhook/campaign-execute"}
        )

        if not self._enabled:
            logger.warning(
                "N8nClient: N8N_WEBHOOK_URL not configured. "
                "n8n delivery disabled — campaign execution will remain simulation-only."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # Attach secret only when configured
        if self._webhook_secret:
            headers["X-Webhook-Secret"] = self._webhook_secret
        return headers

    def _is_available(self) -> bool:
        return self._enabled

    def _parse_n8n_response(
        self,
        campaign_id: str,
        merchant_id: str,
        data: Any,
    ) -> N8nExecutionResult:
        """
        Parse the n8n webhook response body into an N8nExecutionResult.
        n8n may return a single object or a list (first element is used).
        Unknown/partial responses are handled gracefully.
        """
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            data = {}

        return N8nExecutionResult(
            success=True,
            campaign_id=data.get("campaign_id", campaign_id),
            merchant_id=data.get("merchant_id", merchant_id),
            status=str(data.get("status", "completed")),
            targeted=int(data.get("targeted", 0)),
            delivered=int(data.get("delivered", 0)),
            failed=int(data.get("failed", 0)),
            execution_mode=str(data.get("execution_mode", _N8N_EXECUTION_MODE_DEMO)),
            message=str(data.get("message", "n8n workflow completed.")),
            raw_response=data,
        )

    # ------------------------------------------------------------------
    # Public API — trigger_campaign
    # ------------------------------------------------------------------

    def trigger_campaign(
        self,
        *,
        campaign_id: str,
        merchant_id: str,
        campaign_status: str,
        offer_type: str,
        target_segment: str,
        cashback_amount: Optional[float],
        discount_percent: Optional[float],
        minimum_transaction_amount: float,
        target_count: int,
        campaign_name: str,
        campaign_description: Optional[str],
        target_days: Optional[str],
        target_hours: Optional[str],
        marketing_copy_headline: Optional[str] = None,
        marketing_copy_body: Optional[str] = None,
    ) -> N8nExecutionResult:
        """
        POST campaign execution payload to the n8n webhook.

        SAFETY CHECK: This method asserts that campaign_status == "APPROVED".
        A PENDING_APPROVAL campaign MUST NEVER reach this method.

        Args:
            campaign_id:      Campaign unique identifier.
            merchant_id:      Merchant unique identifier.
            campaign_status:  Must be "APPROVED". Enforced defensively.
            offer_type:       fixed_cashback | percentage_discount | custom.
            target_segment:   Customer segment name.
            ... (see parameter list above)

        Returns:
            N8nExecutionResult — always populated; success=False on failure.
        """
        # ── Safety boundary: PENDING_APPROVAL MUST NEVER reach n8n ──────────
        if campaign_status != "APPROVED":
            logger.error(
                f"N8nClient.trigger_campaign: BLOCKED — campaign '{campaign_id}' "
                f"has status '{campaign_status}', not 'APPROVED'. "
                f"n8n MUST NOT be triggered for non-approved campaigns."
            )
            return N8nExecutionResult(
                success=False,
                campaign_id=campaign_id,
                merchant_id=merchant_id,
                status="blocked",
                message="Campaign is not in APPROVED state. n8n trigger blocked.",
                error="APPROVAL_GATE_VIOLATION",
            )

        if not self._is_available():
            logger.info(
                f"N8nClient: Not configured — skipping n8n trigger for campaign '{campaign_id}'."
            )
            return N8nExecutionResult(
                success=False,
                campaign_id=campaign_id,
                merchant_id=merchant_id,
                status="skipped",
                message="n8n integration not configured. Proceeding with internal simulation.",
                error="N8N_NOT_CONFIGURED",
            )

        # Build the payload using only existing backend domain model fields
        payload: Dict[str, Any] = {
            "campaign_id": campaign_id,
            "merchant_id": merchant_id,
            "offer_type": offer_type,
            "target_segment": target_segment,
            "target_count": target_count,
            "campaign_name": campaign_name,
            "campaign_description": campaign_description or "",
            "target_days": target_days,
            "target_hours": target_hours,
            "execution_mode": _N8N_EXECUTION_MODE_DEMO,
        }
        # Include offer value only when relevant
        if cashback_amount is not None and cashback_amount > 0:
            payload["cashback_amount"] = cashback_amount
        if discount_percent is not None and discount_percent > 0:
            payload["discount_percent"] = discount_percent
        if minimum_transaction_amount > 0:
            payload["minimum_transaction_amount"] = minimum_transaction_amount
        if marketing_copy_headline:
            payload["marketing_copy_headline"] = marketing_copy_headline
        if marketing_copy_body:
            payload["marketing_copy_body"] = marketing_copy_body

        try:
            with httpx.Client(timeout=_WEBHOOK_TIMEOUT_SECONDS) as client:
                response = client.post(
                    self._webhook_url,
                    headers=self._build_headers(),
                    content=json.dumps(payload),
                )

            if response.status_code in (200, 201, 202):
                try:
                    data = response.json()
                except Exception:
                    data = {}

                result = self._parse_n8n_response(campaign_id, merchant_id, data)
                logger.info(
                    f"N8nClient: Campaign '{campaign_id}' webhook succeeded. "
                    f"Delivered: {result.delivered}/{result.targeted}."
                )
                return result

            else:
                logger.warning(
                    f"N8nClient: Non-2xx response {response.status_code} "
                    f"for campaign '{campaign_id}'. "
                    f"Body: {response.text[:200]}"
                )
                return N8nExecutionResult(
                    success=False,
                    campaign_id=campaign_id,
                    merchant_id=merchant_id,
                    status="n8n_error",
                    message=f"n8n webhook returned HTTP {response.status_code}.",
                    error=f"HTTP_{response.status_code}",
                )

        except httpx.TimeoutException:
            logger.warning(
                f"N8nClient: Timeout after {_WEBHOOK_TIMEOUT_SECONDS}s "
                f"for campaign '{campaign_id}'."
            )
            return N8nExecutionResult(
                success=False,
                campaign_id=campaign_id,
                merchant_id=merchant_id,
                status="timeout",
                message="n8n webhook timed out. Campaign execution proceeded with internal simulation.",
                error="WEBHOOK_TIMEOUT",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"N8nClient: Unexpected error for campaign '{campaign_id}': "
                f"{type(exc).__name__} — {exc}."
            )
            return N8nExecutionResult(
                success=False,
                campaign_id=campaign_id,
                merchant_id=merchant_id,
                status="error",
                message=f"n8n webhook call failed: {type(exc).__name__}.",
                error=str(type(exc).__name__),
            )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_n8n_client: Optional[N8nClient] = None


def get_n8n_client() -> N8nClient:
    """Return the module-level N8nClient singleton."""
    global _n8n_client
    if _n8n_client is None:
        _n8n_client = N8nClient()
    return _n8n_client
