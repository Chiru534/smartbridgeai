import sys
sys.path.append('.')
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

try:
    from backend.platform_core import github_workspace as gw
except ImportError:
    from platform_core import github_workspace as gw


def _request(*messages: tuple[str, str]) -> SimpleNamespace:
    return SimpleNamespace(
        model="llama-3.3-70b-versatile",
        messages=[SimpleNamespace(role=role, content=content) for role, content in messages],
    )


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(current_user={"username": "admin"})


def test_repo_lists_use_short_names_for_my_repositories() -> None:
    reply = gw._format_repo_list(
        [{"name": "testing-main", "full_name": "Chiru534/testing-main", "language": "TypeScript"}],
        prefer_full_name=False,
    )
    assert "1. testing-main - TypeScript" in reply, reply
    assert "Chiru534/testing-main" not in reply, reply


def test_resolve_repo_reference_from_current_turn() -> None:
    async def _run() -> None:
        request = _request(
            ("assistant", "Here are the GitHub repositories I found:\n1. testing-main"),
            ("user", "give me the testing-main repos files or structure"),
        )
        fake_payload = {
            "items": [
                {"name": "testing-main", "full_name": "Chiru534/testing-main"},
                {"name": "project_agent", "full_name": "Chiru534/project_agent"},
            ]
        }
        with patch.object(gw, "_call_github_tool", AsyncMock(return_value=(fake_payload, None))):
            repo_ref, _ = await gw._resolve_repo_reference(request, _ctx(), [])
        assert repo_ref == ("Chiru534", "testing-main"), repo_ref

    asyncio.run(_run())


def test_resolve_repo_reference_from_prior_turn() -> None:
    async def _run() -> None:
        request = _request(
            ("assistant", "The frontend directory in the Chiru534/testing-main repository contains app.js, index.html, and styles.css."),
            ("user", "app.js file content i mean code inside it"),
        )
        fake_payload = {"items": [{"name": "testing-main", "full_name": "Chiru534/testing-main"}]}
        with patch.object(gw, "_call_github_tool", AsyncMock(return_value=(fake_payload, None))):
            repo_ref, _ = await gw._resolve_repo_reference(request, _ctx(), [])
        assert repo_ref == ("Chiru534", "testing-main"), repo_ref

    asyncio.run(_run())


def test_handle_repo_detail_returns_raw_code_for_file_request() -> None:
    async def _run() -> None:
        request = _request(("user", "app.js file content i mean code inside it"))

        async def fake_call(tool_name, arguments, ctx, tool_events):
            print('\n[DEBUG] fake_call:', tool_name, arguments)
            if tool_name == "github_search_code":
                assert arguments["query"] == "repo:Chiru534/testing-main filename:app.js"
                return ({"items": [{"path": "frontend/app.js"}]}, None)
            if tool_name == "github_get_file":
                assert arguments["path"] == "frontend/app.js"
                return ({"content": "const value = 1;\nexport default value;\n"}, None)
            raise AssertionError(f"Unexpected tool call: {tool_name}")

        with patch.object(gw, "_call_github_tool", side_effect=fake_call):
            result = await gw._handle_repo_detail(request, _ctx(), "Chiru534", "testing-main")
        assert "File content for frontend/app.js in Chiru534/testing-main:" in result["reply"], result["reply"]
        assert "```js" in result["reply"], result["reply"]
        assert "const value = 1;" in result["reply"], result["reply"]
        assert "Summary of" not in result["reply"], result["reply"]

    asyncio.run(_run())


def test_handle_repo_detail_reuses_prior_directory_context() -> None:
    async def _run() -> None:
        request = _request(
            ("assistant", "The frontend directory in the Chiru534/testing-main repository contains app.js, index.html, and styles.css."),
            ("user", "app.js file content i mean code inside it"),
        )

        async def fake_call(tool_name, arguments, ctx, tool_events):
            assert tool_name == "github_get_file", tool_name
            assert arguments["path"] == "frontend/app.js", arguments
            return ({"content": "console.log('frontend');\n"}, None)

        with patch.object(gw, "_call_github_tool", side_effect=fake_call):
            result = await gw._handle_repo_detail(request, _ctx(), "Chiru534", "testing-main")
        assert "File content for frontend/app.js" in result["reply"], result["reply"]
        assert "console.log('frontend');" in result["reply"], result["reply"]

    asyncio.run(_run())


def test_handle_repo_detail_lists_requested_directory() -> None:
    async def _run() -> None:
        request = _request(("user", "frontend files inside it"))

        async def fake_call(tool_name, arguments, ctx, tool_events):
            assert tool_name == "github_list_directory", tool_name
            assert arguments["path"] == "frontend", arguments
            return ({"items": [{"type": "file", "path": "frontend/app.js"}]}, None)

        with patch.object(gw, "_call_github_tool", side_effect=fake_call):
            result = await gw._handle_repo_detail(request, _ctx(), "Chiru534", "testing-main")
        assert result["reply"].startswith("Files in frontend of Chiru534/testing-main:"), result["reply"]
        assert "frontend/app.js" in result["reply"], result["reply"]

    asyncio.run(_run())


if __name__ == "__main__":
    test_repo_lists_use_short_names_for_my_repositories()
    test_resolve_repo_reference_from_current_turn()
    test_resolve_repo_reference_from_prior_turn()
    test_handle_repo_detail_returns_raw_code_for_file_request()
    test_handle_repo_detail_reuses_prior_directory_context()
    test_handle_repo_detail_lists_requested_directory()
    print("PASS: github workspace regression checks passed")
