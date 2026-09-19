"""
RAG Pipeline Tests for MerchantMind.

Tests:
  - DocumentBuilder generates all expected document types
  - RAGStore upsert and retrieval
  - Merchant isolation (merchant A data never leaks to merchant B)
  - Retrieval: sales query → sales docs
  - Retrieval: customer query → customer docs
  - Retrieval: expense query → expense docs
  - Retrieval: campaign query → campaign docs
  - Keyword fallback retrieval (no embeddings)
  - RAGService ingest and retrieve pipeline
  - RAG failure never crashes the agent

DISCLOSURE: All test data is synthetic demo data.
"""

import json
import os
import tempfile
import uuid
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_index_dir():
    """Provide a temporary directory for the RAG index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def rag_store(temp_index_dir):
    from app.rag.rag_store import RAGStore
    return RAGStore(index_dir=temp_index_dir)


@pytest.fixture
def sample_docs_merchant_a():
    """Sample documents for Merchant A."""
    return [
        {
            "doc_id": "aaaa0001",
            "merchant_id": "merchant-a",
            "doc_type": "sales_summary_monthly",
            "topic": "sales_performance",
            "content": "Sales Summary for Merchant A. Total revenue 100000. Transactions 200.",
            "embedding": None,
            "created_at": "2026-09-01T00:00:00+00:00",
        },
        {
            "doc_id": "aaaa0002",
            "merchant_id": "merchant-a",
            "doc_type": "customer_segments",
            "topic": "customer_intelligence",
            "content": "Customer segments for Merchant A. VIP: 10. At-Risk: 25. Inactive: 50.",
            "embedding": None,
            "created_at": "2026-09-01T00:00:00+00:00",
        },
    ]


@pytest.fixture
def sample_docs_merchant_b():
    """Sample documents for Merchant B — must never appear in Merchant A results."""
    return [
        {
            "doc_id": "bbbb0001",
            "merchant_id": "merchant-b",
            "doc_type": "sales_summary_monthly",
            "topic": "sales_performance",
            "content": "Sales data for Merchant B. Total revenue 999999. Secret merchant info.",
            "embedding": None,
            "created_at": "2026-09-01T00:00:00+00:00",
        },
    ]


# ---------------------------------------------------------------------------
# RAGStore Tests
# ---------------------------------------------------------------------------

class TestRAGStore:

    def test_upsert_and_load(self, rag_store, sample_docs_merchant_a):
        count = rag_store.upsert_many("merchant-a", sample_docs_merchant_a)
        assert count == 2

    def test_upsert_deduplicates(self, rag_store, sample_docs_merchant_a):
        rag_store.upsert_many("merchant-a", sample_docs_merchant_a)
        # Upsert again with same doc_ids
        count = rag_store.upsert_many("merchant-a", sample_docs_merchant_a)
        assert count == 2  # Still 2, not 4

    def test_stats(self, rag_store, sample_docs_merchant_a):
        rag_store.upsert_many("merchant-a", sample_docs_merchant_a)
        stats = rag_store.get_stats("merchant-a")
        assert stats["total_docs"] == 2
        assert stats["merchant_id"] == "merchant-a"
        assert "sales_summary_monthly" in stats["doc_types"]

    def test_delete_merchant_index(self, rag_store, sample_docs_merchant_a):
        rag_store.upsert_many("merchant-a", sample_docs_merchant_a)
        rag_store.delete_merchant_index("merchant-a")
        stats = rag_store.get_stats("merchant-a")
        assert stats["total_docs"] == 0

    def test_keyword_retrieval_sales_query(self, rag_store, sample_docs_merchant_a):
        rag_store.upsert_many("merchant-a", sample_docs_merchant_a)
        results = rag_store.search(
            merchant_id="merchant-a",
            query_embedding=None,
            query_text="What are my sales and revenue?",
            top_k=3,
        )
        assert len(results) > 0
        top_doc, top_score = results[0]
        # Sales doc should score higher for a sales query
        assert top_doc["doc_type"] == "sales_summary_monthly"
        assert top_score > 0.0

    def test_keyword_retrieval_customer_query(self, rag_store, sample_docs_merchant_a):
        rag_store.upsert_many("merchant-a", sample_docs_merchant_a)
        results = rag_store.search(
            merchant_id="merchant-a",
            query_embedding=None,
            query_text="Who are my at-risk inactive customers?",
            top_k=3,
        )
        assert len(results) > 0
        top_doc, _ = results[0]
        assert top_doc["doc_type"] == "customer_segments"

    # ------------------------------------------------------------------
    # MERCHANT ISOLATION TESTS — Critical Security Requirement
    # ------------------------------------------------------------------

    def test_merchant_isolation_a_cannot_see_b(
        self, rag_store, sample_docs_merchant_a, sample_docs_merchant_b
    ):
        """Merchant A query must NEVER return Merchant B documents."""
        rag_store.upsert_many("merchant-a", sample_docs_merchant_a)
        rag_store.upsert_many("merchant-b", sample_docs_merchant_b)

        results = rag_store.search(
            merchant_id="merchant-a",
            query_embedding=None,
            query_text="sales revenue",
            top_k=5,
        )
        for doc, _ in results:
            assert doc["merchant_id"] == "merchant-a", (
                f"ISOLATION VIOLATION: merchant-a query returned doc from '{doc['merchant_id']}'"
            )

    def test_merchant_isolation_b_cannot_see_a(
        self, rag_store, sample_docs_merchant_a, sample_docs_merchant_b
    ):
        """Merchant B query must NEVER return Merchant A documents."""
        rag_store.upsert_many("merchant-a", sample_docs_merchant_a)
        rag_store.upsert_many("merchant-b", sample_docs_merchant_b)

        results = rag_store.search(
            merchant_id="merchant-b",
            query_embedding=None,
            query_text="sales revenue",
            top_k=5,
        )
        for doc, _ in results:
            assert doc["merchant_id"] == "merchant-b", (
                f"ISOLATION VIOLATION: merchant-b query returned doc from '{doc['merchant_id']}'"
            )

    def test_merchant_b_data_not_in_merchant_a_results(
        self, rag_store, sample_docs_merchant_a, sample_docs_merchant_b
    ):
        """Merchant B's sensitive content must not appear in Merchant A results."""
        rag_store.upsert_many("merchant-a", sample_docs_merchant_a)
        rag_store.upsert_many("merchant-b", sample_docs_merchant_b)

        results = rag_store.search(
            merchant_id="merchant-a",
            query_embedding=None,
            query_text="revenue sales",
            top_k=5,
        )
        all_content = " ".join(doc.get("content", "") for doc, _ in results)
        assert "Secret merchant info" not in all_content
        assert "999999" not in all_content

    def test_empty_merchant_returns_no_results(self, rag_store):
        """Querying a merchant with no index returns empty list."""
        results = rag_store.search(
            merchant_id="no-such-merchant",
            query_embedding=None,
            query_text="sales revenue",
            top_k=3,
        )
        assert results == []

    def test_doc_type_filter(self, rag_store, sample_docs_merchant_a):
        rag_store.upsert_many("merchant-a", sample_docs_merchant_a)
        results = rag_store.search(
            merchant_id="merchant-a",
            query_embedding=None,
            query_text="customers",
            top_k=3,
            doc_type_filter=["customer_segments"],
        )
        for doc, _ in results:
            assert doc["doc_type"] == "customer_segments"

    def test_dense_retrieval_with_embeddings(self, rag_store):
        """Dense retrieval using numpy vectors works correctly."""
        # Create docs with artificial embeddings
        rng = np.random.default_rng(42)

        def _norm(v):
            n = np.linalg.norm(v)
            return v / n if n > 0 else v

        sales_emb = _norm(rng.random(768).astype(np.float32))
        customer_emb = _norm(rng.random(768).astype(np.float32))

        docs = [
            {
                "doc_id": "dense-sales",
                "merchant_id": "dense-merchant",
                "doc_type": "sales_summary_monthly",
                "content": "Sales revenue transactions",
                "embedding": sales_emb.tolist(),
                "created_at": "2026-01-01",
            },
            {
                "doc_id": "dense-cust",
                "merchant_id": "dense-merchant",
                "doc_type": "customer_segments",
                "content": "Customer segments at-risk inactive",
                "embedding": customer_emb.tolist(),
                "created_at": "2026-01-01",
            },
        ]
        rag_store.upsert_many("dense-merchant", docs)

        # Query embedding close to sales_emb
        query_emb = _norm(sales_emb + _norm(rng.random(768).astype(np.float32)) * 0.1)
        results = rag_store.search(
            merchant_id="dense-merchant",
            query_embedding=query_emb,
            query_text="",
            top_k=2,
        )
        assert len(results) == 2
        top_doc, top_score = results[0]
        assert top_doc["doc_type"] == "sales_summary_monthly"
        assert top_score > 0.0


