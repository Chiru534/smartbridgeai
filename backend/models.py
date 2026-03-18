from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Literal

try:
    from backend.database import Base
except ImportError:
    from database import Base

# SQLAlchemy Models
class TaskDB(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, nullable=True)
    assignee = Column(String, index=True)
    due_date = Column(DateTime, nullable=True)
    status = Column(String, default="Pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class TaskCommentDB(Base):
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), index=True)
    author_name = Column(String)
    comment = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ChatMessageDB(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=True)
    user_id = Column(String, index=True)
    role = Column(String)
    content = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class KnowledgeDocumentDB(Base):
    __tablename__ = "knowledge_documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class KnowledgeChunkDB(Base):
    __tablename__ = "knowledge_chunks"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    content = Column(String)
    embedding_json = Column(String)

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class UserProfileDB(Base):
    __tablename__ = "user_profiles"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    display_name = Column(String, nullable=False)
    role = Column(String, default="employee")
    preferred_model = Column(String, nullable=True)
    preferred_tone = Column(String, default="professional")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class UserSettingsDB(Base):
    __tablename__ = "user_settings"
    username = Column(String, primary_key=True, index=True)
    notification_preference = Column(String, default="email")

class TeamMessageDB(Base):
    __tablename__ = "team_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(String, index=True)
    receiver_id = Column(String, index=True)
    content = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_read = Column(Boolean, default=False)


class AuditLogDB(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    action = Column(String, index=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ConnectorAccountDB(Base):
    __tablename__ = "connector_accounts"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    connector_name = Column(String, index=True)
    auth_method = Column(String)
    config_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class IngestionJobDB(Base):
    __tablename__ = "ingestion_jobs"
    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String, index=True)
    source_name = Column(String, index=True)
    status = Column(String, default="queued")
    initiated_by = Column(String, index=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


class SqlQueryRunDB(Base):
    __tablename__ = "sql_query_runs"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    mode = Column(String, default="sql_agent")
    sql_text = Column(Text)
    row_count = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# Pydantic Schemas
class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, json_schema_extra={"strip_whitespace": True})
    description: Optional[str] = Field(None, max_length=500, json_schema_extra={"strip_whitespace": True})
    assignee: str = Field(..., min_length=1, max_length=50, json_schema_extra={"strip_whitespace": True})
    due_date: Optional[datetime] = None
    status: str = "Pending"

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100, json_schema_extra={"strip_whitespace": True})
    description: Optional[str] = Field(None, max_length=500, json_schema_extra={"strip_whitespace": True})
    assignee: Optional[str] = Field(None, min_length=1, max_length=50, json_schema_extra={"strip_whitespace": True})
    due_date: Optional[datetime] = None
    status: Optional[str] = None

class TaskCommentBase(BaseModel):
    task_id: int
    author_name: str = Field(..., min_length=1, max_length=50, json_schema_extra={"strip_whitespace": True})
    comment: str = Field(..., min_length=1, max_length=1000, json_schema_extra={"strip_whitespace": True})

class TaskCommentCreate(BaseModel):
    author_name: str = Field(..., min_length=1, max_length=50, json_schema_extra={"strip_whitespace": True})
    comment: str = Field(..., min_length=1, max_length=1000, json_schema_extra={"strip_whitespace": True})

class TaskCommentResponse(TaskCommentBase):
    id: int
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class TaskResponse(TaskBase):
    id: int
    created_at: datetime
    updated_at: datetime
    comments: List[TaskCommentResponse] = []

    model_config = ConfigDict(from_attributes=True)

class ChatMessageBase(BaseModel):
    role: str
    content: str

class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000, json_schema_extra={"strip_whitespace": True})
    role: Literal["user", "assistant"] = "user"
    session_id: Optional[str] = None

class ChatMessageResponse(ChatMessageBase):
    id: int
    user_id: str
    session_id: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class ChatSessionCreateResponse(BaseModel):
    session_id: str

class ChatSessionCloseRequest(BaseModel):
    session_id: str

class ChatMessageSessionResponse(BaseModel):
    session_id: str
    title: str
    last_message_timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class KnowledgeDocumentResponse(BaseModel):
    id: int
    filename: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserSettingsResponse(BaseModel):
    username: str
    notification_preference: str

    model_config = ConfigDict(from_attributes=True)

class UserSettingsUpdate(BaseModel):
    notification_preference: str

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, json_schema_extra={"strip_whitespace": True})
    password: str = Field(..., min_length=8, max_length=128)
    email: str = Field(..., min_length=5, max_length=255, json_schema_extra={"strip_whitespace": True})

class UserProfileResponse(BaseModel):
    user_id: int
    username: str
    email: str
    display_name: str
    role: str
    preferred_model: Optional[str] = None
    preferred_tone: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=100, json_schema_extra={"strip_whitespace": True})
    role: Optional[str] = Field(None, min_length=1, max_length=50, json_schema_extra={"strip_whitespace": True})
    preferred_model: Optional[str] = Field(None, min_length=1, max_length=100, json_schema_extra={"strip_whitespace": True})
    preferred_tone: Optional[str] = Field(None, min_length=1, max_length=100, json_schema_extra={"strip_whitespace": True})
    email: Optional[str] = Field(None, min_length=5, max_length=255, json_schema_extra={"strip_whitespace": True})

class TeamMessageCreate(BaseModel):
    receiver_id: str
    content: str
    
class TeamMessageResponse(BaseModel):
    id: int
    sender_id: str
    receiver_id: str
    content: str
    timestamp: datetime
    is_read: bool

    model_config = ConfigDict(from_attributes=True)

class UnreadCountResponse(BaseModel):
    unread_count: int


class CitationResponse(BaseModel):
    source_type: str
    label: str
    document_id: Optional[int] = None
    chunk_index: Optional[int] = None
    score: Optional[float] = None


class ToolEventResponse(BaseModel):
    tool_name: str
    arguments: dict
    result_preview: str


class WorkspaceDefinitionResponse(BaseModel):
    id: str
    label: str
    short_label: str
    description: str
    system_prompt: str
    recommended_model: str
    allowed_native_tools: list[str]
    mcp_servers: list[str]


class ConnectorStatusResponse(BaseModel):
    server: str
    configured: bool
    command: list[str]
    oauth_configured: bool = False
    pat_configured: bool = False
    service_account_configured: bool = False
    auth_flow: Optional[str] = None
    oauth_redirect_uri: Optional[str] = None
    setup_hint: Optional[str] = None
    last_error: Optional[str] = None


class ConnectorAccountSummaryResponse(BaseModel):
    connector_name: str
    connected: bool
    auth_method: Optional[str] = None
    display_name: Optional[str] = None
    login: Optional[str] = None
    email: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentSessionDocumentResponse(BaseModel):
    filename: str
    chunk_count: int
    uploaded_at: str


class ChatReplyResponse(BaseModel):
    reply: str
    session_id: str
    mode: str
    citations: list[CitationResponse] = Field(default_factory=list)
    tool_events: list[ToolEventResponse] = Field(default_factory=list)
