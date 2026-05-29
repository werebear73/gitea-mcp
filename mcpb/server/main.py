"""Entry point for the gitea-mcp MCPB bundle.

Thin launcher invoked by Claude Desktop's MCPB UV-runtime host. Delegates to
``gitea_mcp.server.main`` — the same function the ``gitea-mcp`` console script
and ``python -m gitea_mcp.server`` resolve to — so the bundle behaves
identically to a direct ``uvx gitea-mcp`` invocation.
"""

from gitea_mcp.server import main

if __name__ == "__main__":
    main()
