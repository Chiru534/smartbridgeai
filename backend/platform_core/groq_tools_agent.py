from __future__ import annotations

import json
import re
from typing import Any

from .config import settings
from .doc_sessions import document_session_store
from .tool_registry import ToolExecutionContext, tool_registry
from .workspaces import get_workspace, normalize_workspace_id

# PDF summarization pipeline (new module)
try:
    from pdf_pipeline import summarize_from_chunks
except ImportError:
    try:
        from backend.pdf_pipeline import summarize_from_chunks
    except ImportError:
        summarize_from_chunks = None  # type: ignore[assignment]

try:
    from backend.llm_client import llm_client
except ImportError:
    from llm_client import llm_client


def _build_system_prompt(base_system_prompt: str, mode: str) -> str:
    workspace = get_workspace(mode)
    return (
        f"{workspace.system_prompt}\n\n"
        "### Tool Usage Guidelines ###\n"
        "You MUST use tools to access external data. Never guess or hallucinate information.\n\n"
        "#### Repository and File Operations:\n"
        "- Use `github_list_my_repositories` ONLY when the user explicitly asks for a list of their repositories (e.g., 'show my repos' or 'list repositories').\n"
        "- For any file or folder browsing: Use `github_list_directory` with owner='Chiru534', repo='project_agent', and the appropriate path.\n"
        "- For reading file contents: Use `github_get_file` with the full path (e.g., 'backend/main.py').\n"
        "- If the user mentions a file name without a path, assume it's in the most recently listed directory from the conversation history.\n"
        "- Always provide explicit owner and repo arguments; do not omit them.\n\n"
        "#### Parameter Defaults:\n"
        "- Default owner: 'Chiru534'\n"
        "- Default repo: 'project_agent'\n"
        "- Use these unless the user specifies different values.\n\n"
        "#### Response Rules:\n"
        "- Ground answers in tool-returned evidence.\n"
        "- Be concise and direct.\n"
        "- When asked for a 'summary', 'summarize', or 'key points' of a file or code, output ONLY a concise summary (3-8 bullet points). Never output complete raw contents or full files.\n"
        "- If uncertain, state it clearly.\n"
        "- Avoid redundant tool calls.\n\n"
        f"{base_system_prompt}"
    )


def _serialize_tool_call(tool_call: Any) -> dict[str, Any]:
    if isinstance(tool_call, dict):
        fn = tool_call.get("function") or {}
        return {
            "id": tool_call.get("id", ""),
            "type": "function",
            "function": {
                "name": fn.get("name", ""),
                "arguments": fn.get("arguments", "{}"),
            },
        }
    return {
        "id": getattr(tool_call, "id", ""),
        "type": "function",
        "function": {
            "name": getattr(getattr(tool_call, "function", None), "name", ""),
            "arguments": getattr(getattr(tool_call, "function", None), "arguments", "") or "{}",
        },
    }


