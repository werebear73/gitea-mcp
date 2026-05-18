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

Implementation note: the test originally used ``subprocess.Popen.communicate()``
which closes stdin after writing the full payload. FastMCP 2.x's stdio reader
sees EOF and shuts down before processing the queued ``tools/list`` call —
the initialize response comes back, then nothing. The current implementation
uses a reader thread + queue so stdin stays open until the ``tools/list``
response (id=2) is in hand, after which we close stdin and let the server
exit cleanly. This pattern is robust on both Windows and POSIX.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from typing import IO, Any

EXPECTED_TOOLS = sorted(
    [
        "add_comment",
        "add_comment_on_pr",
        "create_issue",
        "create_release",
        "get_issue",
        "get_pull_request",
        "list_branches",
        "list_issues",
        "list_labels",
        "list_milestones",
        "list_pull_requests",
        "list_releases",
        "list_repos",
        "update_issue",
    ]
)

# How long the test will wait for the server to start up and answer all the
# JSON-RPC messages we send. Generous on purpose — slow CI runners exist.
_RESPONSE_TIMEOUT_SECONDS = 15.0

# How long the test will wait for the server to shut down cleanly after we
# close stdin. The graceful path is fast; killing it is the fallback.
_SHUTDOWN_TIMEOUT_SECONDS = 5.0


def _reader_thread(stream: IO[str], q: queue.Queue[str | None]) -> None:
    """Push every line from ``stream`` onto ``q``; push ``None`` on EOF.

    Runs in a daemon thread so the test never deadlocks waiting for the
    subprocess to close its stdout if we already have what we need.
    """
    try:
        for line in stream:
            q.put(line)
    finally:
        q.put(None)


def test_python_m_launch_registers_all_tools() -> None:
    """Launching via ``python -m gitea_mcp.server`` must expose all 10 tools."""
    env = {
        **os.environ,
        # The subprocess only needs these to satisfy Config.from_env(); no
        # network calls happen because we never invoke a tool, just list them.
        "GITEA_URL": "http://localhost:0",
        "GITEA_TOKEN": "test-token-not-used",
    }

    init_req = {
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
    list_tools_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }

    proc = subprocess.Popen(
        [sys.executable, "-m", "gitea_mcp.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
        bufsize=1,  # line-buffered so we see each JSON-RPC frame as it's written
    )
    # Type narrowing — Popen pipes are Optional[IO[str]] at the type level.
    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None

    stdout_queue: queue.Queue[str | None] = queue.Queue()
    stderr_lines: list[str] = []

    stdout_reader = threading.Thread(
        target=_reader_thread, args=(proc.stdout, stdout_queue), daemon=True
    )
    stderr_reader = threading.Thread(
        target=lambda: stderr_lines.extend(proc.stderr or []), daemon=True
    )
    stdout_reader.start()
    stderr_reader.start()

    responses: dict[Any, dict[str, Any]] = {}

    try:
        # Send all three JSON-RPC messages and FLUSH — but do NOT close stdin
        # yet. Closing stdin races FastMCP's stdio reader; we want the server
        # to fully process tools/list before it sees EOF.
        for msg in (init_req, initialized_notification, list_tools_req):
            proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

        # Read responses until the tools/list reply (id=2) arrives, or until
        # the response timeout fires. ``queue.get(timeout=...)`` raises
        # ``queue.Empty`` on timeout, which we loop on so we can re-check the
        # overall deadline.
        deadline = time.monotonic() + _RESPONSE_TIMEOUT_SECONDS
        while 2 not in responses:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                line = stdout_queue.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue
            if line is None:
                # Server closed stdout — give up; we won't get any more lines.
                break
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

        # Got the response (or timed out). NOW close stdin so the server can
        # shut down cleanly, and wait for it to exit.
        proc.stdin.close()
        try:
            proc.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
    finally:
        # Belt-and-braces: if we hit an unexpected exception above, make sure
        # we don't leak a subprocess.
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)

    stderr_blob = "".join(stderr_lines)

    assert 2 in responses, (
        f"no tools/list response received within {_RESPONSE_TIMEOUT_SECONDS}s.\n"
        f"--- responses received ---\n{list(responses.keys())}\n"
        f"--- stderr ---\n{stderr_blob}"
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
