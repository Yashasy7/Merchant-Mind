"""
RAG Vector Store — MerchantMind.

JSON-backed, in-process vector store with cosine similarity search.
No external vector database required.

Storage layout:
  backend/data/rag_index/
    {merchant_id}.json      ← list of document dicts with content + embedding

Design:
  - Merchant isolation: each merchant has a separate JSON file.
  - Deterministic doc IDs prevent duplicate embeddings on re-index.
  - Upsert semantics: existing docs with same doc_id are replaced.
  - Search always filters by merchant_id before scoring.
  - Two retrieval modes:
      1. Dense (Gemini embedding): cosine similarity via numpy.
      2. Sparse fallback (keyword TF-IDF): used when embeddings unavailable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.core.config import get_settings
from app.core.logging import logger
from app.rag.embeddings import (
    build_keyword_vector,
    build_vocab,
    cosine_similarity,
)


# ---------------------------------------------------------------------------
# RAGStore
# ---------------------------------------------------------------------------

class RAGStore:
    """
    Persists and searches RAG documents for a merchant using cosine similarity.
    Thread-safe for read; writes use atomic JSON dumps.
    """

    def __init__(self, index_dir: Optional[str] = None) -> None:
        settings = get_settings()
        self._index_dir = Path(index_dir or settings.rag_index_dir)
        self._index_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _merchant_path(self, merchant_id: str) -> Path:
        safe = merchant_id.strip().replace("/", "_").replace("..", "_")
        return self._index_dir / f"{safe}.json"

    def _load(self, merchant_id: str) -> List[Dict[str, Any]]:
        path = self._merchant_path(merchant_id)
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception as exc:
            logger.warning(f"RAGStore._load: Failed to read '{path}': {exc}")
            return []

    def _save(self, merchant_id: str, docs: List[Dict[str, Any]]) -> None:
        path = self._merchant_path(merchant_id)
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(docs, f, ensure_ascii=False, default=str)
            tmp_path.replace(path)
        except Exception as exc:
            logger.warning(f"RAGStore._save: Failed to write '{path}': {exc}")
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert_many(self, merchant_id: str, docs: List[Dict[str, Any]]) -> int:
        """
        Upsert a list of documents into the merchant's index.
        Documents with matching doc_id are replaced; new ones are appended.
        Returns the number of documents in the final index.
        """
        existing = self._load(merchant_id)
        existing_by_id = {d["doc_id"]: d for d in existing if "doc_id" in d}

        added, updated = 0, 0
        for doc in docs:
            doc_id = doc.get("doc_id")
            if not doc_id:
                continue
            if doc_id in existing_by_id:
                updated += 1
            else:
                added += 1
            existing_by_id[doc_id] = doc

        final = list(existing_by_id.values())
        self._save(merchant_id, final)
        logger.info(
            f"RAGStore.upsert_many: merchant='{merchant_id}' "
            f"docs={len(final)} (added={added}, updated={updated})."
        )
        return len(final)

    def delete_merchant_index(self, merchant_id: str) -> None:
        """Remove the entire index for a merchant (used for full rebuild)."""
        path = self._merchant_path(merchant_id)
        try:
            path.unlink(missing_ok=True)
            logger.info(f"RAGStore: Deleted index for merchant '{merchant_id}'.")
        except Exception as exc:
            logger.warning(f"RAGStore.delete_merchant_index: {exc}")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        merchant_id: str,
        query_embedding: Optional[np.ndarray],
        query_text: str,
        top_k: int = 3,
        doc_type_filter: Optional[List[str]] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Retrieve the top_k most relevant documents for a query.

        If query_embedding is provided, uses dense cosine similarity.
        Otherwise, falls back to keyword TF-IDF scoring.

        Always filters by merchant_id first (isolation guarantee).

        Returns:
            List of (document_dict, score) tuples, sorted by descending relevance.
        """
        all_docs = self._load(merchant_id)

        # Merchant isolation: filter to only this merchant's docs
        docs = [d for d in all_docs if d.get("merchant_id") == merchant_id]

        if not docs:
            return []

        # Optional doc_type filter (intent-based)
        if doc_type_filter:
            filtered = [d for d in docs if d.get("doc_type") in doc_type_filter]
            if filtered:  # Only apply filter if it returns results
                docs = filtered

        scored: List[Tuple[Dict[str, Any], float]] = []

        if query_embedding is not None:
            # Dense retrieval: cosine similarity
            for doc in docs:
                doc_emb = doc.get("embedding")
                if doc_emb is None:
                    continue
                try:
                    doc_vec = np.array(doc_emb, dtype=np.float32)
                    score = float(np.dot(query_embedding, doc_vec))
                    scored.append((doc, score))
                except Exception:
                    continue
        else:
            # Sparse fallback: keyword TF-IDF cosine
            all_texts = [query_text] + [d.get("content", "") for d in docs]
            vocab = build_vocab(all_texts)
            query_vec = build_keyword_vector(query_text, vocab)
            for doc in docs:
                doc_vec = build_keyword_vector(doc.get("content", ""), vocab)
                score = cosine_similarity(query_vec, doc_vec)
                scored.append((doc, score))

        # Sort by score descending, return top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        results = [(doc, score) for doc, score in scored[:top_k] if score > 0.0]

        logger.debug(
            f"RAGStore.search: merchant='{merchant_id}' "
            f"query_len={len(query_text)} "
            f"candidates={len(docs)} "
            f"returned={len(results)} "
            f"mode={'dense' if query_embedding is not None else 'keyword'}"
        )
        return results

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self, merchant_id: str) -> Dict[str, Any]:
        """Return index statistics for a merchant (debugging)."""
        docs = self._load(merchant_id)
        merchant_docs = [d for d in docs if d.get("merchant_id") == merchant_id]
        doc_types = {}
        has_embeddings = 0
        for d in merchant_docs:
            dt = d.get("doc_type", "unknown")
            doc_types[dt] = doc_types.get(dt, 0) + 1
            if d.get("embedding"):
                has_embeddings += 1
        return {
            "merchant_id": merchant_id,
            "total_docs": len(merchant_docs),
            "docs_with_embeddings": has_embeddings,
            "docs_keyword_only": len(merchant_docs) - has_embeddings,
            "doc_types": doc_types,
            "index_path": str(self._merchant_path(merchant_id)),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_rag_store: Optional[RAGStore] = None


def get_rag_store() -> RAGStore:
    """Return the module-level RAGStore singleton."""
    global _rag_store
    if _rag_store is None:
        _rag_store = RAGStore()
    return _rag_store