def _dedupe_citations(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique_items = []
    seen = set()
    for item in items:
        key = json.dumps(item, sort_keys=True, ensure_ascii=True)
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
    return unique_items


def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and message.get("content"):
            return str(message["content"]).strip()
    return ""


def _document_context_for_query(session_id: str, query: str, top_k: int = 15) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hits = document_session_store.search(session_id, query, top_k=top_k) if query else []
    if not hits:
        hits = document_session_store.get_chunks(session_id, limit=top_k)
    citations = [
        {
            "source_type": "document_session",
            "label": hit.get("filename"),
            "document_id": None,
            "chunk_index": hit.get("chunk_index"),
            "score": hit.get("score"),
        }
        for hit in hits
    ]
    return hits, citations


def _collect_document_sentences(hits: list[dict[str, Any]], limit: int = 5) -> list[str]:
    sentences: list[str] = []
    seen = set()
    for hit in hits:
        content = re.sub(r"\s+", " ", str(hit.get("content") or "")).strip()
        if not content:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", content):
            cleaned = sentence.strip()
            if not cleaned:
                continue
            normalized = cleaned.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            sentences.append(cleaned)
            if len(sentences) >= limit:
                break
        if len(sentences) >= limit:
            break
    return sentences


def _extractive_document_fallback(hits: list[dict[str, Any]]) -> str:
    sentences = _collect_document_sentences(hits, limit=5)

    if not sentences:
        return "I found the uploaded document, but I could not extract enough readable text to answer from it."

    return "\n".join(f"- {sentence}" for sentence in sentences[:5])


def _is_summary_request(query: str) -> bool:
    normalized = (query or "").strip().lower()
    return any(token in normalized for token in ("summary", "summarize", "key points", "overview", "gist"))


def _extractive_document_summary(hits: list[dict[str, Any]]) -> str:
    sentences = _collect_document_sentences(hits, limit=5)
    if not sentences:
        return "I found the uploaded document, but I could not extract enough readable text to summarize it."
    return "\n".join(f"- {sentence}" for sentence in sentences)


async def _run_document_analysis_chat(
    request: Any,
    latest_user_text: str,
    base_system_prompt: str,
    ctx: ToolExecutionContext,
    mode: str,
) -> dict[str, Any]:
    session_id = str(ctx.workspace_options.get("document_session_id") or ctx.session_id or "").strip()
    
    # Identify target document if mentioned, otherwise use most recent
    docs = document_session_store.get_session_documents(session_id)
    target_filename = None
    if docs:
        for doc in docs:
            fname = doc.get("filename", "")
            if fname.lower() in latest_user_text.lower():
                target_filename = fname
                break
        if not target_filename:
            target_filename = docs[-1].get("filename") # Default to most recent

    hits, citations = _document_context_for_query(session_id, latest_user_text, top_k=15)

    if not hits:
        return {
            "reply": "I couldn't find any uploaded session document content for this request. Upload a file and try again.",
            "mode": mode,
            "citations": [],
            "tool_events": ctx.tool_events,
        }

    ctx.add_citations(citations)

    # --- Pipeline path: use hierarchical summarization for summary requests ---
    if _is_summary_request(latest_user_text) and summarize_from_chunks is not None:
        # Filter chunks by target filename to avoid mixing unrelated files
        all_chunks = document_session_store.get_chunks(session_id, limit=500, filename=target_filename)
        chunk_texts = [str(c.get("content") or "") for c in all_chunks if c.get("content")]

        if chunk_texts:
            # OPTIMIZATION: "Quick Summary" path (match Drive agent performance)
            # Use first 8 chunks (~8k tokens) for a fast summary if not explicitly asking for "full/deep"
            is_deep = any(word in latest_user_text.lower() for word in ("full", "complete", "deep", "entire", "all pages"))
            
            if not is_deep and len(chunk_texts) > 8:
                quick_context = "\n\n---\n\n".join(chunk_texts[:8])
                try:
                    quick_prompt = (
                        f"Summarize the file '{target_filename}' based on this representative preview (first few sections):\n\n"
                        f"{quick_context}\n\n"
                        "Provide a structured summary (Overview, Key Themes, Key Points). "
                        "Note if this is a partial preview."
                    )
                    resp = await llm_client.chat_completion(
                        messages=[{"role": "user", "content": quick_prompt}],
                        temperature=0.2,
                        max_tokens=2048,
                        model=getattr(request, "model", None),
                        timeout_seconds=60.0,
                    )
                    data = resp.json()
                    summary = data["choices"][0]["message"].get("content") or ""
                    if summary:
                        return {
                            "reply": f"{summary}\n\n*Note: This is a fast summary of the document's initial sections. For a full analysis of all {len(chunk_texts)} chunks, ask for a 'complete summary'.*",
                            "mode": mode,
                            "citations": _dedupe_citations(ctx.citations),
                            "tool_events": ctx.tool_events,
                        }
                except Exception:
                    pass # Fall back to full pipeline or LLM fallback

            # Full Pipeline
            try:
                pipeline_result = await summarize_from_chunks(
                    chunks_text=chunk_texts,
                    model=getattr(request, "model", None),
                    max_workers=4,
                    timeout_seconds=120.0,
                )
                if pipeline_result.success and pipeline_result.summary.strip():
                    return {
                        "reply": pipeline_result.summary,
                        "mode": mode,
                        "citations": _dedupe_citations(ctx.citations),
                        "tool_events": ctx.tool_events,
                    }
            except Exception:
                pass  # Fall through to LLM fallback below

    # --- LLM fallback path: send document excerpts to LLM directly ---
    context_lines = []
    # If a specific filename was targeted, prioritize hits from that file
    filtered_hits = [h for h in hits if not target_filename or h.get("filename") == target_filename]
    if not filtered_hits: filtered_hits = hits

    for hit in filtered_hits:
        chunk_index = hit.get("chunk_index")
        label = hit.get("filename") or "session document"
        content_snippet = re.sub(r"\s+", " ", str(hit.get("content") or "")).strip()
        context_lines.append(f"[{label}#{chunk_index}] {content_snippet}")

    fallback_messages = [
        {
            "role": "system",
            "content": (
                "You are in Document Analysis mode. Answer only from the provided uploaded document excerpts. "
                "Do not mention repositories, GitHub, or Google Drive. "
                "If the user asks for a summary, provide a well-structured summary with Overview, Topics Covered, Key Points, and Conclusion.\n\n"
                f"{base_system_prompt}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"User request (File: {target_filename}):\n{latest_user_text or 'Summarize the uploaded document.'}\n\n"
                "Uploaded document excerpts:\n"
                + "\n\n".join(context_lines)
            ),
        },
    ]

    try:
        fallback_resp = await llm_client.chat_completion(
            messages=fallback_messages,
            temperature=0.2,
            max_tokens=2048,
            model=getattr(request, "model", None),
            timeout_seconds=120.0,
        )
        fallback_data = fallback_resp.json()
        fallback_reply = fallback_data["choices"][0]["message"].get("content") or ""
        if fallback_reply.strip():
            return {
                "reply": fallback_reply,
                "mode": mode,
                "citations": _dedupe_citations(ctx.citations),
                "tool_events": ctx.tool_events,
            }
    except Exception:
        pass

    # --- Extractive fallback (last resort) ---
    return {
        "reply": _extractive_document_fallback(filtered_hits),
        "mode": mode,
        "citations": _dedupe_citations(ctx.citations),
        "tool_events": ctx.tool_events,
    }


async def run_workspace_chat(
    request: Any,
    base_system_prompt: str,
    ctx: ToolExecutionContext,
) -> dict[str, Any]:
    mode = normalize_workspace_id(getattr(request, "mode", None))
    messages: list[dict[str, Any]] = [{"role": "system", "content": _build_system_prompt(base_system_prompt, mode)}]
    messages.extend([message.model_dump() if hasattr(message, "model_dump") else dict(message) for message in request.messages])
    latest_user_text = _latest_user_text(messages)

    if mode == "document_analysis":
        return await _run_document_analysis_chat(request, latest_user_text, base_system_prompt, ctx, mode)

    tools = await tool_registry.openai_tools_for_mode(mode)

    max_steps = 6
    for _ in range(max_steps):
        resp = await llm_client.chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=8192,
            tools=tools or None,
            tool_choice="auto" if tools else None,
            model=getattr(request, "model", None),
        )
        completion_data = resp.json()
        choice_message = completion_data["choices"][0]["message"]
        assistant_message: dict[str, Any] = {"role": "assistant"}

        content = choice_message.get("content")
        if content:
            assistant_message["content"] = content

        tool_calls = choice_message.get("tool_calls") or []
        if tool_calls:
            assistant_message["tool_calls"] = [_serialize_tool_call(tool_call) for tool_call in tool_calls]

        messages.append(assistant_message)

        if not tool_calls:
            return {
                "reply": content or "I'm sorry, I couldn't generate a response. Please try again.",
                "mode": mode,
                "citations": _dedupe_citations(ctx.citations),
                "tool_events": ctx.tool_events,
            }

        for tool_call in tool_calls:
            if isinstance(tool_call, dict):
                function_name = tool_call.get("function", {}).get("name", "")
                raw_arguments = tool_call.get("function", {}).get("arguments", "{}")
                tool_call_id = tool_call.get("id", "")
            else:
                function_name = getattr(getattr(tool_call, "function", None), "name", "")
                raw_arguments = getattr(getattr(tool_call, "function", None), "arguments", "") or "{}"
                tool_call_id = getattr(tool_call, "id", "")
                
            try:
                parsed_arguments = json.loads(raw_arguments)
            except json.JSONDecodeError:
                parsed_arguments = {"raw_input": raw_arguments}

            tool_result = await tool_registry.execute(function_name, parsed_arguments, ctx)
            tool_output_str = json.dumps(tool_result, ensure_ascii=False)
            if len(tool_output_str) > 32000:
                tool_output_str = tool_output_str[:32000] + "... [Output Truncated due to absolute size limits]"
                
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": function_name,
                    "content": tool_output_str,
                }
            )

    return {
        "reply": "I stopped after reaching the tool-call safety limit. Please refine the request and try again.",
        "mode": mode,
        "citations": _dedupe_citations(ctx.citations),
        "tool_events": ctx.tool_events,
    }
