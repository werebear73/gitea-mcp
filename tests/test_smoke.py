"""Smoke tests: package imports and tool modules register without error."""

from __future__ import annotations


def test_package_imports() -> None:
    import gitea_mcp

    assert gitea_mcp.__version__ is not None


def test_server_module_loads() -> None:
    from gitea_mcp.server import mcp

    assert mcp is not None
    # FastMCP exposes the server name; the gitea-mcp server identifies itself
    # as "gitea-mcp" so MCP clients can find it.
    assert getattr(mcp, "name", None) == "gitea-mcp"


def test_all_tool_modules_load() -> None:
    """Importing each tool module should register its tools against the FastMCP
    instance without raising."""
    from gitea_mcp.tools import issues, releases, repos  # noqa: F401
