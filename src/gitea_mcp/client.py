"""Async HTTP client wrapper for the Gitea REST API."""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

# HTTP methods that are safe to retry on transient failures.
# POST and PATCH are excluded because retrying them could create duplicate
# issues / comments / releases — better to surface the failure to the caller.
_IDEMPOTENT_METHODS = frozenset({"GET", "PUT", "DELETE"})

# HTTP status codes that indicate transient server-side issues worth retrying
# (for idempotent methods only).
_RETRYABLE_STATUS_CODES = frozenset({502, 503, 504})

# Maximum backoff between retries, in seconds.
_MAX_BACKOFF_DELAY = 4.0


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

    Two layers of verb methods:

    * **Untyped verbs** (``get``, ``post``, ``patch``, ``put``, ``delete``)
      return the decoded JSON as :class:`typing.Any`. Use when the caller
      doesn't care about the shape, or when the shape varies.
    * **Typed verbs** (``get_json``, ``get_list``, ``post_json``,
      ``patch_json``, ``put_json``, ``put_list``) wrap the untyped verbs
      with a shape assertion and return ``dict[str, Any]`` or
      ``list[dict[str, Any]]``. Use these in tool implementations so the
      return type flows cleanly to the tool's annotated return without
      needing a typed-intermediate variable (the pattern PR #4 had to
      apply to every tool to satisfy strict mypy).

    **Retry policy** (applied by all verb methods):

    * Idempotent methods (``GET``, ``PUT``, ``DELETE``) are retried on
      transient network errors (``httpx.ConnectError`` /
      ``ReadTimeout`` / ``WriteTimeout``) and on 502 / 503 / 504 responses.
    * ``POST`` and ``PATCH`` are **not** retried automatically — a retry
      could create duplicate issues, comments, or releases.
    * ``429 Too Many Requests`` is retried for **any** method, honoring the
      ``Retry-After`` header if present; otherwise using the same
      exponential backoff schedule.
    * Backoff is exponential with jitter, capped at ``_MAX_BACKOFF_DELAY``
      seconds. Max attempts and base delay are constructor-configurable.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_base_delay: float = 0.5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
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

    @property
    def base_url(self) -> str:
        """The Gitea instance base URL this client is configured against.

        Read-only — set at construction time. Useful for tools that report
        server identity (e.g. ``get_server_info``).
        """
        return self._base_url

    # ---- Untyped verbs (return Any) ----------------------------------------

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        response = await self._request_with_retry("GET", path, params=params)
        return self._handle(response, method="GET", path=path)

    async def post(self, path: str, json: Any | None = None) -> Any:
        response = await self._request_with_retry("POST", path, json=json)
        return self._handle(response, method="POST", path=path)

    async def put(self, path: str, json: Any | None = None) -> Any:
        response = await self._request_with_retry("PUT", path, json=json)
        return self._handle(response, method="PUT", path=path)

    async def patch(self, path: str, json: Any | None = None) -> Any:
        response = await self._request_with_retry("PATCH", path, json=json)
        return self._handle(response, method="PATCH", path=path)

    async def delete(self, path: str) -> Any:
        response = await self._request_with_retry("DELETE", path)
        return self._handle(response, method="DELETE", path=path)

    # ---- Typed verbs (shape-asserted) --------------------------------------

    async def get_json(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """GET and decode as a JSON object. Raises :class:`GiteaError` on
        non-object response."""
        return self._as_object(await self.get(path, params), method="GET", path=path)

    async def get_list(
        self, path: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """GET and decode as a JSON array of objects. Raises
        :class:`GiteaError` on non-array response or non-object items."""
        return self._as_list(await self.get(path, params), method="GET", path=path)

    async def post_json(self, path: str, json: Any | None = None) -> dict[str, Any]:
        """POST and decode the response as a JSON object."""
        return self._as_object(await self.post(path, json=json), method="POST", path=path)

    async def patch_json(self, path: str, json: Any | None = None) -> dict[str, Any]:
        """PATCH and decode the response as a JSON object."""
        return self._as_object(await self.patch(path, json=json), method="PATCH", path=path)

    async def put_json(self, path: str, json: Any | None = None) -> dict[str, Any]:
        """PUT and decode the response as a JSON object."""
        return self._as_object(await self.put(path, json=json), method="PUT", path=path)

    async def put_list(
        self, path: str, json: Any | None = None
    ) -> list[dict[str, Any]]:
        """PUT and decode the response as a JSON array of objects.

        Specific to Gitea's ``PUT /repos/{owner}/{repo}/issues/{n}/labels``,
        which returns the new label list (an array) rather than the issue.
        """
        return self._as_list(await self.put(path, json=json), method="PUT", path=path)

    # ---- Retry & helpers ---------------------------------------------------

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> httpx.Response:
        """Issue a request, retrying transient failures per the class policy.

        Returns the final :class:`httpx.Response` (which may be a non-success
        response — non-retryable errors and exhausted retries both return the
        response so the caller's ``_handle`` can produce a proper
        :class:`GiteaAPIError`).
        """
        idempotent = method in _IDEMPOTENT_METHODS
        url = self._api_path(path)
        last_network_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(
                    method, url, params=params, json=json
                )
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_network_exc = exc
                if not idempotent or attempt >= self._max_retries:
                    raise
                await asyncio.sleep(self._backoff_delay(attempt))
                continue

            # 429 honored for ANY method — the server is asking us to slow down.
            if response.status_code == 429 and attempt < self._max_retries:
                retry_after = self._parse_retry_after(response)
                delay = retry_after if retry_after is not None else self._backoff_delay(attempt)
                await asyncio.sleep(delay)
                continue

            # Transient 5xx: retry only for idempotent methods.
            if (
                response.status_code in _RETRYABLE_STATUS_CODES
                and idempotent
                and attempt < self._max_retries
            ):
                await asyncio.sleep(self._backoff_delay(attempt))
                continue

            return response

        # Loop body either returns a response or re-raises. Reaching here means
        # the last iteration was a network exception that was already re-raised.
        assert last_network_exc is not None
        raise last_network_exc

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter, capped at :data:`_MAX_BACKOFF_DELAY`."""
        base: float = min(_MAX_BACKOFF_DELAY, self._retry_base_delay * (2**attempt))
        jitter: float = random.uniform(0, base * 0.1)
        result: float = base + jitter
        return result

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float | None:
        """Parse the ``Retry-After`` header value (seconds-int form only).

        Returns ``None`` if absent or in HTTP-date form (in which case the
        caller falls back to its normal backoff schedule).
        """
        raw = response.headers.get("retry-after")
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

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

    @staticmethod
    def _as_object(raw: Any, *, method: str, path: str) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise GiteaError(
                f"[{method} {path}] expected a JSON object response, got "
                f"{type(raw).__name__}"
            )
        result: dict[str, Any] = raw
        return result

    @staticmethod
    def _as_list(raw: Any, *, method: str, path: str) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            raise GiteaError(
                f"[{method} {path}] expected a JSON array response, got "
                f"{type(raw).__name__}"
            )
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                raise GiteaError(
                    f"[{method} {path}] expected a JSON array of objects, "
                    f"item {i} is a {type(item).__name__}"
                )
        result: list[dict[str, Any]] = raw
        return result
