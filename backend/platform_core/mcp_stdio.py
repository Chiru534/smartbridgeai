from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import settings

try:
    from mcp import ClientSession, StdioServerParameters
    import mcp.client.stdio as mcp_stdio_module
    from mcp.client.stdio import stdio_client
    import mcp.os.win32.utilities as mcp_win32_utilities
except Exception:  # pragma: no cover - dependency is optional at runtime
    ClientSession = None
    StdioServerParameters = None
    mcp_stdio_module = None
    mcp_win32_utilities = None
    stdio_client = None


@dataclass
class MCPToolBinding:
    server_name: str
    exposed_name: str
    original_name: str
    description: str
    parameters: dict[str, Any]
    hidden_parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ManagedMCPServer:
    name: str
    command: list[str]
    env_overrides: dict[str, str] = field(default_factory=dict)
    timeout_secs: int = settings.mcp_tool_timeout_secs
    cwd: str | None = None

    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _stdio_cm: Any = field(default=None, init=False)
    _session_cm: Any = field(default=None, init=False)
    _session: Any = field(default=None, init=False)
    _bindings: dict[str, MCPToolBinding] = field(default_factory=dict, init=False)
    last_error: str | None = field(default=None, init=False)

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
        if self._session is not None:
            return True

        async with self._lock:
            if self._session is not None:
                return True

            resolved_command = _resolve_command(self.command)
            params = StdioServerParameters(
                command=resolved_command[0],
                args=resolved_command[1:],
                env={**self.env_overrides} if self.env_overrides else None,
                cwd=self.cwd,
            )
            self._stdio_cm = stdio_client(params)
            try:
                read_stream, write_stream = await self._stdio_cm.__aenter__()
                self._session_cm = ClientSession(read_stream, write_stream)
                self._session = await self._session_cm.__aenter__()
                await self._session.initialize()
                self.last_error = None
                return True
            except Exception as exc:
                self.last_error = str(exc)
                self._session = None
                self._session_cm = None
                self._stdio_cm = None
                raise

    async def list_tools(self) -> list[MCPToolBinding]:
        started = await self.ensure_started()
        if not started or self._session is None:
            return []

        result = await asyncio.wait_for(self._session.list_tools(), timeout=self.timeout_secs)
        bindings: list[MCPToolBinding] = []
        for tool in getattr(result, "tools", []):
            original_name = getattr(tool, "name", "")
            exposed_name = original_name if original_name.startswith(f"{self.name}_") else f"{self.name}_{original_name}"
            visible_parameters, hidden_parameters = _split_hidden_parameters(
                getattr(tool, "inputSchema", None) or {"type": "object", "properties": {}}
            )
            binding = MCPToolBinding(
                server_name=self.name,
                exposed_name=exposed_name,
                original_name=original_name,
                description=getattr(tool, "description", "") or "",
                parameters=visible_parameters,
                hidden_parameters=hidden_parameters,
            )
            bindings.append(binding)
            self._bindings[binding.exposed_name] = binding
        return bindings

    async def call_tool(
        self,
        exposed_name: str,
        arguments: dict[str, Any],
        injected_arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Reset dead session so ensure_started will reconnect
        if self._session is not None:
            try:
                await asyncio.wait_for(self._session.list_tools(), timeout=5)
            except Exception:
                async with self._lock:
                    self._session = None
                    self._session_cm = None
                    self._stdio_cm = None
                    self._bindings.clear()

        started = await self.ensure_started()
        if not started or self._session is None:
            raise RuntimeError(self.last_error or f"MCP server '{self.name}' is unavailable")

        binding = self._bindings.get(exposed_name)
        if binding is None:
            for candidate in await self.list_tools():
                if candidate.exposed_name == exposed_name:
                    binding = candidate
                    break
        if binding is None:
            raise RuntimeError(f"Unknown MCP tool '{exposed_name}'")

        result = await asyncio.wait_for(
            self._session.call_tool(
                name=binding.original_name,
                arguments={**arguments, **(injected_arguments or {})},
            ),
            timeout=self.timeout_secs,
        )
        return {
            "server": self.name,
            "tool": binding.exposed_name,
            "is_error": bool(getattr(result, "isError", False)),
            "content": normalize_mcp_content(getattr(result, "content", None)),
        }

    async def close(self) -> None:
        async with self._lock:
            if self._session_cm is not None:
                await self._session_cm.__aexit__(None, None, None)
            if self._stdio_cm is not None:
                await self._stdio_cm.__aexit__(None, None, None)
            self._session = None
            self._session_cm = None
            self._stdio_cm = None
            self._bindings.clear()


def normalize_mcp_content(content: Any) -> Any:
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        normalized_items = []
        for item in content:
            if hasattr(item, "text"):
                normalized_items.append(getattr(item, "text"))
            elif isinstance(item, dict):
                normalized_items.append(item)
            else:
                normalized_items.append(str(item))
        return normalized_items
    return content


def _split_hidden_parameters(parameters: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(parameters, dict):
        return parameters, {}

    hidden_keys = {"connector_username"}
    visible = json.loads(json.dumps(parameters))
    hidden: dict[str, Any] = {}
    properties = visible.get("properties")
    if isinstance(properties, dict):
        for key in list(properties.keys()):
            if key in hidden_keys:
                hidden[key] = properties.pop(key)
        required = visible.get("required")
        if isinstance(required, list):
            visible["required"] = [item for item in required if item not in hidden_keys]
    return visible, hidden


class MCPSubprocessManager:
    def __init__(self):
        self._servers: dict[str, ManagedMCPServer] = {}

    def register_server(
        self,
        name: str,
        command: list[str],
        env_overrides: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> None:
        self._servers[name] = ManagedMCPServer(
            name=name,
            command=command,
            env_overrides=env_overrides or {},
            cwd=cwd,
        )

    async def tools_for_servers(self, server_names: tuple[str, ...]) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for server_name in server_names:
            server = self._servers.get(server_name)
            if server is None:
                continue
            try:
                bindings = await server.list_tools()
            except Exception as exc:
                server.last_error = str(exc)
                continue
            for binding in bindings:
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": binding.exposed_name,
                            "description": binding.description,
                            "parameters": binding.parameters,
                        },
                    }
                )
        return tools

    async def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        injected_arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for server in self._servers.values():
            if tool_name.startswith(f"{server.name}_"):
                return await server.call_tool(tool_name, arguments, injected_arguments=injected_arguments)
        raise RuntimeError(f"No MCP server is registered for tool '{tool_name}'")

    def status(self) -> list[dict[str, Any]]:
        status_rows = []
        for name, server in self._servers.items():
            status_rows.append(
                {
                    "server": name,
                    "configured": bool(server.command),
                    "command": server.command,
                    "last_error": server.last_error,
                }
            )
        return status_rows


