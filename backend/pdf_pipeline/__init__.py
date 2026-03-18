"""
PDF Summarization Pipeline — Hierarchical + Parallel + RAG

Entry point: summarize_large_pdf(file_path, model=None)

Pipeline flow:
    PDF → Loader → Chunker → Parallel Summarizer → Tree Merge → Refiner → Output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .loader import LoaderResult, load_pdf
from .chunker import Chunk, chunk_sections, chunk_text
from .embedder import embed_texts
from .retriever import DocumentRetriever
from .summarizer import ChunkSummary, summarize_chunks_parallel
from .merger import merge_summaries_hierarchical
from .refiner import refine_summary


@dataclass
class PipelineResult:
    """Complete result from the PDF summarization pipeline."""
    summary: str = ""
    page_count: int = 0
    word_count: int = 0
    chunk_count: int = 0
    success: bool = True
    error: Optional[str] = None
    chunk_summaries: List[str] = field(default_factory=list)
    retriever: Optional[DocumentRetriever] = None


async def summarize_large_pdf(
    file_path: str,
    model: Optional[str] = None,
    max_workers: int = 4,
    timeout_seconds: float = 120.0,
) -> PipelineResult:
    """
    Summarize a PDF using the full hierarchical pipeline.

    Pipeline: Load → Chunk → Parallel Summarize → Tree Merge → Refine

    Args:
        file_path: Absolute path to the PDF file.
        model: LLM model name (uses default from config if None).
        max_workers: Max concurrent LLM calls for summarization.
        timeout_seconds: Timeout per individual LLM call.

    Returns:
        PipelineResult with the structured summary and metadata.
    """
    # Step 1: Load and clean the PDF
    loader_result: LoaderResult = load_pdf(file_path)

    if loader_result.error:
        return PipelineResult(
            success=False,
            error=loader_result.error,
            page_count=loader_result.page_count,
        )

    if not loader_result.cleaned_text.strip():
        return PipelineResult(
            success=False,
            error="No text could be extracted from the PDF.",
            page_count=loader_result.page_count,
        )

    # Step 2: Chunk the text (section-aware if sections were detected)
    if loader_result.sections and len(loader_result.sections) > 1:
        chunks: List[Chunk] = chunk_sections(loader_result.sections)
    else:
        chunks = chunk_text(loader_result.cleaned_text)

    if not chunks:
        return PipelineResult(
            success=False,
            error="Text was extracted but could not be chunked.",
            page_count=loader_result.page_count,
            word_count=loader_result.word_count,
        )

    # Step 3: Build retriever index (for later QA use)
    retriever = DocumentRetriever()
    try:
        embeddings = embed_texts([c.text for c in chunks])
        retriever.index_chunks(chunks, embeddings)
    except Exception:
        # Retriever is optional — don't fail the pipeline
        retriever = None

    # Step 4: Parallel chunk summarization
    chunk_summaries: List[ChunkSummary] = await summarize_chunks_parallel(
        chunks=chunks,
        model=model,
        max_workers=max_workers,
        timeout_seconds=timeout_seconds,
    )

    # Collect successful summaries
    successful_summaries = [cs.summary for cs in chunk_summaries if cs.success and cs.summary.strip()]

    if not successful_summaries:
        return PipelineResult(
            success=False,
            error="LLM failed to summarize any chunks. Check if Ollama is running.",
            page_count=loader_result.page_count,
            word_count=loader_result.word_count,
            chunk_count=len(chunks),
        )

    # Step 5: Hierarchical merge
    merged_summary = await merge_summaries_hierarchical(
        summaries=successful_summaries,
        model=model,
        timeout_seconds=timeout_seconds,
    )

    # Step 6: Final refinement
    final_summary = await refine_summary(
        merged_summary=merged_summary,
        model=model,
        timeout_seconds=timeout_seconds,
    )

    return PipelineResult(
        summary=final_summary,
        page_count=loader_result.page_count,
        word_count=loader_result.word_count,
        chunk_count=len(chunks),
        success=True,
        chunk_summaries=successful_summaries,
        retriever=retriever,
    )


async def summarize_from_chunks(
    chunks_text: List[str],
    model: Optional[str] = None,
    max_workers: int = 4,
    timeout_seconds: float = 120.0,
) -> PipelineResult:
    """
    Summarize pre-extracted text chunks (from doc_sessions) using the pipeline.

    This is used when the original PDF file is no longer available
    (temp files are deleted after upload in main.py).

    Args:
        chunks_text: List of text strings (already chunked by doc_sessions).
        model: LLM model name.
        max_workers: Max concurrent LLM calls.
        timeout_seconds: Timeout per LLM call.

    Returns:
        PipelineResult with the structured summary.
    """
    if not chunks_text:
        return PipelineResult(success=False, error="No text chunks provided.")

    # Convert raw text strings into Chunk objects for the summarizer
    pipeline_chunks = [
        Chunk(index=i, text=text, token_estimate=max(1, len(text) // 4))
        for i, text in enumerate(chunks_text)
        if text.strip()
    ]

    if not pipeline_chunks:
        return PipelineResult(success=False, error="All provided chunks were empty.")

    total_words = sum(len(c.text.split()) for c in pipeline_chunks)

    # Step 1: Parallel chunk summarization
    chunk_summaries: List[ChunkSummary] = await summarize_chunks_parallel(
        chunks=pipeline_chunks,
        model=model,
        max_workers=max_workers,
        timeout_seconds=timeout_seconds,
    )

    successful_summaries = [cs.summary for cs in chunk_summaries if cs.success and cs.summary.strip()]

    if not successful_summaries:
        return PipelineResult(
            success=False,
            error="LLM failed to summarize any chunks. Check if Ollama is running.",
            chunk_count=len(pipeline_chunks),
            word_count=total_words,
        )

    # Step 2: Hierarchical merge
    merged_summary = await merge_summaries_hierarchical(
        summaries=successful_summaries,
        model=model,
        timeout_seconds=timeout_seconds,
    )

    # Step 3: Final refinement
    final_summary = await refine_summary(
        merged_summary=merged_summary,
        model=model,
        timeout_seconds=timeout_seconds,
    )

    return PipelineResult(
        summary=final_summary,
        chunk_count=len(pipeline_chunks),
        word_count=total_words,
        success=True,
        chunk_summaries=successful_summaries,
    )


__all__ = [
    "summarize_large_pdf",
    "summarize_from_chunks",
    "PipelineResult",
    "DocumentRetriever",
]
