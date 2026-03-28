from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

try:
    import backend.models as models
    import app.plugins.rag as rag
    from backend.database import engine
except ImportError:
    import models
    import app.plugins.rag as rag
    from database import engine

from .doc_sessions import document_session_store
from .mcp_stdio import default_mcp_manager
from .sql_safety import describe_table, list_database_tables, run_safe_sql
from .workspaces import get_workspace


@dataclass
class ToolExecutionContext:
    db: Session
    current_user: dict[str, Any]
    session_id: str
    mode: str
    workspace_options: dict[str, Any] = field(default_factory=dict)
    citations: list[dict[str, Any]] = field(default_factory=list)
    tool_events: list[dict[str, Any]] = field(default_factory=list)

    def add_citations(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            if item not in self.citations:
                self.citations.append(item)


@dataclass(frozen=True)
class NativeToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    modes: tuple[str, ...]
    handler: Callable[[dict[str, Any], ToolExecutionContext], dict[str, Any]]


def _safe_int(raw_value: Any, default: int) -> int:
    try:
        return max(1, int(raw_value))
    except (TypeError, ValueError):
        return default


def _tool_search_knowledge_base(arguments: dict[str, Any], ctx: ToolExecutionContext) -> dict[str, Any]:
    query = (arguments.get("query") or "").strip()
    top_k = _safe_int(arguments.get("top_k"), 5)
    if not query:
        return {"hits": [], "message": "query is required"}

    hits = rag.retrieve_relevant_chunk_records(query, top_k=top_k)
    if not hits:
        return {"hits": [], "message": "No relevant knowledge base results were found"}

    doc_ids = [hit["document_id"] for hit in hits if hit.get("document_id") is not None]
    doc_rows = {}
    if doc_ids:
        for row in ctx.db.query(models.KnowledgeDocumentDB).filter(models.KnowledgeDocumentDB.id.in_(doc_ids)).all():
            doc_rows[row.id] = row

    citations = []
    normalized_hits = []
    for hit in hits:
        doc = doc_rows.get(hit.get("document_id"))
        filename = doc.filename if doc else f"Document {hit.get('document_id')}"
        citation = {
            "source_type": "knowledge_base",
            "document_id": hit.get("document_id"),
            "label": filename,
            "chunk_index": hit.get("chunk_index"),
            "score": hit.get("score"),
        }
        citations.append(citation)
        normalized_hits.append(
            {
                "filename": filename,
                "document_id": hit.get("document_id"),
                "chunk_index": hit.get("chunk_index"),
                "score": hit.get("score"),
                "content": hit.get("content"),
            }
        )

    ctx.add_citations(citations)
    return {"hits": normalized_hits, "citation_count": len(citations)}


def _tool_search_document_session(arguments: dict[str, Any], ctx: ToolExecutionContext) -> dict[str, Any]:
    query = (arguments.get("query") or "").strip()
    session_id = (arguments.get("document_session_id") or ctx.workspace_options.get("document_session_id") or ctx.session_id).strip()
    top_k = _safe_int(arguments.get("top_k"), 5)
    if not query:
        return {"hits": [], "message": "query is required"}

    hits = document_session_store.search(session_id, query, top_k=top_k)
    citations = [
        {
            "source_type": "document_session",
            "label": hit.get("filename"),
            "chunk_index": hit.get("chunk_index"),
            "score": hit.get("score"),
        }
        for hit in hits
    ]
    ctx.add_citations(citations)
    return {"session_id": session_id, "hits": hits, "citation_count": len(citations)}


def _tool_create_task(arguments: dict[str, Any], ctx: ToolExecutionContext) -> dict[str, Any]:
    title = (arguments.get("title") or "").strip()
    assignee = (arguments.get("assignee") or "").strip()
    description = (arguments.get("description") or "").strip() or None
    due_date = (arguments.get("due_date") or "").strip() or None
    status = (arguments.get("status") or "Pending").strip() or "Pending"

    if not title:
        raise ValueError("title is required")
    if not assignee:
        raise ValueError("assignee is required")

    task = models.TaskDB(
        title=title,
        assignee=assignee,
        description=description,
        status=status,
    )
    if due_date:
        try:
            task.due_date = datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("due_date must be in YYYY-MM-DD format") from exc

    ctx.db.add(task)
    ctx.db.commit()
    ctx.db.refresh(task)
    return {
        "task_id": task.id,
        "title": task.title,
        "assignee": task.assignee,
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
    }


def _tool_list_database_tables(arguments: dict[str, Any], ctx: ToolExecutionContext) -> dict[str, Any]:
    return {"tables": list_database_tables(engine)}


def _tool_describe_table(arguments: dict[str, Any], ctx: ToolExecutionContext) -> dict[str, Any]:
    table_name = (arguments.get("table_name") or "").strip()
    return describe_table(engine, table_name)


def _tool_run_safe_sql(arguments: dict[str, Any], ctx: ToolExecutionContext) -> dict[str, Any]:
    sql = (arguments.get("sql") or "").strip()
    row_limit = arguments.get("row_limit")
    result = run_safe_sql(engine, sql, row_limit=_safe_int(row_limit, 200) if row_limit is not None else None)
    return result


NATIVE_TOOLS: dict[str, NativeToolDefinition] = {
    "search_knowledge_base": NativeToolDefinition(
        name="search_knowledge_base",
        description="Search the persistent knowledge base and return the most relevant chunks with citations.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for in the knowledge base"},
                "top_k": {"type": "integer", "description": "How many chunks to return", "default": 5},
            },
            "required": ["query"],
        },
        modes=("knowledge_base_rag",),
        handler=_tool_search_knowledge_base,
    ),
    "search_document_session": NativeToolDefinition(
        name="search_document_session",
        description="Search transient session documents uploaded for document analysis mode.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for in the uploaded session documents"},
                "top_k": {"type": "integer", "description": "How many chunks to return", "default": 5},
                "document_session_id": {"type": "string", "description": "Override the current document session id"},
            },
            "required": ["query"],
        },
        modes=("document_analysis",),
        handler=_tool_search_document_session,
    ),
    "create_task": NativeToolDefinition(
        name="create_task",
        description="Create a task in the local task manager.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "assignee": {"type": "string"},
                "description": {"type": "string"},
                "due_date": {"type": "string", "description": "Optional due date in YYYY-MM-DD format"},
                "status": {"type": "string", "enum": ["Pending", "In Progress", "Completed"]},
            },
            "required": ["title", "assignee"],
        },
        modes=("standard_chat", "knowledge_base_rag"),
        handler=_tool_create_task,
    ),
    "list_database_tables": NativeToolDefinition(
        name="list_database_tables",
        description="List tables and core columns available to the SQL agent.",
        parameters={"type": "object", "properties": {}},
        modes=("sql_agent",),
        handler=_tool_list_database_tables,
    ),
    "describe_table": NativeToolDefinition(
        name="describe_table",
        description="Describe the columns and types for a specific table.",
        parameters={
            "type": "object",
            "properties": {
                "table_name": {"type": "string"},
            },
            "required": ["table_name"],
        },
        modes=("sql_agent",),
        handler=_tool_describe_table,
    ),
    "run_safe_sql": NativeToolDefinition(
        name="run_safe_sql",
        description="Execute a read-only SQL statement with limits and safety checks.",
        parameters={
            "type": "object",
            "properties": {
                "sql": {"type": "string"},
                "row_limit": {"type": "integer", "default": 200},
            },
            "required": ["sql"],
        },
        modes=("sql_agent",),
        handler=_tool_run_safe_sql,
    ),
}


class ToolRegistry:
    async def openai_tools_for_mode(self, mode: str) -> list[dict[str, Any]]:
        workspace = get_workspace(mode)
        tools = []
        for tool_name in workspace.allowed_native_tools:
            tool = NATIVE_TOOLS.get(tool_name)
            if tool is None:
                continue
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )

        if workspace.mcp_servers:
            tools.extend(await default_mcp_manager.tools_for_servers(workspace.mcp_servers))
        return tools

    async def execute(self, tool_name: str, arguments: dict[str, Any], ctx: ToolExecutionContext) -> dict[str, Any]:
        try:
            if tool_name in NATIVE_TOOLS:
                result = NATIVE_TOOLS[tool_name].handler(arguments, ctx)
            else:
                result = await default_mcp_manager.call(
                    tool_name,
                    arguments,
                    injected_arguments={"connector_username": ctx.current_user["username"]},
                )
        except Exception as exc:
            result = {
                "tool_name": tool_name,
                "error": str(exc),
                "arguments": arguments,
            }

        ctx.tool_events.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "result_preview": json.dumps(result, ensure_ascii=True)[:1000],
            }
        )
        return result


tool_registry = ToolRegistry()
