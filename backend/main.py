from fastapi import FastAPI, Depends, HTTPException, Security, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
import os
import shutil
import uuid
import asyncio
import secrets
import hashlib
import hmac
import base64
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel as PydanticBase
from typing import Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy import or_, and_, func
import re
import json
import tempfile


try:
    from backend.notification_service import notify_user_registered, notify_task_created, notify_task_updated, notify_task_commented
    from backend.database import engine, get_db, SessionLocal
    import backend.models as models
    import backend.llm_agent as llm_agent
    import app.plugins.rag as rag
    from backend.platform_core.doc_sessions import document_session_store
    from backend.platform_core.groq_tools_agent import run_workspace_chat
    from backend.platform_core.github_workspace import (
        github_workspace_fallback_reply,
        maybe_handle_github_request,
    )
    from backend.platform_core.google_drive_workspace import (
        drive_workspace_fallback_reply,
        maybe_handle_google_drive_request,
    )
    from backend.platform_core.mcp_stdio import default_mcp_manager
    from backend.platform_core.tool_registry import ToolExecutionContext
    from backend.platform_core.workspaces import list_workspaces as get_workspace_catalog, normalize_workspace_id
    from backend.platform_core.config import settings
    from backend.platform_core.connectors import (
        build_github_authorize_url,
        build_google_authorize_url,
        connector_error_html,
        connector_success_html,
        connector_redirect_uri,
        connector_setup_hint,
        exchange_github_code,
    exchange_google_code,
    fetch_github_profile,
    fetch_google_profile,
    get_connector_accounts_summary,
    is_connector_oauth_configured,
    is_connector_pat_configured,
    is_google_service_account_configured,
    is_google_service_account_runtime_ready,
    issue_oauth_state,
    pop_oauth_state,
    remove_connector_account,
    upsert_connector_account,
)
except ImportError:
    from notification_service import notify_user_registered, notify_task_created, notify_task_updated, notify_task_commented
    from database import engine, get_db, SessionLocal
    import models
    import llm_agent
    import app.plugins.rag as rag
    from platform_core.doc_sessions import document_session_store
    from platform_core.groq_tools_agent import run_workspace_chat
    from platform_core.github_workspace import (
        github_workspace_fallback_reply,
        maybe_handle_github_request,
    )
    from platform_core.google_drive_workspace import (
        drive_workspace_fallback_reply,
        maybe_handle_google_drive_request,
    )
    from platform_core.mcp_stdio import default_mcp_manager
    from platform_core.tool_registry import ToolExecutionContext
    from platform_core.workspaces import list_workspaces as get_workspace_catalog, normalize_workspace_id
    from platform_core.config import settings
    from platform_core.connectors import (
        build_github_authorize_url,
        build_google_authorize_url,
        build_slack_authorize_url, # Added for Slack OAuth
        connector_error_html,
        connector_success_html,
        connector_redirect_uri,
        connector_setup_hint,
        exchange_github_code,
        exchange_google_code,
        exchange_slack_code, # Added for Slack OAuth
        fetch_github_profile,
        fetch_google_profile,
        get_connector_accounts_summary,
        is_connector_oauth_configured,
        is_connector_pat_configured,
        is_google_service_account_configured,
        is_google_service_account_runtime_ready,
        issue_oauth_state,
        pop_oauth_state,
        remove_connector_account,
        upsert_connector_account,
        parse_github_url,
        fetch_github_repo_structure,
        fetch_github_file_content,
        get_connector_account,
        _parse_config,
    )

try:
    from passlib.context import CryptContext
except ImportError:  # pragma: no cover - install dependency in runtime env
    CryptContext = None

PASSWORD_CONTEXT = None

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

import smtplib
from email.message import EmailMessage

def send_email_notification(subject: str, body: str, recipient: str):
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    if not smtp_user or not smtp_pass:
        print("SMTP credentials not configured. Skipping email.")
        return
        
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = recipient

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"Email sent successfully to {recipient}")
    except Exception as e:
        print(f"Failed to send email: {e}")

# --- Rate Limiting ---
RATE_LIMIT_CACHE = {}
RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW_SECS = 60

