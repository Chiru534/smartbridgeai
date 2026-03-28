import fitz
import docx
from sentence_transformers import SentenceTransformer
import warnings
import os
from typing import Optional

try:
    from backend.platform_core.config import settings
except ImportError:
    from platform_core.config import settings

warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
except Exception:
    QdrantClient = None
    qmodels = None

# Load model lazily
_model = None
def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embeddings_model)
    return _model

def extract_text(file_path: str, filename: str) -> str:
    text = ""
    try:
        if filename.lower().endswith(".pdf"):
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text() + "\n"
        elif filename.lower().endswith(".docx"):
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif filename.lower().endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
    except Exception as e:
        print(f"Error extracting text from {filename}: {e}")
    return text

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def get_embedding(text: str) -> list[float]:
    model = get_model()
    return model.encode(text, normalize_embeddings=True).tolist()

def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    model = get_model()
    return [emb.tolist() for emb in model.encode(texts, normalize_embeddings=True)]

_qdrant_client = None
_qdrant_ready = None


def qdrant_settings() -> dict:
    return {
        "url": settings.qdrant_url,
        "path": settings.qdrant_path,
        "api_key": settings.qdrant_api_key or None,
        "collection": settings.qdrant_collection,
    }


def is_qdrant_enabled() -> bool:
    cfg = qdrant_settings()
    return QdrantClient is not None and bool(cfg["url"] or cfg["path"])


def get_qdrant_client() -> Optional["QdrantClient"]:
    global _qdrant_client
    cfg = qdrant_settings()
    if QdrantClient is None:
        return None
    if _qdrant_client is None:
        # Prefer remote service when URL is configured; otherwise use embedded local store.
        if cfg["url"]:
            _qdrant_client = QdrantClient(url=cfg["url"], api_key=cfg["api_key"], timeout=10)
        else:
            _qdrant_client = QdrantClient(path=cfg["path"])
    return _qdrant_client


def validate_qdrant_connection(vector_size: int = 384) -> bool:
    client = get_qdrant_client()
    if client is None:
        return False
    return ensure_qdrant_collection(vector_size=vector_size)


def ensure_qdrant_collection(vector_size: int) -> bool:
    global _qdrant_ready
    if _qdrant_ready is True:
        return True

    client = get_qdrant_client()
    if client is None or qmodels is None:
        return False

    cfg = qdrant_settings()
    collection = cfg["collection"]
    try:
        exists = False
        if hasattr(client, "collection_exists"):
            exists = client.collection_exists(collection)
        else:
            collections = client.get_collections()
            exists = any(col.name == collection for col in collections.collections)

        if not exists:
            client.create_collection(
                collection_name=collection,
                vectors_config=qmodels.VectorParams(
                    size=vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )
        _qdrant_ready = True
        return True
    except Exception as exc:
        print(f"Qdrant collection init failed: {exc}")
        _qdrant_ready = False
        return False


def upsert_chunks_to_qdrant(document_id: int, chunks: list[str], embeddings: list[list[float]]) -> bool:
    if not chunks or not embeddings:
        return False
    if len(chunks) != len(embeddings):
        return False

    client = get_qdrant_client()
    if client is None or qmodels is None:
        return False
    if not ensure_qdrant_collection(vector_size=len(embeddings[0])):
        return False

    cfg = qdrant_settings()
    try:
        points = []
        for idx, (content, emb) in enumerate(zip(chunks, embeddings)):
            points.append(
                qmodels.PointStruct(
                    id=f"{document_id}:{idx}",
                    vector=emb,
                    payload={
                        "document_id": document_id,
                        "chunk_index": idx,
                        "content": content,
                    },
                )
            )

        client.upsert(collection_name=cfg["collection"], points=points, wait=False)
        return True
    except Exception as exc:
        print(f"Qdrant upsert failed: {exc}")
        return False


def delete_chunks_from_qdrant(document_id: int) -> bool:
    client = get_qdrant_client()
    if client is None or qmodels is None:
        return False

    cfg = qdrant_settings()
    try:
        selector = qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=document_id),
                    )
                ]
            )
        )
        client.delete(collection_name=cfg["collection"], points_selector=selector, wait=False)
        return True
    except Exception as exc:
        print(f"Qdrant delete failed: {exc}")
        return False


def retrieve_relevant_chunk_records(query: str, top_k: int = 3) -> list[dict]:
    client = get_qdrant_client()
    if client is None:
        return []

    cfg = qdrant_settings()
    try:
        query_emb = get_embedding(query)
        results = client.search(
            collection_name=cfg["collection"],
            query_vector=query_emb,
            limit=top_k,
            with_payload=True,
            score_threshold=0.25,
        )

        chunks = []
        for hit in results:
            payload = getattr(hit, "payload", None) or {}
            content = payload.get("content")
            if content:
                chunks.append(
                    {
                        "document_id": payload.get("document_id"),
                        "chunk_index": payload.get("chunk_index"),
                        "content": content,
                        "score": round(float(getattr(hit, "score", 0.0) or 0.0), 4),
                    }
                )
        return chunks
    except Exception as exc:
        print(f"Qdrant search failed: {exc}")
        return []


def retrieve_relevant_chunks(query: str, top_k: int = 3) -> list[str]:
    if not is_qdrant_enabled():
        print("Qdrant is not configured. Skipping RAG retrieval.")
        return []

    return [item["content"] for item in retrieve_relevant_chunk_records(query, top_k=top_k)]
