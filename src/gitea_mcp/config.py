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
    max_retries: int = 3
    retry_base_delay: float = 0.5

    @classmethod
    def from_env(cls) -> Config:
        """Load configuration from environment variables.

        Required:
            GITEA_URL: Base URL of the Gitea instance (e.g. https://gitea.example.com)
            GITEA_TOKEN: Personal Access Token

        Optional:
            GITEA_TIMEOUT: HTTP request timeout in seconds (default: 30)
            GITEA_MAX_RETRIES: Max retries for transient failures on idempotent
                methods (GET/PUT/DELETE). Default 3. Set to 0 to disable retries.
            GITEA_RETRY_BASE_DELAY: Base delay (seconds) for exponential backoff
                between retries. Default 0.5. Effective delay is capped at 4s.

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
        max_retries = int(os.environ.get("GITEA_MAX_RETRIES", "3"))
        retry_base_delay = float(os.environ.get("GITEA_RETRY_BASE_DELAY", "0.5"))

        return cls(
            base_url=base_url.rstrip("/"),
            token=token,
            timeout=timeout,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
        )
