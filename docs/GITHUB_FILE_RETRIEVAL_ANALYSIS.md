# GitHub Agent File Retrieval Failure Analysis
**Date:** March 16, 2026  
**Issue:** GitHub agent cannot retrieve and display file content when user asks "give me the code in database.py"

---

## Executive Summary

The GitHub agent's file retrieval system has **multiple critical failure points** that prevent successful file content display. While some components appear properly implemented, there are **authentication verification gaps**, **missing file path resolution logic**, and **incomplete MCP (Model Context Protocol) integration** that cause the request to fail before reaching GitHub.

### Key Finding
The user receives either:
1. **"GitHub is not connected"** message (even when authenticated)
2. **"404 Not Found"** or silent failures with no file content

---

## Expected Request Flow

### Ideal Flow When User Says "give me the code in database.py"

```
1. User Message → /api/chat endpoint (main.py:1092)
   ↓
2. Mode Detection: normalized_mode == "github_agent" (main.py:1118)
   ↓
3. Call maybe_handle_github_request() (github_workspace.py:1089)
   ├─ Check GitHub connection status (github_workspace.py:900)
   ├─ Parse repository reference from message
   ├─ Parse file path: "database.py" (github_workspace.py:240)
   └─ Resolve file path if needed (github_workspace.py:691)
   ↓
4. Call _handle_repo_detail() (github_workspace.py:680-790)
   ├─ Extract file_path from user_text (line 825)
   ├─ Call _resolve_file_path() if needed (line 828-834)
   └─ Call MCP tool: github_get_file (line 835-842)
   ↓
5. MCP Server (github_mcp_server.py)
   ├─ github_get_file() function (line 246-265)
   ├─ Get GitHub token via require_connector_token() (line 26)
   ├─ Make GitHub API call: GET /repos/{owner}/{repo}/contents/{path}
   └─ Decode base64 file content (line 35-37)
   ↓
6. Return file content to user (github_workspace.py:860-873)
```

---

## Current Code Flow & Failure Points

