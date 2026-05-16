"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Runtime configuration for gitea-mcp.

    Loaded once at startup from environment variables. Immutable thereafter.
    """

    base_url: str
    token: str
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> Config:
        """Load configuration from environment variables.

        Required:
            GITEA_URL: Base URL of the Gitea instance (e.g. https://gitea.example.com)
            GITEA_TOKEN: Personal Access Token

        Optional:
            GITEA_TIMEOUT: HTTP request timeout in seconds (default: 30)

        Raises:
            RuntimeError: if required variables are missing.
        """
        base_url = os.environ.get("GITEA_URL", "").strip()
        if not base_url:
            raise RuntimeError(
                "GITEA_URL environment variable is required. "
                "Set it to the base URL of your Gitea instance."
            )

        token = os.environ.get("GITEA_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "GITEA_TOKEN environment variable is required. "
                "Generate a Personal Access Token in Gitea: Settings -> Applications."
            )

        timeout = float(os.environ.get("GITEA_TIMEOUT", "30"))

        return cls(
            base_url=base_url.rstrip("/"),
            token=token,
            timeout=timeout,
        )
