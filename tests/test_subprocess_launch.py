"""Regression test: ``python -m gitea_mcp.server`` must register all tools.

This catches the dual-module-load bug we hit in pre-release: when ``server.py``
was launched via ``python -m``, Python loaded it as ``__main__``. Any module
that imported ``gitea_mcp.server`` then triggered a *second* load of the same
file under its real name, producing two ``FastMCP`` instances. The
``@mcp.tool()`` decorators registered against the second instance while
``main()`` ran ``mcp.run()`` on the first — empty tools list, zero errors.

The fix moved the ``FastMCP`` singleton into :mod:`gitea_mcp._app`. This test
spawns the real entry point as a subprocess, speaks the MCP JSON-RPC
handshake over stdio, and asserts the server hands back all 10 MVP tools.
If this fails, something has re-introduced the dual-load problem.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

EXPECTED_TOOLS = sorted(
    [
        "add_comment",
        "create_issue",
        "create_release",
        "get_issue",
        "list_issues",
        "list_labels",
        "list_milestones",
        "list_releases",
        "list_repos",
        "update_issue",
    ]
)


def test_python_m_launch_registers_all_tools() -> None:
    """Launching via ``python -m gitea_mcp.server`` must expose all 10 tools."""
    env = {
        **os.environ,
        # The subprocess only needs these to satisfy Config.from_env(); no
        # network calls happen because we never invoke a tool, just list them.
        "GITEA_URL": "http://localhost:0",
        "GITEA_TOKEN": "test-token-not-used",
    }

    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "gitea-mcp-regression-test", "version": "0.0.1"},
        },
    }
    initialized_notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }
    list_tools = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }

    payload = (
        "\n".join(json.dumps(m) for m in [init, initialized_notification, list_tools])
        + "\n"
    )

    proc = subprocess.Popen(
        [sys.executable, "-m", "gitea_mcp.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )

    try:
        stdout, stderr = proc.communicate(input=payload, timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise AssertionError(
            f"gitea-mcp subprocess did not respond within 20s.\n"
            f"--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
        ) from None

    # Parse line-delimited JSON-RPC responses from stdout, keyed by id.
    responses: dict[Any, dict[str, Any]] = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            # FastMCP only writes JSON-RPC to stdout, but be defensive.
            continue
        if "id" in msg:
            responses[msg["id"]] = msg

    assert 2 in responses, (
        f"no tools/list response received.\n"
        f"--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
    )

    tools = responses[2].get("result", {}).get("tools", [])
    tool_names = sorted(t["name"] for t in tools)

    assert tool_names == EXPECTED_TOOLS, (
        f"expected all {len(EXPECTED_TOOLS)} tools to be registered when "
        f"launched via `python -m gitea_mcp.server`, got {len(tool_names)}: "
        f"{tool_names}. An empty list usually means the dual-module-load bug "
        f"has been re-introduced — verify the FastMCP singleton still lives "
        f"in gitea_mcp._app and that tool modules import from there."
    )