def check_rate_limit(request: Request):
    ip = request.client.host if request.client else "127.0.0.1"
    now = datetime.now(timezone.utc)
    window = timedelta(seconds=RATE_LIMIT_WINDOW_SECS)

    # Evict stale IPs to prevent unbounded memory growth
    stale_ips = [k for k, v in RATE_LIMIT_CACHE.items() if not v or (now - v[-1]) > window]
    for k in stale_ips:
        del RATE_LIMIT_CACHE[k]

    if ip not in RATE_LIMIT_CACHE:
        RATE_LIMIT_CACHE[ip] = []

    # Clean up old timestamps outside the window
    RATE_LIMIT_CACHE[ip] = [t for t in RATE_LIMIT_CACHE[ip] if now - t < window]

    if len(RATE_LIMIT_CACHE[ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail="Rate limit reached. Wait 60 seconds."
        )

    RATE_LIMIT_CACHE[ip].append(now)

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smartbridge AI Agent Platform API")

# Mount the static files for uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security setup
security = HTTPBearer()

# Simple bearer token session store for MVP auth.
ACTIVE_TOKENS = {}
ACCESS_TOKEN_TTL_HOURS = int(os.getenv("ACCESS_TOKEN_TTL_HOURS", "24"))

DEFAULT_USERS = {
    "admin": {
        "password": "admin123",
        "display_name": "Admin",
        "role": "admin",
        "email": "admin@smartbridge.local",
    },
    "employee": {
        "password": "emp123",
        "display_name": "Employee",
        "role": "employee",
        "email": "employee@smartbridge.local",
    },
    "ravi": {
        "password": "ravi123",
        "display_name": "Ravi Sharma",
        "role": "employee",
        "email": "ravi@smartbridge.local",
    },
    "ananya": {
        "password": "ananya123",
        "display_name": "Ananya Patel",
        "role": "employee",
        "email": "ananya@smartbridge.local",
    },
}


def get_password_context():
    global CryptContext, PASSWORD_CONTEXT
    if PASSWORD_CONTEXT is not None:
        return PASSWORD_CONTEXT

    if CryptContext is None:
        try:
            from passlib.context import CryptContext as PasslibCryptContext
            CryptContext = PasslibCryptContext
        except ImportError:
            return None

    PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return PASSWORD_CONTEXT

def hash_password(raw_password: str) -> str:
    password_context = get_password_context()
    if password_context is not None:
        return password_context.hash(raw_password)

    # Fallback hash path for environments where passlib/bcrypt is not installed.
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"pbkdf2_sha256${salt}${base64.b64encode(digest).decode('utf-8')}"


def verify_password(raw_password: str, password_hash: str) -> bool:
    if password_hash.startswith("pbkdf2_sha256$"):
        try:
            _, salt, encoded_digest = password_hash.split("$", 2)
            expected_digest = base64.b64decode(encoded_digest.encode("utf-8"))
            computed_digest = hashlib.pbkdf2_hmac(
                "sha256",
                raw_password.encode("utf-8"),
                salt.encode("utf-8"),
                120000,
            )
            return hmac.compare_digest(expected_digest, computed_digest)
        except Exception:
            return False

    password_context = get_password_context()
    if password_context is None:
        return False
    return password_context.verify(raw_password, password_hash)


def create_access_token(username: str) -> str:
    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=ACCESS_TOKEN_TTL_HOURS)
    ACTIVE_TOKENS[token] = {"username": username, "issued_at": now, "expires_at": expires_at}
    return token


def remove_expired_tokens():
    now = datetime.now(timezone.utc)
    for token, payload in list(ACTIVE_TOKENS.items()):
        if payload["expires_at"] <= now:
            ACTIVE_TOKENS.pop(token, None)


def ensure_user_profile(db: Session, user: models.UserDB, default_display_name: Optional[str] = None, default_role: str = "employee"):
    profile = db.query(models.UserProfileDB).filter(models.UserProfileDB.user_id == user.id).first()
    if profile:
        return profile
    profile = models.UserProfileDB(
        user_id=user.id,
        display_name=default_display_name or user.username,
        role=default_role,
        preferred_model=None,
        preferred_tone="professional",
    )
    db.add(profile)
    db.flush()
    return profile


