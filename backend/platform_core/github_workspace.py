from __future__ import annotations

import json
import re
import traceback
from typing import Any

try:
    from groq import APIConnectionError
except Exception:  # pragma: no cover - optional at runtime
    APIConnectionError = Exception

try:
    from backend.llm_client import ChatMessage as LLMChatMessage, ChatRequest as LLMChatRequest, llm_client
except ImportError:
    from llm_client import ChatMessage as LLMChatMessage, ChatRequest as LLMChatRequest, llm_client

try:
    import backend.models as models
except ImportError:
    import models

from .connectors import get_connector_accounts_summary
from .mcp_stdio import default_mcp_manager
from .tool_registry import ToolExecutionContext

REPO_REFERENCE_PATTERN = re.compile(r"\b([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)\b")
FILE_PATH_PATTERN = re.compile(r"(?:`([^`]+)`|\"([^\"]+)\"|'([^']+)')")
FALLBACK_FILE_PATTERN = re.compile(r"\b([A-Za-z0-9_.\-/]+\.[A-Za-z0-9]+)\b")
REPO_LIST_HINTS = (
    "my repositories",
    "my repos",
    "list repositories",
    "list repos",
    "list of repos",
    "list of the repos",
    "list of repositories",
    "show repositories",
    "show repos",
    "github repositories",
    "github repos",
    "repos in the github account",
    "repositories in the github account",
)
REPO_SEARCH_HINTS = ("find repository", "search repositories", "search repos", "find repo")
FILE_HINTS = ("read file", "show file", "file content", "open file", "summary of", "summarize", "contents of", "show me", "get file", "give me the", "display file", "give me code in", "code in", "inside", "in the", "code inside", "the code", "content of")
DIRECTORY_HINTS = (
    "list files",
    "show files",
    "files in",
    "directory",
    "folder",
    "repository contents",
    "repo contents",
    "tree",
    "structure",
    "structure of",
)
ISSUE_HINTS = ("issues", "issue list")
PR_HINTS = ("pull requests", "pull request", "prs", "pr list")
BRANCH_HINTS = ("branches", "branch list")
COMMIT_HINTS = ("commits", "recent commits", "commit history")
WORKFLOW_HINTS = ("workflows", "github actions", "actions workflows")
AUTH_HINTS = ("who am i on github", "authenticated user", "my github account")
RAW_FILE_HINTS = (
    "code inside",
    "inside the",
    "show code",
    "full code",
    "full file",
    "entire file",
    "whole file",
    "raw content",
    "raw file",
    "full content",
    "give me the code",
    "show the code",
    "code of",
    "code for",
    "the code",
    "get the code",
    "give me code",
    "show me the code",
    "display the code",
    "print the code",
    "content inside",
    "what is in",
    "what's in",
)
MAX_ITEMS = 20
MAX_SUMMARY_SOURCE_CHARS = 10000
MAX_FILE_CONTENT_CHARS = 4000
MAX_LLM_CHARS = 8000

VALID_INTENTS = (
    "auth_info", "list_repos", "search_repos", "list_prs", "list_issues",
    "list_branches", "list_commits", "list_workflows", "list_directory",
    "get_file", "explain_code", "repo_info", "unknown",
)

GITHUB_CAPABILITIES_MESSAGE = (
    "I can help you with the following GitHub operations:\n"
    "• **List repositories** — e.g. \"show my repos\"\n"
    "• **Browse files/folders** — e.g. \"show files in backend\"\n"
    "• **Read file content** — e.g. \"show me main.py\"\n"
    "• **Explain code** — e.g. \"explain that file\"\n"
    "• **List pull requests** — e.g. \"show PRs\"\n"
    "• **List issues** — e.g. \"show issues\"\n"
    "• **List branches / commits** — e.g. \"show branches\"\n"
    "• **View repo info** — e.g. \"tell me about project_agent\"\n\n"
    "Please rephrase your request using one of the above patterns."
)

EXPLAIN_HINTS = (
    "explain", "what does", "how does", "describe", "break down",
    "walk through", "walkthrough", "overview of", "purpose of",
)
COMMON_FILE_EXTENSIONS = {
    "c",
    "cpp",
    "css",
    "csv",
    "go",
    "html",
    "java",
    "js",
    "json",
    "jsx",
    "md",
    "pdf",
    "py",
    "sql",
    "ts",
    "tsx",
    "txt",
    "xml",
    "yaml",
    "yml",
}
REPO_NAME_STOP_WORDS = {"github", "repo", "repository", "repositories", "account", "structure", "files", "file"}


def _message_role_and_content(message: Any) -> tuple[str | None, str]:
    role = getattr(message, "role", None)
    content = getattr(message, "content", None)
    if role is None and isinstance(message, dict):
        role = message.get("role")
        content = message.get("content")
    return role, (content.strip() if isinstance(content, str) else "")


def _message_entries(messages: list[Any]) -> list[tuple[str | None, str]]:
    entries: list[tuple[str | None, str]] = []
    for message in messages or []:
        role, content = _message_role_and_content(message)
        if content:
            entries.append((role, content))
    return entries


def _latest_user_text(messages: list[Any]) -> str:
    for role, content in reversed(_message_entries(messages)):
        if role == "user":
            return content
    return ""


def _latest_user_text_from_entries(entries: list[tuple[str | None, str]]) -> str:
    for role, content in reversed(entries):
        if role == "user":
            return content
    return ""


