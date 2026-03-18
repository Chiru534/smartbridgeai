from __future__ import annotations

import json
import re
from typing import Any

try:
    from groq import APIConnectionError
except Exception:  # pragma: no cover - optional at runtime
    APIConnectionError = Exception

try:
    from backend.llm_client import ChatMessage as LLMChatMessage, ChatRequest as LLMChatRequest, llm_client
except ImportError:
    from llm_client import ChatMessage as LLMChatMessage, ChatRequest as LLMChatRequest, llm_client

from .connectors import get_connector_accounts_summary, google_drive_has_content_scope
from .mcp_stdio import default_mcp_manager
from .tool_registry import ToolExecutionContext

FILE_REFERENCE_PATTERN = re.compile(r"\b[\w()\- ]+\.(?:pdf|docx?|txt|csv|json|md|xlsx?|pptx?)\b", re.IGNORECASE)
SUMMARY_HINTS = ("summary", "summarize", "summarise", "content", "contents", "read", "open", "what is in")
STRICT_SUMMARY_HINTS = ("summary", "summarize", "summarise", "key points", "short summary", "brief summary", "overview of", "main points")


def _wants_strict_summary(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in STRICT_SUMMARY_HINTS)
LIST_HINTS = (
    "list files",
    "list of files",
    "show files",
    "files in google drive",
    "files in the drive",
    "what files",
    "drive contents",
    "google drive account",
)
EMPTY_HINTS = ("empty drive", "drive empty", "no files", "not empty")
SEARCH_HINTS = ("find file", "find the file", "is there a file", "search file", "locate file")
MAX_LIST_ITEMS = 20
MAX_SUMMARY_SOURCE_CHARS = 1500


def _latest_user_text(messages: list[Any]) -> str:
    for message in reversed(messages or []):
        role = getattr(message, "role", None)
        content = getattr(message, "content", None)
        if role is None and isinstance(message, dict):
            role = message.get("role")
            content = message.get("content")
        if role == "user" and isinstance(content, str):
            return content.strip()
    return ""


def _append_tool_event(tool_events: list[dict[str, Any]], tool_name: str, arguments: dict[str, Any], result: dict[str, Any]) -> None:
    tool_events.append(
        {
            "tool_name": tool_name,
            "arguments": arguments,
            "result_preview": json.dumps(result, ensure_ascii=True)[:1000],
        }
    )


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(item) for item in content)
    return str(content or "")