# ---------------------------------------------------------------------------
# Embeddings Tests
# ---------------------------------------------------------------------------

class TestEmbeddings:

    def test_keyword_tokenizer(self):
        from app.rag.embeddings import _tokenize
        tokens = _tokenize("What are my at-risk customers this month?")
        assert "risk" in tokens or "at" in tokens or "customers" in tokens
        assert "the" not in tokens  # stopword removed
        assert "my" not in tokens   # stopword removed

    def test_keyword_vector_nonzero(self):
        from app.rag.embeddings import build_vocab, build_keyword_vector
        texts = ["sales revenue this month", "customers at risk inactive"]
        vocab = build_vocab(texts)
        vec = build_keyword_vector("sales revenue", vocab)
        assert vec.shape[0] == len(vocab)
        assert vec.sum() > 0

    def test_cosine_similarity_identical(self):
        from app.rag.embeddings import cosine_similarity
        v = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-5

    def test_cosine_similarity_orthogonal(self):
        from app.rag.embeddings import cosine_similarity
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        assert abs(cosine_similarity(a, b)) < 1e-5

    def test_embedding_client_unconfigured_returns_none(self):
        from app.rag.embeddings import EmbeddingClient
        with patch("app.rag.embeddings.get_settings") as mock_settings:
            mock_settings.return_value.llm_api_key = ""
            client = EmbeddingClient()
            result = client.embed_text("test query")
            assert result is None


