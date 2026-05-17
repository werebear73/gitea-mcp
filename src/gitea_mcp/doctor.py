"""Preflight check for gitea-mcp: verify GITEA_URL + PAT, report status.

Run via ``gitea-mcp doctor``. Reads configuration from the same environment
variables the server uses (``GITEA_URL``, ``GITEA_TOKEN``, ``GITEA_TIMEOUT``)
and performs a ``GET /api/v1/user`` against the Gitea instance to confirm the
URL is reachable, the token works, and the response shape looks like a Gitea
user object. Then loads all tool modules to confirm the MCP surface is intact.

Returns exit ``0`` on success, ``1`` on connection or load failure, ``2`` on
missing configuration. Useful before pointing Claude Desktop at the server, or
when an MCP client reports an empty tools list and you need to know whether
the problem is the connection or the integration.
"""

from __future__ import annotations

import argparse
import os
import sys

from gitea_mcp import __version__
from gitea_mcp.init import check_connection


def run(args: argparse.Namespace) -> int:
    """Execute the doctor flow. Returns a process exit code."""
    url = (args.url or os.environ.get("GITEA_URL", "")).strip().rstrip("/")
    if not url:
        print(
            "Error: GITEA_URL not set. Provide --url or set the GITEA_URL env var.",
            file=sys.stderr,
        )
        return 2

    token = (args.token or os.environ.get("GITEA_TOKEN", "")).strip()
    if not token:
        print(
            "Error: GITEA_TOKEN not set. Provide --token or set the GITEA_TOKEN env var.",
            file=sys.stderr,
        )
        return 2

    timeout = float(os.environ.get("GITEA_TIMEOUT", "30"))

    print(f"gitea-mcp {__version__}")
    print(f"  Gitea URL : {url}")
    print(f"  Timeout   : {timeout}s")
    print()

    print(f"[1/2] Verifying connection to {url} ...")
    try:
        username = check_connection(url, token, timeout=timeout)
    except RuntimeError as exc:
        print(f"      FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"      OK — authenticated as '{username}'.")

    print("[2/2] Loading MCP tool modules ...")
    try:
        # Importing each tool module triggers its @mcp.tool() registrations
        # against the FastMCP singleton in gitea_mcp._app. If any module fails
        # to import, the server would also fail to start — catch it here so
        # the user sees the real exception rather than a silent empty toolset.
        from gitea_mcp.tools import issues, releases, repos  # noqa: F401
    except Exception as exc:
        print(f"      FAILED: {exc}", file=sys.stderr)
        return 1
    print("      OK — all tool modules loaded.")

    print()
    print("All checks passed. gitea-mcp is ready to wire into your MCP client.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """argparse parser for the ``doctor`` subcommand."""
    parser = argparse.ArgumentParser(
        prog="gitea-mcp doctor",
        description=(
            "Preflight check: verify the Gitea URL + Personal Access Token and "
            "report status. Reads GITEA_URL and GITEA_TOKEN from the environment "
            "by default."
        ),
    )
    parser.add_argument(
        "--url",
        help="Override the Gitea base URL (default: GITEA_URL env var).",
    )
    parser.add_argument(
        "--token",
        help="Override the Personal Access Token (default: GITEA_TOKEN env var).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``gitea-mcp doctor``."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
