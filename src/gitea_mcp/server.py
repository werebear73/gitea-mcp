"""MCP server entry point. Registers tools and runs stdio transport."""

from __future__ import annotations

import asyncio

from fastmcp import FastMCP

from gitea_mcp.client import GiteaClient
from gitea_mcp.config import Config

# Module-level FastMCP instance so tool modules can register against it.
mcp: FastMCP = FastMCP("gitea-mcp")

# Singleton client populated at startup. Tool modules access via get_client().
_client: GiteaClient | None = None


def get_client() -> GiteaClient:
    """Return the singleton :class:`GiteaClient`.

    Must be called after :func:`main` has initialized the client.
    """
    if _client is None:
        raise RuntimeError(
            "GiteaClient not initialized. The gitea-mcp server must be started "
            "via the gitea-mcp entry point so the client is available before "
            "any tools are called."
        )
    return _client


# Import tool modules so their @mcp.tool() registrations execute on module load.
# Ordering doesn't matter; each module registers its own tools against `mcp`.
from gitea_mcp.tools import issues, releases, repos  # noqa: E402, F401


def main() -> None:
    """Console-script entry point.

    1. Loads configuration from environment variables.
    2. Initializes the singleton GiteaClient.
    3. Runs the MCP server over stdio (blocks until the client disconnects).
    4. Closes the GiteaClient on shutdown.
    """
    global _client

    config = Config.from_env()
    _client = GiteaClient(
        base_url=config.base_url,
        token=config.token,
        timeout=config.timeout,
    )
    try:
        mcp.run()
    finally:
        # Best-effort cleanup. If the event loop is already closed, ignore.
        try:
            asyncio.run(_client.close())
        except RuntimeError:
            pass


if __name__ == "__main__":
    main()