def _prior_message_entries(messages: list[Any]) -> list[tuple[str | None, str]]:
    entries = _message_entries(messages)
    for index in range(len(entries) - 1, -1, -1):
        if entries[index][0] == "user":
            return entries[:index]
    return entries


def _prior_entries(entries: list[tuple[str | None, str]]) -> list[tuple[str | None, str]]:
    for index in range(len(entries) - 1, -1, -1):
        if entries[index][0] == "user":
            return entries[:index]
    return entries


def _session_message_entries(ctx: ToolExecutionContext) -> list[tuple[str | None, str]]:
    db = getattr(ctx, "db", None)
    session_id = getattr(ctx, "session_id", None)
    username = ((getattr(ctx, "current_user", None) or {}).get("username")) if getattr(ctx, "current_user", None) else None
    if not db or not session_id or not username:
        return []
    try:
        rows = (
            db.query(models.ChatMessageDB)
            .filter(
                models.ChatMessageDB.user_id == username,
                models.ChatMessageDB.session_id == session_id,
            )
            .order_by(models.ChatMessageDB.timestamp.desc())
            .limit(MAX_ITEMS)
            .all()
        )
    except Exception:
        return []
    return [
        (row.role, row.content.strip())
        for row in reversed(rows)
        if isinstance(row.content, str) and row.content.strip()
    ]


def _conversation_entries(request: Any, ctx: ToolExecutionContext) -> list[tuple[str | None, str]]:
    session_entries = _session_message_entries(ctx)
    if session_entries:
        return session_entries
    return _message_entries(getattr(request, "messages", []))


def _wants_raw_file_content(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in RAW_FILE_HINTS)


def _repo_list_label(item: dict[str, Any], *, prefer_full_name: bool = True) -> str:
    if prefer_full_name:
        return item.get("full_name") or item.get("name") or "unknown-repo"
    return item.get("name") or item.get("full_name") or "unknown-repo"


def _repo_ref_from_item(item: dict[str, Any]) -> tuple[str, str] | None:
    full_name = item.get("full_name") or ""
    if "/" not in full_name:
        return None
    owner, repo = full_name.split("/", 1)
    return owner, repo


def _find_repo_item_in_text(text: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    lowered = (text or "").lower()
    ranked_items = sorted(
        items,
        key=lambda item: max(len(item.get("full_name") or ""), len(item.get("name") or "")),
        reverse=True,
    )
    for item in ranked_items:
        full_name = (item.get("full_name") or "").lower()
        name = (item.get("name") or "").lower()
        if full_name and full_name in lowered:
            return item
        if name and re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(name)}(?![A-Za-z0-9_.-])", lowered):
            return item
    return None


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
        return None, raw_text or "GitHub tool call failed."
    if not raw_text.strip():
        return {}, None
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {"text": raw_text}, None
    if isinstance(parsed, dict):
        return parsed, None
    return {"value": parsed}, None


def _format_github_error(error_text: str) -> str:
    lowered = (error_text or "").lower()
    if "not connected" in lowered or "access token is missing" in lowered:
        return "GitHub is not connected for this account. Reconnect GitHub and try again."
    if (
        "401" in lowered
        or "unauthorized" in lowered
        or "bad credentials" in lowered
        or "requires authentication" in lowered
    ):
        return (
            "GitHub authorization for this account is no longer valid. "
            "Disconnect GitHub, reconnect it, and try again."
        )
    if "all connection attempts failed" in lowered:
        return "I could not reach GitHub right now. Try again in a moment."
    return f"I could not complete the GitHub request: {error_text or 'unknown error'}"