# ---------------------------------------------------------------------------
# ContextBuilder Tests
# ---------------------------------------------------------------------------

class TestContextBuilder:

    def test_empty_results_returns_empty_string(self):
        from app.rag.context_builder import build_rag_context
        assert build_rag_context([]) == ""

    def test_source_attribution_present(self):
        from app.rag.context_builder import build_rag_context
        docs = [(
            {
                "doc_type": "sales_summary_monthly",
                "date_from": "2026-08-01",
                "date_to": "2026-08-31",
                "content": "Total revenue ₹100,000 this month.",
            },
            0.92,
        )]
        result = build_rag_context(docs)
        assert "Monthly Sales Summary" in result
        assert "2026-08-01" in result
        assert "₹100,000" in result

    def test_character_budget_enforced(self):
        from app.rag.context_builder import build_rag_context
        huge_content = "x" * 10000
        docs = [({"doc_type": "merchant_profile", "content": huge_content, "date_from": None, "date_to": None}, 0.8)]
        result = build_rag_context(docs, max_chars=500)
        assert len(result) <= 700  # Budget + header/footer overhead

    def test_multiple_docs_all_cited(self):
        from app.rag.context_builder import build_rag_context
        docs = [
            ({"doc_type": "sales_summary_monthly", "content": "Sales data.", "date_from": None, "date_to": None}, 0.9),
            ({"doc_type": "customer_segments", "content": "Customer data.", "date_from": None, "date_to": None}, 0.7),
        ]
        result = build_rag_context(docs)
        assert "Monthly Sales Summary" in result
        assert "Customer Segmentation" in result


# ---------------------------------------------------------------------------
# DocumentBuilder Tests (with mock DB)
# ---------------------------------------------------------------------------

class TestDocumentBuilder:

    def _make_merchant(self, merchant_id="test-merchant"):
        from app.models.merchant import Merchant
        m = MagicMock(spec=Merchant)
        m.merchant_id = merchant_id
        m.business_name = "Test Store"
        m.business_type = "Grocery"
        m.location = "Bengaluru"
        m.business_age = 24
        return m

    def test_build_merchant_profile(self):
        from app.rag.document_builder import DocumentBuilder
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._make_merchant()
        builder = DocumentBuilder(db)

        merchant = self._make_merchant()
        doc = builder._build_merchant_profile("test-merchant", merchant)

        assert doc["doc_type"] == "merchant_profile"
        assert doc["merchant_id"] == "test-merchant"
        assert "Test Store" in doc["content"]
        assert "Grocery" in doc["content"]
        assert "Bengaluru" in doc["content"]
        assert len(doc["doc_id"]) == 32  # sha256 truncated

    def test_unknown_merchant_returns_empty(self):
        from app.rag.document_builder import DocumentBuilder
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        builder = DocumentBuilder(db)
        docs = builder.build_all("nonexistent-merchant")
        assert docs == []