def _load_env_json(raw_value: str) -> dict[str, str]:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


def _resolve_command(command: list[str]) -> list[str]:
    if not command:
        return command
    executable = (command[0] or "").strip().lower()
    if executable in {"python", "python3", "py"}:
        return [sys.executable, *command[1:]]
    return command


def _patch_windows_stdio_process_fallback() -> None:
    if sys.platform != "win32" or mcp_stdio_module is None or mcp_win32_utilities is None:
        return

    original_create_windows_process = getattr(mcp_stdio_module, "create_windows_process", None)
    fallback_factory = getattr(mcp_win32_utilities, "_create_windows_fallback_process", None)
    if original_create_windows_process is None or fallback_factory is None:
        return
    if getattr(mcp_stdio_module, "_smartbridge_stdio_patch_applied", False):
        return

    async def _safe_create_windows_process(command, args, env=None, errlog=sys.stderr, cwd=None):
        try:
            return await original_create_windows_process(command, args, env, errlog, cwd)
        except PermissionError:
            return await fallback_factory(command, args, env, errlog, cwd)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 5:
                return await fallback_factory(command, args, env, errlog, cwd)
            raise

    mcp_stdio_module.create_windows_process = _safe_create_windows_process
    mcp_stdio_module._smartbridge_stdio_patch_applied = True


_patch_windows_stdio_process_fallback()


default_mcp_manager = MCPSubprocessManager()
_MCP_SERVER_CWD = str(Path(__file__).resolve().parents[1])
default_mcp_manager.register_server(
    "github",
    settings.github_mcp_command,
    env_overrides=_load_env_json(settings.github_mcp_env_json),
    cwd=_MCP_SERVER_CWD,
)
default_mcp_manager.register_server(
    "google_drive",
    settings.google_drive_mcp_command,
    env_overrides=_load_env_json(settings.google_drive_mcp_env_json),
    cwd=_MCP_SERVER_CWD,
)

# Register Slack MCP server only if a bot token is configured
if settings.slack_bot_token:
    _slack_env: dict[str, str] = _load_env_json(settings.slack_mcp_env_json)
    # Always inject the bot token so the MCP server subprocess can find it
    _slack_env["SLACK_BOT_TOKEN"] = settings.slack_bot_token
    default_mcp_manager.register_server(
        "slack",
        settings.slack_mcp_command,
        env_overrides=_slack_env,
        cwd=_MCP_SERVER_CWD,
    )

