"""
In-memory vector retrieval module.

Uses FAISS for fast similarity search. Falls back to numpy-based
cosine similarity if FAISS is not installed.

Used for question-answering on specific document parts (NOT for full summarization).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import faiss

    _HAS_FAISS = True
except ImportError:
    faiss = None  # type: ignore[assignment]
    _HAS_FAISS = False

from .embedder import embed_single, embed_texts


@dataclass
class RetrievalHit:
    """A single retrieval result."""
    chunk_index: int
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentRetriever:
    """
    In-memory vector index for document chunks.

    Supports FAISS (preferred) or numpy fallback.
    """

    def __init__(self):
        self._texts: List[str] = []
        self._metadata: List[Dict[str, Any]] = []
        self._embeddings: Optional[np.ndarray] = None
        self._faiss_index: Any = None

    def index_chunks(self, chunks: list, embeddings: Optional[List[List[float]]] = None) -> None:
        """
        Build the vector index from chunks.

        Args:
            chunks: List of Chunk objects (from chunker.py).
            embeddings: Precomputed embeddings. If None, they will be generated.
        """
        self._texts = [c.text for c in chunks]
        self._metadata = [
            {"index": c.index, "section_heading": getattr(c, "section_heading", None)}
            for c in chunks
        ]

        if embeddings is None:
            embeddings = embed_texts(self._texts)

        self._embeddings = np.array(embeddings, dtype=np.float32)

        if _HAS_FAISS and len(self._embeddings) > 0:
            dim = self._embeddings.shape[1]
            self._faiss_index = faiss.IndexFlatIP(dim)  # Inner product (cosine on normalized vectors)
            # Normalize for cosine similarity
            faiss.normalize_L2(self._embeddings)
            self._faiss_index.add(self._embeddings)
        else:
            self._faiss_index = None

    def search(self, query: str, top_k: int = 5) -> List[RetrievalHit]:
        """
        Retrieve the most relevant chunks for a query.

        Args:
            query: Natural language query.
            top_k: Number of results to return.

        Returns:
            List of RetrievalHit sorted by relevance.
        """
        if self._embeddings is None or len(self._texts) == 0:
            return []

        query_emb = np.array(embed_single(query), dtype=np.float32).reshape(1, -1)
        top_k = min(top_k, len(self._texts))

        if self._faiss_index is not None:
            faiss.normalize_L2(query_emb)
            scores, indices = self._faiss_index.search(query_emb, top_k)
            hits = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue
                hits.append(RetrievalHit(
                    chunk_index=int(idx),
                    text=self._texts[idx],
                    score=float(score),
                    metadata=self._metadata[idx],
                ))
            return hits
        else:
            # Numpy fallback: cosine similarity
            return self._numpy_search(query_emb, top_k)

    def _numpy_search(self, query_emb: np.ndarray, top_k: int) -> List[RetrievalHit]:
        """Fallback search using numpy cosine similarity."""
        # Normalize
        query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-10)
        emb_norms = self._embeddings / (np.linalg.norm(self._embeddings, axis=1, keepdims=True) + 1e-10)

        scores = (emb_norms @ query_norm.T).flatten()
        top_indices = np.argsort(scores)[::-1][:top_k]

        hits = []
        for idx in top_indices:
            hits.append(RetrievalHit(
                chunk_index=int(idx),
                text=self._texts[idx],
                score=float(scores[idx]),
                metadata=self._metadata[idx],
            ))
        return hits
