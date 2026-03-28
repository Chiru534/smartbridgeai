from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from typing import Any

import httpx

try:
    from backend.database import SessionLocal
except ImportError:
    from database import SessionLocal
try:
    from app.plugins.rag import extract_text
except ImportError:
    from app.plugins.rag import extract_text
from .config import settings
from .connectors import GOOGLE_DRIVE_API_URL, get_google_access_token

try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover - runtime dependency
    raise RuntimeError("Install the 'mcp' package to run the Google Drive MCP server") from exc


mcp = FastMCP("Smartbridge Google Drive MCP")
MAX_CONTENT_CHARS = 12000
TEXT_FILE_EXTENSIONS = {
    ".c",
    ".css",
    ".csv",
    ".html",
    ".java",
    ".js",
    ".json",
    ".log",
    ".md",
    ".py",
    ".sql",
    ".text",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
TEXT_MIME_TYPES = {
    "application/csv",
    "application/javascript",
    "application/json",
    "application/sql",
    "application/xml",
}
EXTRACTABLE_BINARY_EXTENSIONS = {".docx", ".pdf"}
EXTRACTABLE_BINARY_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
SEARCHABLE_FILE_EXTENSIONS = {
    "csv",
    "doc",
    "docx",
    "json",
    "md",
    "pdf",
    "ppt",
    "pptx",
    "sql",
    "txt",
    "xls",
    "xlsx",
}
FILE_LIST_FIELDS = "files(id,name,mimeType,modifiedTime,webViewLink,owners(displayName,emailAddress),parents,size),nextPageToken"


def _escape_query_value(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace("'", "\\'")


async def _drive_access_token(connector_username: str) -> str:
    db = SessionLocal()
    try:
        return await get_google_access_token(db, connector_username)
    finally:
        db.close()


async def _drive_request(
    connector_username: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    content: bytes | None = None,
    content_type: str | None = None,
    raw: bool = False,
    raw_bytes: bool = False,
    base_url: str = GOOGLE_DRIVE_API_URL,
) -> Any:
    access_token = await _drive_access_token(connector_username)
    headers = {"Authorization": f"Bearer {access_token}"}
    if content_type:
        headers["Content-Type"] = content_type

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.request(
            method,
            f"{base_url}{path}",
            headers=headers,
            params=params,
            json=json_body,
            content=content,
        )
        response.raise_for_status()
        if raw_bytes:
            return response.content
        if raw:
            return response.text
        if response.content:
            return response.json()
        return {"ok": True, "status_code": response.status_code}


async def _get_file_metadata(connector_username: str, file_id: str, fields: str | None = None) -> dict[str, Any]:
    return await _drive_request(
        connector_username,
        "GET",
        f"/files/{file_id}",
        params={
            "fields": fields or "id,name,mimeType,parents,owners(displayName,emailAddress),modifiedTime,webViewLink,size",
            "supportsAllDrives": "true",
        },
    )


def _multipart_drive_payload(metadata: dict[str, Any], content: str, mime_type: str) -> tuple[bytes, str]:
    boundary = f"smartbridge-{uuid.uuid4().hex}"
    metadata_json = json.dumps(metadata)
    body = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{metadata_json}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
        f"{content}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    return body, f"multipart/related; boundary={boundary}"


def _decode_text_bytes(payload: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def _normalize_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _add_candidate(candidates: list[str], seen: set[str], value: str) -> None:
    cleaned = " ".join((value or "").strip().split())
    lowered = cleaned.lower()
    if len(cleaned) < 2 or lowered in seen:
        return
    seen.add(lowered)
    candidates.append(cleaned)


def _search_query_candidates(query: str) -> list[str]:
    raw = " ".join((query or "").strip().split())
    if not raw:
        return []

    candidates: list[str] = []
    seen: set[str] = set()
    _add_candidate(candidates, seen, raw)

    quoted_segments = re.findall(r'"([^"]+)"|\'([^\']+)\'', raw)
    for double_quoted, single_quoted in quoted_segments:
        _add_candidate(candidates, seen, double_quoted or single_quoted)

    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9()_.-]*", raw)
    for index, token in enumerate(tokens):
        if "." not in token:
            continue
        extension = token.rsplit(".", 1)[-1].lower()
        if extension not in SEARCHABLE_FILE_EXTENSIONS:
            continue
        for window in range(1, min(6, index + 1) + 1):
            _add_candidate(candidates, seen, " ".join(tokens[index - window + 1:index + 1]))

    stripped = re.sub(
        r"(?i)\b(please|can you|could you|would you|give me|show me|open|read|summarize|summary|tell me|what is|what's|the|of|for|about|content|contents)\b",
        " ",
        raw,
    )
    stripped = re.sub(r"\s+", " ", stripped).strip(" ?!.,")
    _add_candidate(candidates, seen, stripped)
    return candidates


def _score_file_match(file_name: str, query_candidates: list[str]) -> int:
    normalized_name = _normalize_name(file_name)
    name_words = set(normalized_name.split())
    best_score = 0
    for candidate in query_candidates:
        normalized_candidate = _normalize_name(candidate)
        if not normalized_candidate:
            continue
        if normalized_name == normalized_candidate:
            best_score = max(best_score, 1000 + len(normalized_candidate))
            continue
        if normalized_candidate in normalized_name:
            best_score = max(best_score, 800 + len(normalized_candidate))
            continue
        if normalized_name in normalized_candidate:
            best_score = max(best_score, 650 + len(normalized_name))
            continue
        overlap = len(name_words.intersection(normalized_candidate.split()))
        if overlap >= 2:
            best_score = max(best_score, 100 * overlap + len(normalized_candidate))
    return best_score


def _bounded_content_payload(metadata: dict[str, Any], content: str, extraction_method: str, warning: str | None = None) -> dict[str, Any]:
    normalized = content or ""
    truncated = len(normalized) > MAX_CONTENT_CHARS
    bounded_content = normalized[:MAX_CONTENT_CHARS]
    payload = {
        "metadata": metadata,
        "content": bounded_content,
        "content_length": len(normalized),
        "truncated": truncated,
        "extraction_method": extraction_method,
    }
    if warning:
        payload["warning"] = warning
    return payload


async def _download_file_bytes(connector_username: str, file_id: str) -> bytes:
    return await _drive_request(
        connector_username,
        "GET",
        f"/files/{file_id}",
        params={"alt": "media", "supportsAllDrives": "true"},
        raw_bytes=True,
    )


def _root_folder_id() -> str:
    return settings.google_drive_root_folder_id or "root"


def _normalize_drive_path(path: str) -> list[str]:
    return [segment.strip() for segment in (path or "").replace("\\", "/").split("/") if segment.strip()]


def _extract_full_text_terms(query: str) -> list[str]:
    candidates = _search_query_candidates(query)
    terms: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        cleaned = " ".join(candidate.split()).strip()
        lowered = cleaned.lower()
        if len(cleaned) < 2 or lowered in seen:
            continue
        seen.add(lowered)
        terms.append(cleaned)
    return terms[:6]


async def _list_files_with_query(connector_username: str, query: str, page_size: int = 20) -> dict[str, Any]:
    return await _drive_request(
        connector_username,
        "GET",
        "/files",
        params={
            "pageSize": page_size,
            "q": query,
            "fields": FILE_LIST_FIELDS,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        },
    )


async def _find_children_by_name(
    connector_username: str,
    parent_id: str,
    name: str,
    *,
    folder_only: bool = True,
    page_size: int = 20,
) -> list[dict[str, Any]]:
    name_clause = f"name = '{_escape_query_value(name)}'"
    folder_clause = " and mimeType = 'application/vnd.google-apps.folder'" if folder_only else ""
    payload = await _list_files_with_query(
        connector_username,
        f"trashed=false and '{parent_id}' in parents and {name_clause}{folder_clause}",
        page_size=page_size,
    )
    return payload.get("files") or []


async def _resolve_folder_path(connector_username: str, path: str) -> dict[str, Any]:
    segments = _normalize_drive_path(path)
    current_parent = _root_folder_id()
    resolved_segments: list[dict[str, Any]] = []
    for segment in segments:
        matches = await _find_children_by_name(connector_username, current_parent, segment, folder_only=True)
        step = {
            "name": segment,
            "parent_id": current_parent,
            "matched_count": len(matches),
        }
        if len(matches) != 1:
            step["candidates"] = [
                {"id": row.get("id"), "name": row.get("name"), "mimeType": row.get("mimeType")}
                for row in matches[:5]
            ]
            resolved_segments.append(step)
            return {
                "input_path": path,
                "normalized_path": "/" + "/".join(segments),
                "root_id": _root_folder_id(),
                "found": False,
                "matched_id": None,
                "segments": resolved_segments,
            }
        selected = matches[0]
        current_parent = selected.get("id") or current_parent
        step["selected_id"] = selected.get("id")
        step["selected_name"] = selected.get("name")
        step["selected_mimeType"] = selected.get("mimeType")
        resolved_segments.append(step)

    return {
        "input_path": path,
        "normalized_path": "/" + "/".join(segments),
        "root_id": _root_folder_id(),
        "found": True,
        "matched_id": current_parent,
        "segments": resolved_segments,
    }


async def _drive_name_search(connector_username: str, query: str, page_size: int = 20) -> dict[str, Any]:
    query_candidates = _search_query_candidates(query)
    if not query_candidates:
        return {"files": [], "matched_query": None, "query_candidates": [], "nextPageToken": None}

    for candidate in query_candidates:
        payload = await _list_files_with_query(
            connector_username,
            f"trashed=false and name contains '{_escape_query_value(candidate)}'",
            page_size=page_size,
        )
        files = payload.get("files") or []
        if files:
            payload["matched_query"] = candidate
            payload["query_candidates"] = query_candidates
            return payload

    fallback_payload = await _list_files_with_query(connector_username, "trashed=false", page_size=max(page_size, 100))
    ranked_files = []
    for file_row in fallback_payload.get("files") or []:
        score = _score_file_match(file_row.get("name", ""), query_candidates)
        if score <= 0:
            continue
        ranked_files.append((score, file_row))
    ranked_files.sort(key=lambda item: item[0], reverse=True)
    return {
        "files": [row for _, row in ranked_files[:page_size]],
        "nextPageToken": fallback_payload.get("nextPageToken"),
        "matched_query": None,
        "query_candidates": query_candidates,
        "fallback_used": True,
    }


@mcp.tool()
async def list_files(connector_username: str, page_size: int = 20) -> dict[str, Any]:
    """List recent non-trashed Drive files and folders visible to the connected account."""
    return await _list_files_with_query(connector_username, "trashed=false", page_size=page_size)


@mcp.tool()
async def list_root(connector_username: str, page_size: int = 20) -> dict[str, Any]:
    """List the direct contents of Drive root or the configured Drive root folder when one is set."""
    root_id = _root_folder_id()
    payload = await _list_files_with_query(
        connector_username,
        f"trashed=false and '{root_id}' in parents",
        page_size=page_size,
    )
    payload["root_id"] = root_id
    payload["configured_root"] = bool(settings.google_drive_root_folder_id)
    return payload


@mcp.tool()
async def search_files(connector_username: str, query: str, page_size: int = 20) -> dict[str, Any]:
    """Search Drive files by filename or title. Natural-language requests that include a filename are supported."""
    return await _drive_name_search(connector_username, query, page_size=page_size)


@mcp.tool()
async def search_full_text(
    connector_username: str,
    query: str,
    page_size: int = 20,
    mime_filters: list[str] | None = None,
) -> dict[str, Any]:
    """Search Drive file contents using Drive full-text search, with optional MIME type filters."""
    query_terms = _extract_full_text_terms(query)
    if not query_terms:
        return {"files": [], "query_terms": [], "mime_filters": mime_filters or [], "nextPageToken": None}

    content_clause = " or ".join(f"fullText contains '{_escape_query_value(term)}'" for term in query_terms)
    mime_clause = ""
    if mime_filters:
        mime_parts = [f"mimeType = '{_escape_query_value(item)}'" for item in mime_filters if item]
        if mime_parts:
            mime_clause = " and (" + " or ".join(mime_parts) + ")"
    payload = await _list_files_with_query(
        connector_username,
        f"trashed=false and ({content_clause}){mime_clause}",
        page_size=page_size,
    )
    payload["query_terms"] = query_terms
    payload["mime_filters"] = mime_filters or []
    return payload


@mcp.tool()
async def list_folder(connector_username: str, folder_id: str, page_size: int = 50) -> dict[str, Any]:
    """List the direct contents of a Drive folder when you already know its folder ID."""
    payload = await _drive_request(
        connector_username,
        "GET",
        "/files",
        params={
            "pageSize": page_size,
            "q": f"trashed=false and '{folder_id}' in parents",
            "fields": "files(id,name,mimeType,modifiedTime,webViewLink,owners(displayName,emailAddress),parents,size),nextPageToken",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        },
    )
    return payload


@mcp.tool()
async def list_shared_with_me(connector_username: str, page_size: int = 20) -> dict[str, Any]:
    """List non-trashed Drive files currently shared with the connected account."""
    payload = await _drive_request(
        connector_username,
        "GET",
        "/files",
        params={
            "pageSize": page_size,
            "q": "sharedWithMe = true and trashed=false",
            "fields": "files(id,name,mimeType,modifiedTime,webViewLink,owners(displayName,emailAddress),parents,size),nextPageToken",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        },
    )
    return payload


@mcp.tool()
async def get_metadata(connector_username: str, file_id: str) -> dict[str, Any]:
    """Return Drive metadata for a specific file or folder ID."""
    return await _get_file_metadata(connector_username, file_id)


@mcp.tool()
async def read_text_file(connector_username: str, file_id: str) -> dict[str, Any]:
    """Read the text content of a Drive file. Supports Google Docs, Google Sheets, PDF, DOCX, TXT, CSV, JSON, Markdown, and other text-like files."""
    metadata = await _get_file_metadata(connector_username, file_id, fields="id,name,mimeType,modifiedTime,size,webViewLink")
    mime_type = metadata.get("mimeType", "")
    file_name = metadata.get("name", "") or file_id
    file_ext = os.path.splitext(file_name)[1].lower()
    if mime_type == "application/vnd.google-apps.document":
        content = await _drive_request(
            connector_username,
            "GET",
            f"/files/{file_id}/export",
            params={"mimeType": "text/plain"},
            raw=True,
        )
        return _bounded_content_payload(metadata, content, extraction_method="google_doc_export_text")
    elif mime_type == "application/vnd.google-apps.spreadsheet":
        content = await _drive_request(
            connector_username,
            "GET",
            f"/files/{file_id}/export",
            params={"mimeType": "text/csv"},
            raw=True,
        )
        return _bounded_content_payload(metadata, content, extraction_method="google_sheet_export_csv")

    if mime_type.startswith("text/") or mime_type in TEXT_MIME_TYPES or file_ext in TEXT_FILE_EXTENSIONS:
        content = _decode_text_bytes(await _download_file_bytes(connector_username, file_id))
        return _bounded_content_payload(metadata, content, extraction_method="decoded_text")

    if mime_type in EXTRACTABLE_BINARY_MIME_TYPES or file_ext in EXTRACTABLE_BINARY_EXTENSIONS:
        downloaded_bytes = await _download_file_bytes(connector_username, file_id)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext or ".bin") as tmp:
                tmp.write(downloaded_bytes)
                temp_path = tmp.name
            extracted_content = extract_text(temp_path, file_name)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

        warning = None
        if not extracted_content.strip():
            warning = f"No readable text could be extracted from '{file_name}'."
        return _bounded_content_payload(
            metadata,
            extracted_content,
            extraction_method="local_document_extraction",
            warning=warning,
        )

    return _bounded_content_payload(
        metadata,
        "",
        extraction_method="unsupported_binary",
        warning=(
            f"'{file_name}' uses unsupported content type '{mime_type or 'unknown'}'. "
            "Use metadata only or convert the file to PDF, DOCX, TXT, CSV, or Google Docs format."
        ),
    )


@mcp.tool()
async def search_and_read_file(connector_username: str, query: str, page_size: int = 10) -> dict[str, Any]:
    """Search for the best matching Drive file by name and immediately return its readable content when possible."""
    search_result = await _drive_name_search(connector_username, query, page_size=page_size)
    files = search_result.get("files") or []
    if not files:
        return {
            "query": query,
            "query_candidates": search_result.get("query_candidates", []),
            "matched_query": search_result.get("matched_query"),
            "message": "No matching Drive file was found.",
            "files": [],
        }

    best_match = files[0]
    if best_match.get("mimeType") == "application/vnd.google-apps.folder":
        folder_listing = await list_folder(connector_username, best_match["id"], page_size=page_size)
        return {
            "query": query,
            "matched_query": search_result.get("matched_query"),
            "query_candidates": search_result.get("query_candidates", []),
            "selected_item": best_match,
            "folder_contents": folder_listing.get("files", []),
            "message": f"Best match '{best_match.get('name')}' is a folder, so its direct contents were listed instead.",
        }

    content_result = await read_text_file(connector_username, best_match["id"])
    return {
        "query": query,
        "matched_query": search_result.get("matched_query"),
        "query_candidates": search_result.get("query_candidates", []),
        "selected_item": best_match,
        "search_results": files,
        **content_result,
    }


@mcp.tool()
async def resolve_path(connector_username: str, path: str) -> dict[str, Any]:
    """Resolve a slash-delimited Drive folder path relative to Drive root or the configured root folder."""
    return await _resolve_folder_path(connector_username, path)


@mcp.tool()
async def export_google_doc(connector_username: str, file_id: str, mime_type: str = "text/plain") -> dict[str, Any]:
    """Export a Google Doc into a target textual format such as plain text."""
    content = await _drive_request(
        connector_username,
        "GET",
        f"/files/{file_id}/export",
        params={"mimeType": mime_type},
        raw=True,
    )
    return {
        "file_id": file_id,
        "mime_type": mime_type,
        "content": content[:MAX_CONTENT_CHARS],
        "content_length": len(content),
        "truncated": len(content) > MAX_CONTENT_CHARS,
    }


@mcp.tool()
async def export_sheet_csv(connector_username: str, file_id: str) -> dict[str, Any]:
    """Export a Google Sheet as CSV text."""
    content = await _drive_request(
        connector_username,
        "GET",
        f"/files/{file_id}/export",
        params={"mimeType": "text/csv"},
        raw=True,
    )
    return {
        "file_id": file_id,
        "mime_type": "text/csv",
        "content": content[:MAX_CONTENT_CHARS],
        "content_length": len(content),
        "truncated": len(content) > MAX_CONTENT_CHARS,
    }


@mcp.tool()
async def create_folder(connector_username: str, name: str, parent_id: str | None = None) -> dict[str, Any]:
    """Create a new Drive folder, optionally under a parent folder ID."""
    metadata: dict[str, Any] = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]
    return await _drive_request(connector_username, "POST", "/files", json_body=metadata)


