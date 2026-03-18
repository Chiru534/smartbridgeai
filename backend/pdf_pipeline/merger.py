"""
Hierarchical tree-based summary merging module.

Merges chunk summaries bottom-up in balanced pairs/triples to
avoid passing too many summaries to the LLM at once.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

try:
    from backend.llm_client import llm_client
except ImportError:
    from llm_client import llm_client  # type: ignore[import-untyped]


MERGE_PROMPT = (
    "You are merging partial summaries of the same document into one combined summary. "
    "Preserve ALL important details — do not over-compress.\n\n"
    "Rules:\n"
    "- Keep every distinct fact, topic, question, answer, or data point.\n"
    "- Remove only exact duplicates.\n"
    "- Group related points together under topic headings if possible.\n"
    "- Use bullet points for each piece of information.\n"
    "- Do NOT add commentary — just merge the summaries.\n\n"
    "Summaries to merge:\n{summaries}"
)

# Maximum summaries to merge in one LLM call
_MERGE_GROUP_SIZE = 4


async def _merge_group(
    summaries: List[str],
    model: Optional[str],
    timeout_seconds: float = 120.0,
) -> str:
    """Merge a small group of summaries into one via LLM."""
    combined = "\n\n---\n\n".join(summaries)
    messages = [
        {"role": "system", "content": "You are a precise document summarizer. Merge summaries accurately."},
        {"role": "user", "content": MERGE_PROMPT.format(summaries=combined)},
    ]

    try:
        response = await llm_client.chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        data = response.json()
        reply = data["choices"][0]["message"].get("content", "").strip()
        return reply if reply else "\n".join(summaries)
    except Exception:
        # On failure, concatenate rather than lose data
        return "\n".join(summaries)


async def merge_summaries_hierarchical(
    summaries: List[str],
    model: Optional[str] = None,
    group_size: int = _MERGE_GROUP_SIZE,
    timeout_seconds: float = 120.0,
) -> str:
    """
    Merge summaries using a tree-based hierarchical approach.

    Summaries are grouped into batches of `group_size`, each group is merged
    by the LLM, and the process repeats until a single summary remains.

    Args:
        summaries: List of summary strings from chunk summarization.
        model: LLM model name.
        group_size: How many summaries to merge at once (default 4).
        timeout_seconds: Timeout per LLM call.

    Returns:
        Single merged summary string.
    """
    if not summaries:
        return ""

    # Filter out empty summaries
    current_level = [s for s in summaries if s.strip()]
    if not current_level:
        return ""

    # If only one summary, return it directly
    if len(current_level) == 1:
        return current_level[0]

    # Tree reduction: keep merging until one summary remains
    level = 0
    while len(current_level) > 1:
        level += 1
        groups = []
        for i in range(0, len(current_level), group_size):
            group = current_level[i : i + group_size]
            groups.append(group)

        # Merge groups sequentially to avoid Ollama overload during merge phase
        # (parallel summarization already handles the heavy lifting)
        next_level = []
        for group in groups:
            if len(group) == 1:
                next_level.append(group[0])
            else:
                merged = await _merge_group(group, model, timeout_seconds)
                next_level.append(merged)

        current_level = next_level

        # Safety: prevent infinite loops
        if level > 10:
            break

    return current_level[0] if current_level else ""
