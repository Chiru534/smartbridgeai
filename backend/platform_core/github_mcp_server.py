from __future__ import annotations

import base64
from typing import Any

import httpx

try:
    from backend.database import SessionLocal
except ImportError:
    from database import SessionLocal
from .connectors import GITHUB_API_URL, require_connector_token

try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover - runtime dependency
    raise RuntimeError("Install the 'mcp' package to run the GitHub MCP server") from exc


mcp = FastMCP("Smartbridge GitHub MCP")


def _get_github_config(connector_username: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return require_connector_token(db, connector_username, "github")
    finally:
        db.close()


def _get_github_token(connector_username: str) -> str:
    config = _get_github_config(connector_username)
    access_token = config.get("access_token")
    if not access_token:
        raise RuntimeError("GitHub access token is missing")
    return access_token


def _decode_github_file_payload(payload: dict[str, Any]) -> dict[str, Any]:
    content = None
    if payload.get("encoding") == "base64" and payload.get("content"):
        content = base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
    return {
        "name": payload.get("name"),
        "path": payload.get("path"),
        "sha": payload.get("sha"),
        "size": payload.get("size"),
        "download_url": payload.get("download_url"),
        "content": content,
    }


def _parse_scope_header(raw_value: str | None) -> list[str]:
    return [scope.strip() for scope in (raw_value or "").split(",") if scope.strip()]


async def _github_request(
    connector_username: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> tuple[Any, httpx.Headers]:
    token = _get_github_token(connector_username)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.request(
            method,
            f"{GITHUB_API_URL}{path}",
            headers=headers,
            params=params,
            json=json_body,
        )
        response.raise_for_status()
        if response.content:
            return response.json(), response.headers
        return {"ok": True, "status_code": response.status_code}, response.headers


async def _get_repository_default_branch(owner: str, repo: str, connector_username: str) -> str:
    payload, _ = await _github_request(connector_username, "GET", f"/repos/{owner}/{repo}")
    branch = payload.get("default_branch")
    if not branch:
        raise RuntimeError("Repository default branch could not be determined")
    return branch


async def _get_branch_sha(owner: str, repo: str, branch: str, connector_username: str) -> str:
    payload, _ = await _github_request(connector_username, "GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
    sha = (((payload or {}).get("object")) or {}).get("sha")
    if not sha:
        raise RuntimeError("Branch SHA could not be resolved")
    return sha


def _summarize_repositories(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for repo in items or []:
        owner = (repo.get("owner") or {}).get("login")
        summaries.append(
            {
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "owner": owner,
                "private": repo.get("private"),
                "default_branch": repo.get("default_branch"),
                "language": repo.get("language"),
                "description": repo.get("description"),
                "html_url": repo.get("html_url"),
                "updated_at": repo.get("updated_at"),
            }
        )
    return summaries


@mcp.tool()
async def get_authenticated_user(connector_username: str) -> dict[str, Any]:
    payload, _ = await _github_request(connector_username, "GET", "/user")
    return {
        "login": payload.get("login"),
        "name": payload.get("name"),
        "email": payload.get("email"),
        "html_url": payload.get("html_url"),
        "public_repos": payload.get("public_repos"),
        "owned_private_repos": ((payload.get("plan") or {}).get("private_repos")),
    }


@mcp.tool()
async def get_token_info(connector_username: str) -> dict[str, Any]:
    payload, headers = await _github_request(connector_username, "GET", "/user")
    config = _get_github_config(connector_username)
    return {
        "login": payload.get("login"),
        "name": payload.get("name"),
        "email": payload.get("email"),
        "html_url": payload.get("html_url"),
        "scopes": _parse_scope_header(headers.get("X-OAuth-Scopes")),
        "accepted_scopes": _parse_scope_header(headers.get("X-Accepted-OAuth-Scopes")),
        "token_source": config.get("auth_method") or "oauth",
    }


@mcp.tool()
async def list_organizations(connector_username: str, per_page: int = 100, page: int = 1) -> dict[str, Any]:
    payload, _ = await _github_request(
        connector_username,
        "GET",
        "/user/orgs",
        params={"per_page": per_page, "page": page},
    )
    items = []
    for org in payload if isinstance(payload, list) else []:
        items.append(
            {
                "login": org.get("login"),
                "id": org.get("id"),
                "description": org.get("description"),
                "url": org.get("url"),
                "avatar_url": org.get("avatar_url"),
            }
        )
    return {"items": items}


@mcp.tool()
async def list_my_repositories(
    connector_username: str,
    visibility: str = "all",
    affiliation: str = "owner,collaborator,organization_member",
    sort: str = "updated",
    per_page: int = 100,
    page: int = 1,
) -> dict[str, Any]:
    payload, _ = await _github_request(
        connector_username,
        "GET",
        "/user/repos",
        params={
            "visibility": visibility,
            "affiliation": affiliation,
            "sort": sort,
            "per_page": per_page,
            "page": page,
        },
    )
    return {"items": _summarize_repositories(payload if isinstance(payload, list) else [])}


@mcp.tool()
async def list_user_repositories(
    connector_username: str,
    owner: str,
    sort: str = "updated",
    per_page: int = 100,
    page: int = 1,
) -> dict[str, Any]:
    payload, _ = await _github_request(
        connector_username,
        "GET",
        f"/users/{owner}/repos",
        params={"sort": sort, "per_page": per_page, "page": page},
    )
    return {"items": _summarize_repositories(payload if isinstance(payload, list) else [])}


@mcp.tool()
async def search_repositories(connector_username: str, query: str, per_page: int = 10) -> dict[str, Any]:
    payload, _ = await _github_request(
        connector_username,
        "GET",
        "/search/repositories",
        params={"q": query, "per_page": per_page},
    )
    return {"total_count": payload.get("total_count", 0), "items": _summarize_repositories(payload.get("items", []))}


@mcp.tool()
async def get_repository(connector_username: str, owner: str, repo: str) -> dict[str, Any]:
    payload, _ = await _github_request(connector_username, "GET", f"/repos/{owner}/{repo}")
    return payload


@mcp.tool()
async def list_directory(connector_username: str, owner: str, repo: str, path: str = "", ref: str | None = None) -> dict[str, Any]:
    """
    List files, files inside folders, and contents inside a continuous tree path layout of a GitHub repository.
    Use this tool whenever you need to fetch, view, or read files directly inside a specific folder relative to the root.
    
    :param connector_username: The connector context string setup on setup triggers.
    :param owner: The repository owner (e.g., 'Chiru534').
    :param repo: The repository name (e.g., 'project_agent').
    :param path: The path inside the repository to list (e.g., 'backend' or 'frontend'). Leave empty for absolute root.
    :param ref: Optional branch or tag reference node.
    """
    params = {"ref": ref} if ref else None
    payload, _ = await _github_request(
        connector_username,
        "GET",
        f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}" if path else f"/repos/{owner}/{repo}/contents",
        params=params,
    )
    
    # Prune JSON bloat to prevent standard IO pipe buffering jams on Windows
    items = []
    for item in (payload if isinstance(payload, list) else [payload]):
        items.append({
            "name": item.get("name"),
            "path": item.get("path"),
            "type": item.get("type"),
            "size": item.get("size")
        })
    return {"items": items}


@mcp.tool()
async def get_file(connector_username: str, owner: str, repo: str, path: str, ref: str | None = None) -> dict[str, Any]:
    """
    Get the string content, code, or payload of a file from a GitHub repository.
    Use this tool whenever you are asked to read, view, or output the code/text inside a file.
    
    :param connector_username: The connector context string setup on tools.
    :param owner: The GitHub repository owner (e.g., 'Chiru534').
    :param repo: The repository name (e.g., 'project_agent').
    :param path: The complete relative file path (e.g., 'backend/main.py').
    :param ref: Optional branch or SHA reference name.
    """
    params = {"ref": ref} if ref else None
    payload, _ = await _github_request(
        connector_username,
        "GET",
        f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}",
        params=params,
    )
    return _decode_github_file_payload(payload)


@mcp.tool()
async def get_readme(connector_username: str, owner: str, repo: str, ref: str | None = None) -> dict[str, Any]:
    params = {"ref": ref} if ref else None
    payload, _ = await _github_request(
        connector_username,
        "GET",
        f"/repos/{owner}/{repo}/readme",
        params=params,
    )
    return _decode_github_file_payload(payload)


@mcp.tool()
async def search_code(connector_username: str, query: str, per_page: int = 10) -> dict[str, Any]:
    payload, _ = await _github_request(
        connector_username,
        "GET",
        "/search/code",
        params={"q": query, "per_page": per_page},
    )
    return {"total_count": payload.get("total_count", 0), "items": payload.get("items", [])}


@mcp.tool()
async def list_issues(
    connector_username: str,
    owner: str,
    repo: str,
    state: str = "open",
    per_page: int = 20,
    page: int = 1,
) -> dict[str, Any]:
    payload, _ = await _github_request(
        connector_username,
        "GET",
        f"/repos/{owner}/{repo}/issues",
        params={"state": state, "per_page": per_page, "page": page},
    )
    return {"items": payload}


@mcp.tool()
async def get_issue(connector_username: str, owner: str, repo: str, issue_number: int) -> dict[str, Any]:
    payload, _ = await _github_request(connector_username, "GET", f"/repos/{owner}/{repo}/issues/{issue_number}")
    return payload


@mcp.tool()
async def create_issue(
    connector_username: str,
    owner: str,
    repo: str,
    title: str,
    body: str = "",
    assignees: list[str] | None = None,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    payload, _ = await _github_request(
        connector_username,
        "POST",
        f"/repos/{owner}/{repo}/issues",
        json_body={
            "title": title,
            "body": body,
            "assignees": assignees or [],
            "labels": labels or [],
        },
    )
    return payload


@mcp.tool()
async def list_issue_comments(
    connector_username: str,
    owner: str,
    repo: str,
    issue_number: int,
    per_page: int = 20,
    page: int = 1,
) -> dict[str, Any]:
    payload, _ = await _github_request(
        connector_username,
        "GET",
        f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
        params={"per_page": per_page, "page": page},
    )
    return {"items": payload}


@mcp.tool()
async def list_pull_requests(
    connector_username: str,
    owner: str,
    repo: str,
    state: str = "open",
    per_page: int = 20,
    page: int = 1,
) -> dict[str, Any]:
    payload, _ = await _github_request(
        connector_username,
        "GET",
        f"/repos/{owner}/{repo}/pulls",
        params={"state": state, "per_page": per_page, "page": page},
    )
    return {"items": payload}


@mcp.tool()
async def get_pull_request(connector_username: str, owner: str, repo: str, pull_number: int) -> dict[str, Any]:
    payload, _ = await _github_request(connector_username, "GET", f"/repos/{owner}/{repo}/pulls/{pull_number}")
    return payload


@mcp.tool()
async def create_pull_request(
    connector_username: str,
    owner: str,
    repo: str,
    title: str,
    head: str,
    base: str,
    body: str = "",
) -> dict[str, Any]:
    payload, _ = await _github_request(
        connector_username,
        "POST",
        f"/repos/{owner}/{repo}/pulls",
        json_body={"title": title, "head": head, "base": base, "body": body},
    )
    return payload


@mcp.tool()
async def list_branches(connector_username: str, owner: str, repo: str, per_page: int = 50) -> dict[str, Any]:
    payload, _ = await _github_request(
        connector_username,
        "GET",
        f"/repos/{owner}/{repo}/branches",
        params={"per_page": per_page},
    )
    return {"items": payload}


@mcp.tool()
async def list_commits(connector_username: str, owner: str, repo: str, sha: str | None = None, per_page: int = 20) -> dict[str, Any]:
    params = {"per_page": per_page}
    if sha:
        params["sha"] = sha
    payload, _ = await _github_request(
        connector_username,
        "GET",
        f"/repos/{owner}/{repo}/commits",
        params=params,
    )
    return {"items": payload}


@mcp.tool()
async def get_commit(connector_username: str, owner: str, repo: str, ref: str) -> dict[str, Any]:
    payload, _ = await _github_request(connector_username, "GET", f"/repos/{owner}/{repo}/commits/{ref}")
    return payload


@mcp.tool()
async def create_branch(
    connector_username: str,
    owner: str,
    repo: str,
    new_branch: str,
    from_branch: str | None = None,
    from_sha: str | None = None,
) -> dict[str, Any]:
    source_branch = from_branch or await _get_repository_default_branch(owner, repo, connector_username)
    source_sha = from_sha or await _get_branch_sha(owner, repo, source_branch, connector_username)
    payload, _ = await _github_request(
        connector_username,
        "POST",
        f"/repos/{owner}/{repo}/git/refs",
        json_body={"ref": f"refs/heads/{new_branch}", "sha": source_sha},
    )
    return payload


@mcp.tool()
async def create_or_update_file(
    connector_username: str,
    owner: str,
    repo: str,
    path: str,
    message: str,
    content: str,
    sha: str | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    request_body: dict[str, Any] = {"message": message, "content": encoded_content}
    if sha:
        request_body["sha"] = sha
    if branch:
        request_body["branch"] = branch
    payload, _ = await _github_request(
        connector_username,
        "PUT",
        f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}",
        json_body=request_body,
    )
    return payload


@mcp.tool()
async def delete_file(
    connector_username: str,
    owner: str,
    repo: str,
    path: str,
    message: str,
    sha: str,
    branch: str | None = None,
) -> dict[str, Any]:
    request_body: dict[str, Any] = {"message": message, "sha": sha}
    if branch:
        request_body["branch"] = branch
    payload, _ = await _github_request(
        connector_username,
        "DELETE",
        f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}",
        json_body=request_body,
    )
    return payload


@mcp.tool()
async def list_languages(connector_username: str, owner: str, repo: str) -> dict[str, Any]:
    payload, _ = await _github_request(connector_username, "GET", f"/repos/{owner}/{repo}/languages")
    languages = payload if isinstance(payload, dict) else {}
    total_bytes = sum(value for value in languages.values() if isinstance(value, int))
    return {"languages": languages, "total_bytes": total_bytes}


@mcp.tool()
async def list_workflows(connector_username: str, owner: str, repo: str) -> dict[str, Any]:
    payload, _ = await _github_request(connector_username, "GET", f"/repos/{owner}/{repo}/actions/workflows")
    return payload


@mcp.tool()
async def trigger_workflow(
    connector_username: str,
    owner: str,
    repo: str,
    workflow_id: str,
    ref: str,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload, _ = await _github_request(
        connector_username,
        "POST",
        f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
        json_body={"ref": ref, "inputs": inputs or {}},
    )
    return payload


@mcp.tool()
async def get_workflow_run(connector_username: str, owner: str, repo: str, run_id: int) -> dict[str, Any]:
    payload, _ = await _github_request(connector_username, "GET", f"/repos/{owner}/{repo}/actions/runs/{run_id}")
    return payload


if __name__ == "__main__":
    mcp.run(transport="stdio")
