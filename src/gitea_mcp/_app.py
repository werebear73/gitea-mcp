"""Internal seam holding the FastMCP singleton and client slot.

This module exists so the ``FastMCP`` instance and the ``GiteaClient`` singleton
live in a module that is imported exactly once, regardless of how the package
entry point is launched.

Why this matters: when a user runs ``python -m gitea_mcp.server``, Python loads
``server.py`` as ``__main__``. Any module that later imports
``gitea_mcp.server`` (e.g. one of the tool modules) causes Python to load
``server.py`` a *second* time, registered under its real name. If the
``FastMCP`` instance lived in ``server.py`` the tool decorators would register
against the second instance while the entry point's ``mcp.run()`` ran the
first — empty tools list, no errors. Keeping the singleton here means both
loads see the same ``mcp`` object.

Tool modules should always import from here, not from ``gitea_mcp.server``.
"""

from __future__ import annotations

from fastmcp import FastMCP

from gitea_mcp.client import GiteaClient

# Module-level FastMCP instance. Tool modules register against this via
# ``@mcp.tool()`` at import time.
mcp: FastMCP = FastMCP("gitea-mcp")

# Singleton client populated at startup by ``gitea_mcp.server.main()``.
# Tool modules access it via ``get_client()``.
_client: GiteaClient | None = None


def get_client() -> GiteaClient:
    """Return the singleton :class:`GiteaClient`.

    Must be called after :func:`gitea_mcp.server.main` has initialized the
    client. Tool functions call this at request time, not at import time.
    """
    if _client is None:
        raise RuntimeError(
            "GiteaClient not initialized. The gitea-mcp server must be started "
            "via the gitea-mcp entry point so the client is available before "
            "any tools are called."
        )
    return _client