@mcp.tool()
async def upload_text_file(
    connector_username: str,
    name: str,
    content: str,
    parent_id: str | None = None,
    mime_type: str = "text/plain",
) -> dict[str, Any]:
    """Upload a new text file to Drive, optionally inside a parent folder."""
    metadata: dict[str, Any] = {"name": name}
    if parent_id:
        metadata["parents"] = [parent_id]
    body, content_type = _multipart_drive_payload(metadata, content, mime_type)
    return await _drive_request(
        connector_username,
        "POST",
        "/files",
        params={"uploadType": "multipart", "supportsAllDrives": "true"},
        content=body,
        content_type=content_type,
        base_url="https://www.googleapis.com/upload/drive/v3",
    )


@mcp.tool()
async def create_text_file_at_path(
    connector_username: str,
    path: str,
    content: str,
    mime_type: str = "text/plain",
) -> dict[str, Any]:
    """Create a text file at an existing slash-delimited Drive path relative to root or the configured root folder."""
    segments = _normalize_drive_path(path)
    if not segments:
        raise RuntimeError("A file path is required")

    file_name = segments[-1]
    folder_segments = segments[:-1]
    parent_id: str | None = None
    if folder_segments:
        folder_result = await _resolve_folder_path(connector_username, "/".join(folder_segments))
        if not folder_result.get("found"):
            raise RuntimeError(f"Drive folder path '/{'/'.join(folder_segments)}' does not exist or is ambiguous")
        parent_id = folder_result.get("matched_id")

    result = await upload_text_file(
        connector_username,
        name=file_name,
        content=content,
        parent_id=parent_id,
        mime_type=mime_type,
    )
    return {
        "path": "/" + "/".join(segments),
        "parent_id": parent_id or _root_folder_id(),
        **result,
    }


