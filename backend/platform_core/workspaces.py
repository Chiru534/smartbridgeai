from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class WorkspaceDefinition:
    id: str
    label: str
    short_label: str
    description: str
    system_prompt: str
    recommended_model: str
    allowed_native_tools: tuple[str, ...]
    mcp_servers: tuple[str, ...] = ()


WORKSPACE_DEFINITIONS: dict[str, WorkspaceDefinition] = {
    "standard_chat": WorkspaceDefinition(
        id="standard_chat",
        label="Standard Chat",
        short_label="Chat",
        description="General assistant chat with task creation and enterprise memory context.",
        system_prompt=(
            "You are the primary enterprise AI assistant. "
            "Answer directly, stay grounded, and use tools only when they materially improve the answer."
        ),
        recommended_model="llama-3.3-70b-versatile",
        allowed_native_tools=("create_task",),
    ),
    "knowledge_base_rag": WorkspaceDefinition(
        id="knowledge_base_rag",
        label="Knowledge Base RAG",
        short_label="Knowledge",
        description="Retrieve answers from the persistent Qdrant/PostgreSQL-backed knowledge base with citations.",
        system_prompt=(
            "You are in Knowledge Base mode. Prioritize the internal knowledge base and cite the retrieved sources."
        ),
        recommended_model="llama-3.3-70b-versatile",
        allowed_native_tools=("create_task", "search_knowledge_base"),
    ),
    "document_analysis": WorkspaceDefinition(
        id="document_analysis",
        label="Document Analysis",
        short_label="Docs",
        description="Session-only document retrieval over user-uploaded documents held in transient memory.",
        system_prompt=(
            "You are in Document Analysis mode. Use the uploaded session documents first and be explicit when evidence is missing."
        ),
        recommended_model="llama-3.3-70b-versatile",
        allowed_native_tools=("search_document_session",),
    ),
    "sql_agent": WorkspaceDefinition(
        id="sql_agent",
        label="SQL Agent",
        short_label="SQL",
        description="Generate and execute safe read-only SQL against the configured local database.",
        system_prompt=(
            "You are in SQL Agent mode. Inspect the schema before querying, keep queries read-only, and explain results clearly."
        ),
        recommended_model="llama-3.3-70b-versatile",
        allowed_native_tools=("list_database_tables", "describe_table", "run_safe_sql"),
    ),
    "github_agent": WorkspaceDefinition(
        id="github_agent",
        label="GitHub Agent",
        short_label="GitHub",
        description="Operate on GitHub repositories through MCP tools exposed from a local stdio subprocess.",
        system_prompt=(
            "You are in GitHub Agent mode. Use GitHub tools for repository operations and summarize any code or workflow changes carefully. "
            "When the user asks about their own repositories, first use the authenticated-user GitHub tools such as listing the connected user's repositories. "
            "Do not claim you cannot access GitHub or real-time data when GitHub tools are available."
        ),
        recommended_model="llama-3.3-70b-versatile",
        allowed_native_tools=(),
        mcp_servers=("github",),
    ),
    "google_drive_agent": WorkspaceDefinition(
        id="google_drive_agent",
        label="Google Drive Agent",
        short_label="Drive",
        description="Browse and manage Google Drive content through MCP tools exposed from a local stdio subprocess.",
        system_prompt=(
            "You are in Google Drive Agent mode. Use Drive tools for document operations and clearly identify selected files and folders. "
            "When the user asks about a specific file or asks for a summary of a document, prefer the combined Drive search-and-read tool so you search for the best match and then inspect its content before answering. "
            "If the user asks about folder contents, list the folder first. If content extraction fails, explain the file type limitation instead of claiming the file is missing. "
            "When the user asks to 'summarize', 'summary', or 'key points' of a file, output ONLY a concise summary (3-8 bullet points). Never output raw content or long text extracts for summary requests."
        ),
        recommended_model="llama-3.3-70b-versatile",
        allowed_native_tools=(),
        mcp_servers=("google_drive",),
    ),
    "slack_agent": WorkspaceDefinition(
        id="slack_agent",
        label="Slack Agent",
        short_label="Slack",
        description="Interact with Slack channels and messages through localized MCP tools.",
        system_prompt=(
            "You are in Slack Agent mode. Use Slack tools to search messages, list channels, or post updates. "
            "Be professional and summarize long threads when asked for a summary."
        ),
        recommended_model="llama-3.3-70b-versatile",
        allowed_native_tools=(),
        mcp_servers=("slack",),
    ),
}



WORKSPACE_ALIASES = {
    "chat": "standard_chat",
    "standard": "standard_chat",
    "standard_chat": "standard_chat",
    "knowledge": "knowledge_base_rag",
    "knowledge_base": "knowledge_base_rag",
    "knowledge_base_rag": "knowledge_base_rag",
    "document": "document_analysis",
    "document_analysis": "document_analysis",
    "sql": "sql_agent",
    "sql_agent": "sql_agent",
    "github": "github_agent",
    "github_agent": "github_agent",
    "drive": "google_drive_agent",
    "google_drive": "google_drive_agent",
    "google_drive_agent": "google_drive_agent",
    "slack": "slack_agent",
    "slack_agent": "slack_agent",
}



def normalize_workspace_id(raw_mode: str | None) -> str:
    if not raw_mode:
        return "standard_chat"
    return WORKSPACE_ALIASES.get(raw_mode.strip().lower(), "standard_chat")


def get_workspace(raw_mode: str | None) -> WorkspaceDefinition:
    return WORKSPACE_DEFINITIONS[normalize_workspace_id(raw_mode)]


def list_workspaces() -> list[dict]:
    return [asdict(workspace) for workspace in WORKSPACE_DEFINITIONS.values()]