# ─── DEV / TEST MODE: Auth completely bypassed ───────────────────────────────
# get_current_user always returns a fixed admin user, no token required.
MOCK_USER_ID = 1  # uses whatever user id=1 is in the DB (seeded as 'admin')

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Returns a hardcoded admin user — authentication is disabled for testing."""
    # Try to load the real 'admin' db record for proper role/display_name
    db_user = db.query(models.UserDB).filter(models.UserDB.username == "admin").first()
    if db_user:
        profile = ensure_user_profile(db, db_user, default_display_name="Admin", default_role="admin")
        db.commit()
        return {
            "user_id": db_user.id,
            "username": db_user.username,
            "displayName": profile.display_name or "Admin",
            "role": profile.role or "admin",
            "email": db_user.email,
            "token": "dev-bypass-token",
        }
    # Fallback if DB is empty / admin not seeded yet
    return {
        "user_id": 1,
        "username": "admin",
        "displayName": "Admin",
        "role": "admin",
        "email": "admin@smartbridge.local",
        "token": "dev-bypass-token",
    }


def ensure_default_users():
    db = SessionLocal()
    try:
        for username, user_data in DEFAULT_USERS.items():
            db_user = db.query(models.UserDB).filter(models.UserDB.username == username).first()
            if not db_user:
                db_user = models.UserDB(
                    username=username,
                    password_hash=hash_password(user_data["password"]),
                    email=user_data["email"],
                )
                db.add(db_user)
                db.flush()

            profile = db.query(models.UserProfileDB).filter(models.UserProfileDB.user_id == db_user.id).first()
            if not profile:
                profile = models.UserProfileDB(
                    user_id=db_user.id,
                    display_name=user_data["display_name"],
                    role=user_data["role"],
                    preferred_model=None,
                    preferred_tone="professional",
                )
                db.add(profile)

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        print(f"Error seeding default users: {exc}")
        raise
    finally:
        db.close()


def require_non_empty(value: str, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} is required",
        )
    return cleaned

_app_loop = None
CHAT_SESSION_MIGRATION_KEY = "chat_session_backfill_v2"
SESSION_SPLIT_MINUTES = 30


def _parse_message_timestamp(raw_ts):
    if isinstance(raw_ts, datetime):
        return raw_ts
    if isinstance(raw_ts, str):
        # SQLite stores timestamps like "2026-03-09 11:37:48.590664"
        try:
            return datetime.fromisoformat(raw_ts)
        except ValueError:
            return None
    return None


def run_chat_session_migration():
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"))
        already_applied = conn.execute(
            text("SELECT 1 FROM schema_migrations WHERE name = :name"),
            {"name": CHAT_SESSION_MIGRATION_KEY}
        ).first()
        if already_applied:
            return

        # Ensure session_id column + index exist.
        try:
            conn.execute(text("ALTER TABLE chat_messages ADD COLUMN session_id VARCHAR;"))
        except Exception:
            # Column likely already exists.
            pass
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_messages_session_id ON chat_messages (session_id);"))

        legacy_rows = conn.execute(
            text(
                """
                SELECT id, user_id, role, timestamp
                FROM chat_messages
                WHERE session_id IS NULL OR session_id = 'legacy-session-0'
                ORDER BY user_id ASC, timestamp ASC, id ASC
                """
            )
        ).fetchall()

        current_user = None
        current_session_id = None
        previous_ts = None

        for row_id, user_id, role, timestamp_raw in legacy_rows:
            ts = _parse_message_timestamp(timestamp_raw)

            start_new_session = False
            if user_id != current_user:
                start_new_session = True
                previous_ts = None
            elif current_session_id is None:
                start_new_session = True
            elif role == "user" and ts and previous_ts and (ts - previous_ts) > timedelta(minutes=SESSION_SPLIT_MINUTES):
                start_new_session = True
            elif role == "user" and previous_ts is None:
                start_new_session = True

            if start_new_session:
                current_session_id = str(uuid.uuid4())

            conn.execute(
                text("UPDATE chat_messages SET session_id = :session_id WHERE id = :id"),
                {"session_id": current_session_id, "id": row_id}
            )

            current_user = user_id
            if ts:
                previous_ts = ts

        conn.execute(
            text("INSERT INTO schema_migrations (name, applied_at) VALUES (:name, :applied_at)"),
            {"name": CHAT_SESSION_MIGRATION_KEY, "applied_at": datetime.utcnow().isoformat()}
        )


@app.on_event("startup")
def on_startup():
    global _app_loop
    _app_loop = asyncio.get_running_loop()

    # Seed DB-backed auth users to preserve existing demo behavior.
    try:
        ensure_default_users()
    except Exception as exc:
        print(f"Default user seeding failed: {exc}")

    # One-time session-id backfill for legacy messages.
    try:
        run_chat_session_migration()
    except Exception:
        # Migration errors should not prevent API startup.
        pass

sse_clients = set()

def broadcast_event_sync(event_type: str, payload: dict):
    if not _app_loop:
        return
    message = json.dumps({"type": event_type, "payload": payload})
    for queue in list(sse_clients):
        try:
            _app_loop.call_soon_threadsafe(queue.put_nowait, message)
        except Exception:
            pass

@app.get("/api/events")
async def sse_events(request: Request, current_user: dict = Depends(get_current_user)):
    queue = asyncio.Queue()
    sse_clients.add(queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=2.0)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            sse_clients.discard(queue)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

class LoginRequest(PydanticBase):
    username: str
    password: str

def build_profile_response(db_user: models.UserDB, profile: models.UserProfileDB):
    return {
        "user_id": db_user.id,
        "username": db_user.username,
        "email": db_user.email,
        "display_name": profile.display_name,
        "role": profile.role,
        "preferred_model": profile.preferred_model,
        "preferred_tone": profile.preferred_tone,
        "created_at": db_user.created_at,
        "updated_at": profile.updated_at,
    }


@app.post("/api/register")
def register_user(request: models.RegisterRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    username = require_non_empty(request.username, "username").lower()
    password = require_non_empty(request.password, "password")
    email = require_non_empty(request.email, "email").lower()

    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing_by_username = db.query(models.UserDB).filter(models.UserDB.username == username).first()
    if existing_by_username:
        raise HTTPException(status_code=409, detail="Username already exists")

    existing_by_email = db.query(models.UserDB).filter(models.UserDB.email == email).first()
    if existing_by_email:
        raise HTTPException(status_code=409, detail="Email already exists")

    try:
        db_user = models.UserDB(
            username=username,
            password_hash=hash_password(password),
            email=email,
        )
        db.add(db_user)
        db.flush()

        profile = models.UserProfileDB(
            user_id=db_user.id,
            display_name=username,
            role="employee",
            preferred_model=None,
            preferred_tone="professional",
        )
        db.add(profile)
        db.commit()
        db.refresh(db_user)
        db.refresh(profile)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        print(f"Registration error: {exc}")
        raise HTTPException(status_code=500, detail="Failed to register user")

    token = create_access_token(db_user.username)
    # Prepare user info for Slack notification
    user_info = {
        "username": db_user.username,
        "displayName": profile.display_name,
        "email": db_user.email,
    }
    # Notify Slack about new user registration
    notify_user_registered(background_tasks, user_info)

    return {
        "token": token,
        "username": db_user.username,
        "displayName": profile.display_name,
        "role": profile.role,
        "email": db_user.email,
    }


@app.post("/api/login")
def handle_login(request: LoginRequest, db: Session = Depends(get_db)):
    username = require_non_empty(request.username, "username").lower()
    password = require_non_empty(request.password, "password")

    db_user = db.query(models.UserDB).filter(models.UserDB.username == username).first()
    if not db_user or not verify_password(password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    profile = ensure_user_profile(db, db_user, default_display_name=db_user.username)
    db.commit()
    db.refresh(profile)

    token = create_access_token(db_user.username)
    return {
        "token": token,
        "username": db_user.username,
        "displayName": profile.display_name,
        "role": profile.role,
        "email": db_user.email,
    }


@app.get("/api/user/profile", response_model=models.UserProfileResponse)
def get_user_profile(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = db.query(models.UserDB).filter(models.UserDB.id == current_user["user_id"]).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    profile = ensure_user_profile(db, db_user, default_display_name=current_user["displayName"], default_role=current_user["role"])
    db.commit()
    db.refresh(profile)
    return build_profile_response(db_user, profile)


@app.patch("/api/user/profile", response_model=models.UserProfileResponse)
def update_user_profile(profile_update: models.UserProfileUpdate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = db.query(models.UserDB).filter(models.UserDB.id == current_user["user_id"]).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = ensure_user_profile(db, db_user, default_display_name=current_user["displayName"], default_role=current_user["role"])
    update_data = profile_update.model_dump(exclude_unset=True)

    if "display_name" in update_data and update_data["display_name"]:
        profile.display_name = update_data["display_name"].strip()
    if "role" in update_data and update_data["role"]:
        profile.role = update_data["role"].strip()
    if "preferred_model" in update_data and update_data["preferred_model"]:
        profile.preferred_model = update_data["preferred_model"].strip()
    if "preferred_tone" in update_data and update_data["preferred_tone"]:
        profile.preferred_tone = update_data["preferred_tone"].strip()
    if "email" in update_data and update_data["email"]:
        new_email = update_data["email"].strip().lower()
        if "@" not in new_email:
            raise HTTPException(status_code=400, detail="Invalid email address")
        email_owner = db.query(models.UserDB).filter(models.UserDB.email == new_email, models.UserDB.id != db_user.id).first()
        if email_owner:
            raise HTTPException(status_code=409, detail="Email already exists")
        db_user.email = new_email

    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_user)
    db.refresh(profile)
    return build_profile_response(db_user, profile)

@app.get("/api/tasks", response_model=list[models.TaskResponse])
def read_tasks(skip: int = 0, limit: int = 100, assignee: Optional[str] = None, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # Optimization: Use joinedload for comments to avoid N+1 queries if we get more complex,
        # but for now lazy loading is fine since SQLite is fast.
        query = db.query(models.TaskDB)
        if assignee:
            query = query.filter(models.TaskDB.assignee == assignee)
        tasks = query.order_by(models.TaskDB.created_at.desc()).offset(skip).limit(limit).all()
        # Ensure comments are loaded
        for task in tasks:
            task.comments = db.query(models.TaskCommentDB).filter(models.TaskCommentDB.task_id == task.id).order_by(models.TaskCommentDB.timestamp.desc()).all()
        return tasks
    except Exception as e:
        print(f"Error fetching tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch tasks")

@app.post("/api/tasks", response_model=models.TaskResponse)
def create_task(task: models.TaskCreate, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_task = models.TaskDB(**task.model_dump())
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        db_task.comments = []
        task_resp = models.TaskResponse.model_validate(db_task).model_dump(mode="json")
        broadcast_event_sync("task_created", task_resp)
        print(f"NOTIFICATION: New task '{db_task.title}' assigned to {db_task.assignee}.")
        
        # Determine recipient - simplified for prototyping to use the sender's own auth smtp email
        recipient_email = os.getenv("SMTP_USER")
        if recipient_email:
            subject = f"[Smartbridge] New Task Assigned: {db_task.title}"
            body = f"Hello,\n\nA new task '{db_task.title}' has been assigned to {db_task.assignee} by {current_user.get('displayName', 'User')}.\n\nDescription: {db_task.description or 'No description provided.'}\n\nPlease check the Smartbridge platform for more details."
            background_tasks.add_task(send_email_notification, subject, body, recipient_email)
            
        # Notify Slack about task creation
        notify_task_created(background_tasks, task_resp, current_user)
        return db_task
    except Exception as e:
        db.rollback()
        print(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail="Failed to create task")

@app.put("/api/tasks/{task_id}", response_model=models.TaskResponse)
def update_task(task_id: int, task_update: models.TaskUpdate, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_task = db.query(models.TaskDB).filter(models.TaskDB.id == task_id).first()
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        update_data = task_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_task, key, value)
        
        db.commit()
        db.refresh(db_task)
        db_task.comments = db.query(models.TaskCommentDB).filter(models.TaskCommentDB.task_id == task_id).order_by(models.TaskCommentDB.timestamp.desc()).all()
        
        task_resp = models.TaskResponse.model_validate(db_task).model_dump(mode="json")
        broadcast_event_sync("task_updated", task_resp)
        print(f"NOTIFICATION: Task {task_id} updated. Status: {db_task.status}")
        
        recipient_email = os.getenv("SMTP_USER")
        if recipient_email:
            subject = f"[Smartbridge] Task Updated: {db_task.title}"
            body = f"Hello,\n\nThe task '{db_task.title}' has been updated to status '{db_task.status}'.\nAssignee: {db_task.assignee}\n\nPlease check the Smartbridge platform for more details."
            background_tasks.add_task(send_email_notification, subject, body, recipient_email)
            
        # Notify Slack about task update
        notify_task_updated(background_tasks, task_resp, current_user)
        return db_task
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error updating task: {e}")
        raise HTTPException(status_code=500, detail="Failed to update task")

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_task = db.query(models.TaskDB).filter(models.TaskDB.id == task_id).first()
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Also delete all associated comments
        db.query(models.TaskCommentDB).filter(models.TaskCommentDB.task_id == task_id).delete()
        
        db.delete(db_task)
        db.commit()
        broadcast_event_sync("task_deleted", {"task_id": task_id})
        print(f"NOTIFICATION: Task {task_id} deleted.")
        return {"success": True, "message": "Task deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error deleting task: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete task")


@app.post("/api/tasks/{task_id}/comments", response_model=models.TaskCommentResponse)
def add_task_comment(task_id: int, comment: models.TaskCommentCreate, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_task = db.query(models.TaskDB).filter(models.TaskDB.id == task_id).first()
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")
            
        new_comment = models.TaskCommentDB(
            task_id=task_id,
            author_name=comment.author_name,
            comment=comment.comment
        )
        db.add(new_comment)
        db.commit()
        db.refresh(new_comment)
        
        db_task.comments = db.query(models.TaskCommentDB).filter(models.TaskCommentDB.task_id == task_id).order_by(models.TaskCommentDB.timestamp.desc()).all()
        task_resp = models.TaskResponse.model_validate(db_task).model_dump(mode="json")
        broadcast_event_sync("task_updated", task_resp)
        
        recipient_email = os.getenv("SMTP_USER")
        if recipient_email:
            subject = f"[Smartbridge] New Comment on Task: {db_task.title}"
            body = f"Hello,\n\nA new comment was added to the task '{db_task.title}' by {comment.author_name}:\n\n\"{comment.comment}\"\n\nPlease check the Smartbridge platform for more details."
            background_tasks.add_task(send_email_notification, subject, body, recipient_email)
            
        # Notify Slack about new comment
        notify_task_commented(background_tasks, task_id, comment.model_dump(), current_user)
        return new_comment
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error adding comment: {e}")
        raise HTTPException(status_code=500, detail="Failed to add comment")

@app.get("/api/chat/sessions", response_model=list[models.ChatMessageSessionResponse])
def get_chat_sessions(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        from sqlalchemy import func
        # We need distinct session_ids, and we can use the first message of the session as a title
        sessions = db.query(
            models.ChatMessageDB.session_id,
            func.min(models.ChatMessageDB.timestamp).label("start_time"),
            func.max(models.ChatMessageDB.timestamp).label("last_time")
        ).filter(
            models.ChatMessageDB.user_id == current_user["username"],
            models.ChatMessageDB.session_id.isnot(None)
        ).group_by(models.ChatMessageDB.session_id).order_by(func.max(models.ChatMessageDB.timestamp).desc()).all()
        
        results = []
        for session_id, start_time, last_time in sessions:
            # Get the first user message for title to keep it simple
            first_msg = db.query(models.ChatMessageDB).filter(
                models.ChatMessageDB.session_id == session_id,
                models.ChatMessageDB.user_id == current_user["username"],
                models.ChatMessageDB.role == 'user'
            ).order_by(models.ChatMessageDB.timestamp.asc()).first()
            
            title = "New Conversation"
            if first_msg and first_msg.content:
                title = first_msg.content[:40] + ("..." if len(first_msg.content) > 40 else "")
                
            results.append({
                "session_id": session_id,
                "title": title,
                "last_message_timestamp": last_time
            })
            
        return results
    except Exception as e:
        print(f"Error fetching chat sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chat sessions")


@app.post("/api/chat/sessions", response_model=models.ChatSessionCreateResponse)
def create_chat_session(current_user: dict = Depends(get_current_user)):
    # Session is lightweight; it is persisted once first message is saved.
    return {"session_id": str(uuid.uuid4())}


@app.get("/api/chat/history", response_model=list[models.ChatMessageResponse])
def get_chat_history(session_id: Optional[str] = None, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        query = db.query(models.ChatMessageDB).filter(models.ChatMessageDB.user_id == current_user["username"])
        
        if session_id:
            query = query.filter(models.ChatMessageDB.session_id == session_id)
        else:
            # Default to the latest non-null session to avoid mixing multiple conversations together.
            latest_session_row = db.query(models.ChatMessageDB.session_id).filter(
                models.ChatMessageDB.user_id == current_user["username"],
                models.ChatMessageDB.session_id.isnot(None)
            ).order_by(models.ChatMessageDB.timestamp.desc()).first()

            if latest_session_row and latest_session_row[0]:
                query = query.filter(models.ChatMessageDB.session_id == latest_session_row[0])
            else:
                # Fallback for legacy rows created before session tracking.
                query = query.filter(models.ChatMessageDB.session_id.is_(None))
            
        messages = query.order_by(models.ChatMessageDB.timestamp.desc()).limit(100).all()
        return list(reversed(messages))
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chat history")


@app.post("/api/chat/message", response_model=models.ChatMessageResponse)
def create_chat_message(message: models.ChatMessageCreate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        resolved_session_id = message.session_id or str(uuid.uuid4())
        db_message = models.ChatMessageDB(
            session_id=resolved_session_id,
            user_id=current_user["username"],
            role=message.role,
            content=message.content
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        return db_message
    except Exception as e:
        db.rollback()
        print(f"Error saving chat message: {e}")
        raise HTTPException(status_code=500, detail="Failed to save chat message")


NAME_PATTERNS = [
    re.compile(r"\bmy name is\s+([A-Za-z][A-Za-z\s'\-]{0,49})", re.IGNORECASE),
    re.compile(r"\bi am\s+([A-Za-z][A-Za-z\s'\-]{0,49})", re.IGNORECASE),
    re.compile(r"\bcall me\s+([A-Za-z][A-Za-z\s'\-]{0,49})", re.IGNORECASE),
]


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def truncate_text(text: str, max_len: int) -> str:
    clean = normalize_whitespace(text)
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 3].rstrip() + "..."


def extract_display_name_from_message(content: str) -> Optional[str]:
    clean_text = normalize_whitespace(content)
    for pattern in NAME_PATTERNS:
        match = pattern.search(clean_text)
        if not match:
            continue
        name = match.group(1).strip(" .,!?:;\"'")
        name = re.sub(r"\s+", " ", name).strip()
        if len(name) < 2:
            continue
        return " ".join(part.capitalize() for part in name.split())
    return None


def hydrate_request_messages(
    db: Session,
    username: str,
    session_id: str,
    request_messages: list[llm_agent.ChatMessage],
    *,
    max_messages: int = 20,
) -> list[llm_agent.ChatMessage]:
    normalized_messages = [
        llm_agent.ChatMessage(role=message.role, content=message.content)
        for message in (request_messages or [])
        if getattr(message, "content", None)
    ]
    if not session_id or len(normalized_messages) >= 3:
        return normalized_messages[-max_messages:]

    history_rows = (
        db.query(models.ChatMessageDB)
        .filter(
            models.ChatMessageDB.user_id == username,
            models.ChatMessageDB.session_id == session_id,
        )
        .order_by(models.ChatMessageDB.timestamp.desc())
        .limit(max_messages)
        .all()
    )
    if not history_rows:
        return normalized_messages[-max_messages:]

    history_messages = [
        llm_agent.ChatMessage(role=row.role, content=row.content)
        for row in reversed(history_rows)
        if row.content
    ]
    return history_messages[-max_messages:]


def build_recent_session_summaries(db: Session, username: str, current_session_id: str, limit: int = 3):
    recent_session_rows = (
        db.query(
            models.ChatMessageDB.session_id,
            func.max(models.ChatMessageDB.timestamp).label("latest_ts"),
        )
        .filter(
            models.ChatMessageDB.user_id == username,
            models.ChatMessageDB.session_id.isnot(None),
            models.ChatMessageDB.session_id != current_session_id,
        )
        .group_by(models.ChatMessageDB.session_id)
        .order_by(func.max(models.ChatMessageDB.timestamp).desc())
        .limit(limit)
        .all()
    )

    summaries = []
    for idx, (session_id, _latest_ts) in enumerate(recent_session_rows, start=1):
        session_msgs = (
            db.query(models.ChatMessageDB)
            .filter(
                models.ChatMessageDB.user_id == username,
                models.ChatMessageDB.session_id == session_id,
            )
            .order_by(models.ChatMessageDB.timestamp.asc())
            .limit(30)
            .all()
        )
        if not session_msgs:
            continue

        first_user_msg = next((m.content for m in session_msgs if m.role == "user" and m.content), "")
        last_assistant_msg = next((m.content for m in reversed(session_msgs) if m.role == "assistant" and m.content), "")

        summary_parts = []
        if first_user_msg:
            summary_parts.append(f"{truncate_text(first_user_msg, 120)}")
        if last_assistant_msg:
            summary_parts.append(f"Response: {truncate_text(last_assistant_msg, 140)}")

        if summary_parts:
            summaries.append(f"- Conversation {idx}: " + " | ".join(summary_parts))
    return summaries


def build_personalized_system_prompt(profile: models.UserProfileDB, summaries: list[str]) -> str:
    display_name = profile.display_name or "the user"
    role = profile.role or "employee"
    preferred_tone = profile.preferred_tone or "professional"

    profile_line = (
        f"You are talking to {display_name} ({role}). "
        f"Use their name naturally when addressing them. "
        f"Preferred tone: {preferred_tone}."
    )

    memory_line = "No prior conversation summaries available."
    if summaries:
        memory_line = "Relevant recent conversations:\n" + "\n".join(summaries)

    return (
        profile_line
        + "\nRemember this user context across conversations.\n"
        + memory_line
        + "\n\n"
        + "Stay concise, accurate, and helpful. Use tools when needed and summarize their results clearly."
    )


from fastapi.responses import StreamingResponse
from app.runtime.AgentRuntime import AgentRuntime

agent_runtime = AgentRuntime()

@app.post("/api/chat")
async def chat_endpoint(request: llm_agent.ChatRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db), _: None = Depends(check_rate_limit)):
    session_id = request.session_id or ""
    request.mode = normalize_workspace_id(getattr(request, "mode", None))
    try:
        db_user = db.query(models.UserDB).filter(models.UserDB.id == current_user["user_id"]).first()
        if not db_user:
            raise HTTPException(status_code=401, detail="Invalid user session")
        
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
            
        newest_user_msg = ""
        if request.messages and request.messages[-1].role == 'user':
            newest_user_msg = request.messages[-1].content
            user_msg = models.ChatMessageDB(
                session_id=session_id,
                user_id=current_user["username"],
                role="user",
                content=newest_user_msg
            )
            db.add(user_msg)
            db.commit()

        # Build context hits
        context_hits = []
        if request.mode == "document_analysis":
            hits = document_session_store.search(session_id, newest_user_msg, top_k=5)
            context_hits = hits

        async def sse_stream_generator():
            """Yields SSE-formatted JSON events and saves the clean final message to DB."""
            import json as _json
            final_reply_parts = []
            try:
                async for sse_chunk in agent_runtime.run_loop_stream(request, context_hits):
                    yield sse_chunk
                    # Accumulate only 'message' type content for DB storage
                    try:
                        # SSE format: "data: {...}\n\n" — extract the JSON part
                        if sse_chunk.startswith("data: "):
                            event_data = _json.loads(sse_chunk[6:].strip())
                            if event_data.get("type") == "message":
                                final_reply_parts.append(event_data.get("content", ""))
                    except Exception:
                        pass
            finally:
                # Save the clean final reply to DB (no thought preamble)
                full_reply = "".join(final_reply_parts).strip()
                if full_reply:
                    assistant_msg = models.ChatMessageDB(
                        session_id=session_id,
                        user_id=current_user["username"],
                        role="assistant",
                        content=full_reply
                    )
                    db.add(assistant_msg)
                    db.commit()

        headers = {
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
        }
        return StreamingResponse(
            sse_stream_generator(),
            media_type="text/event-stream",
            headers=headers,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")




@app.get("/api/workspaces", response_model=list[models.WorkspaceDefinitionResponse])
def get_workspaces(current_user: dict = Depends(get_current_user)):
    rows = []
    for workspace in get_workspace_catalog():
        rows.append(
            {
                **workspace,
                "allowed_native_tools": list(workspace.get("allowed_native_tools", [])),
                "mcp_servers": list(workspace.get("mcp_servers", [])),
            }
        )
    return rows


@app.get("/api/connectors/accounts", response_model=list[models.ConnectorAccountSummaryResponse])
def get_connector_accounts(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_connector_accounts_summary(db, current_user["username"])


@app.get("/api/connectors/github/start")
def start_github_connector(current_user: dict = Depends(get_current_user)):
    if not settings.github_client_id or not settings.github_client_secret:
        return HTMLResponse(
            connector_error_html("github", connector_setup_hint("github")),
            status_code=503,
        )
    state = issue_oauth_state("github", current_user["username"])
    return RedirectResponse(build_github_authorize_url(state), status_code=307)


@app.get("/api/connectors/google/start")
def start_google_connector(current_user: dict = Depends(get_current_user)):
    if is_google_service_account_runtime_ready():
        return HTMLResponse(connector_success_html("google_drive"))
    if not settings.google_client_id or not settings.google_client_secret:
        return HTMLResponse(
            connector_error_html("google_drive", connector_setup_hint("google_drive")),
            status_code=503,
        )
    state = issue_oauth_state("google", current_user["username"])
    return RedirectResponse(build_google_authorize_url(state), status_code=307)


@app.get("/api/connectors/slack/start")
def start_slack_connector(current_user: dict = Depends(get_current_user)):
    if not settings.slack_client_id or not settings.slack_client_secret:
        return HTMLResponse(
            connector_error_html("slack", connector_setup_hint("slack")),
            status_code=503,
        )
    state = issue_oauth_state("slack", current_user["username"])
    return RedirectResponse(build_slack_authorize_url(state), status_code=307)


@app.get("/api/oauth/slack/callback", response_class=HTMLResponse)
async def slack_oauth_callback(code: Optional[str] = None, state: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        if not code or not state:
            return HTMLResponse(
                connector_error_html("slack", "Slack did not return the required OAuth callback parameters."),
                status_code=400,
            )
        state_payload = pop_oauth_state(state, "slack")
        token_data = await exchange_slack_code(code)
        profile = await fetch_slack_profile(token_data["access_token"])
        upsert_connector_account(
            db,
            username=state_payload.username,
            connector_name="slack",
            auth_method="oauth",
            config={
                "access_token": token_data.get("access_token"),
                "bot_user_id": token_data.get("bot_user_id"),
                "app_id": token_data.get("app_id"),
                "team_id": token_data.get("team.id"),
                "team_name": token_data.get("team.name"),
                "display_name": profile.get("user"),
                "login": profile.get("user"),
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "connected": True,
            },
        )
        return HTMLResponse(connector_success_html("slack"))
    except Exception as exc:
        return HTMLResponse(connector_error_html("slack", str(exc)), status_code=400)


@app.get("/api/oauth/github/callback", response_class=HTMLResponse)
async def github_oauth_callback(code: Optional[str] = None, state: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        if not code or not state:
            return HTMLResponse(
                connector_error_html("github", "GitHub did not return the required OAuth callback parameters."),
                status_code=400,
            )
        state_payload = pop_oauth_state(state, "github")
        token_data = await exchange_github_code(code)
        profile = await fetch_github_profile(token_data["access_token"])
        upsert_connector_account(
            db,
            username=state_payload.username,
            connector_name="github",
            auth_method="oauth",
            config={
                "access_token": token_data.get("access_token"),
                "token_type": token_data.get("token_type"),
                "scope": token_data.get("scope"),
                "login": profile.get("login"),
                "display_name": profile.get("name") or profile.get("login"),
                "email": profile.get("email"),
                "profile_url": profile.get("html_url"),
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "connected": True,
            },
        )
        return HTMLResponse(connector_success_html("github"))
    except Exception as exc:
        return HTMLResponse(connector_error_html("github", str(exc)), status_code=400)


@app.get("/api/oauth/google/callback", response_class=HTMLResponse)
async def google_oauth_callback(code: Optional[str] = None, state: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        if not code or not state:
            return HTMLResponse(
                connector_error_html("google_drive", "Google did not return the required OAuth callback parameters."),
                status_code=400,
            )
        state_payload = pop_oauth_state(state, "google")
        token_data = await exchange_google_code(code)
        profile = await fetch_google_profile(token_data["access_token"])
        expires_in = int(token_data.get("expires_in", 3600))
        upsert_connector_account(
            db,
            username=state_payload.username,
            connector_name="google_drive",
            auth_method="oauth",
            config={
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "scope": token_data.get("scope"),
                "token_type": token_data.get("token_type"),
                "display_name": profile.get("name") or profile.get("email"),
                "login": profile.get("email"),
                "email": profile.get("email"),
                "drive_user": profile.get("drive_user"),
                "storage_quota": profile.get("storage_quota"),
                "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat(),
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "connected": True,
            },
        )
        return HTMLResponse(connector_success_html("google_drive"))
    except Exception as exc:
        return HTMLResponse(connector_error_html("google_drive", str(exc)), status_code=400)


@app.delete("/api/connectors/{connector_name}")
def disconnect_connector(
    connector_name: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized = connector_name.strip().lower()
    if normalized not in {"github", "google_drive", "slack"}:
        raise HTTPException(status_code=404, detail="Connector not found")

    remove_connector_account(db, current_user["username"], normalized)
    return {"success": True}


@app.post("/api/github/repo-structure", response_model=models.GithubRepoStructureResponse)
async def get_github_repo_structure(
    request: models.GithubRepoStructureRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = parse_github_url(request.repo_url)
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
    
    owner, repo = parsed
    
    # Try to get access token from connected account if available
    access_token = None
    account = get_connector_account(db, current_user["username"], "github")
    if account:
        config = _parse_config(account)
        access_token = config.get("access_token")
    
    # Fallback to shared PAT if configured
    if not access_token and settings.github_pat:
        access_token = settings.github_pat

    try:
        tree = await fetch_github_repo_structure(owner, repo, access_token)
        files = []
        for item in tree:
            files.append(models.GithubFileItem(
                path=item["path"],
                type=item["type"], # 'blob' or 'tree'
                size=item.get("size"),
                url=item.get("url")
            ))
        return models.GithubRepoStructureResponse(owner=owner, repo=repo, files=files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repository structure: {str(e)}")


@app.post("/api/github/file-content", response_model=models.GithubFileContentResponse)
async def get_github_file_content(
    request: models.GithubFileContentRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = parse_github_url(request.repo_url)
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
    
    owner, repo = parsed
    
    # Try to get access token from connected account if available
    access_token = None
    account = get_connector_account(db, current_user["username"], "github")
    if account:
        config = _parse_config(account)
        access_token = config.get("access_token")
    
    # Fallback to shared PAT if configured
    if not access_token and settings.github_pat:
        access_token = settings.github_pat

    try:
        content = await fetch_github_file_content(owner, repo, request.file_path, access_token)
        return models.GithubFileContentResponse(path=request.file_path, content=content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch file content: {str(e)}")


@app.get("/api/connectors/status", response_model=list[models.ConnectorStatusResponse])
def get_connector_status(current_user: dict = Depends(get_current_user)):
    base_status_rows = {row["server"]: row for row in default_mcp_manager.status()}
    statuses = []
    for connector_name in ("github", "google_drive"):
        row = base_status_rows.get(
            connector_name,
            {
                "server": connector_name,
                "configured": False,
                "command": [],
                "last_error": None,
            },
        )
        callback_name = "google" if connector_name == "google_drive" else connector_name
        statuses.append(
            {
                **row,
                "oauth_configured": is_connector_oauth_configured(connector_name),
                "pat_configured": is_connector_pat_configured(connector_name),
                "service_account_configured": is_google_service_account_configured() if connector_name == "google_drive" else False,
                "auth_flow": (
                    "oauth_or_pat"
                    if connector_name == "github"
                    else ("service_account" if is_google_service_account_runtime_ready() else "oauth_popup")
                ),
                "oauth_redirect_uri": connector_redirect_uri(callback_name),
                "setup_hint": connector_setup_hint(connector_name),
            }
        )
    return statuses


@app.post("/api/document-analysis/upload")
async def upload_document_analysis(
    session_id: str,
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        uploaded = []
        for file in files:
            suffix = os.path.splitext(file.filename or "")[1]
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    shutil.copyfileobj(file.file, tmp)
                    temp_path = tmp.name
                text = rag.extract_text(temp_path, file.filename or "upload.txt")
                uploaded.append(document_session_store.ingest_text(session_id, file.filename or "upload.txt", text))
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
        return {
            "session_id": session_id,
            "documents": document_session_store.list_documents(session_id),
            "uploaded": uploaded,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/document-analysis/{session_id}", response_model=list[models.DocumentSessionDocumentResponse])
def get_document_analysis_session(session_id: str, current_user: dict = Depends(get_current_user)):
    return document_session_store.list_documents(session_id)


@app.delete("/api/document-analysis/{session_id}")
def clear_document_analysis_session(session_id: str, current_user: dict = Depends(get_current_user)):
    document_session_store.clear(session_id)
    return {"success": True}

@app.get("/api/available-models")
async def get_models(current_user: dict = Depends(get_current_user)):
    available_models = await llm_agent.get_available_models()
    return {"models": available_models}

@app.get("/api/health")
def health_check(current_user: dict = Depends(get_current_user)):
    return {"status": "ok", "version": "2.1.0"}

@app.post("/api/knowledge/upload")
async def upload_knowledge(file: UploadFile = File(...), current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        if not rag.is_qdrant_enabled():
            raise HTTPException(status_code=503, detail="Qdrant is required for knowledge uploads. Set QDRANT_URL.")

        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        text = rag.extract_text(file_path, file.filename)
        if not text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from file")
            
        doc = models.KnowledgeDocumentDB(filename=file.filename)
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        chunks = rag.chunk_text(text)
        if chunks:
            embeddings = rag.get_embeddings_batch(chunks)
            upsert_ok = rag.upsert_chunks_to_qdrant(doc.id, chunks, embeddings)
            if not upsert_ok:
                # Keep metadata consistent: if vectors fail, remove document metadata.
                db.delete(doc)
                db.commit()
                raise HTTPException(status_code=503, detail="Failed to index document in Qdrant.")
            
        return {"success": True, "message": f"Processed {len(chunks)} chunks"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error uploading file: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to process file")

@app.post("/api/upload_attachment")
async def upload_attachment(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    try:
        ext = file.filename.split(".")[-1] if "." in file.filename else ""
        unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
        file_path = os.path.join(UPLOAD_DIR, unique_name)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"filename": file.filename, "url": f"/uploads/{unique_name}"}
    except Exception as e:
        print(f"Error uploading attachment: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload attachment")



@app.get("/api/knowledge", response_model=list[models.KnowledgeDocumentResponse])
def get_knowledge(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.KnowledgeDocumentDB).order_by(models.KnowledgeDocumentDB.uploaded_at.desc()).all()

@app.delete("/api/knowledge/{doc_id}")
def delete_knowledge(doc_id: int, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        doc = db.query(models.KnowledgeDocumentDB).filter(models.KnowledgeDocumentDB.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        # Cleanup legacy SQLite chunk rows (if any) and Qdrant vectors.
        db.query(models.KnowledgeChunkDB).filter(models.KnowledgeChunkDB.document_id == doc_id).delete()
        rag.delete_chunks_from_qdrant(doc_id)
        db.delete(doc)
        db.commit()
        return {"success": True}
    except Exception as e:
        print("Error deleting document:", e)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete document")

@app.get("/api/settings", response_model=models.UserSettingsResponse)
def get_user_settings(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = db.query(models.UserSettingsDB).filter(models.UserSettingsDB.username == current_user["username"]).first()
    if not settings:
        settings = models.UserSettingsDB(username=current_user["username"], notification_preference="email")
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

@app.put("/api/settings", response_model=models.UserSettingsResponse)
def update_user_settings(settings_update: models.UserSettingsUpdate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = db.query(models.UserSettingsDB).filter(models.UserSettingsDB.username == current_user["username"]).first()
    if not settings:
        settings = models.UserSettingsDB(username=current_user["username"])
        db.add(settings)
        
    settings.notification_preference = settings_update.notification_preference
    db.commit()
    db.refresh(settings)
    return settings
