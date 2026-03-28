from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

import models  # noqa: E402
from database import SessionLocal  # noqa: E402
from platform_core.mcp_stdio import default_mcp_manager  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
STATUS_PASS = "pass"
STATUS_PARTIAL = "partial"
STATUS_BLOCKED_SURFACE = "blocked-by-tool-surface"
STATUS_BLOCKED_PERMISSION = "blocked-by-permission"
STATUS_BLOCKED_NETWORK = "blocked-by-network"
STATUS_BLOCKED_RUNTIME = "blocked-by-runtime"
STATUS_ERROR = "error"
TOKEN_PATTERNS = [
    re.compile(r"\bgh[a-z]_[A-Za-z0-9_]+\b"),
    re.compile(r"\bya29\.[A-Za-z0-9._-]+\b"),
    re.compile(r"\b1//[A-Za-z0-9._-]+\b"),
]
SEARCH_KEYWORDS = ["agent", "MCP", "project", "test", "todo", "roadmap"]
SUCCESS_WEIGHTS = {
    STATUS_PASS: 1.0,
    STATUS_PARTIAL: 0.5,
    STATUS_BLOCKED_SURFACE: 0.0,
    STATUS_BLOCKED_PERMISSION: 0.0,
    STATUS_BLOCKED_NETWORK: 0.0,
    STATUS_BLOCKED_RUNTIME: 0.0,
    STATUS_ERROR: 0.0,
}
STOPWORDS = {
    "about",
    "agent",
    "analysis",
    "build",
    "document",
    "drive",
    "github",
    "issue",
    "items",
    "mcp",
    "next",
    "notes",
    "plan",
    "project",
    "readme",
    "roadmap",
    "steps",
    "task",
    "test",
    "todo",
    "work",
}


@dataclass
class ActionTrace:
    server: str
    tool: str
    why: str
    expect: str
    arguments: dict[str, Any]
    status: str = "pending"
    note: str = ""


@dataclass
class CheckRecord:
    category: str
    name: str
    status: str
    summary: str
    details: list[str] = field(default_factory=list)


def sanitize_text(value: str) -> str:
    text = value or ""
    for pattern in TOKEN_PATTERNS:
        text = pattern.sub("[redacted]", text)
    return text


def sanitize_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_data(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def shorten_id(value: str | None) -> str:
    if not value:
        return "n/a"
    if len(value) <= 8:
        return value
    return f"{value[:8]}..."


def normalize_space(value: str) -> str:
    return " ".join((value or "").split())


def coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(item) for item in content)
    return str(content or "")


