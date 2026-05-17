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

from gitea_mcp import _app
from gitea_mcp._app import mcp
from gitea_mcp.client import GiteaClient
from gitea_mcp.config import Config

# Import tool modules so their @mcp.tool() registrations execute on module
# load. Ordering doesn't matter; each module registers against the shared
# ``mcp`` instance in ``_app``.
from gitea_mcp.tools import issues, releases, repos  # noqa: E402, F401


def main() -> None:
    """Console-script entry point.

    With no arguments (the default Claude Desktop invocation): runs the MCP
    server over stdio. With ``init`` as the first argument: hands off to
    :func:`gitea_mcp.init.main` for the interactive setup flow.

    Server path:
        1. Loads configuration from environment variables.
        2. Initializes the singleton GiteaClient on the ``_app`` module.
        3. Runs the MCP server over stdio (blocks until the client disconnects).
        4. Closes the GiteaClient on shutdown.
    """
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        from gitea_mcp.init import main as init_main

        sys.exit(init_main(sys.argv[2:]))

    _run_server()


def _run_server() -> None:
    config = Config.from_env()
    client = GiteaClient(
        base_url=config.base_url,
        token=config.token,
        timeout=config.timeout,
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
