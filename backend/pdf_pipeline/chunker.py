"""
Smart token-based text chunking module.

Splits text into chunks of ~800-1200 tokens (estimated as len(text)/4).
Ensures chunks do not break mid-sentence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass
class Chunk:
    """A text chunk with metadata."""
    index: int
    text: str
    token_estimate: int
    section_heading: str | None = None


# Sentence-ending patterns
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _estimate_tokens(text: str) -> int:
    """Estimate token count (~4 characters per token for English text)."""
    return max(1, len(text) // 4)


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences, preserving the sentence text."""
    parts = _SENTENCE_END.split(text)
    sentences = [s.strip() for s in parts if s.strip()]
    return sentences


def chunk_text(
    text: str,
    min_tokens: int = 800,
    max_tokens: int = 1200,
    section_heading: str | None = None,
) -> List[Chunk]:
    """
    Split text into chunks respecting sentence boundaries.

    Each chunk targets min_tokens..max_tokens range.
    Sentences are never split mid-way.

    Args:
        text: The input text to chunk.
        min_tokens: Minimum tokens per chunk (soft target).
        max_tokens: Maximum tokens per chunk (hard limit).
        section_heading: Optional section heading to attach to chunks.

    Returns:
        List of Chunk objects.
    """
    if not text or not text.strip():
        return []

    sentences = _split_into_sentences(text)
    if not sentences:
        # Fall back to the whole text as one chunk
        return [Chunk(index=0, text=text.strip(), token_estimate=_estimate_tokens(text), section_heading=section_heading)]

    chunks: List[Chunk] = []
    current_sentences: List[str] = []
    current_tokens: int = 0

    for sentence in sentences:
        sentence_tokens = _estimate_tokens(sentence)

        # If adding this sentence would exceed max_tokens and we already have content,
        # finalize the current chunk first
        if current_tokens + sentence_tokens > max_tokens and current_sentences:
            chunk_text_str = " ".join(current_sentences)
            chunks.append(Chunk(
                index=len(chunks),
                text=chunk_text_str,
                token_estimate=current_tokens,
                section_heading=section_heading,
            ))
            current_sentences = []
            current_tokens = 0

        current_sentences.append(sentence)
        current_tokens += sentence_tokens

        # If we've reached a comfortable size, finalize
        if current_tokens >= min_tokens:
            chunk_text_str = " ".join(current_sentences)
            chunks.append(Chunk(
                index=len(chunks),
                text=chunk_text_str,
                token_estimate=current_tokens,
                section_heading=section_heading,
            ))
            current_sentences = []
            current_tokens = 0

    # Handle remaining sentences
    if current_sentences:
        chunk_text_str = " ".join(current_sentences)
        # If small leftover and there's a previous chunk, merge into it
        if chunks and current_tokens < min_tokens // 2:
            prev = chunks[-1]
            merged_text = prev.text + " " + chunk_text_str
            chunks[-1] = Chunk(
                index=prev.index,
                text=merged_text,
                token_estimate=prev.token_estimate + current_tokens,
                section_heading=prev.section_heading,
            )
        else:
            chunks.append(Chunk(
                index=len(chunks),
                text=chunk_text_str,
                token_estimate=current_tokens,
                section_heading=section_heading,
            ))

    # Re-index
    for i, chunk in enumerate(chunks):
        chunk.index = i

    return chunks


def chunk_sections(sections: list, min_tokens: int = 800, max_tokens: int = 1200) -> List[Chunk]:
    """
    Chunk multiple sections, preserving section headings in chunk metadata.

    Args:
        sections: List of Section objects (from loader.py).
        min_tokens: Minimum tokens per chunk.
        max_tokens: Maximum tokens per chunk.

    Returns:
        Flat list of Chunk objects with section headings preserved.
    """
    all_chunks: List[Chunk] = []
    for section in sections:
        body = getattr(section, "body", "") or ""
        heading = getattr(section, "heading", None)
        if not body.strip():
            continue

        section_chunks = chunk_text(body, min_tokens=min_tokens, max_tokens=max_tokens, section_heading=heading)
        for chunk in section_chunks:
            chunk.index = len(all_chunks)
            all_chunks.append(chunk)

    return all_chunks