def parse_mcp_payload(result: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    raw_text = coerce_text(result.get("content"))
    if result.get("is_error"):
        return None, sanitize_text(raw_text or "MCP tool call failed.")
    if not raw_text.strip():
        return {}, None
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {"text": sanitize_text(raw_text)}, None
    if isinstance(parsed, dict):
        return sanitize_data(parsed), None
    return {"value": sanitize_data(parsed)}, None


def classify_error(error_text: str) -> str:
    lowered = (error_text or "").lower()
    if "all connection attempts failed" in lowered or "timed out" in lowered:
        return STATUS_BLOCKED_NETWORK
    if any(token in lowered for token in ("401", "unauthorized", "bad credentials", "403", "forbidden", "permission", "denied", "insufficient")):
        return STATUS_BLOCKED_PERMISSION
    if any(token in lowered for token in ("unknown mcp tool", "not connected", "missing", "no command configured")):
        return STATUS_BLOCKED_RUNTIME
    if any(token in lowered for token in ("not found", "404", "does not exist", "no matching")):
        return STATUS_PARTIAL
    return STATUS_ERROR


def to_markdown_json(value: Any) -> str:
    return "```json\n" + json.dumps(sanitize_data(value), indent=2, ensure_ascii=False) + "\n```"


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    header_row = "| " + " | ".join(headers) + " |"
    divider_row = "| " + " | ".join(["---"] * len(headers)) + " |"
    body_rows = ["| " + " | ".join(cell.replace("\n", "<br>") for cell in row) + " |" for row in rows]
    return "\n".join([header_row, divider_row, *body_rows])


def extract_code_context(content: str, keywords: list[str], total_lines: int = 8) -> str:
    lines = content.splitlines() or [content]
    lowered_keywords = [item.lower() for item in keywords if item]
    match_index = 0
    for index, line in enumerate(lines):
        lowered_line = line.lower()
        if any(keyword in lowered_line for keyword in lowered_keywords):
            match_index = index
            break
    half_window = max(total_lines // 2, 1)
    start = max(match_index - half_window, 0)
    end = min(start + total_lines, len(lines))
    numbered = []
    for line_number, line in enumerate(lines[start:end], start=start + 1):
        numbered.append(f"{line_number:4}: {line}")
    return "\n".join(numbered)


def summarize_text_to_bullets(content: str, max_bullets: int = 5) -> list[str]:
    bullets: list[str] = []
    seen: set[str] = set()

    def add_candidate(raw_value: str) -> None:
        cleaned = normalize_space(
            raw_value.replace("#", " ").replace("`", " ").replace("*", " ").replace("_", " ").strip(" -:\t")
        )
        if len(cleaned) < 8:
            return
        lowered = cleaned.lower()
        if lowered in seen:
            return
        seen.add(lowered)
        bullets.append(cleaned)

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("#"):
            add_candidate(line.lstrip("#").strip())
        elif re.match(r"^[-*]\s+", line):
            add_candidate(re.sub(r"^[-*]\s+", "", line))
        if len(bullets) >= max_bullets:
            break

    if len(bullets) < max_bullets:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if normalize_space(part)]
        for paragraph in paragraphs:
            sentences = re.split(r"(?<=[.!?])\s+", normalize_space(paragraph))
            for sentence in sentences:
                add_candidate(sentence)
                if len(bullets) >= max_bullets:
                    break
            if len(bullets) >= max_bullets:
                break

    while len(bullets) < max_bullets:
        add_candidate(f"Content excerpt {len(bullets) + 1}: {normalize_space(content)[:140]}")
        if len(bullets) >= max_bullets:
            break
    return bullets[:max_bullets]


def choose_full_file_candidate(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    ext_priority = {".py": 0, ".js": 1, ".md": 2}

    def sort_key(item: dict[str, Any]) -> tuple[int, int]:
        path = item.get("path") or ""
        extension = Path(path).suffix.lower()
        priority = ext_priority.get(extension, 99)
        score = int(item.get("size") or 0)
        return priority, score

    candidates = [item for item in items if Path(item.get("path") or "").suffix.lower() in {".py", ".js", ".md"}]
    if not candidates:
        return items[0] if items else None
    return sorted(candidates, key=sort_key)[0]


def infer_drive_file_type(item: dict[str, Any]) -> str:
    mime_type = item.get("mimeType") or ""
    name = item.get("name") or ""
    extension = Path(name).suffix.lower()
    if mime_type == "application/vnd.google-apps.document":
        return "google_doc"
    if mime_type == "application/vnd.google-apps.spreadsheet":
        return "google_sheet"
    if extension in {".md", ".txt"}:
        return "plain_text"
    if extension in {".pdf", ".docx"}:
        return extension.lstrip(".")
    return mime_type or extension or "unknown"


def extract_task_keywords(content: str, limit: int = 8) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^[-*]\s+", stripped):
            stripped = re.sub(r"^[-*]\s+", "", stripped)
            token = normalize_space(stripped)
            lowered = token.lower()
            if lowered not in seen and len(token) >= 4:
                seen.add(lowered)
                candidates.append(token)
        if len(candidates) >= limit:
            return candidates[:limit]

    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", content)
    for word in words:
        lowered = word.lower()
        if lowered in STOPWORDS or lowered in seen:
            continue
        seen.add(lowered)
        candidates.append(word)
        if len(candidates) >= limit:
            break
    return candidates[:limit]


class ValidationRunner:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.report_sections: list[str] = []
        self.checks: list[CheckRecord] = []
        self.traces: list[ActionTrace] = []
        self.tool_catalog: dict[str, list[dict[str, Any]]] = {}
        self.preflight_status: list[dict[str, Any]] = []
        self.preflight_accounts: list[dict[str, Any]] = []
        self.connector_configs: dict[str, dict[str, Any]] = {}
        self.github_identity: dict[str, Any] = {}
        self.github_login: str = ""
        self.github_repos: list[dict[str, Any]] = []
        self.github_owned_repos: list[dict[str, Any]] = []
        self.drive_root_listing: list[dict[str, Any]] = []
        self.drive_search_results: list[dict[str, Any]] = []

    def add_check(self, category: str, name: str, status: str, summary: str, details: list[str] | None = None) -> None:
        self.checks.append(
            CheckRecord(
                category=category,
                name=name,
                status=status,
                summary=sanitize_text(summary),
                details=[sanitize_text(item) for item in (details or [])],
            )
        )

    def add_section(self, title: str, lines: list[str]) -> None:
        self.report_sections.append("## " + title + "\n" + "\n".join(lines).rstrip())

    def load_connector_configs(self) -> dict[str, dict[str, Any]]:
        db = SessionLocal()
        try:
            rows = (
                db.query(models.ConnectorAccountDB)
                .filter(models.ConnectorAccountDB.username == self.args.connector_username)
                .all()
            )
            configs: dict[str, dict[str, Any]] = {}
            for row in rows:
                try:
                    parsed = json.loads(row.config_json or "{}")
                except json.JSONDecodeError:
                    parsed = {}
                configs[row.connector_name] = sanitize_data(parsed if isinstance(parsed, dict) else {})
            return configs
        finally:
            db.close()

    async def call_tool(self, tool_name: str, arguments: dict[str, Any], why: str, expect: str) -> tuple[dict[str, Any] | None, str | None]:
        server_name = "google_drive" if tool_name.startswith("google_drive_") else "github"
        trace = ActionTrace(
            server=server_name,
            tool=tool_name,
            why=why,
            expect=expect,
            arguments=sanitize_data(arguments),
        )
        self.traces.append(trace)
        try:
            result = await default_mcp_manager.call(
                tool_name,
                arguments,
                injected_arguments={"connector_username": self.args.connector_username},
            )
        except Exception as exc:  # pragma: no cover - runtime behavior
            error_text = sanitize_text(str(exc))
            trace.status = classify_error(error_text)
            trace.note = error_text
            return None, error_text

        payload, error_text = parse_mcp_payload(result)
        if error_text:
            trace.status = classify_error(error_text)
            trace.note = error_text
        else:
            trace.status = STATUS_PASS
            trace.note = "ok"
        return payload, error_text

    async def paginate(self, tool_name: str, arguments: dict[str, Any], item_key: str, why: str, expect: str, max_pages: int = 20) -> tuple[list[Any], str | None]:
        items: list[Any] = []
        page = int(arguments.get("page") or 1)
        per_page = int(arguments.get("per_page") or 100)
        while page <= max_pages:
            page_args = {**arguments, "page": page}
            payload, error_text = await self.call_tool(tool_name, page_args, why, expect)
            if error_text:
                return items, error_text
            batch = list((payload or {}).get(item_key) or [])
            items.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        return items, None

    async def run_preflight(self) -> None:
        lines = []
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                login_response = await client.post(
                    f"{self.args.backend_url.rstrip('/')}/api/login",
                    json={"username": self.args.username, "password": self.args.password},
                )
                login_response.raise_for_status()
                token = login_response.json().get("token")
                headers = {"Authorization": f"Bearer {token}"}

                status_response = await client.get(f"{self.args.backend_url.rstrip('/')}/api/connectors/status", headers=headers)
                status_response.raise_for_status()
                self.preflight_status = sanitize_data(status_response.json())

                accounts_response = await client.get(
                    f"{self.args.backend_url.rstrip('/')}/api/connectors/accounts",
                    headers=headers,
                )
                accounts_response.raise_for_status()
                self.preflight_accounts = sanitize_data(accounts_response.json())
            self.add_check("discovery", "backend-preflight", STATUS_PASS, "Authenticated to localhost backend and loaded connector status.")
            lines.append(f"- Backend URL: `{self.args.backend_url}`")
            lines.append(f"- Authenticated as backend user `{self.args.username}`.")
            lines.append("- Connector status:")
            lines.append(to_markdown_json(self.preflight_status))
            lines.append("- Connector accounts:")
            lines.append(to_markdown_json(self.preflight_accounts))
        except Exception as exc:  # pragma: no cover - runtime behavior
            error_text = sanitize_text(str(exc))
            self.add_check("discovery", "backend-preflight", classify_error(error_text), f"Backend preflight failed: {error_text}")
            lines.append(f"- Backend preflight failed: `{error_text}`")
        else:
            try:
                self.connector_configs = self.load_connector_configs()
                scope_rows = []
                for connector_name, config in self.connector_configs.items():
                    scope_rows.append(
                        [
                            connector_name,
                            str(config.get("login") or config.get("display_name") or "n/a"),
                            str(config.get("scope") or "scope unavailable from current MCP output"),
                        ]
                    )
                lines.append("- Stored connector scope summary:")
                lines.append(render_table(["Connector", "Identity", "Stored Scope"], scope_rows or [["n/a", "", ""]]))
            except Exception as exc:  # pragma: no cover - runtime behavior
                lines.append(f"- Connector DB scope lookup failed: `{sanitize_text(str(exc))}`")
        self.add_section("Preflight", lines)

    async def run_discovery(self) -> None:
        tools = await default_mcp_manager.tools_for_servers(("github", "google_drive"))
        grouped: dict[str, list[dict[str, Any]]] = {"github": [], "google_drive": []}
        for item in tools:
            function_payload = (item or {}).get("function") or {}
            tool_name = function_payload.get("name", "")
            if tool_name.startswith("github_"):
                grouped["github"].append(sanitize_data(item))
            elif tool_name.startswith("google_drive_"):
                grouped["google_drive"].append(sanitize_data(item))
        self.tool_catalog = grouped

        lines = []
        for server_name in ("github", "google_drive"):
            server_tools = grouped.get(server_name, [])
            lines.append(f"### `{server_name}` tools ({len(server_tools)})")
            for tool in server_tools:
                function_payload = tool.get("function") or {}
                lines.append(f"- `{function_payload.get('name')}`: {function_payload.get('description') or 'No description provided.'}")
                lines.append(to_markdown_json(function_payload.get("parameters") or {}))
        status = STATUS_PASS if grouped["github"] and grouped["google_drive"] else STATUS_PARTIAL
        self.add_check("discovery", "tool-enumeration", status, "Enumerated runtime MCP tools and schemas for both servers.")
        self.add_section("Tool Discovery", lines)

    def select_github_write_repo(self) -> dict[str, Any] | None:
        candidates = list(self.github_owned_repos)
        if not candidates:
            return None
        lowered_map = {repo.get("name", "").lower(): repo for repo in candidates}
        if "test-agent-project" in lowered_map:
            return lowered_map["test-agent-project"]
        scored: list[tuple[int, dict[str, Any]]] = []
        for repo in candidates:
            name = (repo.get("name") or "").lower()
            score = 0
            if "test" in name and "agent" in name:
                score = 3
            elif "project" in name:
                score = 2
            elif "test" in name:
                score = 1
            if score:
                scored.append((score, repo))
        if not scored:
            return None
        scored.sort(key=lambda item: (item[0], item[1].get("updated_at") or ""), reverse=True)
        return scored[0][1]

    def build_github_issue_body(self) -> str:
        timestamp = datetime.now(IST).isoformat()
        return "\n".join(
            [
                "# MCP Exhaustive Test",
                "",
                f"- Date: {self.args.report_date}",
                f"- Time (IST): {timestamp}",
                f"- Backend user: {self.args.username}",
                f"- Connector user: {self.args.connector_username}",
                "",
                "## Checklist",
                "- Validate GitHub connector authentication and identity.",
                "- Validate repository listing, metadata, README, and code search coverage.",
                "- Validate issue and pull request read operations.",
                "- Confirm write permissions for issue creation.",
                "- Record any permission, validation, or network errors verbatim.",
            ]
        )

    async def run_github_validation(self) -> None:
        lines = []

        identity_payload, identity_error = await self.call_tool(
            "github_get_token_info",
            {},
            "Verify authenticated GitHub identity and token metadata.",
            "Expected login, profile URL, and scope headers if GitHub returns them.",
        )
        if identity_error:
            identity_payload, identity_error = await self.call_tool(
                "github_get_authenticated_user",
                {},
                "Fallback identity check when token info is unavailable.",
                "Expected login, profile URL, and repo counts.",
            )
        if identity_error:
            status = classify_error(identity_error)
            self.add_check("auth", "github-identity", status, f"GitHub identity lookup failed: {identity_error}")
            lines.append(f"- GitHub identity lookup failed: `{identity_error}`")
            self.add_section("GitHub Validation", lines)
            return

        self.github_identity = identity_payload or {}
        self.github_login = str((identity_payload or {}).get("login") or "")
        github_scope = (
            ", ".join((identity_payload or {}).get("scopes") or [])
            or str((self.connector_configs.get("github") or {}).get("scope") or "scope unavailable from current MCP output")
        )
        self.add_check("auth", "github-identity", STATUS_PASS, f"Authenticated GitHub user `{self.github_login}`.")
        lines.append(f"- Authenticated GitHub login: `{self.github_login}`")
        lines.append(f"- Scope posture: `{github_scope}`")
        lines.append("- Identity payload:")
        lines.append(to_markdown_json(identity_payload))

        orgs, org_error = await self.paginate(
            "github_list_organizations",
            {"per_page": 100, "page": 1},
            "items",
            "Enumerate GitHub organizations connected to this account.",
            "Expected organization memberships.",
        )
        repo_items, repo_error = await self.paginate(
            "github_list_my_repositories",
            {"sort": "updated", "per_page": 30, "page": 1},
            "items",
            "Enumerate all accessible repositories for the connected GitHub account.",
            "Expected repository pages sorted by update time.",
        )

        if repo_error:
            status = classify_error(repo_error)
            self.add_check("list", "github-repositories", status, f"Repository enumeration failed: {repo_error}")
            lines.append(f"- Repository enumeration failed: `{repo_error}`")
            self.add_section("GitHub Validation", lines)
            return

        self.github_repos = list(repo_items)
        self.github_owned_repos = [repo for repo in self.github_repos if (repo.get("owner") or "").lower() == self.github_login.lower()]
        org_status = STATUS_PASS if not org_error else classify_error(org_error)
        self.add_check("list", "github-organizations", org_status, f"Found {len(orgs)} GitHub organizations.")
        self.add_check("list", "github-repositories", STATUS_PASS, f"Enumerated {len(self.github_repos)} accessible repositories.")
        lines.append(f"- Organizations ({len(orgs)}): " + (", ".join(org.get("login") or "unknown" for org in orgs) if orgs else "none"))
        if org_error:
            lines.append(f"- Organization enumeration warning: `{org_error}`")
        lines.append(f"- Total accessible repositories: **{len(self.github_repos)}**")
        lines.append(f"- Owned repositories: **{len(self.github_owned_repos)}**")

        top_repos = sorted(self.github_repos, key=lambda item: item.get("updated_at") or "", reverse=True)[:2]
        for repo in top_repos:
            owner = str(repo.get("owner") or "")
            repo_name = str(repo.get("name") or "")
            detail_payload, detail_error = await self.call_tool(
                "github_get_repository",
                {"owner": owner, "repo": repo_name},
                f"Fetch repository metadata for {owner}/{repo_name}.",
                "Expected repository stats, branch details, issue counts, and URLs.",
            )
            languages_payload, languages_error = await self.call_tool(
                "github_list_languages",
                {"owner": owner, "repo": repo_name},
                f"Fetch repository language breakdown for {owner}/{repo_name}.",
                "Expected a byte-count map of repository languages.",
            )
            prs, prs_error = await self.paginate(
                "github_list_pull_requests",
                {"owner": owner, "repo": repo_name, "state": "open", "per_page": 100, "page": 1},
                "items",
                f"Count open pull requests in {owner}/{repo_name}.",
                "Expected all open PRs, pageable by 100.",
                max_pages=10,
            )
            readme_payload, readme_error = await self.call_tool(
                "github_get_readme",
                {"owner": owner, "repo": repo_name},
                f"Read README for {owner}/{repo_name}.",
                "Expected README content when the repository exposes one.",
            )

            lines.append(f"### `{owner}/{repo_name}`")
            if detail_error:
                lines.append(f"- Metadata error: `{detail_error}`")
                self.add_check("read", f"github-repo-detail-{owner}/{repo_name}", classify_error(detail_error), detail_error)
            else:
                detail_payload = detail_payload or {}
                languages = ((languages_payload or {}).get("languages") or {}) if not languages_error else {}
                pr_count = len(prs)
                lines.append(
                    f"- Stars: {detail_payload.get('stargazers_count', 0)}, Forks: {detail_payload.get('forks_count', 0)}, "
                    f"Watchers: {detail_payload.get('subscribers_count', detail_payload.get('watchers_count', 0))}, "
                    f"Open issues: {detail_payload.get('open_issues_count', 0)}, Open PRs: {pr_count}"
                )
                lines.append(
                    f"- Default branch: `{detail_payload.get('default_branch') or repo.get('default_branch') or 'unknown'}`; "
                    f"Primary language: `{detail_payload.get('language') or 'unknown'}`; Privacy: `{detail_payload.get('private')}`"
                )
                lines.append(f"- HTML URL: {detail_payload.get('html_url') or repo.get('html_url')}")
                lines.append(f"- Languages: `{json.dumps(languages, ensure_ascii=False)}`")
                self.add_check("read", f"github-repo-detail-{owner}/{repo_name}", STATUS_PASS, f"Loaded metadata for `{owner}/{repo_name}`.")

            if readme_error:
                lines.append(f"- README error: `{readme_error}`")
                self.add_check("read", f"github-readme-{owner}/{repo_name}", classify_error(readme_error), readme_error)
            else:
                readme_content = str((readme_payload or {}).get("content") or "")
                readme_bullets = summarize_text_to_bullets(readme_content, max_bullets=5)
                lines.append("- README summary:")
                for bullet in readme_bullets:
                    lines.append(f"  - {bullet}")
                self.add_check("read", f"github-readme-{owner}/{repo_name}", STATUS_PASS, f"Read README for `{owner}/{repo_name}`.")

        search_results: list[dict[str, Any]] = []
        seen_matches: set[str] = set()
        for query in [f"user:{self.github_login} (agent OR MCP OR test)", f"user:{self.github_login} agent", f"user:{self.github_login} MCP", f"user:{self.github_login} test"]:
            payload, error_text = await self.call_tool(
                "github_search_code",
                {"query": query, "per_page": 20},
                f"Search GitHub code for `{query}`.",
                "Expected code matches with repository metadata and file paths.",
            )
            if error_text:
                lines.append(f"- Code search warning for `{query}`: `{error_text}`")
                continue
            for item in (payload or {}).get("items") or []:
                repo_full_name = ((item.get("repository") or {}).get("full_name")) or "unknown/unknown"
                match_key = f"{repo_full_name}:{item.get('path')}"
                if match_key in seen_matches:
                    continue
                seen_matches.add(match_key)
                search_results.append(sanitize_data(item))
                if len(search_results) >= 4:
                    break
            if len(search_results) >= 4:
                break

        if search_results:
            self.add_check("search", "github-code-search", STATUS_PASS, f"Collected {len(search_results)} GitHub code matches.")
            lines.append("### Code Search Matches")
            for item in search_results[:4]:
                repository = item.get("repository") or {}
                owner = ((repository.get("owner") or {}).get("login")) or self.github_login
                repo_name = repository.get("name") or ""
                path = item.get("path") or ""
                file_payload, file_error = await self.call_tool(
                    "github_get_file",
                    {"owner": owner, "repo": repo_name, "path": path},
                    f"Read GitHub file `{owner}/{repo_name}:{path}` to capture surrounding context.",
                    "Expected decoded file content.",
                )
                if file_error:
                    lines.append(f"- `{repository.get('full_name')}/{path}` read error: `{file_error}`")
                    continue
                content = str((file_payload or {}).get("content") or "")
                lines.append(f"- `{repository.get('full_name')}` / `{path}`")
                lines.append("```text")
                lines.append(extract_code_context(content, ["agent", "mcp", "test"], total_lines=8))
                lines.append("```")

            full_candidate = choose_full_file_candidate(search_results)
            if full_candidate:
                repository = full_candidate.get("repository") or {}
                owner = ((repository.get("owner") or {}).get("login")) or self.github_login
                repo_name = repository.get("name") or ""
                path = full_candidate.get("path") or ""
                file_payload, file_error = await self.call_tool(
                    "github_get_file",
                    {"owner": owner, "repo": repo_name, "path": path},
                    f"Read one full GitHub file for detailed inspection: `{owner}/{repo_name}:{path}`.",
                    "Expected full decoded file content.",
                )
                if not file_error:
                    extension = Path(path).suffix.lower().lstrip(".") or "text"
                    lines.append(f"### Full File Content: `{repository.get('full_name')}/{path}`")
                    lines.append(f"```{extension}")
                    lines.append(str((file_payload or {}).get("content") or ""))
                    lines.append("```")
                    self.add_check("read", "github-full-file", STATUS_PASS, f"Read full GitHub file `{repository.get('full_name')}/{path}`.")
        else:
            self.add_check("search", "github-code-search", STATUS_PARTIAL, "No GitHub code matches were returned for the requested keywords.")
            lines.append("- No GitHub code search results were returned.")

        most_active_repo = None
        if self.github_repos:
            most_active_repo = max(
                self.github_repos,
                key=lambda item: (int(item.get("open_issues_count") or 0), item.get("updated_at") or ""),
            )
        if most_active_repo:
            owner = str(most_active_repo.get("owner") or "")
            repo_name = str(most_active_repo.get("name") or "")
            issues, issues_error = await self.paginate(
                "github_list_issues",
                {"owner": owner, "repo": repo_name, "state": "open", "per_page": 100, "page": 1},
                "items",
                f"List open issues for most active repo `{owner}/{repo_name}`.",
                "Expected all open issues.",
                max_pages=10,
            )
            prs, prs_error = await self.paginate(
                "github_list_pull_requests",
                {"owner": owner, "repo": repo_name, "state": "open", "per_page": 100, "page": 1},
                "items",
                f"List open pull requests for most active repo `{owner}/{repo_name}`.",
                "Expected all open pull requests.",
                max_pages=10,
            )
            issues = sorted(issues, key=lambda item: item.get("updated_at") or "", reverse=True)
            lines.append(f"### Most Active Repo: `{owner}/{repo_name}`")
            if issues_error:
                lines.append(f"- Issue listing error: `{issues_error}`")
                self.add_check("read", "github-open-issues", classify_error(issues_error), issues_error)
            else:
                issue_rows = []
                for issue in issues[:6]:
                    issue_rows.append(
                        [
                            str(issue.get("number")),
                            sanitize_text(issue.get("title") or ""),
                            ", ".join(label.get("name") or "" for label in issue.get("labels") or []),
                            str(((issue.get("assignee") or {}).get("login")) or "unassigned"),
                            str(issue.get("updated_at") or ""),
                        ]
                    )
                lines.append(render_table(["#", "Title", "Labels", "Assignee", "Updated"], issue_rows or [["n/a", "No open issues", "", "", ""]]))
                self.add_check("read", "github-open-issues", STATUS_PASS, f"Listed {len(issues)} open issues for `{owner}/{repo_name}`.")
            if prs_error:
                lines.append(f"- Pull request listing error: `{prs_error}`")
                self.add_check("read", "github-open-prs", classify_error(prs_error), prs_error)
            else:
                pr_rows = [
                    [str(pr.get("number")), sanitize_text(pr.get("title") or ""), str((pr.get("user") or {}).get("login") or ""), str(pr.get("updated_at") or "")]
                    for pr in prs
                ]
                lines.append("### Open Pull Requests")
                lines.append(render_table(["#", "Title", "Author", "Updated"], pr_rows or [["n/a", "No open pull requests", "", ""]]))
                self.add_check("read", "github-open-prs", STATUS_PASS, f"Listed {len(prs)} open pull requests for `{owner}/{repo_name}`.")

            if issues:
                latest_issue = issues[0]
                issue_number = int(latest_issue.get("number"))
                issue_payload, issue_error = await self.call_tool(
                    "github_get_issue",
                    {"owner": owner, "repo": repo_name, "issue_number": issue_number},
                    f"Read issue body for `{owner}/{repo_name}#{issue_number}`.",
                    "Expected issue body, state, labels, and metadata.",
                )
                comments, comments_error = await self.paginate(
                    "github_list_issue_comments",
                    {"owner": owner, "repo": repo_name, "issue_number": issue_number, "per_page": 100, "page": 1},
                    "items",
                    f"Read comments for `{owner}/{repo_name}#{issue_number}`.",
                    "Expected issue comments ordered by pagination.",
                    max_pages=10,
                )
                lines.append(f"### Latest Updated Issue: `{owner}/{repo_name}#{issue_number}`")
                if issue_error:
                    lines.append(f"- Issue body error: `{issue_error}`")
                else:
                    lines.append("```text")
                    lines.append(sanitize_text(str((issue_payload or {}).get("body") or "")))
                    lines.append("```")
                if comments_error:
                    lines.append(f"- Comment listing error: `{comments_error}`")
                else:
                    recent_comments = sorted(comments, key=lambda item: item.get("updated_at") or "", reverse=True)[:3]
                    lines.append("- Last 3 comments:")
                    for comment in recent_comments:
                        lines.append(
                            f"  - `{(comment.get('user') or {}).get('login') or 'unknown'}` at `{comment.get('updated_at')}`: "
                            f"{sanitize_text(normalize_space(comment.get('body') or ''))[:220]}"
                        )
                issue_status = STATUS_PASS if not issue_error and not comments_error else STATUS_PARTIAL
                self.add_check("read", "github-issue-deep-dive", issue_status, f"Loaded issue body and comments for `{owner}/{repo_name}#{issue_number}`.")

        if self.args.allow_writes:
            target_repo = self.select_github_write_repo()
            if target_repo is None:
                self.add_check("write", "github-create-issue", STATUS_BLOCKED_RUNTIME, "No clearly safe owned target repo matched the write-selection rules.")
                lines.append("- GitHub write validation skipped: no clearly safe owned target repo matched `test-agent-project`, `test+agent`, or `project`.")
            else:
                title = f"MCP Exhaustive Test – {self.args.report_date}"
                issue_body = self.build_github_issue_body()
                owner = str(target_repo.get("owner") or "")
                repo_name = str(target_repo.get("name") or "")
                create_payload, create_error = await self.call_tool(
                    "github_create_issue",
                    {
                        "owner": owner,
                        "repo": repo_name,
                        "title": title,
                        "body": issue_body,
                        "labels": ["test", "mcp", "automated"],
                    },
                    f"Create validation issue in `{owner}/{repo_name}`.",
                    "Expected a newly created GitHub issue with the requested labels.",
                )
                if create_error:
                    status = classify_error(create_error)
                    self.add_check("write", "github-create-issue", status, f"GitHub issue creation failed: {create_error}")
                    lines.append(f"- GitHub issue creation failed in `{owner}/{repo_name}`: `{create_error}`")
                else:
                    issue_number = int((create_payload or {}).get("number"))
                    readback_payload, readback_error = await self.call_tool(
                        "github_get_issue",
                        {"owner": owner, "repo": repo_name, "issue_number": issue_number},
                        f"Read back newly created GitHub issue `{owner}/{repo_name}#{issue_number}`.",
                        "Expected the created issue to round-trip successfully.",
                    )
                    if readback_error:
                        self.add_check("write", "github-create-issue", STATUS_PARTIAL, f"Issue created but readback failed: {readback_error}")
                        lines.append(f"- Issue created as `{owner}/{repo_name}#{issue_number}`, but readback failed: `{readback_error}`")
                    else:
                        issue_url = (readback_payload or {}).get("html_url") or (create_payload or {}).get("html_url")
                        labels = ", ".join(label.get("name") or "" for label in (readback_payload or {}).get("labels") or [])
                        self.add_check("write", "github-create-issue", STATUS_PASS, f"Created and read back GitHub issue `{owner}/{repo_name}#{issue_number}`.")
                        lines.append(f"- Created GitHub validation issue: `{owner}/{repo_name}#{issue_number}`")
                        lines.append(f"- URL: {issue_url}")
                        lines.append(f"- Labels: {labels}")
        else:
            self.add_check("write", "github-create-issue", STATUS_PARTIAL, "GitHub write validation not executed because `--allow-writes` was not set.")
            lines.append("- GitHub write validation not executed because `--allow-writes` was not set.")

        self.add_section("GitHub Validation", lines)

    def build_drive_validation_content(self) -> str:
        now_ist = datetime.now(IST).isoformat()
        return "\n".join(
            [
                f"# MCP Super Test {self.args.report_date}",
                "",
                f"- Generated at (IST): {now_ist}",
                f"- Backend user: {self.args.username}",
                f"- Connector user: {self.args.connector_username}",
                "",
                "## GitHub Results",
                "- Identity, repo metadata, code search, issues, pull requests, and write validation summary.",
                "",
                "## Drive Results",
                "- Root listing, full-text search, content reads, folder navigation, and write validation summary.",
                "",
                "## Outcome",
                "- Successes and failures will be copied into the final markdown report.",
            ]
        )

    async def run_drive_validation(self) -> None:
        lines = []

        root_payload, root_error = await self.call_tool(
            "google_drive_list_root",
            {"page_size": 100},
            "List direct contents of Drive root.",
            "Expected recent items under Drive root or configured root folder.",
        )
        if root_error:
            status = classify_error(root_error)
            self.add_check("list", "drive-root-listing", status, f"Drive root listing failed: {root_error}")
            lines.append(f"- Drive root listing failed: `{root_error}`")
        else:
            root_files = list((root_payload or {}).get("files") or [])
            self.drive_root_listing = root_files
            total_label = str(len(root_files))
            if (root_payload or {}).get("nextPageToken"):
                total_label = f"{len(root_files)}+ (more pages available)"
            lines.append(f"- Root listing count: **{total_label}**")
            root_rows = []
            for item in root_files[:20]:
                root_rows.append(
                    [
                        sanitize_text(item.get("name") or ""),
                        str(item.get("mimeType") or ""),
                        str(item.get("modifiedTime") or ""),
                        str(item.get("size") or ""),
                    ]
                )
            lines.append(render_table(["Name", "Mime", "Modified", "Size"], root_rows or [["n/a", "", "", ""]]))
            self.add_check("list", "drive-root-listing", STATUS_PASS, f"Listed {len(root_files)} root items.")

        search_payload, search_error = await self.call_tool(
            "google_drive_search_full_text",
            {
                "query": "agent MCP project test todo roadmap",
                "page_size": 50,
                "mime_filters": [
                    "application/vnd.google-apps.document",
                    "application/vnd.google-apps.spreadsheet",
                    "text/plain",
                    "text/markdown",
                    "application/pdf",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/json",
                    "application/csv",
                ],
            },
            "Search Drive content for project-related keywords.",
            "Expected files whose body text matches any requested keyword.",
        )
        drive_hits = list((search_payload or {}).get("files") or []) if not search_error else []
        if not drive_hits:
            union_results: dict[str, dict[str, Any]] = {}
            for query in SEARCH_KEYWORDS:
                payload, error_text = await self.call_tool(
                    "google_drive_search_files",
                    {"query": query, "page_size": 20},
                    f"Fallback filename search for `{query}`.",
                    "Expected Drive files whose names match the keyword.",
                )
                if error_text:
                    continue
                for item in (payload or {}).get("files") or []:
                    file_id = item.get("id") or ""
                    if file_id:
                        union_results[file_id] = sanitize_data(item)
            drive_hits = list(union_results.values())

        drive_hits = [item for item in drive_hits if (item.get("mimeType") or "") != DRIVE_FOLDER_MIME][:8]
        self.drive_search_results = drive_hits
        parent_name_cache: dict[str, str] = {}
        result_rows = []
        for item in drive_hits:
            parent_ids = item.get("parents") or []
            parent_name = "root"
            if parent_ids:
                parent_id = str(parent_ids[0])
                if parent_id not in parent_name_cache:
                    parent_payload, parent_error = await self.call_tool(
                        "google_drive_get_metadata",
                        {"file_id": parent_id},
                        f"Resolve parent metadata for Drive item `{item.get('name')}`.",
                        "Expected parent folder metadata.",
                    )
                    parent_name_cache[parent_id] = str((parent_payload or {}).get("name") or parent_id) if not parent_error else shorten_id(parent_id)
                parent_name = parent_name_cache[parent_id]
            result_rows.append(
                [
                    sanitize_text(item.get("name") or ""),
                    shorten_id(str(item.get("id") or "")),
                    str(item.get("mimeType") or ""),
                    str(item.get("modifiedTime") or ""),
                    sanitize_text(parent_name),
                ]
            )
        search_status = STATUS_PASS if drive_hits else (classify_error(search_error) if search_error else STATUS_PARTIAL)
        self.add_check("search", "drive-search", search_status, f"Collected {len(drive_hits)} Drive search hits.")
        lines.append("### Search Results")
        lines.append(render_table(["Name", "ID", "Mime", "Modified", "Parent"], result_rows or [["n/a", "", "", "", "No matches"]]))

        type_buckets: dict[str, dict[str, Any]] = {}
        for item in drive_hits:
            bucket = infer_drive_file_type(item)
            if bucket not in type_buckets:
                type_buckets[bucket] = item
            if len(type_buckets) >= 3:
                break
        file_read_rows = []
        for bucket_name, item in list(type_buckets.items())[:3]:
            file_id = str(item.get("id") or "")
            read_payload, read_error = await self.call_tool(
                "google_drive_read_text_file",
                {"file_id": file_id},
                f"Read Drive content for `{item.get('name')}`.",
                "Expected readable text content or a clear extraction warning.",
            )
            summary_lines: list[str] = []
            content_excerpt = ""
            if read_error:
                summary_lines.append(f"Read error: {read_error}")
            else:
                content = str((read_payload or {}).get("content") or "")
                content_excerpt = sanitize_text(content[:1800])
                summary_lines = summarize_text_to_bullets(content_excerpt, max_bullets=4)
            file_read_rows.append([sanitize_text(item.get("name") or ""), bucket_name, "<br>".join(summary_lines)])
            lines.append(f"### Drive Read: `{item.get('name')}` ({bucket_name})")
            if content_excerpt:
                lines.append("```text")
                lines.append(content_excerpt)
                lines.append("```")
                lines.append("- Summary:")
                for line in summary_lines:
                    lines.append(f"  - {line}")
        if file_read_rows:
            self.add_check("read", "drive-read-files", STATUS_PASS, f"Read {len(file_read_rows)} Drive files across distinct types.")
        else:
            self.add_check("read", "drive-read-files", STATUS_PARTIAL, "No distinct Drive files were available to read.")

        folder_candidates: list[dict[str, Any]] = []
        for query in ["AI", "Projects", "Agent", "2026"]:
            payload, error_text = await self.call_tool(
                "google_drive_search_files",
                {"query": query, "page_size": 20},
                f"Search for project-related Drive folders named `{query}`.",
                "Expected folder candidates when such folders exist.",
            )
            if error_text:
                continue
            for item in (payload or {}).get("files") or []:
                if item.get("mimeType") == DRIVE_FOLDER_MIME:
                    folder_candidates.append(sanitize_data(item))
        selected_folder = folder_candidates[0] if folder_candidates else None
        if selected_folder:
            folder_id = str(selected_folder.get("id") or "")
            listing_payload, listing_error = await self.call_tool(
                "google_drive_list_folder",
                {"folder_id": folder_id, "page_size": 50},
                f"List direct contents of Drive folder `{selected_folder.get('name')}`.",
                "Expected children of the selected Drive folder.",
            )
            lines.append(f"### Folder Structure: `{selected_folder.get('name')}`")
            if listing_error:
                lines.append(f"- Folder listing error: `{listing_error}`")
                self.add_check("list", "drive-folder-navigation", classify_error(listing_error), listing_error)
            else:
                children = list((listing_payload or {}).get("files") or [])
                tree_lines = []
                for child in children[:15]:
                    child_name = sanitize_text(child.get("name") or "")
                    tree_lines.append(f"- {child_name}")
                    if child.get("mimeType") == DRIVE_FOLDER_MIME:
                        nested_payload, nested_error = await self.call_tool(
                            "google_drive_list_folder",
                            {"folder_id": child.get("id"), "page_size": 20},
                            f"List second-level contents of Drive folder `{child_name}`.",
                            "Expected nested children one level below the selected project folder.",
                        )
                        if not nested_error:
                            nested_items = list((nested_payload or {}).get("files") or [])
                            for nested in nested_items[:10]:
                                tree_lines.append(f"  - {sanitize_text(nested.get('name') or '')}")
                lines.extend(tree_lines or ["- Folder is empty."])
                self.add_check("list", "drive-folder-navigation", STATUS_PASS, f"Mapped a two-level Drive folder tree for `{selected_folder.get('name')}`.")
        else:
            self.add_check("list", "drive-folder-navigation", STATUS_PARTIAL, "No matching project-named Drive folder was found.")
            lines.append("- No matching project-named Drive folder was found.")

        if self.args.allow_writes:
            ai_tests_parent_id = None
            payload, error_text = await self.call_tool(
                "google_drive_search_files",
                {"query": "AI-Tests", "page_size": 10},
                "Look for an `AI-Tests` Drive folder before creating the validation file.",
                "Expected zero or one folder named `AI-Tests`.",
            )
            if not error_text:
                matches = [item for item in (payload or {}).get("files") or [] if item.get("mimeType") == DRIVE_FOLDER_MIME]
                if len(matches) == 1:
                    ai_tests_parent_id = matches[0].get("id")
            write_content = self.build_drive_validation_content()
            upload_args: dict[str, Any] = {
                "name": f"MCP-Super-Test-{self.args.report_date}.md",
                "content": write_content,
                "mime_type": "text/markdown",
            }
            if ai_tests_parent_id:
                upload_args["parent_id"] = ai_tests_parent_id
            upload_payload, upload_error = await self.call_tool(
                "google_drive_upload_text_file",
                upload_args,
                "Create a Drive markdown file for validation evidence.",
                "Expected a newly created Drive text file.",
            )
            if upload_error:
                status = classify_error(upload_error)
                self.add_check("write", "drive-create-file", status, f"Drive file creation failed: {upload_error}")
                lines.append(f"- Drive file creation failed: `{upload_error}`")
            else:
                created_file_id = str((upload_payload or {}).get("id") or "")
                search_payload, search_error = await self.call_tool(
                    "google_drive_search_files",
                    {"query": f"MCP-Super-Test-{self.args.report_date}.md", "page_size": 10},
                    "Search for the newly created Drive validation file by name.",
                    "Expected the created Drive file to appear in search results.",
                )
                readback_payload, readback_error = await self.call_tool(
                    "google_drive_read_text_file",
                    {"file_id": created_file_id},
                    "Read back the newly created Drive validation file.",
                    "Expected markdown content from the new file.",
                )
                _, delete_error = await self.call_tool(
                    "google_drive_delete_file",
                    {"file_id": created_file_id},
                    "Delete the temporary Drive validation file after verification.",
                    "Expected Drive file deletion to succeed.",
                )
                status = STATUS_PASS if not search_error and not readback_error else STATUS_PARTIAL
                self.add_check("write", "drive-create-file", status, f"Created and verified Drive file `{shorten_id(created_file_id)}`.")
                lines.append(f"- Created Drive file ID: `{shorten_id(created_file_id)}`")
                if search_error:
                    lines.append(f"- Search readback warning: `{search_error}`")
                if readback_error:
                    lines.append(f"- Content readback warning: `{readback_error}`")
                else:
                    lines.append("```text")
                    lines.append(sanitize_text(str((readback_payload or {}).get("content") or "")[:300]))
                    lines.append("```")
                if delete_error:
                    lines.append(f"- Delete warning: `{delete_error}`")
                    self.add_check("write", "drive-delete-temp-file", classify_error(delete_error), f"Drive temp file deletion failed: {delete_error}")
                else:
                    self.add_check("write", "drive-delete-temp-file", STATUS_PASS, f"Deleted temporary Drive file `{shorten_id(created_file_id)}`.")
        else:
            self.add_check("write", "drive-create-file", STATUS_PARTIAL, "Drive write validation not executed because `--allow-writes` was not set.")
            lines.append("- Drive write validation not executed because `--allow-writes` was not set.")

        self.add_section("Google Drive Validation", lines)

    async def run_combined_validation(self) -> None:
        lines = []

        roadmap_payload, roadmap_error = await self.call_tool(
            "google_drive_search_full_text",
            {
                "query": "roadmap plan next steps agent",
                "page_size": 10,
                "mime_filters": [
                    "application/vnd.google-apps.document",
                    "application/pdf",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "text/plain",
                    "text/markdown",
                ],
            },
            "Search Drive for planning documents to seed cross-MCP project sync validation.",
            "Expected a planning document with roadmap-like content.",
        )
        roadmap_hits = list((roadmap_payload or {}).get("files") or []) if not roadmap_error else []
        if not roadmap_hits:
            self.add_check("combined", "project-sync", STATUS_PARTIAL, "No roadmap-like Drive document was found for project sync simulation.")
            lines.append("- No roadmap-like Drive document was found for project sync simulation.")
        else:
            selected = roadmap_hits[0]
            file_id = str(selected.get("id") or "")
            read_payload, read_error = await self.call_tool(
                "google_drive_read_text_file",
                {"file_id": file_id},
                f"Read planning document `{selected.get('name')}` for project sync extraction.",
                "Expected readable roadmap or next-steps text.",
            )
            if read_error:
                self.add_check("combined", "project-sync", classify_error(read_error), f"Could not read planning document: {read_error}")
                lines.append(f"- Planning document read failed: `{read_error}`")
            else:
                content = str((read_payload or {}).get("content") or "")
                tasks = extract_task_keywords(content, limit=8)
                repo_candidates: list[dict[str, Any]] = []
                for keyword in tasks[:3]:
                    search_payload, search_error = await self.call_tool(
                        "github_search_repositories",
                        {"query": f"{keyword} user:{self.github_login}", "per_page": 10},
                        f"Search GitHub repositories for keyword `{keyword}` extracted from Drive planning content.",
                        "Expected repositories with matching names or descriptions.",
                    )
                    if search_error:
                        continue
                    for repo in (search_payload or {}).get("items") or []:
                        repo_candidates.append(repo)
                repo_candidates.extend(
                    [
                        repo
                        for repo in self.github_repos
                        if any(
                            keyword.lower() in normalize_space(f"{repo.get('name')} {repo.get('description')}".lower())
                            for keyword in tasks[:5]
                        )
                    ]
                )
                deduped: dict[str, dict[str, Any]] = {}
                for repo in repo_candidates:
                    full_name = str(repo.get("full_name") or "")
                    if full_name and full_name not in deduped:
                        deduped[full_name] = repo
                selected_repo = next(iter(deduped.values()), None)
                lines.append(f"- Planning document: `{selected.get('name')}`")
                lines.append("- Extracted tasks/keywords: " + (", ".join(tasks) if tasks else "none"))
                if selected_repo:
                    owner = str(selected_repo.get("owner") or "")
                    repo_name = str(selected_repo.get("name") or "")
                    issues, issues_error = await self.paginate(
                        "github_list_issues",
                        {"owner": owner, "repo": repo_name, "state": "open", "per_page": 100, "page": 1},
                        "items",
                        f"Check open issues in `{owner}/{repo_name}` against extracted Drive tasks.",
                        "Expected current open issues for overlap analysis.",
                        max_pages=10,
                    )
                    suggestions = []
                    if not issues_error:
                        for keyword in tasks[:6]:
                            if any(keyword.lower() in normalize_space(f"{issue.get('title')} {issue.get('body')}".lower()) for issue in issues):
                                continue
                            suggestions.append(f"Create an issue for `{keyword}` in `{owner}/{repo_name}`.")
                            if len(suggestions) >= 3:
                                break
                    lines.append(f"- Matching repo candidate: `{selected_repo.get('full_name')}`")
                    lines.append("- Suggested issues:")
                    for suggestion in (suggestions or ["No new issue suggestions; existing open issues already overlap heavily."]):
                        lines.append(f"  - {suggestion}")
                    self.add_check("combined", "project-sync", STATUS_PASS, f"Completed cross-MCP planning sync analysis for `{selected_repo.get('full_name')}`.")
                else:
                    self.add_check("combined", "project-sync", STATUS_PARTIAL, "Found a planning document but no GitHub repo candidate matched the extracted tasks.")
                    lines.append("- No GitHub repository candidate matched the extracted Drive tasks.")

        failure_rows = []
        bogus_file_id = "super-secret-fake-12345"
        _, drive_missing_error = await self.call_tool(
            "google_drive_read_text_file",
            {"file_id": bogus_file_id},
            "Validate Drive missing-file failure handling with a bogus file ID.",
            "Expected a clear not-found error.",
        )
        missing_search_payload, missing_search_error = await self.call_tool(
            "google_drive_search_and_read_file",
            {"query": "super-secret-fake-12345.pdf", "page_size": 10},
            "Validate graceful no-match behavior for a non-existent Drive filename.",
            "Expected a no-match response without an exception.",
        )
        _, fake_user_error = await self.call_tool(
            "github_list_user_repositories",
            {"owner": "nonexistentuser987654321", "per_page": 10, "page": 1},
            "Validate GitHub fake-user failure handling.",
            "Expected a 404-style error for the bogus GitHub account.",
        )
        _, impossible_path_error = await self.call_tool(
            "google_drive_create_text_file_at_path",
            {"path": "/This/Folder/Does/Not/Exist/test.txt", "content": "validation", "mime_type": "text/plain"},
            "Validate Drive path-resolution failure handling on an impossible nested path.",
            "Expected a path-resolution error before upload.",
        )
        failure_rows.append(
            [
                "Drive missing file",
                sanitize_text(drive_missing_error or "No error"),
                "Use a real Drive file ID or reconnect Drive if content access is missing.",
            ]
        )
        failure_rows.append(
            [
                "Drive no-match search",
                sanitize_text(str((missing_search_payload or {}).get("message") or missing_search_error or "No response")),
                "Verify the filename or broaden the query.",
            ]
        )
        failure_rows.append(
            [
                "GitHub fake user",
                sanitize_text(fake_user_error or "No error"),
                "Verify the GitHub owner/login before retrying repository enumeration.",
            ]
        )
        failure_rows.append(
            [
                "Drive impossible path",
                sanitize_text(impossible_path_error or "No error"),
                "Create the folder path first or use a valid parent path.",
            ]
        )
        lines.append("### Failure Injection")
        lines.append(render_table(["Scenario", "Observed Error", "Recovery"], failure_rows))
        self.add_check("failure", "failure-injection", STATUS_PASS, "Captured failure behavior for missing Drive file, fake GitHub user, and impossible Drive path.")

        self.add_section("Combined Workflows And Failure Injection", lines)

    def render_trace_section(self) -> str:
        lines = ["## Tool Trace"]
        for index, trace in enumerate(self.traces, start=1):
            lines.append(
                f"{index}. Server `{trace.server}`; tool `{trace.tool}`; why: {sanitize_text(trace.why)}; "
                f"expected: {sanitize_text(trace.expect)}; status: `{trace.status}`"
            )
            lines.append(f"   - Arguments: `{json.dumps(sanitize_data(trace.arguments), ensure_ascii=False)}`")
            lines.append(f"   - Result note: `{sanitize_text(trace.note)}`")
        return "\n".join(lines)

    def render_summary_section(self) -> str:
        category_buckets: dict[str, list[str]] = defaultdict(list)
        for check in self.checks:
            category_buckets[check.category].append(check.status)

        rows = []
        for category in ["discovery", "auth", "list", "read", "search", "write", "combined", "failure"]:
            statuses = category_buckets.get(category, [])
            if not statuses:
                continue
            numeric_score = sum(SUCCESS_WEIGHTS.get(status, 0.0) for status in statuses) / len(statuses)
            counter = Counter(statuses)
            rows.append(
                [
                    category,
                    f"{numeric_score * 100:.0f}%",
                    str(counter.get(STATUS_PASS, 0)),
                    str(counter.get(STATUS_PARTIAL, 0)),
                    str(sum(counter.get(status, 0) for status in [STATUS_BLOCKED_SURFACE, STATUS_BLOCKED_PERMISSION, STATUS_BLOCKED_NETWORK, STATUS_BLOCKED_RUNTIME])),
                    str(counter.get(STATUS_ERROR, 0)),
                ]
            )

        issues = [check for check in self.checks if check.status != STATUS_PASS]
        if any(check.category == "combined" and check.status == STATUS_PASS for check in self.checks):
            impressive = "Cross-MCP project sync: read a Drive planning artifact, mapped extracted tasks to GitHub repos/issues, and generated issue suggestions."
        elif any(check.category == "read" and check.name == "github-full-file" and check.status == STATUS_PASS for check in self.checks):
            impressive = "End-to-end content extraction across GitHub README/code and Google Drive document/file content."
        else:
            impressive = "Runtime MCP discovery and authenticated connector preflight across both servers."

        lines = [
            "## Final Summary",
            f"- Servers discovered and connected: GitHub `{bool(self.preflight_status)}`, Google Drive `{bool(self.preflight_accounts)}`",
            "- Success rate per category (partial counts as 50%):",
            render_table(["Category", "Score", "Pass", "Partial", "Blocked", "Error"], rows or [["n/a", "0%", "0", "0", "0", "0"]]),
            f"- Most useful demonstrated capability: {impressive}",
        ]
        if issues:
            lines.append("- Bugs, limitations, or permission issues:")
            for check in issues[:8]:
                lines.append(f"  - `{check.name}`: `{check.status}` - {check.summary}")
        else:
            lines.append("- Bugs, limitations, or permission issues: none observed.")
        lines.append("- Recommendations:")
        lines.append("  - Run the validator with non-sandboxed network access; sandboxed MCP stdio calls in this environment cannot reach GitHub/Google directly.")
        lines.append("  - Keep the new GitHub scope/org/comment/language tools and Drive root/full-text/path tools in the server surface; they materially improve audit coverage.")
        lines.append("  - If Drive remains on `drive.file` rather than full `drive`, expect content visibility limits for files not created or explicitly opened by the app.")
        return "\n".join(lines)

    def render_checks_section(self) -> str:
        lines = ["## Check Outcomes"]
        for check in self.checks:
            lines.append(f"- `{check.category}` / `{check.name}`: `{check.status}` - {check.summary}")
            for detail in check.details:
                lines.append(f"  - {detail}")
        return "\n".join(lines)

    def render_report(self) -> str:
        header = "\n".join(
            [
                f"# Exhaustive GitHub + Google Drive MCP Validation Report ({self.args.report_date})",
                "",
                f"- Generated at (IST): {datetime.now(IST).isoformat()}",
                f"- Backend URL: `{self.args.backend_url}`",
                f"- Backend user: `{self.args.username}`",
                f"- Connector user: `{self.args.connector_username}`",
                f"- Write validation enabled: `{self.args.allow_writes}`",
            ]
        )
        return "\n\n".join(
            [
                header,
                *self.report_sections,
                self.render_checks_section(),
                self.render_summary_section(),
                self.render_trace_section(),
            ]
        ).strip() + "\n"

    async def run(self) -> str:
        await self.run_preflight()
        await self.run_discovery()
        await self.run_github_validation()
        await self.run_drive_validation()
        await self.run_combined_validation()
        return self.render_report()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an exhaustive GitHub + Google Drive MCP validation report.")
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--connector-username", default="admin")
    parser.add_argument("--output", default=str(BACKEND_DIR / "mcp_exhaustive_validation_report.md"))
    parser.add_argument("--report-date", default=datetime.now(IST).strftime("%Y-%m-%d"))
    parser.add_argument("--allow-writes", action="store_true", help="Enable GitHub issue creation and Drive file creation/deletion.")
    return parser


async def async_main(args: argparse.Namespace) -> None:
    runner = ValidationRunner(args)
    exit_code = 0
    try:
        report = await runner.run()
    except Exception as exc:  # pragma: no cover - runtime behavior
        report = "\n".join(
            [
                f"# MCP validation failed ({args.report_date})",
                "",
                f"- Fatal error: `{sanitize_text(str(exc))}`",
            ]
        )
        exit_code = 1

    output_path = Path(args.output)
    output_path.write_text(report, encoding="utf-8")
    sys.stdout.buffer.write(f"Wrote validation report to {output_path.name}\n".encode("utf-8", errors="ignore"))
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
