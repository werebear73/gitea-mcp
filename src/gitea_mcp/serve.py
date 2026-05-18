"""Transport-selectable runner for the gitea-mcp MCP server.

Adds a ``gitea-mcp serve`` subcommand that lets the operator pick between
stdio (the default — what Claude Desktop and other local MCP clients use)
and HTTP transport (for self-hosting one running instance that multiple
clients connect to over the network).

The no-args invocation ``gitea-mcp`` continues to run in stdio mode via the
dispatcher in :mod:`gitea_mcp.server` so existing Claude Desktop / Cowork /
Claude Code integrations and the dual-load regression test are unaffected.

**Auth model for HTTP transport (v0.5.0).** Single-user — the server reads
``GITEA_TOKEN`` from its own environment exactly as the stdio mode does, and
any client that reaches the URL acts as that one user against Gitea. This is
appropriate for self-hosted personal use behind your own access controls
(firewall, reverse-proxy auth, VPN). Multi-tenant bring-your-own-token is a
real auth-integration project deferred to a later release.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import sys

from gitea_mcp import _app
from gitea_mcp._app import mcp
from gitea_mcp.client import GiteaClient
from gitea_mcp.config import Config

# Tool modules must be imported so their @mcp.tool() decorators fire and
# register against the singleton in _app. Importing them here (in addition
# to in server.py) keeps `python -m gitea_mcp.serve` viable as a direct
# invocation path, though the canonical entry is `gitea-mcp serve`.
from gitea_mcp.tools import files, issues, pulls, releases, repos, server_info  # noqa: F401

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000
_DEFAULT_PATH = "/mcp"


def run(args: argparse.Namespace) -> int:
    """Execute the serve flow. Returns a process exit code."""
    config = Config.from_env()
    client = GiteaClient(
        base_url=config.base_url,
        token=config.token,
        timeout=config.timeout,
        max_retries=config.max_retries,
        retry_base_delay=config.retry_base_delay,
    )
    _app._client = client

    try:
        if args.transport == "stdio":
            mcp.run()
        else:
            # FastMCP accepts "http" / "streamable-http" / "sse" — we expose
            # the friendlier "http" alias on the CLI which FastMCP maps to
            # streamable-http internally.
            mcp.run(
                transport="http",
                host=args.host,
                port=args.port,
                path=args.path,
            )
    finally:
        # Best-effort cleanup. If the event loop is already closed, ignore.
        with contextlib.suppress(RuntimeError):
            asyncio.run(client.close())
    return 0


def build_parser() -> argparse.ArgumentParser:
    """argparse parser for the ``serve`` subcommand."""
    parser = argparse.ArgumentParser(
        prog="gitea-mcp serve",
        description=(
            "Start the gitea-mcp MCP server with the chosen transport. "
            "Defaults match the no-args `gitea-mcp` invocation (stdio) so "
            "existing Claude Desktop / Cowork integrations are unaffected; "
            "pass --transport http to self-host one instance for multiple clients."
        ),
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.environ.get("GITEA_MCP_TRANSPORT", "stdio"),
        help=(
            "Transport to run. 'stdio' (default) for local MCP-client launch; "
            "'http' for self-hosted streamable-HTTP. "
            "Env: GITEA_MCP_TRANSPORT."
        ),
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("GITEA_MCP_HOST", _DEFAULT_HOST),
        help=(
            f"Bind address for HTTP transport (default: {_DEFAULT_HOST}). "
            "Use 0.0.0.0 to listen on all interfaces (Docker, public hosting). "
            "Env: GITEA_MCP_HOST. Ignored for stdio."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("GITEA_MCP_PORT", _DEFAULT_PORT)),
        help=(
            f"TCP port for HTTP transport (default: {_DEFAULT_PORT}). "
            "Env: GITEA_MCP_PORT. Ignored for stdio."
        ),
    )
    parser.add_argument(
        "--path",
        default=os.environ.get("GITEA_MCP_PATH", _DEFAULT_PATH),
        help=(
            f"URL path the MCP endpoint serves at (default: {_DEFAULT_PATH}). "
            "Env: GITEA_MCP_PATH. Ignored for stdio."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``gitea-mcp serve``."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
