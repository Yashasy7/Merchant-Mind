"""
RAG Service — MerchantMind.

Public interface for the RAG pipeline:
  - ingest(merchant_id, db): Build documents from DB, embed, and store in RAGStore.
  - retrieve(merchant_id, query, intent, top_k): Semantic search + context assembly.
  - get_stats(merchant_id): Debugging info about the index.

Architecture:
  ingest()
    DocumentBuilder.build_all()
    → EmbeddingClient.embed_batch()   (Gemini text-embedding-004 or keyword fallback)
    → RAGStore.upsert_many()          (JSON index, atomic write)

  retrieve()
    EmbeddingClient.embed_text(query)
    → RAGStore.search()               (cosine similarity or keyword scoring)
    → context_builder.build_rag_context()
    → str context ready for Gemini prompt

Query Routing:
  Based on detected intent, applies doc_type filters so only relevant
  document types are retrieved (avoids polluting answers with unrelated context).

Fallback Policy:
  Every step is wrapped in try/except. RAG failure NEVER crashes the Copilot.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import logger
from app.rag.document_builder import DocumentBuilder
from app.rag.embeddings import get_embedding_client
from app.rag.rag_store import get_rag_store
from app.rag.context_builder import build_rag_context


# ---------------------------------------------------------------------------
# Intent → doc_type filter mapping
# ---------------------------------------------------------------------------
# Controls which document types are searched for each intent.
# None means: search all doc types.

_INTENT_DOC_FILTERS: Dict[str, Optional[List[str]]] = {
    "analyze_sales":              ["sales_summary_monthly", "sales_patterns", "business_observations"],
    "analyze_customers":          ["customer_segments", "customer_at_risk", "business_observations"],
    "recover_inactive_customers": ["customer_at_risk", "customer_segments", "campaign_history"],
    "analyze_financials":         ["expense_summary_monthly", "business_observations"],
    "analyze_cash_flow":          ["expense_summary_monthly", "business_observations"],
    "increase_weekend_revenue":   ["sales_patterns", "sales_summary_monthly", "campaign_history"],
    "create_campaign":            ["campaign_history", "customer_segments"],
    "simulate_campaign":          ["campaign_history", "customer_segments"],
    "get_campaign_history":       ["campaign_history"],
    "get_business_health":        ["business_observations", "sales_patterns", "customer_segments"],
    "forecast_sales":             ["sales_summary_monthly", "business_observations"],
    "general_guidance":           None,  # All types (broad semantic question)
    "analyze_business":           None,
}

# Intents where RAG is not useful (structured tool is sufficient)
_STRUCTURED_ONLY_INTENTS = {
    "approve_campaign",
    "execute_campaign",
    "get_campaign_status",
}


# ---------------------------------------------------------------------------
# RAGService
# ---------------------------------------------------------------------------

class RAGService:
    """
    Orchestrates ingestion and retrieval for the MerchantMind RAG pipeline.
    Thread-safe ingestion lock prevents concurrent index rebuilds.
    """

    def __init__(self) -> None:
        self._store = get_rag_store()
        self._embed = get_embedding_client()
        self._settings = get_settings()
        self._ingest_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest(self, merchant_id: str, db: Session, force_rebuild: bool = False) -> Dict[str, Any]:
        """
        Build RAG documents from the database and store them.

        Args:
            merchant_id:    Merchant to index.
            db:             SQLAlchemy session.
            force_rebuild:  If True, clears existing index before rebuilding.

        Returns:
            Dict with ingestion stats and status.
        """
        if not self._settings.rag_enabled:
            return {"status": "disabled", "merchant_id": merchant_id}

        with self._ingest_lock:
            try:
                if force_rebuild:
                    self._store.delete_merchant_index(merchant_id)

                # Check if index already current (avoid redundant rebuilds)
                stats = self._store.get_stats(merchant_id)
                if not force_rebuild and stats["total_docs"] > 0:
                    logger.info(
                        f"RAGService.ingest: Merchant '{merchant_id}' already has "
                        f"{stats['total_docs']} docs. Performing incremental upsert."
                    )

                # Build documents
                builder = DocumentBuilder(db)
                docs = builder.build_all(merchant_id)

                if not docs:
                    logger.warning(f"RAGService.ingest: No documents built for '{merchant_id}'.")
                    return {"status": "no_data", "merchant_id": merchant_id, "docs_built": 0}

                # Embed documents
                texts = [d["content"] for d in docs]
                embeddings = self._embed.embed_batch(texts)

                embedded_count = 0
                for doc, emb in zip(docs, embeddings):
                    if emb is not None:
                        doc["embedding"] = emb.tolist()
                        embedded_count += 1
                    else:
                        doc["embedding"] = None  # Will use keyword fallback at search time

                # Store (upsert)
                final_count = self._store.upsert_many(merchant_id, docs)

                result = {
                    "status": "success",
                    "merchant_id": merchant_id,
                    "docs_built": len(docs),
                    "docs_embedded": embedded_count,
                    "docs_keyword_only": len(docs) - embedded_count,
                    "total_in_index": final_count,
                }
                logger.info(
                    f"RAGService.ingest: Complete for '{merchant_id}' — "
                    f"{len(docs)} docs built, {embedded_count} embedded."
                )
                return result

            except Exception as exc:
                logger.warning(f"RAGService.ingest: Failed for '{merchant_id}': {type(exc).__name__}: {exc}")
                return {"status": "error", "merchant_id": merchant_id, "error": str(exc)}

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        merchant_id: str,
        query: str,
        intent: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> str:
        """
        Retrieve relevant context for a merchant query.

        Args:
            merchant_id: Merchant to retrieve for (isolation enforced).
            query:       User's natural language question.
            intent:      Detected intent (used for doc_type filtering).
            top_k:       Max chunks to return (defaults to config value).

        Returns:
            Formatted context string for Gemini prompt injection,
            or empty string if nothing relevant is found or RAG fails.
        """
        if not self._settings.rag_enabled:
            return ""

        if not query or not query.strip():
            return ""

        # Skip RAG for action-only intents
        if intent in _STRUCTURED_ONLY_INTENTS:
            return ""

        effective_top_k = top_k or self._settings.rag_top_k

        try:
            # Query routing: select relevant doc types based on intent
            doc_type_filter = _INTENT_DOC_FILTERS.get(intent) if intent else None

            # Embed the query
            query_embedding = None
            try:
                query_embedding = self._embed.embed_text(query)
            except Exception as emb_err:
                logger.debug(f"RAGService: Query embedding failed ({emb_err}), using keyword mode.")

            # Search
            results = self._store.search(
                merchant_id=merchant_id,
                query_embedding=query_embedding,
                query_text=query,
                top_k=effective_top_k,
                doc_type_filter=doc_type_filter,
            )

            if not results:
                logger.debug(
                    f"RAGService.retrieve: No results for merchant='{merchant_id}' "
                    f"intent='{intent}' query='{query[:60]}...'"
                )
                return ""

            # Build context string
            context = build_rag_context(results)

            # Debug log (no sensitive data)
            logger.info(
                f"RAGService.retrieve: merchant='{merchant_id}' "
                f"intent='{intent}' "
                f"query_chars={len(query)} "
                f"docs_retrieved={len(results)} "
                f"context_chars={len(context)} "
                f"mode={'dense' if query_embedding is not None else 'keyword'} "
                f"doc_types={[r[0].get('doc_type') for r in results]}"
            )

            return context

        except Exception as exc:
            logger.warning(
                f"RAGService.retrieve: Failed for merchant='{merchant_id}': "
                f"{type(exc).__name__}: {exc}. Returning empty context."
            )
            return ""

    # ------------------------------------------------------------------
    # Stats / Debugging
    # ------------------------------------------------------------------

    def get_stats(self, merchant_id: str) -> Dict[str, Any]:
        """Return index statistics for debugging."""
        try:
            stats = self._store.get_stats(merchant_id)
            stats["rag_enabled"] = self._settings.rag_enabled
            stats["rag_top_k"] = self._settings.rag_top_k
            stats["embedding_configured"] = self._embed._is_configured
            return stats
        except Exception as exc:
            return {"status": "error", "error": str(exc), "merchant_id": merchant_id}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Return the module-level RAGService singleton."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


# ---------------------------------------------------------------------------
# CLI convenience (manual re-index)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os

    # Add backend root to path
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    merchant = sys.argv[1] if len(sys.argv) > 1 else "demo-merchant-001"
    force = "--force" in sys.argv

    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        svc = RAGService()
        result = svc.ingest(merchant, db, force_rebuild=force)
        print(f"Ingestion result: {result}")
        print(f"Stats: {svc.get_stats(merchant)}")
    finally:
        db.close()
