"""Async HTTP client wrapper for the Gitea REST API."""

from __future__ import annotations

from typing import Any

import httpx


class GiteaError(Exception):
    """Base exception for Gitea client errors."""


class GiteaAPIError(GiteaError):
    """Raised when the Gitea API returns a non-success response."""

    def __init__(self, status_code: int, message: str, method: str, url: str) -> None:
        self.status_code = status_code
        self.method = method
        self.url = url
        super().__init__(f"[{method} {url}] {status_code}: {message}")


class GiteaClient:
    """Async HTTP client for the Gitea REST API.

    Uses Personal Access Token authentication via the
    ``Authorization: token <PAT>`` header (Gitea's convention; NOT Bearer).
    One shared :class:`httpx.AsyncClient` per server lifetime.

    All paths passed to the verb methods are appended under ``/api/v1``; pass
    ``/repos/{owner}/{repo}`` rather than the full URL.
    """

    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client. Safe to call multiple times."""
        await self._client.aclose()

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        response = await self._client.get(self._api_path(path), params=params)
        return self._handle(response, method="GET", path=path)

    async def post(self, path: str, json: Any | None = None) -> Any:
        response = await self._client.post(self._api_path(path), json=json)
        return self._handle(response, method="POST", path=path)

    async def put(self, path: str, json: Any | None = None) -> Any:
        response = await self._client.put(self._api_path(path), json=json)
        return self._handle(response, method="PUT", path=path)

    async def patch(self, path: str, json: Any | None = None) -> Any:
        response = await self._client.patch(self._api_path(path), json=json)
        return self._handle(response, method="PATCH", path=path)

    async def delete(self, path: str) -> Any:
        response = await self._client.delete(self._api_path(path))
        return self._handle(response, method="DELETE", path=path)

    @staticmethod
    def _api_path(path: str) -> str:
        """Prefix a relative path with /api/v1, leaving absolute API paths intact."""
        if path.startswith("/api/v1"):
            return path
        if path.startswith("/"):
            return f"/api/v1{path}"
        return f"/api/v1/{path}"

    def _handle(self, response: httpx.Response, method: str, path: str) -> Any:
        if response.is_success:
            if response.status_code == 204 or not response.content:
                return None
            return response.json()
        message = response.text.strip() or response.reason_phrase
        raise GiteaAPIError(
            status_code=response.status_code,
            message=message,
            method=method,
            url=str(response.request.url),
        )
