"""gitea-mcp — Model Context Protocol server for Gitea (and Forgejo, Codeberg)."""

try:
    from gitea_mcp._version import __version__
except ImportError:
    # Package not installed in editable mode or version file not yet generated
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
