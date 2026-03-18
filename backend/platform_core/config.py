from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _parse_bool(raw_value: str | None, default: bool = False) -> bool:
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _split_command(raw_command: str | None) -> list[str]:
    if not raw_command:
        return []
    return shlex.split(raw_command, posix=os.name != "nt")


@dataclass(frozen=True)
class AppSettings:
    database_url: str = field(default_factory=lambda: (os.getenv("DATABASE_URL") or "sqlite:///./sql_app.db").strip())
    groq_api_key: str = field(default_factory=lambda: (os.getenv("GROQ_API_KEY") or "").strip())
    default_model: str = field(default_factory=lambda: (os.getenv("MODEL_NAME") or "llama-3.1-8b-instant").strip())
    frontend_url: str = field(default_factory=lambda: (os.getenv("FRONTEND_URL") or "http://localhost:5173").strip())
    public_backend_url: str = field(default_factory=lambda: (os.getenv("PUBLIC_BACKEND_URL") or "http://localhost:8000").strip())
    embeddings_model: str = field(default_factory=lambda: (os.getenv("EMBEDDINGS_MODEL") or "BAAI/bge-small-en-v1.5").strip())
    qdrant_collection: str = field(default_factory=lambda: (os.getenv("QDRANT_COLLECTION") or "knowledge_chunks").strip())
    qdrant_path: str = field(default_factory=lambda: (os.getenv("QDRANT_PATH") or "./qdrant_data").strip())
    qdrant_url: str = field(default_factory=lambda: (os.getenv("QDRANT_URL") or "").strip())
    qdrant_api_key: str = field(default_factory=lambda: (os.getenv("QDRANT_API_KEY") or "").strip())
    mcp_enabled: bool = field(default_factory=lambda: _parse_bool(os.getenv("MCP_ENABLED"), default=True))
    mcp_tool_timeout_secs: int = field(default_factory=lambda: int(os.getenv("MCP_TOOL_TIMEOUT_SECS") or "45"))
    github_mcp_command: list[str] = field(default_factory=lambda: _split_command(os.getenv("GITHUB_MCP_COMMAND") or "python -m backend.platform_core.github_mcp_server"))
    github_mcp_env_json: str = field(default_factory=lambda: (os.getenv("GITHUB_MCP_ENV_JSON") or "").strip())
    google_drive_mcp_command: list[str] = field(default_factory=lambda: _split_command(os.getenv("GOOGLE_DRIVE_MCP_COMMAND") or "python -m backend.platform_core.google_drive_mcp_server"))
    google_drive_mcp_env_json: str = field(default_factory=lambda: (os.getenv("GOOGLE_DRIVE_MCP_ENV_JSON") or "").strip())
    document_session_ttl_hours: int = field(default_factory=lambda: int(os.getenv("DOCUMENT_SESSION_TTL_HOURS") or "2"))
    sql_agent_row_limit: int = field(default_factory=lambda: int(os.getenv("SQL_AGENT_ROW_LIMIT") or "200"))
    sql_agent_timeout_ms: int = field(default_factory=lambda: int(os.getenv("SQL_AGENT_TIMEOUT_MS") or "5000"))
    oauth_state_ttl_secs: int = field(default_factory=lambda: int(os.getenv("OAUTH_STATE_TTL_SECS") or "900"))
    github_client_id: str = field(default_factory=lambda: (os.getenv("GITHUB_CLIENT_ID") or "").strip())
    github_client_secret: str = field(default_factory=lambda: (os.getenv("GITHUB_CLIENT_SECRET") or "").strip())
    github_oauth_scope: str = field(default_factory=lambda: (os.getenv("GITHUB_OAUTH_SCOPE") or "repo read:user user:email").strip())
    github_pat: str = field(default_factory=lambda: (os.getenv("GITHUB_PAT") or "").strip())
    google_client_id: str = field(default_factory=lambda: (os.getenv("GOOGLE_CLIENT_ID") or "").strip())
    google_client_secret: str = field(default_factory=lambda: (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip())
    google_service_account_email: str = field(default_factory=lambda: (os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL") or "").strip())
    google_service_account_json: str = field(default_factory=lambda: (os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip())
    google_service_account_json_path: str = field(default_factory=lambda: (os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH") or "").strip())
    google_drive_root_folder_id: str = field(default_factory=lambda: (os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID") or "").strip())
    google_oauth_scope: str = field(
        default_factory=lambda: (
            os.getenv("GOOGLE_OAUTH_SCOPE")
            or "openid email profile https://www.googleapis.com/auth/drive"
        ).strip()
    )

    @property
    def is_postgres(self) -> bool:
        return self.database_url.lower().startswith("postgresql")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()


settings = get_settings()
