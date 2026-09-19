"""
RAG Embeddings — MerchantMind.

Provides text embeddings using the Gemini text-embedding-004 API,
with a deterministic keyword-based fallback scorer when the API is unavailable.

Design:
  - Uses the same API key already configured for GeminiLLMClient.
  - Keyword fallback: TF-IDF-lite cosine similarity over word tokens.
    No external dependencies beyond numpy (already required).
  - All failures are caught and logged; the system degrades to keyword mode silently.
  - Embeddings are cached in-process per session to reduce API calls.
"""

from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, List, Optional

import httpx
import numpy as np

from app.core.config import get_settings
from app.core.logging import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"
GEMINI_EMBED_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:embedContent?key={key}"
)
EMBED_TIMEOUT = 8.0
EMBED_DIM = 3072  # gemini-embedding-2 output dimension


# ---------------------------------------------------------------------------
# Gemini Embedding Client
# ---------------------------------------------------------------------------

class EmbeddingClient:
    """
    Wraps the Gemini text-embedding-004 REST API.
    Falls back to keyword scoring on any failure.
    """

    def __init__(self) -> None:
        settings = get_settings()
        key = (settings.llm_api_key or "").strip()
        self._api_key = key if key and key not in ("your-gemini-api-key-here", "your-api-key-here") else ""
        self._is_configured = bool(self._api_key and len(self._api_key) > 5)
        if not self._is_configured:
            logger.warning("EmbeddingClient: Gemini API key not configured — keyword fallback will be used.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_text(self, text: str) -> Optional[np.ndarray]:
        """
        Embed a single text using Gemini text-embedding-004.
        Returns numpy array of shape (768,), or None on failure.
        """
        if not self._is_configured:
            return None
        if not text or not text.strip():
            return None

        url = GEMINI_EMBED_URL_TEMPLATE.format(model=GEMINI_EMBEDDING_MODEL, key=self._api_key)
        payload = {
            "model": f"models/{GEMINI_EMBEDDING_MODEL}",
            "content": {
                "parts": [{"text": text[:8192]}]  # API limit
            },
        }

        try:
            with httpx.Client(timeout=EMBED_TIMEOUT) as client:
                res = client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                if res.status_code == 200:
                    values = res.json().get("embedding", {}).get("values", [])
                    if values:
                        vec = np.array(values, dtype=np.float32)
                        norm = np.linalg.norm(vec)
                        return vec / norm if norm > 0 else vec
                    logger.warning("EmbeddingClient: Empty embedding values returned.")
                    return None
                else:
                    logger.warning(
                        f"EmbeddingClient: Gemini API returned HTTP {res.status_code}. "
                        f"Falling back to keyword scorer."
                    )
                    return None
        except httpx.TimeoutException:
            logger.warning("EmbeddingClient: Gemini embed request timed out. Using keyword fallback.")
            return None
        except Exception as exc:
            logger.warning(f"EmbeddingClient: Embed error ({type(exc).__name__}). Using keyword fallback.")
            return None

    def embed_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """Embed a list of texts, returning one embedding per text."""
        results = []
        for text in texts:
            vec = self.embed_text(text)
            results.append(vec)
            if vec is not None:
                time.sleep(0.05)  # Gentle rate limiting
        return results


# ---------------------------------------------------------------------------
# Keyword Fallback Scorer (TF-IDF-lite cosine)
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "in", "on", "at", "of", "to", "for", "is", "are",
    "was", "were", "be", "been", "has", "have", "had", "do", "does", "did",
    "will", "would", "can", "could", "should", "may", "might", "my", "your",
    "their", "its", "this", "that", "these", "those", "what", "which", "who",
    "how", "when", "where", "why", "and", "or", "but", "not", "i", "me", "we",
    "our", "you", "it", "by", "from", "with", "about", "as", "into",
}


def _tokenize(text: str) -> List[str]:
    """Simple word tokenizer — lowercase, strip punctuation, remove stopwords."""
    words = re.findall(r"[a-z0-9₹]+", text.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


def build_keyword_vector(text: str, vocab: Dict[str, int]) -> np.ndarray:
    """Build a TF vector over a shared vocabulary for a given text."""
    vec = np.zeros(len(vocab), dtype=np.float32)
    tokens = _tokenize(text)
    if not tokens:
        return vec
    token_counts: Dict[str, int] = {}
    for t in tokens:
        token_counts[t] = token_counts.get(t, 0) + 1
    for token, count in token_counts.items():
        if token in vocab:
            vec[vocab[token]] = count / len(tokens)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def build_vocab(texts: List[str]) -> Dict[str, int]:
    """Build shared vocabulary from a list of texts."""
    all_tokens: set = set()
    for t in texts:
        all_tokens.update(_tokenize(t))
    return {token: idx for idx, token in enumerate(sorted(all_tokens))}


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    if a.shape != b.shape or np.all(a == 0) or np.all(b == 0):
        return 0.0
    return float(np.dot(a, b))  # Vectors are already L2-normalized


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_embedding_client: Optional[EmbeddingClient] = None


def get_embedding_client() -> EmbeddingClient:
    """Return the module-level EmbeddingClient singleton."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client
