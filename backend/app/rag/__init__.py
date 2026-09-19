"""
RAG (Retrieval-Augmented Generation) package for MerchantMind.

Provides semantic retrieval of merchant business context to augment Gemini responses.
Architecture:
  document_builder  → builds aggregated text documents from SQLAlchemy models
  embeddings        → Gemini text-embedding-004 API + keyword fallback
  rag_store         → JSON-backed vector store with cosine similarity search
  rag_service       → public interface: ingest() and retrieve()
  context_builder   → formats retrieved chunks into Gemini-ready context string

Design principles:
  - Merchant isolation: every operation is scoped to a single merchant_id
  - Graceful degradation: all RAG failures are logged and silently ignored
  - No new infrastructure: uses numpy (already a dep) + Gemini Embedding API (same key)
  - Never overrides structured SQL tool results for financial figures
"""

from app.rag.rag_service import RAGService, get_rag_service

__all__ = ["RAGService", "get_rag_service"]
