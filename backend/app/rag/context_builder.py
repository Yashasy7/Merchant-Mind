"""
RAG Context Builder — MerchantMind.

Formats retrieved RAG chunks into a clean, structured context string
suitable for injection into the Gemini prompt.

Design:
  - Source attribution is preserved for every chunk.
  - Total context length is bounded (no unbounded text injection).
  - Returns empty string when no relevant context was retrieved.
  - Never overrides structured tool data (it sits alongside it, not above it).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.core.logging import logger


# Max characters injected per RAG context block (keeps Gemini prompt lean)
MAX_RAG_CONTEXT_CHARS = 2500

# Doc type → human-readable source label for citation
_DOC_TYPE_LABELS: Dict[str, str] = {
    "merchant_profile":       "Merchant Business Profile",
    "sales_summary_monthly":  "Monthly Sales Summary",
    "sales_patterns":         "Sales Patterns & Peak Hours",
    "customer_segments":      "Customer Segmentation",
    "customer_at_risk":       "At-Risk & Inactive Customer Analysis",
    "expense_summary_monthly": "Monthly Expense Summary",
    "campaign_history":       "Campaign History",
    "business_observations":  "Business Health Observations",
}


def build_rag_context(
    results: List[Tuple[Dict[str, Any], float]],
    max_chars: int = MAX_RAG_CONTEXT_CHARS,
) -> str:
    """
    Convert a list of (document, score) tuples into a formatted context string.

    Args:
        results:   List of (doc_dict, relevance_score) from RAGStore.search().
        max_chars: Maximum total characters for the RAG context block.

    Returns:
        Multi-line string ready for injection into the Gemini prompt,
        or empty string if results is empty.
    """
    if not results:
        return ""

    parts: List[str] = []
    total_chars = 0

    for doc, score in results:
        doc_type = doc.get("doc_type", "unknown")
        label = _DOC_TYPE_LABELS.get(doc_type, doc_type.replace("_", " ").title())
        date_from = doc.get("date_from")
        date_to = doc.get("date_to")

        # Build source citation line
        if date_from and date_to:
            citation = f"[Source: {label} | {date_from} to {date_to}]"
        elif date_from:
            citation = f"[Source: {label} | from {date_from}]"
        else:
            citation = f"[Source: {label}]"

        content = doc.get("content", "").strip()
        if not content:
            continue

        chunk = f"{citation}\n{content}"

        # Enforce character budget
        remaining = max_chars - total_chars
        if remaining <= 0:
            break
        if len(chunk) > remaining:
            chunk = chunk[:remaining] + "…"

        parts.append(chunk)
        total_chars += len(chunk)

    if not parts:
        return ""

    header = "--- Retrieved Business Context (Synthetic / Illustrative Demo Data) ---\n"
    footer = "\n--- End of Retrieved Context ---"
    body = "\n\n".join(parts)

    context = header + body + footer

    logger.debug(
        f"ContextBuilder: assembled {len(results)} chunks into "
        f"{len(context)} chars of RAG context."
    )
    return context