@mcp.tool()
async def update_text_file(
    connector_username: str,
    file_id: str,
    content: str,
    mime_type: str = "text/plain",
) -> dict[str, Any]:
    """Replace the content of an existing Drive text file."""
    existing = await _get_file_metadata(connector_username, file_id, fields="id,name,parents")
    metadata = {"name": existing.get("name")}
    body, content_type = _multipart_drive_payload(metadata, content, mime_type)
    return await _drive_request(
        connector_username,
        "PATCH",
        f"/files/{file_id}",
        params={"uploadType": "multipart", "supportsAllDrives": "true"},
        content=body,
        content_type=content_type,
        base_url="https://www.googleapis.com/upload/drive/v3",
    )


@mcp.tool()
async def delete_file(connector_username: str, file_id: str) -> dict[str, Any]:
    """Delete a Drive file or folder by ID."""
    return await _drive_request(connector_username, "DELETE", f"/files/{file_id}", params={"supportsAllDrives": "true"})


@mcp.tool()
async def move_file(connector_username: str, file_id: str, new_parent_id: str) -> dict[str, Any]:
    """Move a Drive file or folder into a different parent folder ID."""
    metadata = await _get_file_metadata(connector_username, file_id, fields="id,name,parents")
    current_parents = ",".join(metadata.get("parents", []))
    return await _drive_request(
        connector_username,
        "PATCH",
        f"/files/{file_id}",
        params={
            "addParents": new_parent_id,
            "removeParents": current_parents,
            "supportsAllDrives": "true",
        },
    )


@mcp.tool()
async def share_file(
    connector_username: str,
    file_id: str,
    email: str,
    role: str = "reader",
    permission_type: str = "user",
) -> dict[str, Any]:
    """Share a Drive file with a user email using the requested permission role."""
    return await _drive_request(
        connector_username,
        "POST",
        f"/files/{file_id}/permissions",
        params={"supportsAllDrives": "true", "sendNotificationEmail": "true"},
        json_body={
            "role": role,
            "type": permission_type,
            "emailAddress": email,
        },
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
