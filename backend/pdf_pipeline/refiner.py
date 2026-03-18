"""
Final summary refinement module.

Takes the merged summary and produces a structured final output
with Overview, Key Points, and Conclusion sections.
"""

from __future__ import annotations

from typing import Optional

try:
    from backend.llm_client import llm_client
except ImportError:
    from llm_client import llm_client  # type: ignore[import-untyped]


REFINE_PROMPT = (
    "Generate a final, well-structured summary from the following merged notes.\n\n"
    "Format the output EXACTLY as:\n\n"
    "## Overview\n"
    "A 3-5 sentence overview describing what this document is about, "
    "its purpose, structure, and scope.\n\n"
    "## Topics Covered\n"
    "List every major topic or subject area found in the document.\n\n"
    "## Key Points\n"
    "- List ALL important details, facts, findings, and conclusions.\n"
    "- Include specific data: numbers, names, dates, answers.\n"
    "- Use 10-20 bullet points for thorough coverage.\n"
    "- If it is an exam paper, mention question types, topics, and difficulty.\n\n"
    "## Conclusion\n"
    "A concise concluding statement.\n\n"
    "Merged notes:\n{merged_summary}"
)


async def refine_summary(
    merged_summary: str,
    model: Optional[str] = None,
    timeout_seconds: float = 120.0,
) -> str:
    """
    Refine a merged summary into a structured final output.

    Args:
        merged_summary: The combined summary from the merger.
        model: LLM model name.
        timeout_seconds: Timeout for the LLM call.

    Returns:
        Refined summary with Overview, Key Points, and Conclusion.
    """
    if not merged_summary or not merged_summary.strip():
        return "No content available to summarize."

    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional document analyst. "
                "Produce clear, structured summaries. "
                "Always use the exact format: Overview, Key Points, Conclusion."
            ),
        },
        {"role": "user", "content": REFINE_PROMPT.format(merged_summary=merged_summary)},
    ]

    try:
        response = await llm_client.chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=4096,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        data = response.json()
        reply = data["choices"][0]["message"].get("content", "").strip()

        if reply:
            return reply

        # If LLM returns empty, format the merged summary as-is
        return _format_fallback(merged_summary)

    except Exception:
        return _format_fallback(merged_summary)


def _format_fallback(merged_summary: str) -> str:
    """Format merged summary as a basic structured output when LLM fails."""
    return (
        "## Overview\n"
        "The document contains the following information:\n\n"
        "## Key Points\n"
        f"{merged_summary}\n\n"
        "## Conclusion\n"
        "Please refer to the key points above for the document's main content."
    )
