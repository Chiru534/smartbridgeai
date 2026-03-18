"""
PDF text extraction and cleaning module.

Extracts text from PDFs using PyMuPDF, cleans noise (headers, footers, page numbers),
and preserves section structure using font-size heuristics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

import fitz  # PyMuPDF


@dataclass
class Section:
    """A document section with an optional heading and body text."""
    heading: Optional[str] = None
    body: str = ""
    page_start: int = 0
    page_end: int = 0


@dataclass
class LoaderResult:
    """Result of PDF loading and cleaning."""
    raw_text: str = ""
    cleaned_text: str = ""
    sections: List[Section] = field(default_factory=list)
    page_count: int = 0
    word_count: int = 0
    error: Optional[str] = None


# Patterns for common header/footer noise
_NOISE_PATTERNS = [
    re.compile(r"^\s*Page\s+\d+\s*(of\s+\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),                       # Standalone page numbers
    re.compile(r"^\s*-\s*\d+\s*-\s*$"),                # Dashed page numbers
    re.compile(r"^\s*©.*$", re.IGNORECASE),            # Copyright lines
    re.compile(r"^\s*(confidential|draft|internal)\s*$", re.IGNORECASE),
    re.compile(r"^\s*https?://\S+\s*$"),               # Standalone URLs
]


def _is_noise_line(line: str) -> bool:
    """Check if a line is likely a header, footer, or page number."""
    stripped = line.strip()
    if not stripped:
        return True
    if len(stripped) <= 3 and stripped.isdigit():
        return True
    return any(pattern.match(stripped) for pattern in _NOISE_PATTERNS)


def _clean_text(raw_text: str) -> str:
    """Remove noise lines and normalize whitespace."""
    lines = raw_text.split("\n")
    cleaned_lines = []
    for line in lines:
        if _is_noise_line(line):
            continue
        # Normalize internal whitespace but preserve line breaks
        cleaned = re.sub(r"[ \t]+", " ", line).strip()
        if cleaned:
            cleaned_lines.append(cleaned)
    # Collapse multiple blank lines
    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _extract_sections_with_font_heuristics(doc: fitz.Document) -> List[Section]:
    """
    Extract sections by detecting headings based on font size.
    Text blocks with font size significantly larger than the median
    are treated as section headings.
    """
    # Collect all text spans with their font sizes
    all_spans = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        for block in blocks:
            if block.get("type") != 0:  # Skip non-text blocks (images, etc.)
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        all_spans.append({
                            "text": text,
                            "size": round(span.get("size", 12), 1),
                            "page": page_num,
                            "flags": span.get("flags", 0),
                        })

    if not all_spans:
        return []

    # Determine median font size
    sizes = sorted(s["size"] for s in all_spans)
    median_size = sizes[len(sizes) // 2] if sizes else 12.0
    heading_threshold = median_size * 1.2  # 20% larger than median = heading

    sections: List[Section] = []
    current_section = Section(heading=None, page_start=0)
    body_parts: list[str] = []

    for span in all_spans:
        is_heading = (
            span["size"] >= heading_threshold
            and len(span["text"]) < 200  # Headings are short
            and not _is_noise_line(span["text"])
        )

        if is_heading:
            # Close previous section
            if body_parts or current_section.heading:
                current_section.body = _clean_text("\n".join(body_parts))
                current_section.page_end = span["page"]
                if current_section.body or current_section.heading:
                    sections.append(current_section)

            # Start new section
            current_section = Section(
                heading=span["text"].strip(),
                page_start=span["page"],
            )
            body_parts = []
        else:
            body_parts.append(span["text"])

    # Close final section
    if body_parts or current_section.heading:
        current_section.body = _clean_text("\n".join(body_parts))
        current_section.page_end = len(doc) - 1
        if current_section.body or current_section.heading:
            sections.append(current_section)

    return sections


def load_pdf(file_path: str) -> LoaderResult:
    """
    Load a PDF, extract text, clean it, and identify sections.

    Args:
        file_path: Path to the PDF file.

    Returns:
        LoaderResult with raw text, cleaned text, sections, and metadata.
    """
    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        return LoaderResult(error=f"Failed to open PDF: {exc}")

    if doc.page_count == 0:
        doc.close()
        return LoaderResult(error="PDF has no pages")

    # Extract raw text page by page
    raw_pages = []
    for page in doc:
        raw_pages.append(page.get_text())
    raw_text = "\n".join(raw_pages)

    if not raw_text.strip():
        doc.close()
        return LoaderResult(
            page_count=doc.page_count,
            error="No extractable text found in PDF (may be scanned/image-based)",
        )

    cleaned_text = _clean_text(raw_text)

    # Try section extraction
    try:
        sections = _extract_sections_with_font_heuristics(doc)
    except Exception:
        sections = []

    # If no sections detected, create one big section
    if not sections:
        sections = [Section(heading=None, body=cleaned_text, page_start=0, page_end=doc.page_count - 1)]

    word_count = len(cleaned_text.split())
    page_count = doc.page_count
    doc.close()

    return LoaderResult(
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        sections=sections,
        page_count=page_count,
        word_count=word_count,
    )
