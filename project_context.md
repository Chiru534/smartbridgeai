# Project Context: Smartbridge AI Agent Platform

---

## Project Overview
The **Smartbridge AI Agent Platform** is a full‑stack AI‑powered application that provides a unified interface for:
- User authentication and profile management.
- Task creation, assignment, commenting and real‑time updates via Server‑Sent Events.
- Document ingestion, chunking, vector storage (Qdrant) and Retrieval‑Augmented Generation (RAG) using LLMs.
- Integration with external services (GitHub, Google Drive) through a Model Context Protocol (MCP) agent layer.
- Email notifications for key workflow events.

The backend is built with **FastAPI** and the frontend with **Vite + React (TypeScript)**, styled using **Tailwind CSS** and modern UI utilities.

---

## Tech Stack
| Layer | Technology | Key Packages |
|-------|------------|--------------|
| **Frontend** | Vite, React, TypeScript | `react`, `react-dom`, `axios`, `tailwindcss`, `framer-motion`, `lucide-react`, `sonner`, `next-themes` |
| **Backend** | FastAPI (Python) | `fastapi`, `uvicorn[standard]`, `pydantic`, `sqlalchemy`, `python‑dotenv`, `passlib[bcrypt]`, `slack-sdk` |
| **Database** | SQLite (default) – optional PostgreSQL via `psycopg[binary]` | `sqlite3`, `psycopg` |
| **Vector Store** | Qdrant | `qdrant-client` |
| **LLM / Embeddings** | Groq, Ollama (via `groq`), Sentence‑Transformers | `groq`, `sentence-transformers`, `google-auth` |
| **Document Processing** | PDF, DOCX, web search | `pymupdf`, `python-docx`, `duckduckgo-search` |
| **MCP Agent** | Custom protocol for tool calls | `mcp` |

---

## Folder Structure (important directories)
```
SmartbridgePlatform/
├─ backend/                     # FastAPI server
│   ├─ main.py                 # API entry point
│   ├─ notification_service.py # Slack/Email service
│   ├─ slack_client.py         # Slack SDK wrapper
│   ├─ archive/                # Past reports and docs
│   ├─ scripts/                # Backend utility scripts
│   ├─ tests/                  # Backend unit/integration tests
│   └─ ...
├─ frontend/                    # Vite + React UI
├─ docs/                        # Project documentation & analysis
├─ scripts/                     # Root utility & runner scripts
├─ project_context.md
├─ README.md
└─ .gitignore
```

---

## Coding Standards & Architectural Patterns
- **Backend (Python)**
  - Files and modules use **snake_case** naming.
  - Classes (e.g., `UserDB`, `TaskResponse`) use **PascalCase**.
  - FastAPI route functions are thin – they delegate to service / model layers.
  - Pydantic models (`BaseModel`) define request/response schemas; SQLAlchemy models inherit from `Base`.
  - Environment variables are loaded via `python‑dotenv` (`.env`).
  - Dependency injection (`Depends`) for DB session, authentication, and MCP manager.
  - Rate‑limiting middleware implemented in `main.py`.
  - SSE events broadcast through a global `sse_clients` set.
- **Frontend (TypeScript/React)**
  - Component files use **PascalCase** (`TaskList.tsx`, `LoginForm.tsx`).
  - Hook and utility files use **camelCase** (`useAuth.ts`, `apiClient.ts`).
  - Tailwind utility‑first styling; custom CSS kept in `index.css`.
  - API calls are centralized in `src/lib/api.ts` (axios instance).
  - State management via React Context for auth & SSE streams.
- **Overall Architecture**
  - **FastAPI + SQLite/PostgreSQL** backend exposing a **REST** API.
  - **React** SPA consumes the API.
  - **MCP** agents act as adapters for external services (GitHub, Google Drive).
  - **RAG pipeline** stores embeddings in Qdrant and retrieves context for LLM calls.
  - The project follows a **micro‑service‑ish** separation: `platform_core` for workspace logic, `pdf_pipeline` for document processing, `llm_*` for model interaction.

---

## 🏗 Technical Blueprints (AI-Ready Context)

### 💾 Core Database Schema (SQLAlchemy/SQLite)
| Table | Key Columns | Purpose |
|-------|-------------|---------|
| **`tasks`** | `id(PK)`, `title`, `status`, `assignee`, `due_date` | Main workflow items tracking. |
| **`task_comments`** | `id(PK)`, `task_id(FK)`, `author_name`, `comment` | Collaboration thread for tasks. |
| **`chat_messages`** | `id(PK)`, `session_id`, `role`, `content` | Persistent chat history for all agent modes. |
| **`knowledge_documents`**| `id(PK)`, `filename`, `uploaded_at` | Metadata for indexed documents (RAG). |
| **`users`** | `id(PK)`, `username`, `password_hash`, `email` | Core authentication data. |
| **`user_profiles`** | `user_id(FK)`, `display_name`, `role`, `preferred_model` | Customizable AI and user metadata. |
| **`audit_logs`** | `id(PK)`, `action`, `details_json` | Platform-wide event tracking. |
| **`connector_accounts`** | `id(PK)`, `connector_name`, `auth_method`, `config_json`| OAuth tokens & configs for GitHub/Google Drive. |

