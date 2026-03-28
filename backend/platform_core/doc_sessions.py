from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    import app.plugins.rag as rag
except ImportError:
    import app.plugins.rag as rag

from .config import settings


@dataclass
class DocumentSessionState:
    documents: list[dict[str, Any]] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    embeddings: list[list[float]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=settings.document_session_ttl_hours)
    )


def _dot_product(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _magnitude(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector)) or 1.0


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    return _dot_product(left, right) / (_magnitude(left) * _magnitude(right))


class DocumentSessionStore:
    def __init__(self):
        self._sessions: dict[str, DocumentSessionState] = {}

    def cleanup_expired(self) -> None:
        now = datetime.now(timezone.utc)
        for session_id, state in list(self._sessions.items()):
            if state.expires_at <= now:
                self._sessions.pop(session_id, None)

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list_documents(self, session_id: str) -> list[dict[str, Any]]:
        self.cleanup_expired()
        state = self._sessions.get(session_id)
        if not state:
            return []
        return list(state.documents)

    def ingest_text(self, session_id: str, filename: str, text: str) -> dict[str, Any]:
        self.cleanup_expired()
        if not session_id:
            raise ValueError("session_id is required")
        if not text.strip():
            raise ValueError("No extractable text was found in the uploaded file")

        state = self._sessions.setdefault(session_id, DocumentSessionState())
        chunks = rag.chunk_text(text)
        if not chunks:
            raise ValueError("The uploaded file did not produce any searchable chunks")

        embeddings = rag.get_embeddings_batch(chunks)
        start_index = len(state.chunks)
        for local_index, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            state.chunks.append(
                {
                    "filename": filename,
                    "chunk_index": start_index + local_index,
                    "content": chunk_text,
                }
            )
            state.embeddings.append(embedding)

        state.documents.append(
            {
                "filename": filename,
                "chunk_count": len(chunks),
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        state.expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.document_session_ttl_hours)
        return {
            "filename": filename,
            "chunk_count": len(chunks),
            "document_count": len(state.documents),
            "expires_at": state.expires_at.isoformat(),
        }

    def search(self, session_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        self.cleanup_expired()
        state = self._sessions.get(session_id)
        if not state or not state.chunks:
            return []

        query_embedding = rag.get_embedding(query)
        scored_hits = []
        for chunk, embedding in zip(state.chunks, state.embeddings):
            scored_hits.append(
                {
                    **chunk,
                    "score": round(_cosine_similarity(query_embedding, embedding), 4),
                }
            )

        scored_hits.sort(key=lambda item: item["score"], reverse=True)
        return scored_hits[:top_k]

    def get_chunks(self, session_id: str, limit: int = 5, filename: Optional[str] = None) -> list[dict[str, Any]]:
        self.cleanup_expired()
        state = self._sessions.get(session_id)
        if not state or not state.chunks:
            return []
        
        chunks = state.chunks
        if filename:
            chunks = [c for c in chunks if c.get("filename") == filename]
            
        return list(chunks[: max(1, limit)])


    def get_session_documents(self, session_id: str) -> list[dict[str, Any]]:
        self.cleanup_expired()
        state = self._sessions.get(session_id)
        if not state:
            return []
        return list(state.documents)


document_session_store = DocumentSessionStore()
