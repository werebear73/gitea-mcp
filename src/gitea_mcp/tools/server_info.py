"""MCP tools for introspecting the running gitea-mcp server.

These are *runtime* introspection tools — callable from any MCP client (e.g.
Claude during a conversation) to ask the server about itself. Different from
the ``gitea-mcp doctor`` CLI command, which is a pre-launch check the human
runs in a shell before pointing an MCP client at the server.

Why this exists:

* **Multi-instance disambiguation.** A user may have several gitea-mcp
  servers configured in their MCP client (e.g. personal Gitea + work Gitea).
  Calling ``get_server_info`` lets Claude tell them apart by URL and user.
* **Version-aware debugging.** When a behavior diverges from the documented
  contract, the LLM can ask the server its version directly rather than
  guessing.
* **Self-awareness for upgrade prompts.** A future client can compare the
  running version against the latest on PyPI to nudge users to upgrade.
"""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from gitea_mcp import __version__
from gitea_mcp._app import get_client, mcp
from gitea_mcp.client import GiteaAPIError

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def get_server_version() -> dict[str, str]:
    """Return the running gitea-mcp server's version.

    No network call — just reports the package version. ``openWorldHint`` is
    ``False`` for this tool only, since it doesn't touch the Gitea instance
    or any external system.
    """
    return {"gitea_mcp_version": __version__}


@mcp.tool(annotations=_READ_ONLY)
async def get_server_info() -> dict[str, Any]:
    """Return information about the running gitea-mcp server and its Gitea connection.

    Performs two Gitea API calls — ``GET /user`` (to identify the authenticated
    user the PAT belongs to) and ``GET /version`` (to report the Gitea instance
    version). If ``/version`` is unavailable (older Gitea, or the PAT lacks the
    scope), ``gitea_version`` falls back to ``None`` rather than raising.

    Returns a dict with:

    * ``gitea_mcp_version`` — the gitea-mcp package version (e.g. ``"0.4.1"``).
    * ``gitea_url`` — the Gitea base URL this server is configured against.
    * ``gitea_user`` — the ``login`` of the authenticated Gitea user.
    * ``gitea_version`` — the Gitea instance version string, or ``None`` if
      unavailable.
    """
    client = get_client()
    user = await client.get_json("/user")
    gitea_version: str | None = None
    try:
        version_payload = await client.get_json("/version")
        raw_version = version_payload.get("version")
        if isinstance(raw_version, str):
            gitea_version = raw_version
    except GiteaAPIError:
        # /version isn't always available (older Gitea, or PAT lacks scope).
        # Don't fail the whole introspection over it.
        gitea_version = None

    login = user.get("login")
    return {
        "gitea_mcp_version": __version__,
        "gitea_url": client.base_url,
        "gitea_user": login if isinstance(login, str) else None,
        "gitea_version": gitea_version,
    }