async def _call_github_tool(
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


def _is_github_connected(ctx: ToolExecutionContext) -> bool:
    for row in get_connector_accounts_summary(ctx.db, ctx.current_user["username"]):
        if row.get("connector_name") == "github":
            return bool(row.get("connected"))
    return False


def _extract_repo_reference(text: str) -> tuple[str, str] | None:
    candidates: list[tuple[str, str]] = []
    for match in REPO_REFERENCE_PATTERN.finditer(text or ""):
        owner, repo = match.groups()
        if owner.lower() in {"http", "https", "files", "directories", "folders"}:
            continue
        if "." in repo:
            extension = repo.rsplit(".", 1)[-1].lower()
            if extension in COMMON_FILE_EXTENSIONS:
                continue
        # Do not match if preceded by 'file ' or 'dir ' which happens during directory listing
        if re.search(rf"(?:file|dir)\s+{re.escape(match.group(0))}", text or "", re.IGNORECASE):
            continue
        candidates.append((owner, repo))
    return candidates[-1] if candidates else None


def _extract_file_path(text: str, repo_ref: tuple[str, str] | None) -> str | None:
    # First pass: quoted/backtick paths (with or without slash)
    for groups in FILE_PATH_PATTERN.findall(text or ""):
        candidate = next((value for value in groups if value), "").strip().strip("/")
        if not candidate:
            continue
        if repo_ref and candidate == f"{repo_ref[0]}/{repo_ref[1]}":
            continue
        return candidate

    # Second pass: bare tokens that look like filenames (contain a dot with known extension)
    for match in FALLBACK_FILE_PATTERN.finditer(text or ""):
        candidate = match.group(1).strip().strip("/")
        if repo_ref and candidate == f"{repo_ref[0]}/{repo_ref[1]}":
            continue
        if candidate.startswith(("http://", "https://")):
            continue
        return candidate
    return None


DIRECTORY_STOP_WORDS = {
    "the", "a", "an", "all", "show", "give", "me", "some", "it", "them", "that", "these", "those", "of", "in"
}


def _extract_directory_path(text: str, repo_ref: tuple[str, str] | None) -> str | None:
    patterns = [
        r"\b([A-Za-z0-9_.\-/]+)\s+(?:directory|folder)\b",
        r"\b([A-Za-z0-9_.\-/]+)\s+files\s+inside\b",
        r"\b([A-Za-z0-9_.\-/]+)\s+files\b",
        r"(?:in|inside|under)\s+(?:the\s+)?([A-Za-z0-9_.\-/]+)\s+(?:directory|folder)\b",
        r"(?:in|inside)\s+(?:the\s+)?(?:dir|directory|folder)\s+([A-Za-z0-9_.\-/]+)\b",
        r"(?:files in|files inside)\s+(?:the\s+)?([A-Za-z0-9_.\-/]+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "", flags=re.IGNORECASE)
        if not match:
            continue
        candidate = (match.group(1) or "").strip().strip("/").strip("`'\"")
        if not candidate:
            continue
        if candidate.lower() in DIRECTORY_STOP_WORDS:
            continue
        if repo_ref and candidate in {repo_ref[1], f"{repo_ref[0]}/{repo_ref[1]}"}:
            continue
        if "." in candidate:
            extension = candidate.rsplit(".", 1)[-1].lower()
            if extension in COMMON_FILE_EXTENSIONS:
                continue
        return candidate
    return None


def _extract_recent_directory_path(entries: list[tuple[str | None, str]], repo_ref: tuple[str, str]) -> str | None:
    # Check all prior entries including assistant messages (directory listings appear in assistant replies)
    for _, content in reversed(_prior_entries(entries)):
        candidate = _extract_directory_path(content, repo_ref)
        if candidate:
            return candidate
    # Also scan assistant messages for paths like "backend/check_db.py" that reveal the directory
    for role, content in reversed(_prior_entries(entries)):
        if role != "assistant":
            continue
        # Match "file backend/check_db.py" or "dir backend/__pycache__" patterns
        for match in re.finditer(r"(?:file|dir)\s+([A-Za-z0-9_.\-]+)/[A-Za-z0-9_.\-/]+", content):
            dir_candidate = match.group(1).strip()
            if dir_candidate and dir_candidate.lower() not in REPO_NAME_STOP_WORDS:
                return dir_candidate
        # Also match "path/file" patterns
        for match in re.finditer(r"\b([A-Za-z0-9_.\-]+)/[A-Za-z0-9_.\-/]+\b", content):
            dir_candidate = match.group(1).strip()
            if dir_candidate and dir_candidate.lower() not in REPO_NAME_STOP_WORDS:
                return dir_candidate
    return None


def _extract_recently_listed_file(filename: str, entries: list[tuple[str | None, str]]) -> str | None:
    """
    Extract full path of a file from recent assistant messages that listed files.
    E.g., if filename="llm_agent.py" and assistant listed "file backend/llm_agent.py",
    return "backend/llm_agent.py"
    """
    filename_lower = (filename or "").lower().strip()
    if not filename_lower:
        return None
    
    for role, content in reversed(_prior_entries(entries)):
        if role != "assistant":
            continue
        # Look for "file <full_path>" patterns where the filename matches
        for match in re.finditer(rf"(?:file|dir)\s+([A-Za-z0-9_.\-/]+{re.escape(filename_lower)})", content, re.IGNORECASE):
            full_path = match.group(1).strip()
            if full_path:
                return full_path
    return None


def _wants_directory_listing(text: str, file_path: str | None) -> bool:
    lowered = text.lower()
    return _contains_hint(text, DIRECTORY_HINTS) or ("files" in lowered and not file_path)


def _wants_names_only(text: str) -> bool:
    lowered = text.lower()
    return "only the names" in lowered or "only names" in lowered or "just the names" in lowered or "repo names" in lowered


ASCII_TREE_HINTS = (
    "project structure",
    "project tree",
    "file tree",
    "directory tree",
    "show tree",
    "ascii tree",
    "tree structure",
    "show structure",
    "folder structure",
    "whole structure",
    "full structure",
)


def _wants_ascii_tree(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in ASCII_TREE_HINTS) or (
        ("structure" in lowered or "tree" in lowered)
        and any(tok in lowered for tok in ("repo", "repository", "project", "agent", "folder", "directory"))
    )


def _format_repo_list(
    items: list[dict[str, Any]],
    *,
    limit: int = MAX_ITEMS,
    names_only: bool = False,
    prefer_full_name: bool = True,
) -> str:
    if not items:
        return "I could not find any matching GitHub repositories."
    visible = items[:limit]
    lines = []
    for index, item in enumerate(visible, start=1):
        label = _repo_list_label(item, prefer_full_name=prefer_full_name)
        if names_only:
            lines.append(f"{index}. {label}")
            continue
        language = item.get("language")
        description = (item.get("description") or "").strip()
        suffix = []
        if language:
            suffix.append(language)
        if description:
            suffix.append(description)
        line = f"{index}. {label}"
        if suffix:
            line += f" - {' | '.join(suffix)}"
        lines.append(line)
    title = "Here are the GitHub repository names:" if names_only else "Here are the GitHub repositories I found:"
    reply = title + "\n" + "\n".join(lines)
    if len(items) > limit:
        reply += f"\n\nShowing the first {limit} repositories."
    return reply


def _format_named_items(title: str, items: list[dict[str, Any]], label_builder, *, limit: int = MAX_ITEMS) -> str:
    if not items:
        return title + "\nNo items found."
    lines = [f"{index}. {label_builder(item)}" for index, item in enumerate(items[:limit], start=1)]
    reply = title + "\n" + "\n".join(lines)
    if len(items) > limit:
        reply += f"\n\nShowing the first {limit} items."
    return reply


ASCII_TREE_LIMIT = 80


def _format_ascii_tree(repo_label: str, items: list[dict[str, Any]]) -> str:
    """Format a flat list of GitHub file/dir items as an ASCII tree."""
    # Sort items: directories first, then files; alphabetically within each group
    dirs = sorted([i for i in items if i.get("type") == "dir"], key=lambda i: (i.get("path") or "").lower())
    files = sorted([i for i in items if i.get("type") != "dir"], key=lambda i: (i.get("path") or "").lower())
    sorted_items = dirs + files

    truncated = len(sorted_items) > ASCII_TREE_LIMIT
    sorted_items = sorted_items[:ASCII_TREE_LIMIT]

    lines = [f"{repo_label}/"]
    total = len(sorted_items)
    for idx, item in enumerate(sorted_items):
        is_last = idx == total - 1 and not truncated
        connector = "└──" if is_last else "├──"
        name = item.get("name") or item.get("path") or "unknown"
        suffix = "/" if item.get("type") == "dir" else ""
        lines.append(f"{connector} {name}{suffix}")

    if truncated:
        lines.append("└── ... (truncated, too many items)")

    return "\n".join(lines)


def detect_intent(text: str) -> str:
    """Unified rule-based intent classifier. Returns a single intent string."""
    q = (text or "").lower().strip()
    if not q:
        return "unknown"
    if _wants_auth_info(q):            return "auth_info"
    if _wants_repo_list(q):            return "list_repos"
    if _wants_repo_search(q):          return "search_repos"
    if _contains_hint(q, PR_HINTS):    return "list_prs"
    if _contains_hint(q, ISSUE_HINTS): return "list_issues"
    if _contains_hint(q, BRANCH_HINTS): return "list_branches"
    if _contains_hint(q, COMMIT_HINTS): return "list_commits"
    if _contains_hint(q, WORKFLOW_HINTS): return "list_workflows"
    if _contains_hint(q, EXPLAIN_HINTS): return "explain_code"
    if _contains_hint(q, RAW_FILE_HINTS) or _contains_hint(q, FILE_HINTS):
        return "get_file"
    if _contains_hint(q, DIRECTORY_HINTS):
        return "list_directory"
    # If it mentions a repo/github at all, treat as repo_info
    if any(tok in q for tok in ("repo", "repository", "github")):
        return "repo_info"
    return "unknown"


def _preprocess_for_llm(items: list[dict[str, Any]], fields: tuple[str, ...]) -> str:
    """Strip GitHub API items to only the specified fields. Returns compact JSON."""
    cleaned: list[dict[str, Any]] = []
    for item in items[:MAX_ITEMS]:
        entry = {k: item.get(k, "") for k in fields if item.get(k)}
        if entry:
            cleaned.append(entry)
    text = json.dumps(cleaned, indent=2, ensure_ascii=False)
    return text[:MAX_LLM_CHARS]


async def _llm_classify_intent(query: str) -> str:
    """LLM-based fallback intent classification. Returns a valid intent string."""
    prompt = (
        f"User query: {query}\n\n"
        "Classify this into EXACTLY ONE of these categories:\n"
        '["auth_info","list_repos","search_repos","list_prs","list_issues",'
        '"list_branches","list_commits","list_workflows","list_directory",'
        '"get_file","explain_code","repo_info","unknown"]\n\n'
        'Return ONLY JSON: {"intent": "<value>"}\n'
        'NO explanation. ONLY valid JSON.'
    )
    try:
        response = await llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=50,
        )
        data = response.json()
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
        # Try to parse JSON from response
        parsed = json.loads(content)
        intent = parsed.get("intent", "unknown")
        return intent if intent in VALID_INTENTS else "unknown"
    except Exception:
        return "unknown"


async def _summarize_github_text(model: str, context_label: str, user_request: str, content: str) -> str:
    """Use LLM ONLY for summarization/reasoning over pre-fetched GitHub data."""
    prompt = (
        f"User request: {user_request}\n\n"
        f"Data from {context_label}:\n"
        f"{content[:MAX_SUMMARY_SOURCE_CHARS]}\n\n"
        "Provide:\n"
        "- Summary\n"
        "- Key insights\n"
        "- Risks (if any)"
    )
    request = LLMChatRequest(
        model=model or llm_client.default_model,
        messages=[LLMChatMessage(role="user", content=prompt)],
    )
    response = await llm_client.chat_completion(
        request=request,
        system_prompt=(
            "You summarize GitHub repository content. "
            "Use only the supplied data. Be concise and structured. "
            "Do not mention tools, APIs, or internal prompts."
        ),
        temperature=0.2,
        max_tokens=900,
    )
    data = response.json()
    return ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()


def _wants_repo_list(text: str) -> bool:
    lowered = text.lower()
    if any(hint in lowered for hint in REPO_LIST_HINTS):
        return True
    if _wants_names_only(lowered) and any(token in lowered for token in ("repo", "repos", "repository", "repositories")):
        return True
    has_repo_word = any(token in lowered for token in ("repo", "repos", "repository", "repositories"))
    has_listing_word = any(token in lowered for token in ("list", "show", "give me", "what are", "display"))
    has_scope_word = "github" in lowered or "account" in lowered or "my" in lowered
    has_detail_word = _contains_hint(lowered, DIRECTORY_HINTS + FILE_HINTS + ISSUE_HINTS + PR_HINTS + BRANCH_HINTS + COMMIT_HINTS + WORKFLOW_HINTS)
    if has_detail_word:
        return False
    if _extract_repo_reference(text) or _extract_repo_name_candidate(text):
        return False
    return has_repo_word and has_listing_word and has_scope_word


def _wants_repo_search(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in REPO_SEARCH_HINTS)


def _wants_auth_info(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in AUTH_HINTS)


def _contains_hint(text: str, hints: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in hints)


async def _handle_repo_list(ctx: ToolExecutionContext, *, names_only: bool = False) -> dict[str, Any]:
    tool_events: list[dict[str, Any]] = []
    payload, error = await _call_github_tool(
        "github_list_my_repositories",
        {"per_page": MAX_ITEMS},
        ctx,
        tool_events,
    )
    if error:
        return {"reply": _format_github_error(error), "citations": [], "tool_events": tool_events}
    items = list(payload.get("items") or [])
    return {
        "reply": _format_repo_list(items, names_only=names_only, prefer_full_name=False),
        "citations": [],
        "tool_events": tool_events,
    }


async def _handle_auth_info(ctx: ToolExecutionContext) -> dict[str, Any]:
    tool_events: list[dict[str, Any]] = []
    payload, error = await _call_github_tool("github_get_authenticated_user", {}, ctx, tool_events)
    if error:
        return {"reply": _format_github_error(error), "citations": [], "tool_events": tool_events}
    reply = (
        f"GitHub account: {payload.get('login') or 'unknown'}\n"
        f"Name: {payload.get('name') or 'N/A'}\n"
        f"Profile: {payload.get('html_url') or 'N/A'}"
    )
    return {"reply": reply, "citations": [], "tool_events": tool_events}


async def _handle_repo_search(text: str, ctx: ToolExecutionContext) -> dict[str, Any]:
    tool_events: list[dict[str, Any]] = []
    payload, error = await _call_github_tool(
        "github_search_repositories",
        {"query": text, "per_page": 10},
        ctx,
        tool_events,
    )
    if error:
        return {"reply": _format_github_error(error), "citations": [], "tool_events": tool_events}
    items = list(payload.get("items") or [])
    return {"reply": _format_repo_list(items, limit=10), "citations": [], "tool_events": tool_events}


def _extract_repo_name_candidate(text: str) -> str | None:
    patterns = [
        r"(?:structure|summary|summarize|contents|content|files)\s+of\s+(?:the\s+)?([A-Za-z0-9_.-]+)",
        r"(?:files|contents)\s+in\s+(?:the\s+)?([A-Za-z0-9_.-]+)",
        r"\b([A-Za-z0-9_.-]+)\s+repos?\b",
        r"\b([A-Za-z0-9_.-]+)\s+repository\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "", flags=re.IGNORECASE)
        if not match:
            continue
        candidate = (match.group(1) or "").strip().strip("`'\"")
        if candidate and candidate.lower() not in REPO_NAME_STOP_WORDS:
            return candidate
    return None


async def _resolve_repo_reference(
    request: Any,
    ctx: ToolExecutionContext,
    tool_events: list[dict[str, Any]],
) -> tuple[tuple[str, str] | None, list[dict[str, Any]] | None]:
    entries = _conversation_entries(request, ctx)
    user_text = _latest_user_text_from_entries(entries)
    repo_ref = _extract_repo_reference(user_text)
    if repo_ref:
        return repo_ref, None

    repo_name = _extract_repo_name_candidate(user_text)
    items: list[dict[str, Any]] | None = None
    lowered = user_text.lower()
    needs_repo_inventory = bool(
        repo_name
        or _contains_hint(user_text, DIRECTORY_HINTS + FILE_HINTS + ISSUE_HINTS + PR_HINTS + BRANCH_HINTS + COMMIT_HINTS + WORKFLOW_HINTS)
        or "repo" in lowered
        or "repository" in lowered
    )

    # Check conversation history for a known repo reference before calling the API
    for role, content in reversed(_prior_entries(entries)):
        if role == "assistant":
            # Assistant messages can contain code or file paths (e.g. "of backend/gesture_state.py")
            # Iterate through all matches to find a legitimate owner/repo
            for match in re.finditer(r"(?:in|of|about|Repository:)\s+([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)\b", content or ""):
                owner, repo = match.groups()
                if owner.lower() in {"http", "https", "files", "directories", "folders"}:
                    continue
                if "." in repo:
                    extension = repo.rsplit(".", 1)[-1].lower()
                    if extension in COMMON_FILE_EXTENSIONS:
                        continue
                return (owner, repo), None
        else:
            prior_ref = _extract_repo_reference(content)
            if prior_ref:
                return prior_ref, None

    if needs_repo_inventory:
        payload, error = await _call_github_tool(
            "github_list_my_repositories",
            {"per_page": 100},
            ctx,
            tool_events,
        )
        if not error:
            items = list(payload.get("items") or [])
            direct_match = _find_repo_item_in_text(user_text, items)
            if direct_match:
                repo_ref = _repo_ref_from_item(direct_match)
                if repo_ref:
                    return repo_ref, items
            if repo_name:
                exact_match = next((item for item in items if (item.get("name") or "").lower() == repo_name.lower()), None)
                if exact_match:
                    repo_ref = _repo_ref_from_item(exact_match)
                    if repo_ref:
                        return repo_ref, items

    for _, content in reversed(_prior_entries(entries)):
        repo_ref = _extract_repo_reference(content)
        if repo_ref:
            return repo_ref, items

    if items:
        for _, content in reversed(_prior_entries(entries)):
            history_match = _find_repo_item_in_text(content, items)
            if history_match:
                repo_ref = _repo_ref_from_item(history_match)
                if repo_ref:
                    return repo_ref, items
    return None, items


async def _resolve_file_path(
    owner: str,
    repo: str,
    raw_path: str,
    entries: list[tuple[str | None, str]],
    ctx: ToolExecutionContext,
    tool_events: list[dict[str, Any]],
) -> str:
    path = (raw_path or "").strip().strip("/")
    if not path:
        return path
    
    # If path already contains /, it's likely a full path
    if "/" in path:
        return path

    # First, try to find the file in recently listed files
    recent_file = _extract_recently_listed_file(path, entries)
    if recent_file:
        return recent_file

    # Try to prepend recent directory
    recent_directory = _extract_recent_directory_path(entries, (owner, repo))
    if recent_directory:
        return f"{recent_directory.rstrip('/')}/{path}"

    # Try common root directories (backend/, frontend/, src/) before expensive search
    # Fall back to GitHub search if no recent file or directory matched
    payload, error = await _call_github_tool(
        "github_search_code",
        {"query": f"repo:{owner}/{repo} filename:{path}", "per_page": 10},
        ctx,
        tool_events,
    )
    if error:
        return path

    matches = [
        item.get("path")
        for item in list(payload.get("items") or [])
        if isinstance(item.get("path"), str) and item.get("path")
    ]
    basename_matches = [match for match in matches if match.rsplit("/", 1)[-1].lower() == path.lower()]
    if basename_matches:
        return sorted(basename_matches, key=len)[0]
    return path


def _format_file_content_reply(path: str, repo_label: str, content: str) -> str:
    snippet = content[:MAX_FILE_CONTENT_CHARS].rstrip()
    extension = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    fenced_content = f"```{extension}\n{snippet}\n```" if extension else f"```\n{snippet}\n```"
    if len(content) > MAX_FILE_CONTENT_CHARS:
        fenced_content += "\n\nFile content was truncated. Ask for the next chunk if you need more."
    return f"File content for {path} in {repo_label}:\n{fenced_content}"


async def _handle_repo_detail(request: Any, ctx: ToolExecutionContext, owner: str, repo: str) -> dict[str, Any]:
    entries = _conversation_entries(request, ctx)
    user_text = _latest_user_text_from_entries(entries)
    repo_label = f"{owner}/{repo}"
    tool_events: list[dict[str, Any]] = []
    citations = [{"source_type": "github", "label": repo_label}]

    if _contains_hint(user_text, ISSUE_HINTS):
        payload, error = await _call_github_tool(
            "github_list_issues",
            {"owner": owner, "repo": repo, "state": "open", "per_page": 10},
            ctx,
            tool_events,
        )
        if error:
            if "404" in error or "Not Found" in error:
                return {"reply": f"Issues for {repo_label} could not be found (404).", "citations": citations, "tool_events": tool_events}
            return {"reply": _format_github_error(error), "citations": citations, "tool_events": tool_events}
        items = list(payload.get("items") or [])
        reply = _format_named_items(
            f"Open issues for {repo_label}:",
            items,
            lambda item: f"#{item.get('number')} {item.get('title') or 'Untitled issue'}",
            limit=10,
        )
        return {"reply": reply, "citations": citations, "tool_events": tool_events}

    if _contains_hint(user_text, PR_HINTS):
        payload, error = await _call_github_tool(
            "github_list_pull_requests",
            {"owner": owner, "repo": repo, "state": "open", "per_page": 10},
            ctx,
            tool_events,
        )
        if error:
            if "404" in error or "Not Found" in error:
                return {"reply": f"Pull requests for {repo_label} could not be found (404).", "citations": citations, "tool_events": tool_events}
            return {"reply": _format_github_error(error), "citations": citations, "tool_events": tool_events}
        items = list(payload.get("items") or [])
        reply = _format_named_items(
            f"Open pull requests for {repo_label}:",
            items,
            lambda item: f"#{item.get('number')} {item.get('title') or 'Untitled PR'}",
            limit=10,
        )
        return {"reply": reply, "citations": citations, "tool_events": tool_events}

    if _contains_hint(user_text, BRANCH_HINTS):
        payload, error = await _call_github_tool(
            "github_list_branches",
            {"owner": owner, "repo": repo, "per_page": 20},
            ctx,
            tool_events,
        )
        if error:
            if "404" in error or "Not Found" in error:
                return {"reply": f"Branches for {repo_label} could not be found (404).", "citations": citations, "tool_events": tool_events}
            return {"reply": _format_github_error(error), "citations": citations, "tool_events": tool_events}
        items = list(payload.get("items") or [])
        reply = _format_named_items(
            f"Branches in {repo_label}:",
            items,
            lambda item: item.get("name") or "unknown-branch",
            limit=20,
        )
        return {"reply": reply, "citations": citations, "tool_events": tool_events}

    if _contains_hint(user_text, COMMIT_HINTS):
        payload, error = await _call_github_tool(
            "github_list_commits",
            {"owner": owner, "repo": repo, "per_page": 10},
            ctx,
            tool_events,
        )
        if error:
            if "404" in error or "Not Found" in error:
                return {"reply": f"Commits for {repo_label} could not be found (404).", "citations": citations, "tool_events": tool_events}
            return {"reply": _format_github_error(error), "citations": citations, "tool_events": tool_events}
        items = list(payload.get("items") or [])
        reply = _format_named_items(
            f"Recent commits in {repo_label}:",
            items,
            lambda item: f"{(item.get('sha') or '')[:7]} {(((item.get('commit') or {}).get('message')) or '').splitlines()[0]}",
            limit=10,
        )
        return {"reply": reply, "citations": citations, "tool_events": tool_events}

    if _contains_hint(user_text, WORKFLOW_HINTS):
        payload, error = await _call_github_tool(
            "github_list_workflows",
            {"owner": owner, "repo": repo},
            ctx,
            tool_events,
        )
        if error:
            if "404" in error or "Not Found" in error:
                return {"reply": f"Workflows for {repo_label} could not be found (404).", "citations": citations, "tool_events": tool_events}
            return {"reply": _format_github_error(error), "citations": citations, "tool_events": tool_events}
        items = list(payload.get("workflows") or [])
        reply = _format_named_items(
            f"GitHub Actions workflows for {repo_label}:",
            items,
            lambda item: item.get("name") or "unnamed-workflow",
            limit=20,
        )
        return {"reply": reply, "citations": citations, "tool_events": tool_events}

    file_path = _extract_file_path(user_text, (owner, repo))
    if not file_path and _contains_hint(user_text, FILE_HINTS):
        for role, content in reversed(_prior_entries(entries)):
            if role == "assistant":
                m = re.search(r"(?:File content for|Content preview for|Summary of) ([A-Za-z0-9_.\-/]+) in", content or "")
                if m:
                    file_path = m.group(1)
                    break

    if file_path and (_contains_hint(user_text, FILE_HINTS) or "." in file_path):
        resolved_file_path = await _resolve_file_path(
            owner,
            repo,
            file_path,
            entries,
            ctx,
            tool_events,
        )
        payload, error = await _call_github_tool(
            "github_get_file",
            {"owner": owner, "repo": repo, "path": resolved_file_path},
            ctx,
            tool_events,
        )
        if error:
            if "404" in error or "Not Found" in error:
                return {"reply": f"File `{resolved_file_path}` was not found in {repo_label}.", "citations": citations, "tool_events": tool_events}
            return {"reply": _format_github_error(error), "citations": citations, "tool_events": tool_events}

        content = (payload.get("content") or "").strip()
        if not content:
            reply = f"I found `{resolved_file_path}` in {repo_label}, but the file content was not available."
            return {"reply": reply, "citations": citations, "tool_events": tool_events}

        if _wants_raw_file_content(user_text):
            return {
                "reply": _format_file_content_reply(resolved_file_path, repo_label, content),
                "citations": citations,
                "tool_events": tool_events,
            }

        if _contains_hint(user_text, FILE_HINTS) or _contains_hint(user_text, EXPLAIN_HINTS) or "summary" in user_text.lower():
            try:
                summary = await _summarize_github_text(
                    getattr(request, "model", None),
                    f"{repo_label}:{resolved_file_path}",
                    user_text,
                    content,
                )
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                print(f"[_summarize_github_text Error]: {e}\n{error_trace}")
                return {
                    "reply": f"I found the file `{resolved_file_path}`, but I couldn't generate a summary because the internal LLM request failed: {str(e)}",
                    "citations": citations,
                    "tool_events": tool_events,
                }
            if summary:
                return {
                    "reply": f"Summary of {resolved_file_path} in {repo_label}:\n{summary}",
                    "citations": citations,
                    "tool_events": tool_events,
                }

        preview = content[:1200].strip()
        if len(content) > 1200:
            preview += "\n..."
        return {
            "reply": f"Content preview for {resolved_file_path} in {repo_label}:\n{preview}",
            "citations": citations,
            "tool_events": tool_events,
        }

    if _wants_directory_listing(user_text, file_path):
        directory_path = _extract_directory_path(user_text, (owner, repo)) or ""
        payload, error = await _call_github_tool(
            "github_list_directory",
            {"owner": owner, "repo": repo, "path": directory_path},
            ctx,
            tool_events,
        )
        if error:
            if "404" in error or "Not Found" in error:
                return {"reply": f"Directory `{directory_path or '/'}` was not found in {repo_label}.", "citations": citations, "tool_events": tool_events}
            return {"reply": _format_github_error(error), "citations": citations, "tool_events": tool_events}
        items = list(payload.get("items") or [])
        if _wants_ascii_tree(user_text):
            reply = _format_ascii_tree(repo_label, items)
        else:
            title = f"Files in {directory_path} of {repo_label}:" if directory_path else f"Top-level files in {repo_label}:"
            reply = _format_named_items(
                title,
                items,
                lambda item: f"{item.get('type') or 'item'} {item.get('path') or item.get('name') or 'unknown'}",
                limit=20,
            )
        return {"reply": reply, "citations": citations, "tool_events": tool_events}

    # Fallback: show repository info instead of returning None
    payload, error = await _call_github_tool(
        "github_get_repository",
        {"owner": owner, "repo": repo},
        ctx,
        tool_events,
    )
    if error:
        return {"reply": _format_github_error(error), "citations": citations, "tool_events": tool_events}
    reply = (
        f"Repository: {payload.get('full_name') or repo_label}\n"
        f"Description: {payload.get('description') or 'No description'}\n"
        f"Default branch: {payload.get('default_branch') or 'unknown'}\n"
        f"Language: {payload.get('language') or 'unknown'}\n"
        f"Visibility: {'private' if payload.get('private') else 'public'}\n"
        f"URL: {payload.get('html_url') or 'N/A'}"
    )
    return {"reply": reply, "citations": citations, "tool_events": tool_events}


async def maybe_handle_github_request(request: Any, ctx: ToolExecutionContext) -> dict[str, Any]:
    """Backend-controlled GitHub agent handler. ALWAYS returns a dict — NEVER None.

    Architecture:
      Backend = control plane (ALL decisions)
      MCP     = data layer (GitHub API access)
      LLM     = summarization / reasoning ONLY
    """
    user_text = _latest_user_text(getattr(request, "messages", []))
    if not user_text:
        return {
            "reply": GITHUB_CAPABILITIES_MESSAGE,
            "citations": [],
            "tool_events": [],
        }

    if not _is_github_connected(ctx):
        return {
            "reply": "GitHub is not connected for this account. Connect GitHub and try again.",
            "citations": [],
            "tool_events": [],
        }

    # --- Step 1: Intent Detection (rule-based) ---
    intent = detect_intent(user_text)

    # --- Step 2: Handle top-level intents that don't need a repo ---
    if intent == "auth_info":
        return await _handle_auth_info(ctx)
    if intent == "list_repos":
        return await _handle_repo_list(ctx, names_only=_wants_names_only(user_text))
    if intent == "search_repos":
        return await _handle_repo_search(user_text, ctx)

    # --- Step 3: Resolve repo from current/prior conversation ---
    tool_events: list[dict[str, Any]] = []
    repo_ref, resolved_items = await _resolve_repo_reference(request, ctx, tool_events)

    if repo_ref:
        # _handle_repo_detail now ALWAYS returns a dict (never None)
        detail_result = await _handle_repo_detail(request, ctx, repo_ref[0], repo_ref[1])
        detail_result["tool_events"] = tool_events + list(detail_result.get("tool_events") or [])
        return detail_result

    # --- Step 4: If we have a repo inventory, show it ---
    if intent == "repo_info" or intent == "list_repos":
        if resolved_items:
            return {
                "reply": _format_repo_list(list(resolved_items), names_only=_wants_names_only(user_text)),
                "citations": [],
                "tool_events": tool_events,
            }
        return await _handle_repo_list(ctx)

    # --- Step 5: LLM fallback classification for ambiguous queries ---
    if intent == "unknown":
        try:
            llm_intent = await _llm_classify_intent(user_text)
        except Exception:
            llm_intent = "unknown"
        if llm_intent != "unknown":
            # Re-run with reclassified intent — but only for intents that don't need a repo
            if llm_intent == "list_repos":
                return await _handle_repo_list(ctx)
            if llm_intent == "search_repos":
                return await _handle_repo_search(user_text, ctx)
            if llm_intent == "auth_info":
                return await _handle_auth_info(ctx)
            # For repo-specific intents, try to find a repo first
            repo_ref_retry, _ = await _resolve_repo_reference(request, ctx, tool_events)
            if repo_ref_retry:
                detail = await _handle_repo_detail(request, ctx, repo_ref_retry[0], repo_ref_retry[1])
                detail["tool_events"] = tool_events + list(detail.get("tool_events") or [])
                return detail

    # --- Step 6: Catch-all — NEVER return None ---
    return {
        "reply": GITHUB_CAPABILITIES_MESSAGE,
        "citations": [],
        "tool_events": tool_events,
    }


def github_workspace_fallback_reply(request: Any, error: Exception | None = None) -> dict[str, Any]:
    user_text = _latest_user_text(getattr(request, "messages", []))
    lowered = user_text.lower()
    if error and any(
        token in str(error).lower()
        for token in ("401", "unauthorized", "bad credentials", "requires authentication")
    ):
        return {
            "reply": (
                "GitHub authorization for this account is no longer valid. "
                "Disconnect GitHub, reconnect it, and try again."
            ),
            "citations": [],
            "tool_events": [],
        }
    if "repo" in lowered or "repository" in lowered:
        reply = "I could not complete the GitHub repository request right now. Try again in a moment."
    elif "issue" in lowered or "pull request" in lowered or "pr" in lowered:
        reply = "I could not fetch the requested GitHub issue or pull request data right now. Try again in a moment."
    else:
        reply = (
            "I could not complete the GitHub request right now. "
            "Try asking me to list repositories, inspect a specific owner/repo, or read a file from a repository."
        )
    if error:
        reply += f"\n\n[Traceback]\n{traceback.format_exc()}"
    return {"reply": reply, "citations": [], "tool_events": []}