### **FAILURE POINT #1: GitHub Connection Check** 
**File:** [backend/platform_core/github_workspace.py](backend/platform_core/github_workspace.py#L900)  
**Function:** `_is_github_connected()`  
**Lines:** 297-301

```python
def _is_github_connected(ctx: ToolExecutionContext) -> bool:
    for row in get_connector_accounts_summary(ctx.db, ctx.current_user["username"]):
        if row.get("connector_name") == "github":
            return bool(row.get("connected"))
    return False
```

**Problem:** This function checks if GitHub is marked as "connected" in the database. However:

1. **Connection Status is Not Set During OAuth**
   - When user connects GitHub via OAuth, the code at [main.py:1318-1360](main.py#L1318-L1360) stores the account but doesn't set `connected=True`
   - Looking at [connectors.py:397-444](connectors.py#L397-L444), `get_connector_accounts_summary()` returns account info but the "connected" field depends on:
     - Account existence + auth_method validation
     - OR service account for Google Drive

2. **Database Nullable Issue**
   - The `ConnectorAccountDB` model likely stores account data, but there's **no explicit boolean field for connection status**
   - The `_parse_config()` function extracts a "connected" key that may not exist in the stored JSON

**Evidence:** [connectors.py:402-410](connectors.py#L402-L410)
```python
if connector_name == "github" and account is None and settings.github_pat:
    results.append(
        {
            "connector_name": connector_name,
            "connected": True,  # ← Only set to True for PAT fallback!
            ...
        }
    )
```

**Root Cause:** Account creation doesn't set a "connected" flag in the config JSON. The check relies on a non-existent field.

---

### **FAILURE POINT #2: Repository Reference Not Detected** 
**File:** [backend/platform_core/github_workspace.py](backend/platform_core/github_workspace.py#L604-L680)  
**Function:** `_resolve_repo_reference()`  
**Lines:** 604-680

**Problem:** When user says "give me the code in database.py":

1. **No Owner/Repo in Message**
   - `_extract_repo_reference(user_text)` pattern looks for "owner/repo" format
   - User only said "database.py" with no GitHub repo context
   - Function returns `None` → agent doesn't know which repo to search (line 609)

2. **Fallback Only Lists Repos, Doesn't Assume One**
   - Code tries to infer repo from conversation history (lines 640-648)
   - If no prior repo mentioned, it lists all user repos as fallback (lines 664-668)
   - **Does NOT automatically use the "most recent" repo from history**

**Evidence:** [github_workspace.py:687-688](github_workspace.py#L687-L688)
```python
if needs_repo_inventory:
    payload, error = await _call_github_tool(
        "github_list_my_repositories",
        {"per_page": 100},
        ctx,
        tool_events,
    )
```

**Root Cause:** Without explicit repo name in request, system can't determine target repository.

---

### **FAILURE POINT #3: File Path Extraction Incomplete**
**File:** [backend/platform_core/github_workspace.py](backend/platform_core/github_workspace.py#L220-L260)  
**Function:** `_extract_file_path()`  
**Lines:** 220-260

**Problem:** File path extraction has limited fallback patterns:

```python
def _extract_file_path(text: str, repo_ref: tuple[str, str] | None) -> str | None:
    # First pass: quoted/backtick paths (with or without slash)
    for groups in FILE_PATH_PATTERN.findall(text or ""):
        candidate = next((value for value in groups if value), "").strip().strip("/")
        # ...

    # Second pass: bare tokens that look like filenames (contain a dot with known extension)
    for match in FALLBACK_FILE_PATTERN.finditer(text or ""):
        candidate = match.group(1).strip().strip("/")
        # ...
    
    return None  # ← FAILURE if file not found by pattern matching
```

**Actual Pattern Definitions:** [github_workspace.py:73-74](github_workspace.py#L73-L74)
```python
FILE_PATH_PATTERN = re.compile(r"(?:`([^`]+)`|\"([^\"]+)\"|'([^']+)')")
FALLBACK_FILE_PATTERN = re.compile(r"\b([A-Za-z0-9_.\-/]+\.[A-Za-z0-9]+)\b")
```

**Failure Case:**
- User says: "give me the code in database.py"
- Pattern looks for: backticks, quotes, OR filename.extension
- "database.py" **should** match `FALLBACK_FILE_PATTERN` because it has a dot
- But if extraction fails, returns `None`

**Root Cause:** If file path is not extracted, line 825 check fails:
```python
file_path = _extract_file_path(user_text, (owner, repo))
if file_path and (_contains_hint(user_text, FILE_HINTS) or "." in file_path):
    # ← Only enters if file_path is truthy
```

---

### **FAILURE POINT #4: File Path Resolution Not Robust**
**File:** [backend/platform_core/github_workspace.py](backend/platform_core/github_workspace.py#L691-L720)  
**Function:** `_resolve_file_path()`  
**Lines:** 691-720

**Problem:** Attempts to resolve simple filename to full path, but has gaps:

```python
async def _resolve_file_path(
    owner: str,
    repo: str,
    raw_path: str,
    entries: list[tuple[str | None, str]],
    ctx: ToolExecutionContext,
    tool_events: list[dict[str, Any]],
) -> str:
    path = (raw_path or "").strip().strip("/")
    if not path or "/" in path:
        return path  # ← Returns as-is if it's already a path
```

**Issues:**
1. **No Default Root Directory Check**
   - If user says "database.py", code doesn't check repo root
   - Only searches in recent directory context or via GitHub code search API
   - GitHub code search is slow and may fail (429 rate limits)

2. **Search API Dependency**
   ```python
   payload, error = await _call_github_tool(
       "github_search_code",
       {"query": f"repo:{owner}/{repo} filename:{path}", "per_page": 10},
       ctx,
       tool_events,
   )
   ```
   - Code search API call can be slow (~2-5s per request)
   - May fail with rate limit or authorization errors
   - Doesn't fall back to simple root-level check

**Root Cause:** Missing simple heuristic: try repo root first before expensive searches.

---

### **FAILURE POINT #5: MCP Server Not Started**
**File:** [backend/platform_core/mcp_stdio.py](backend/platform_core/mcp_stdio.py#L45-L80)  
**Function:** `ensure_started()`  
**Lines:** 45-80

**Problem:** MCP server initialization can fail silently:

```python
async def ensure_started(self) -> bool:
    if not settings.mcp_enabled:
        self.last_error = "MCP integration is disabled"
        return False
    if not self.command:
        self.last_error = f"No command configured for MCP server '{self.name}'"
        return False
    if ClientSession is None or StdioServerParameters is None or stdio_client is None:
        self.last_error = "Install the 'mcp' Python package to enable MCP stdio subprocesses"
        return False
    # ... actual startup code ...
```

**Possible Failures:**
1. **MCP_ENABLED=false** in .env (disables all MCP tools)
2. **Missing MCP command** - GITHUB_MCP_COMMAND not configured correctly
3. **MCP package not installed** - requires `pip install mcp`
4. **Subprocess startup fails** on Windows (see Windows process creation fallback at lines 355-395)

**Example Configuration Issue:** [config.py:30-31](backend/platform_core/config.py#L30-L31)
```python
github_mcp_command: list[str] = field(
    default_factory=lambda: _split_command(
        os.getenv("GITHUB_MCP_COMMAND") or "python -m platform_core.github_mcp_server"
    )
)
```

If GITHUB_MCP_COMMAND is blank or malformed, the default command tries to run:
```bash
python -m platform_core.github_mcp_server
```

**This fails because:**
- The module path is incorrect from the subprocess perspective
- Should be: `python -m backend.platform_core.github_mcp_server` (with `backend.` prefix)
- OR requires proper PYTHONPATH configuration

**Root Cause:** Default MCP command has incorrect module path for subprocess invocation.

---

### **FAILURE POINT #6: Token Retrieval Fails**
**File:** [backend/platform_core/github_mcp_server.py](backend/platform_core/github_mcp_server.py#L22-29)  
**Function:** `_get_github_token()`  
**Lines:** 22-29

```python
def _get_github_token(connector_username: str) -> str:
    config = _get_github_config(connector_username)
    access_token = config.get("access_token")
    if not access_token:
        raise RuntimeError("GitHub access token is missing")
    return access_token
```

**Problem:** This function calls `_get_github_config()` which calls `require_connector_token()`:

```python
def _get_github_config(connector_username: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return require_connector_token(db, connector_username, "github")
    finally:
        db.close()
```

[connectors.py:460-471](connectors.py#L460-L471):
```python
def require_connector_token(db: Session, username: str, connector_name: str) -> dict[str, Any]:
    account = get_connector_account(db, username, connector_name)
    if account is None and connector_name == "github" and settings.github_pat:
        return {
            "access_token": settings.github_pat,
            "auth_method": "pat_env",
            "display_name": "Shared GitHub PAT",
        }
    if account is None:
        raise RuntimeError(f"{connector_name} is not connected for user '{username}'")
        # ← THIS IS THE ERROR MESSAGE USERS SEE!
```

**Root Cause:**
- If no ConnectorAccountDB record exists AND no GITHUB_PAT env var set
- Function raises: `RuntimeError("github is not connected for user 'username'")`
- This error message bubbles up to frontend as "GitHub is not connected"

---

## Issue Flow Diagram

```
User: "give me the code in database.py"
  |
  v
/api/chat endpoint (main.py:1092)
  |
  ├─→ Detect mode: "github_agent" (main.py:1118)
  |
  ├─→ maybe_handle_github_request() (github_workspace.py:1089)
  |
  └─→ _is_github_connected() [FAILURE POINT #1]
      ├─→ get_connector_accounts_summary()
      ├─→ Look for "connected": True in account
      └─→ RETURNS FALSE (account exists but no "connected" field)
          |
          └─→ Return error: "GitHub is not connected for this account"
          
          ===== IF THAT CHECK PASSES =====
          |
          ├─→ _resolve_repo_reference() [FAILURE POINT #2]
          |   ├─→ _extract_repo_reference(user_text)
          |   ├─→ NO "owner/repo" pattern found
          |   └─→ Lists all repos as fallback (slower path)
          |
          ├─→ _handle_repo_detail() [FAILURE POINT #3-4]
          |   ├─→ _extract_file_path() [FAILURE POINT #3]
          |   |   └─→ Extracts "database.py" if pattern matches
          |   |
          |   ├─→ _resolve_file_path() [FAILURE POINT #4]
          |   |   ├─→ Tries recent directory context
          |   |   └─→ Falls back to github_search_code API (slow/rate-limited)
          |   |
          |   └─→ Call MCP tool: github_get_file [FAILURE POINT #5-6]
          |       ├─→ default_mcp_manager.call() (tool_registry.py:169)
          |       ├─→ ManagedMCPServer.call_tool() (mcp_stdio.py:113-149)
          |       ├─→ ensure_started() [FAILURE POINT #5]
          |       |   ├─→ Check MCP_ENABLED
          |       |   ├─→ Check command configured
          |       |   └─→ Attempt subprocess startup
          |       |       └─→ FAILS: Wrong module path "platform_core.github_mcp_server"
          |       |           Should be "backend.platform_core.github_mcp_server"
          |       |
          |       └─→ github_get_file() in MCP server [FAILURE POINT #6]
          |           ├─→ _get_github_token() 
          |           ├─→ require_connector_token()
          |           └─→ RAISES: "github is not connected for user '...'"
          |
          └─→ Error handling (github_workspace.py:999-1009)
              └─→ Format error message and return to user
```

---

## Root Causes Summary

| # | Failure Point | Root Cause | Severity | Impact |
|---|---|---|---|---|
| **1** | GitHub Connection Check | "connected" field not set in DB during OAuth flow | **CRITICAL** | All GitHub requests fail immediately |
| **2** | Repo Reference Detection | No repo context when user only mentions filename | **HIGH** | Can't identify target repo without explicit mention |
| **3** | File Path Extraction | Limited pattern matching; may miss simple filenames | **MEDIUM** | Falls through to expensive API searches |
| **4** | File Path Resolution | No simple root-level check before expensive searches | **MEDIUM** | Performance degradation, rate limit hits |
| **5** | MCP Server Startup | Wrong module path in default command | **CRITICAL** | MCP subprocess never starts |
| **6** | Token Retrieval | No account record + no GITHUB_PAT fallback | **HIGH** | Tokens can't be retrieved for user |

---

## Specific Code Issues

### Issue #1: Missing "connected" Field During OAuth Setup
**File:** [main.py:1318-1360](main.py#L1318-L1360)  
**Current Code:**
```python
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
        # ... other fields ...
        # ← "connected": True is MISSING!
    },
)
```

**Should Be:**
```python
config={
    # ... existing fields ...
    "connected": True,  # ← ADD THIS
    # ... rest ...
}
```

---

### Issue #2: Wrong MCP Command Path
**File:** [config.py:30-31](backend/platform_core/config.py#L30-L31)  
**Current Code:**
```python
github_mcp_command: list[str] = field(
    default_factory=lambda: _split_command(
        os.getenv("GITHUB_MCP_COMMAND") or "python -m platform_core.github_mcp_server"
        #                                                    ↑ WRONG MODULE PATH
    )
)
```

**Should Be:**
```python
github_mcp_command: list[str] = field(
    default_factory=lambda: _split_command(
        os.getenv("GITHUB_MCP_COMMAND") or "python -m backend.platform_core.github_mcp_server"
        #                                                            ↑ ADD "backend." prefix
    )
)
```

**OR in .env:**
```bash
GITHUB_MCP_COMMAND="python -m backend.platform_core.github_mcp_server"
```

---

### Issue #3: github_get_file Tool Not Finding Files
**File:** [github_mcp_server.py:246-265](backend/platform_core/github_mcp_server.py#L246-265)  
**Current Implementation:**
```python
async def get_file(connector_username: str, owner: str, repo: str, path: str, ref: str | None = None) -> dict[str, Any]:
    """Get the string content, code, or payload of a file from a GitHub repository."""
    params = {"ref": ref} if ref else None
    payload, _ = await _github_request(
        connector_username,
        "GET",
        f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}",
        params=params,
    )
    return _decode_github_file_payload(payload)
```

**Problem:** If path is already full (e.g., "backend/database.py"), this works. But if path is bare filename ("database.py") and GitHub API returns 404, there's **no fallback**.

**Also:** `_decode_github_file_payload()` expects base64-encoded content, but may receive an error dict from GitHub API 404 response.

---

### Issue #4: Connection Check Logic Broken in github_workspace.py
**File:** [github_workspace.py:297-301](backend/platform_core/github_workspace.py#L297-301)  
**Current Code:**
```python
def _is_github_connected(ctx: ToolExecutionContext) -> bool:
    for row in get_connector_accounts_summary(ctx.db, ctx.current_user["username"]):
        if row.get("connector_name") == "github":
            return bool(row.get("connected"))
    return False
```

**Problem:** This checks for `row.get("connected")` which must be explicitly set. But:
1. OAuth flow doesn't set this field (Issue #1)
2. No account at all → returns False (when it could use GITHUB_PAT)

**Better Implementation:**
```python
def _is_github_connected(ctx: ToolExecutionContext) -> bool:
    for row in get_connector_accounts_summary(ctx.db, ctx.current_user["username"]):
        if row.get("connector_name") == "github":
            # Check if account is connected OR if shared PAT is available
            if row.get("connected") or row.get("auth_method") == "pat_env":
                return True
    return False
```

---

## Testing the File Retrieval

### Test Case: User Asks for database.py

**Setup Prerequisites:**
1. ✅ User logged in
2. ❌ GitHub connected (fails at FAILURE POINT #1)
3. ❌ MCP server running (fails at FAILURE POINT #5)
4. Repository context: unknown (fails at FAILURE POINT #2)

**Expected Error Sequence:**
```
Step 1: /api/chat → github_agent mode detected
Step 2: maybe_handle_github_request() called
Step 3: _is_github_connected() returns False
Step 4: Return:  {"reply": "GitHub is not connected...", "citations": [], "tool_events": []}
```

---

## Recommended Fixes (Priority Order)

### 🔴 P0: Fix GitHub Connection Detection
**Location:** [main.py:1336](main.py#L1336) (OAuth callback) AND [connectors.py:400-410](connectors.py#L400-L410)

1. **Add "connected": True to OAuth config**
2. **Or modify _is_github_connected() to check for valid access_token**

```python
# In main.py oauth callback:
config={
    "access_token": token_data.get("access_token"),
    # ... other fields ...
    "connected": True,  # ← ADD THIS LINE
}

# Or in github_workspace.py _is_github_connected():
def _is_github_connected(ctx: ToolExecutionContext) -> bool:
    try:
        for row in get_connector_accounts_summary(ctx.db, ctx.current_user["username"]):
            if row.get("connector_name") == "github":
                # Check if account has valid token OR shared PAT available
                if row.get("auth_method") == "oauth" or row.get("auth_method") == "pat_env":
                    return True
    except:
        pass
    return False
```

### 🔴 P0: Fix MCP Command Path
**Location:** [config.py:31](backend/platform_core/config.py#L31)

```python
github_mcp_command: list[str] = field(
    default_factory=lambda: _split_command(
        os.getenv("GITHUB_MCP_COMMAND") or "python -m backend.platform_core.github_mcp_server"
    )
)

google_drive_mcp_command: list[str] = field(
    default_factory=lambda: _split_command(
        os.getenv("GOOGLE_DRIVE_MCP_COMMAND") or "python -m backend.platform_core.google_drive_mcp_server"
    )
)
```

### 🟠 P1: Improve File Path Resolution
**Location:** [github_workspace.py:691-720](backend/platform_core/github_workspace.py#L691-L720)

Add root-level check before expensive search:
```python
async def _resolve_file_path(
    owner: str,
    repo: str,
    raw_path: str,
    entries: list[tuple[str | None, str]],
    ctx: ToolExecutionContext,
    tool_events: list[dict[str, Any]],
) -> str:
    path = (raw_path or "").strip().strip("/")
    if not path or "/" in path:
        return path
    
    # NEW: Try root-level file first (fast path)
    payload, error = await _call_github_tool(
        "github_list_directory",
        {"owner": owner, "repo": repo, "path": ""},  # List root
        ctx,
        tool_events,
    )
    if not error:
        items = payload.get("items", [])
        for item in items:
            if item.get("name", "").lower() == path.lower():
                return path  # Found at root!
    
    # Fallback: Check recent directory
    recent_directory = _extract_recent_directory_path(entries, (owner, repo))
    if recent_directory:
        return f"{recent_directory.rstrip('/')}/{path}"
    
    # Last resort: Code search (slow)
    # ... existing search code ...
```

### 🟠 P1: Better Error Handling in github_get_file
**Location:** [github_mcp_server.py:246-265](backend/platform_core/github_mcp_server.py#L246-265)

```python
async def get_file(connector_username: str, owner: str, repo: str, path: str, ref: str | None = None) -> dict[str, Any]:
    params = {"ref": ref} if ref else None
    try:
        payload, _ = await _github_request(
            connector_username,
            "GET",
            f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}",
            params=params,
        )
        if not isinstance(payload, dict):
            return {"error": "Invalid response from GitHub API"}
        
        # Check if response is an error
        if payload.get("message"):  # GitHub API error format
            return {"error": payload.get("message"), "documentation_url": payload.get("documentation_url")}
        
        return _decode_github_file_payload(payload)
    except Exception as e:
        return {"error": str(e)}
```

---

## Verification Checklist

After applying fixes, verify:

- [ ] **Connection Check:** User can see GitHub connected status in /api/connectors/accounts
- [ ] **MCP Server:** Subprocess starts without errors (check logs for "Smartbridge GitHub MCP" server started)
- [ ] **Token Access:** MCP server can successfully call _get_github_token()
- [ ] **File Retrieval:** User can ask "give me the code in database.py" and receive file content
- [ ] **Error Messages:** Clear, actionable error messages if GitHub not connected
- [ ] **Fallback:** GITHUB_PAT env var works as fallback when no user account

---

## Environment Variables to Check

```bash
# Critical for MCP
MCP_ENABLED=true
GITHUB_MCP_COMMAND="python -m backend.platform_core.github_mcp_server"

# Optional fallback token (if no OAuth)
GITHUB_PAT="ghp_xxxxxxxxxxxx"

# OAuth configuration (if using OAuth)
GITHUB_CLIENT_ID="Iv1.xxxxx..."
GITHUB_CLIENT_SECRET="xxxxx..."

# LLM provider
GROQ_API_KEY="gsk_xxxxx..."
MODEL_NAME="llama-3.1-8b-instant"
```

---

## Summary Table of Findings

| Component | Status | Issue | Fix |
|---|---|---|---|
| **GitHub Connection Check** | ❌ BROKEN | "connected" field not set in auth data | Add field to OAuth config |
| **Repo Reference Detection** | ⚠️ WORKS (slow) | Falls back to list all repos | Document limitation |
| **File Path Extraction** | ✅ OK | Pattern matching works for "database.py" | N/A |
| **File Resolution** | ⚠️ WORKS (slow) | Uses expensive code search | Add root-level check first |
| **MCP Server Startup** | ❌ BROKEN | Wrong module path in default command | Fix to "backend.platform_core..." |
| **Token Retrieval** | ⚠️ CONDITIONAL | Works if account exists; fails if not | Check account + GITHUB_PAT |
| **GitHub API Call** | ✅ OK | Proper auth headers, correct endpoint | Add error handling |
| **File Decoding** | ✅ OK | Base64 decoding implemented | N/A |

---

## Conclusion

The GitHub agent file retrieval fails due to **compounding issues in authentication verification and MCP server initialization**. The two most critical blockers are:

1. **OAuth doesn't set "connected" flag** → _is_github_connected() always returns False
2. **MCP command path is wrong** → subprocess never starts → tools unavailable

Fixing these two issues will restore basic functionality. Secondary improvements (file path resolution, error handling) will improve UX and performance.