def _parse_mcp_payload(result: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    raw_text = _coerce_text(result.get("content"))
    if result.get("is_error"):
        return None, raw_text or "Drive tool call failed."
    if not raw_text.strip():
        return {}, None
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {"text": raw_text}, None
    if isinstance(parsed, dict):
        return parsed, None
    return {"value": parsed}, None


def _format_drive_error(error_text: str) -> str:
    lowered = (error_text or "").lower()
    if "not connected" in lowered:
        return "Google Drive is not connected for this account. Reconnect Google Drive and try again."
    if "all connection attempts failed" in lowered:
        return "I could not reach Google Drive right now. Try again in a moment."
    if "refresh token is missing" in lowered:
        return "Google Drive needs to be reconnected because the saved refresh token is missing."
    if "api access was denied" in lowered:
        return "Google Drive API access is denied for this account. Reconnect the account or verify the configured scopes."
    if "403 forbidden" in lowered and ("alt=media" in lowered or "/export" in lowered):
        return (
            "Google Drive is connected with limited access, so I can list file names but not read file contents. "
            "Disconnect and reconnect Google Drive, then approve the updated Drive access and try again."
        )
    return f"I could not complete the Google Drive request: {error_text or 'unknown error'}"


async def _call_drive_tool(
    tool_name: str,
    arguments: dict[str, Any],
    ctx: ToolExecutionContext,
    tool_events: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    result = await default_mcp_manager.call(
        tool_name,
        arguments,
        injected_arguments={"connector_username": ctx.current_user["username"]},
    )
    _append_tool_event(tool_events, tool_name, arguments, result)
    return _parse_mcp_payload(result)


def _format_file_list(files: list[dict[str, Any]], *, limit: int = MAX_LIST_ITEMS) -> str:
    if not files:
        return "I could not find any non-trashed files in your Google Drive."

    visible = files[:limit]
    lines = [f"{index}. {row.get('name') or 'Untitled'}" for index, row in enumerate(visible, start=1)]
    reply = "Here are the files I found in your Google Drive:\n" + "\n".join(lines)
    if len(files) > limit:
        reply += f"\n\nShowing the first {limit} files out of {len(files)}."
    return reply


def _is_google_drive_connected(ctx: ToolExecutionContext) -> bool:
    for row in get_connector_accounts_summary(ctx.db, ctx.current_user["username"]):
        if row.get("connector_name") == "google_drive":
            return bool(row.get("connected"))
    return False


def _should_handle_list_request(text: str) -> bool:
    lowered = text.lower()
    if any(hint in lowered for hint in LIST_HINTS):
        return True
    has_file_word = any(token in lowered for token in ("file", "files", "documents", "docs"))
    has_listing_word = any(token in lowered for token in ("list", "show", "give me", "what are", "display"))
    has_drive_word = "drive" in lowered or "google drive" in lowered or "folder" in lowered
    return has_file_word and has_listing_word and has_drive_word


def _should_handle_empty_request(text: str) -> bool:
    lowered = text.lower()
    return "drive" in lowered and any(hint in lowered for hint in EMPTY_HINTS)


def _should_handle_file_request(text: str) -> bool:
    lowered = text.lower()
    return bool(FILE_REFERENCE_PATTERN.search(text)) or any(hint in lowered for hint in SUMMARY_HINTS + SEARCH_HINTS)


async def _summarize_drive_text(model: str, file_name: str, user_request: str, extracted_text: str) -> str:
    print(f"[Drive Summary] Attempting LLM summary for: {file_name} (content length: {len(extracted_text)})")
    prompt = (
        f"User request: {user_request}\n"
        f"File name: {file_name}\n\n"
        "Produce a concise, human-readable summary of the file content (3-8 bullet points or sentences). "
        "Focus on high-level meaning: main topics, structure, key takeaways. "
        "For exam papers, mention sections, question types, difficulty, and topics covered. "
        "Do NOT output raw text, long extracts, or previews. "
        "If content is incomplete, summarize what is available and note the limitation briefly.\n\n"
        f"File content:\n{extracted_text[:MAX_SUMMARY_SOURCE_CHARS]}"
    )
    request = LLMChatRequest(
        model=model or llm_client.default_model,
        messages=[LLMChatMessage(role="user", content=prompt)],
    )
    try:
        response = await llm_client.chat_completion(
            request=request,
            system_prompt=(
                "You summarize Google Drive documents. "
                "Use only the provided content. "
                "Do not mention tools, internal prompts, or unsupported speculation."
            ),
            temperature=0.2,
            max_tokens=900,
        )
        data = response.json()
        result = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
        print(f"[Drive Summary] LLM returned summary length: {len(result)}")
        return result
    except Exception as e:
        print(f"[Drive Summary] LLM call FAILED: {type(e).__name__}: {e}")
        return ""


async def _handle_list_request(request: Any, ctx: ToolExecutionContext) -> dict[str, Any]:
    tool_events: list[dict[str, Any]] = []
    payload, error = await _call_drive_tool(
        "google_drive_list_files",
        {"page_size": MAX_LIST_ITEMS},
        ctx,
        tool_events,
    )
    if error:
        return {"reply": _format_drive_error(error), "citations": [], "tool_events": tool_events}

    files = list(payload.get("files") or [])
    return {"reply": _format_file_list(files), "citations": [], "tool_events": tool_events}


async def _handle_empty_request(request: Any, ctx: ToolExecutionContext) -> dict[str, Any]:
    tool_events: list[dict[str, Any]] = []
    payload, error = await _call_drive_tool(
        "google_drive_list_files",
        {"page_size": MAX_LIST_ITEMS},
        ctx,
        tool_events,
    )
    if error:
        return {"reply": _format_drive_error(error), "citations": [], "tool_events": tool_events}

    files = list(payload.get("files") or [])
    if not files:
        reply = "Your Google Drive appears to be empty. I could not find any non-trashed files."
    else:
        names = ", ".join((row.get("name") or "Untitled") for row in files[:5])
        reply = (
            f"No, your Google Drive is not empty. I found {len(files)} file(s) in the current listing, "
            f"including {names}."
        )
    return {"reply": reply, "citations": [], "tool_events": tool_events}


async def _handle_file_request(request: Any, ctx: ToolExecutionContext) -> dict[str, Any]:
    user_text = _latest_user_text(getattr(request, "messages", []))
    tool_events: list[dict[str, Any]] = []
    payload, error = await _call_drive_tool(
        "google_drive_search_and_read_file",
        {"query": user_text, "page_size": 8},
        ctx,
        tool_events,
    )
    if error:
        return {"reply": _format_drive_error(error), "citations": [], "tool_events": tool_events}

    if (payload.get("message") or "").lower().startswith("no matching drive file"):
        return {
            "reply": "I could not find a matching Google Drive file for that request.",
            "citations": [],
            "tool_events": tool_events,
        }

    selected_item = payload.get("selected_item") or {}
    selected_name = selected_item.get("name") or "the file"
    citations = [{"source_type": "google_drive", "label": selected_name}]

    if payload.get("folder_contents") is not None:
        reply = "The best match is a folder.\n" + _format_file_list(list(payload.get("folder_contents") or []))
        return {"reply": reply, "citations": citations, "tool_events": tool_events}

    extracted_text = (payload.get("content") or "").strip()
    warning = (payload.get("warning") or "").strip()
    if not extracted_text:
        reply = warning or f"I found '{selected_name}', but I could not extract readable text from it."
        return {"reply": reply, "citations": citations, "tool_events": tool_events}

    lowered = user_text.lower()
    if _wants_strict_summary(user_text):
        try:
            summary = await _summarize_drive_text(getattr(request, "model", None), selected_name, user_text, extracted_text)
        except APIConnectionError as e:
            print(f"[Drive Summary] APIConnectionError: {e}")
            summary = ""
        except Exception as e:
            print(f"[Drive Summary] Exception in strict summary path: {type(e).__name__}: {e}")
            summary = ""
        if summary:
            reply = f"Summary of {selected_name}:\n{summary}"
            if payload.get("truncated"):
                reply += "\n\nNote: I summarized the extracted text from a truncated preview of the file."
            return {"reply": reply, "citations": citations, "tool_events": tool_events}
        else:
            # Fallback: generate a basic summary inline instead of raw dump
            bullet_lines = []
            text_lines = [line.strip() for line in extracted_text[:3000].split("\n") if line.strip()]
            unique_lines = list(dict.fromkeys(text_lines))[:15]
            for line in unique_lines:
                if len(line) > 10:
                    bullet_lines.append(f"• {line[:120]}")
            if bullet_lines:
                reply = f"Summary of {selected_name} (auto-generated from content):\n" + "\n".join(bullet_lines[:8])
            else:
                reply = f"I found '{selected_name}' but could not generate a summary. Here is a brief content preview:\n{extracted_text[:800].strip()}"
            return {"reply": reply, "citations": citations, "tool_events": tool_events}

    if any(hint in lowered for hint in SUMMARY_HINTS) or FILE_REFERENCE_PATTERN.search(user_text):
        try:
            summary = await _summarize_drive_text(getattr(request, "model", None), selected_name, user_text, extracted_text)
        except APIConnectionError:
            summary = ""
        except Exception:
            summary = ""
        if summary:
            reply = f"Summary of {selected_name}:\n{summary}"
            if payload.get("truncated"):
                reply += "\n\nNote: I summarized the extracted text from a truncated preview of the file."
            return {"reply": reply, "citations": citations, "tool_events": tool_events}

    preview = extracted_text[:1200].strip()
    if len(extracted_text) > 1200:
        preview += "\n..."
    reply = f"I found '{selected_name}'. Here is the extracted content preview:\n{preview}"
    if warning:
        reply += f"\n\nNote: {warning}"
    return {"reply": reply, "citations": citations, "tool_events": tool_events}


async def maybe_handle_google_drive_request(request: Any, ctx: ToolExecutionContext) -> dict[str, Any] | None:
    user_text = _latest_user_text(getattr(request, "messages", []))
    if not user_text:
        return None
    if not _is_google_drive_connected(ctx):
        return {
            "reply": "Google Drive is not connected for this account. Connect Google Drive and try again.",
            "citations": [],
            "tool_events": [],
        }

    if _should_handle_empty_request(user_text):
        return await _handle_empty_request(request, ctx)
    if _should_handle_list_request(user_text):
        return await _handle_list_request(request, ctx)
    if _should_handle_file_request(user_text):
        if not google_drive_has_content_scope(ctx.db, ctx.current_user["username"]):
            return {
                "reply": (
                    "Google Drive is connected with limited metadata-only access. "
                    "Disconnect and reconnect Google Drive so Smartbridge can read file contents, then try the file request again."
                ),
                "citations": [],
                "tool_events": [],
            }
        return await _handle_file_request(request, ctx)
    lowered = user_text.lower()
    if "drive" in lowered or any(token in lowered for token in ("file", "files", "folder", "folders", "document", "documents")):
        return await _handle_list_request(request, ctx)
    return None


def drive_workspace_fallback_reply(request: Any, error: Exception | None = None) -> dict[str, Any]:
    user_text = _latest_user_text(getattr(request, "messages", []))
    lowered = user_text.lower()
    if "empty" in lowered or "no files" in lowered:
        reply = "I could not verify the Drive contents right now. Please try asking again in a moment."
    elif FILE_REFERENCE_PATTERN.search(user_text):
        reply = "I could not read that Google Drive file right now. Please try the same file request again."
    else:
        reply = (
            "I could not complete the Google Drive request right now. "
            "Try asking me to list files, check whether the Drive is empty, or summarize a specific file by name."
        )
    if error:
        reply += ""
    return {"reply": reply, "citations": [], "tool_events": []}