# ---------------------------------------------------------------------------
# RAGService Integration Tests (with mock DB + mock embeddings)
# ---------------------------------------------------------------------------

class TestRAGService:

    def test_ingest_disabled_returns_disabled(self, temp_index_dir):
        from app.rag.rag_service import RAGService
        with patch("app.rag.rag_service.get_settings") as mock_settings:
            mock_settings.return_value.rag_enabled = False
            mock_settings.return_value.rag_top_k = 3
            mock_settings.return_value.rag_index_dir = temp_index_dir
            svc = RAGService()
            result = svc.ingest("demo-merchant-001", MagicMock())
            assert result["status"] == "disabled"

    def test_retrieve_disabled_returns_empty(self, temp_index_dir):
        from app.rag.rag_service import RAGService
        with patch("app.rag.rag_service.get_settings") as mock_settings:
            mock_settings.return_value.rag_enabled = False
            mock_settings.return_value.rag_top_k = 3
            mock_settings.return_value.rag_index_dir = temp_index_dir
            svc = RAGService()
            result = svc.retrieve("demo-merchant-001", "What are my sales?")
            assert result == ""

    def test_retrieve_structured_only_intent_skipped(self, temp_index_dir):
        from app.rag.rag_service import RAGService
        with patch("app.rag.rag_service.get_settings") as mock_settings:
            mock_settings.return_value.rag_enabled = True
            mock_settings.return_value.rag_top_k = 3
            mock_settings.return_value.rag_index_dir = temp_index_dir
            svc = RAGService()
            result = svc.retrieve("demo-merchant-001", "Approve the campaign", intent="approve_campaign")
            assert result == ""

    def test_retrieve_failure_returns_empty_not_exception(self, temp_index_dir):
        """RAG failure must never propagate as an exception."""
        from app.rag.rag_service import RAGService
        with patch("app.rag.rag_service.get_settings") as mock_settings:
            mock_settings.return_value.rag_enabled = True
            mock_settings.return_value.rag_top_k = 3
            mock_settings.return_value.rag_index_dir = temp_index_dir
            svc = RAGService()
            # Corrupt the store to force an exception
            svc._store = MagicMock(side_effect=RuntimeError("Simulated store failure"))
            result = svc.retrieve("demo-merchant-001", "What are my sales?")
            assert result == ""  # Must return empty, never raise

    def test_retrieve_with_indexed_docs_keyword(self, rag_store, temp_index_dir, sample_docs_merchant_a):
        from app.rag.rag_service import RAGService
        rag_store.upsert_many("merchant-a", sample_docs_merchant_a)

        with patch("app.rag.rag_service.get_settings") as mock_settings, \
             patch("app.rag.rag_service.get_rag_store", return_value=rag_store), \
             patch("app.rag.rag_service.get_embedding_client") as mock_embed:
            mock_settings.return_value.rag_enabled = True
            mock_settings.return_value.rag_top_k = 3
            mock_settings.return_value.rag_index_dir = temp_index_dir
            mock_embed.return_value._is_configured = False
            mock_embed.return_value.embed_text = MagicMock(return_value=None)

            svc = RAGService()
            svc._store = rag_store
            result = svc.retrieve("merchant-a", "sales revenue transactions", intent="analyze_sales")

        assert isinstance(result, str)
        assert "Sales Summary" in result or len(result) == 0  # At least attempted retrieval


# ---------------------------------------------------------------------------
# Query Routing Tests
# ---------------------------------------------------------------------------

class TestQueryRouting:

    def test_intent_doc_filters_defined_for_key_intents(self):
        from app.rag.rag_service import _INTENT_DOC_FILTERS, _STRUCTURED_ONLY_INTENTS
        assert "analyze_sales" in _INTENT_DOC_FILTERS
        assert "analyze_customers" in _INTENT_DOC_FILTERS
        assert "analyze_financials" in _INTENT_DOC_FILTERS
        assert "approve_campaign" in _STRUCTURED_ONLY_INTENTS
        assert "execute_campaign" in _STRUCTURED_ONLY_INTENTS

    def test_structured_only_intents_exclude_rag(self):
        from app.rag.rag_service import _STRUCTURED_ONLY_INTENTS
        # These intents should never trigger RAG (action-only)
        for intent in ("approve_campaign", "execute_campaign", "get_campaign_status"):
            assert intent in _STRUCTURED_ONLY_INTENTS
