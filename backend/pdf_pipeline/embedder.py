"""
Embedding generation module.

Reuses the existing sentence-transformers model from rag.py.
Provides batch embedding for chunks.
"""

from __future__ import annotations

from typing import List

# Reuse the existing embedding infrastructure
try:
    import app.plugins.rag as rag
except ImportError:
    import app.plugins.rag as rag  # type: ignore[import-untyped]


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using the existing model.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of embedding vectors.
    """
    if not texts:
        return []
    return rag.get_embeddings_batch(texts)


def embed_single(text: str) -> List[float]:
    """
    Generate embedding for a single text.

    Args:
        text: Text to embed.

    Returns:
        Embedding vector.
    """
    return rag.get_embedding(text)
