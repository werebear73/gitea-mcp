"""MCP server entry point. Initializes the client and runs stdio transport.

The ``FastMCP`` singleton lives in :mod:`gitea_mcp._app`, not here. This module
is intentionally a thin launcher so that ``python -m gitea_mcp.server`` is safe
to load twice (once as ``__main__``, once under its real name when a tool
module indirectly imports it). See :mod:`gitea_mcp._app` for the full rationale.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys

from gitea_mcp import __version__, _app
from gitea_mcp._app import mcp
from gitea_mcp.client import GiteaClient
from gitea_mcp.config import Config

# Import tool modules so their @mcp.tool() registrations execute on module
# load. Ordering doesn't matter; each module registers against the shared
# ``mcp`` instance in ``_app``.
from gitea_mcp.tools import (  # noqa: E402, F401
    files,
    issues,
    pulls,
    releases,
    repos,
    server_info,
)


def main() -> None:
    """Console-script entry point.

    Dispatches based on the first positional argument:

    * No arguments (the default Claude Desktop / Claude Code invocation):
      runs the MCP server over stdio. This path is byte-identical to the
      pre-v0.1.2 behavior and is guarded by ``tests/test_subprocess_launch``.
    * ``--help`` / ``-h``: prints top-level help.
    * ``--version`` / ``-V``: prints ``gitea-mcp <version>``.
    * ``init``: hands off to :func:`gitea_mcp.init.main` for interactive setup.
    * ``doctor``: hands off to :func:`gitea_mcp.doctor.main` for the preflight.
    * Anything else: prints an unknown-subcommand error and exits 2.

    Subcommand-level flag parsing (e.g. ``gitea-mcp init --help``) lives in
    the subcommand modules' own argparse parsers; this dispatcher passes the
    remaining argv through unchanged.
    """
    argv = sys.argv[1:]

    if not argv:
        _run_server()
        return

    first = argv[0]

    if first in ("-h", "--help"):
        _print_help()
        return

    if first in ("-V", "--version"):
        print(f"gitea-mcp {__version__}")
        return

    if first == "init":
        from gitea_mcp.init import main as init_main

        sys.exit(init_main(argv[1:]))

    if first == "doctor":
        from gitea_mcp.doctor import main as doctor_main

        sys.exit(doctor_main(argv[1:]))

    print(f"Error: unknown subcommand '{first}'.", file=sys.stderr)
    print("Run 'gitea-mcp --help' for usage.", file=sys.stderr)
    sys.exit(2)


def _print_help() -> None:
    """Print the top-level help text."""
    print(
        "gitea-mcp — Model Context Protocol server for Gitea (and Forgejo, Codeberg)\n"
        "\n"
        "Usage:\n"
        "  gitea-mcp                  Start the MCP server (stdio transport).\n"
        "                             This is what Claude Desktop / Claude Code\n"
        "                             invoke. Requires GITEA_URL and GITEA_TOKEN\n"
        "                             environment variables.\n"
        "  gitea-mcp init [opts]      Interactive setup: add gitea-mcp to\n"
        "                             claude_desktop_config.json.\n"
        "                             Run 'gitea-mcp init --help' for options.\n"
        "  gitea-mcp doctor [opts]    Preflight check: verify GITEA_URL + token\n"
        "                             and report status.\n"
        "                             Run 'gitea-mcp doctor --help' for options.\n"
        "  gitea-mcp --version, -V    Print version and exit.\n"
        "  gitea-mcp --help, -h       This message.\n"
    )


def _run_server() -> None:
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
        mcp.run()
    finally:
        # Best-effort cleanup. If the event loop is already closed, ignore.
        with contextlib.suppress(RuntimeError):
            asyncio.run(client.close())


if __name__ == "__main__":
    main()
