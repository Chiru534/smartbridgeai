"""
Parallel chunk summarization module.

Summarizes chunks concurrently using asyncio with limited parallelism
to avoid overloading the Ollama server.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, List, Optional

try:
    from backend.llm_client import llm_client
except ImportError:
    from llm_client import llm_client  # type: ignore[import-untyped]


# Default concurrency limiter — prevents Ollama overload
_DEFAULT_MAX_WORKERS = 4

CHUNK_SUMMARIZE_PROMPT = (
    "You are summarizing a section of a larger document. "
    "Capture ALL important information — do not skip details.\n\n"
    "Rules:\n"
    "- List every key fact, concept, question, answer, or data point.\n"
    "- Use 8-12 bullet points to cover the content thoroughly.\n"
    "- If this is an exam/test paper, list the topics and types of questions covered.\n"
    "- If this contains Q&A, summarize each question's topic and the correct answer.\n"
    "- Preserve numbers, names, dates, and specific details.\n"
    "- Do NOT add any preamble — just output bullet points.\n\n"
    "Content:\n{content}"
)


@dataclass
class ChunkSummary:
    """Summary result for a single chunk."""
    chunk_index: int
    summary: str
    section_heading: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


async def _summarize_one_chunk(
    chunk_index: int,
    text: str,
    section_heading: Optional[str],
    model: Optional[str],
    semaphore: asyncio.Semaphore,
    timeout_seconds: float = 120.0,
) -> ChunkSummary:
    """Summarize a single chunk with concurrency control."""
    async with semaphore:
        prompt = CHUNK_SUMMARIZE_PROMPT.format(content=text)
        if section_heading:
            prompt = f"[Section: {section_heading}]\n{prompt}"

        messages = [
            {"role": "system", "content": "You are a precise document summarizer. Output only bullet points."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await llm_client.chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=2048,
                model=model,
                timeout_seconds=timeout_seconds,
            )
            data = response.json()
            reply = data["choices"][0]["message"].get("content", "").strip()
            if not reply:
                return ChunkSummary(
                    chunk_index=chunk_index,
                    summary="",
                    section_heading=section_heading,
                    success=False,
                    error="Empty LLM response",
                )
            return ChunkSummary(
                chunk_index=chunk_index,
                summary=reply,
                section_heading=section_heading,
            )
        except Exception as exc:
            return ChunkSummary(
                chunk_index=chunk_index,
                summary="",
                section_heading=section_heading,
                success=False,
                error=str(exc),
            )


async def summarize_chunks_parallel(
    chunks: list,
    model: Optional[str] = None,
    max_workers: int = _DEFAULT_MAX_WORKERS,
    timeout_seconds: float = 120.0,
) -> List[ChunkSummary]:
    """
    Summarize all chunks in parallel with bounded concurrency.

    Args:
        chunks: List of Chunk objects (from chunker.py).
        model: LLM model name (uses default if None).
        max_workers: Maximum concurrent LLM calls.
        timeout_seconds: Timeout per LLM call.

    Returns:
        List of ChunkSummary objects, ordered by chunk index.
    """
    if not chunks:
        return []

    semaphore = asyncio.Semaphore(max_workers)

    tasks = [
        _summarize_one_chunk(
            chunk_index=chunk.index,
            text=chunk.text,
            section_heading=getattr(chunk, "section_heading", None),
            model=model,
            semaphore=semaphore,
            timeout_seconds=timeout_seconds,
        )
        for chunk in chunks
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    summaries: List[ChunkSummary] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            summaries.append(ChunkSummary(
                chunk_index=i,
                summary="",
                success=False,
                error=str(result),
            ))
        else:
            summaries.append(result)

    # Sort by chunk index to maintain document order
    summaries.sort(key=lambda s: s.chunk_index)
    return summaries