### 🔌 Primary API Handshake
| Method | Route | Request Payload | Response |
|--------|-------|-----------------|----------|
| **POST** | `/api/login` | `{username: str, password: str}` | `{access_token: str, token_type: str}` |
| **POST** | `/api/chat` | `{messages: Message[], mode: str, model: str}` | `{reply: str, citations: Citation[], tool_events: Event[]}` |
| **GET** | `/api/tasks` | `limit: int, offset: int` | `TaskResponse[]` |
| **POST** | `/api/tasks` | `{title: str, assignee: str, due_date: ISO8601}` | `TaskResponse` |
| **GET** | `/api/events` | *None* | **SSE Stream** (Real-time task/auth updates) |
| **POST** | `/api/knowledge/upload` | `multipart/form-data (file)` | `{success: bool, message: str}` |

### 🤖 MCP Tools (Agent Capabilities)
| Tool Name | Parameters | Target Workspace |
|-----------|------------|------------------|
| **`search_knowledge_base`**| `query`, `top_k` | `knowledge_base_rag` |
| **`search_document_session`**| `query`, `top_k`, `document_session_id` | `document_analysis` |
| **`create_task`** | `title`, `assignee`, `description`, `due_date` | `standard_chat` |
| **`list_database_tables`** | *None* | `sql_agent` |
| **`describe_table`** | `table_name` | `sql_agent` |
| **`run_safe_sql`** | `sql`, `row_limit` | `sql_agent` |

### 🔄 Standard Workflow Pattern
1. **Frontend Request**: User sends a prompt from a specific Workspace (e.g., `sql_agent`).
2. **Backend Gateway**: `main.py` authorizes the request and identifies the `mode`.
3. **Agent Loop**: `groq_tools_agent.py` retrieves the `system_prompt` and relevant `tools` from the `tool_registry`.
4. **Tool Execution**: If the LLM requests a tool call (e.g., `run_safe_sql`), the registry executes the logic and returns the **Observation**.
5. **Final Answer**: LLM synthesizes the observation into a user-friendly `reply`.
6. **Persistence**: The conversation is saved to `chat_messages` for session continuity.

---

## Current Progress
| Area | Implemented | Notes |
|------|-------------|-------|
| **Authentication** | ✅ Login, Register, token generation, password hashing, rate limiting | Simple bearer‑token store (in‑memory). |
| **User Profile** | ✅ CRUD endpoints, profile auto‑creation | Uses Pydantic + SQLAlchemy. |
| **Task Management** | ✅ Create, read, update, delete, comment endpoints | SSE broadcast for real‑time UI updates. |
| **Email Notifications** | ✅ SMTP integration (optional via env vars) | |
| **Slack Notifications** | ✅ Backend integration for key events | Async via FastAPI BackgroundTasks |
| **RAG / Vector Store** | ✅ Qdrant client, document chunker, `rag.py` scaffolding |
| **MCP Agents** | ✅ GitHub & Google Drive workspace stubs, fallback replies |
| **Frontend UI** | ✅ Vite project scaffold, Tailwind config, basic component structure |
| **Testing** | ✅ `tests/` folder with placeholder tests, `run_*.py` scripts |
| **DevOps** | ✅ `requirements.txt`, `package.json`, scripts for running dev servers |

---

## Next Steps (Missing Logic & Enhancements)
1. **Frontend Pages**
   - Implement login/register UI and token storage (e.g., `localStorage`).
   - Build task list, task detail, and comment components.
   - Add PDF upload flow and visualisation of processed chunks.
   - Integrate SSE client to receive real‑time task updates.
2. **Authentication Middleware**
   - Replace in‑memory token store with JWT or database‑backed sessions for production.
3. **RAG Completion**
   - Finish `rag.py` logic: embed documents, store in Qdrant, query during LLM calls.
   - Add endpoint to trigger document ingestion from the UI.
4. **MCP Agent Polish**
   - Complete GitHub and Google Drive workspace implementations (OAuth flow, file listing, commit actions).
5. **Testing & CI**
   - Write comprehensive unit tests for backend services and frontend components.
   - Set up GitHub Actions for linting, type‑checking, and test execution.
6. **Docker / Deployment**
   - Provide Dockerfiles for backend and frontend, and a `docker‑compose.yml` to spin up the full stack with Qdrant.
7. **Styling & UX**
   - Apply premium UI design: glass‑morphism cards, dark mode toggle, micro‑animations (Framer Motion).
   - Ensure responsive layout for mobile and desktop.
8. **Environment Management**
   - Add `.env.example` documentation for required variables (SMTP, DB URL, Qdrant host, LLM keys).
   - Validate config at startup and fail fast on missing secrets.
9. **Performance & Security**
   - Harden rate‑limiting, add CORS whitelist, enable HTTPS in production.
   - Review and sanitize all external inputs (file uploads, query parameters).

---

*This `project_context.md` file provides a concise snapshot of the Smartbridge Platform codebase, useful for onboarding new contributors or AI assistants.*
