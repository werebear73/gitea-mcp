"""Unit tests for the GiteaClient retry policy.

Covers the v0.2.0 retry-with-backoff behavior added to ``_request_with_retry``:
idempotent methods retry on transient 5xx and network errors; POST/PATCH do
not retry; 429 with Retry-After is honored for any method.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from pytest_httpx import HTTPXMock

from gitea_mcp.client import GiteaAPIError, GiteaClient


@pytest_asyncio.fixture
async def fast_client() -> AsyncIterator[GiteaClient]:
    """Client with retries enabled but zero backoff for fast tests."""
    c = GiteaClient(
        base_url="https://gitea.example.com",
        token="test-token",
        timeout=5.0,
        max_retries=3,
        retry_base_delay=0.0,  # no real sleep
    )
    try:
        yield c
    finally:
        await c.close()


# ---- Idempotent retry on transient 5xx ------------------------------------


@pytest.mark.asyncio
async def test_get_retries_on_503_then_succeeds(
    fast_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/o/r/issues",
        status_code=503,
        text="service unavailable",
    )
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/o/r/issues",
        status_code=503,
        text="service unavailable",
    )
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/o/r/issues",
        json=[{"number": 1}],
    )
    result = await fast_client.get_list("/repos/o/r/issues")
    assert result == [{"number": 1}]


@pytest.mark.asyncio
async def test_get_gives_up_after_max_retries(
    fast_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    # max_retries=3 means 4 total attempts. Mock 4 failures.
    for _ in range(4):
        httpx_mock.add_response(
            method="GET",
            url="https://gitea.example.com/api/v1/repos/o/r/issues",
            status_code=503,
            text="service unavailable",
        )
    with pytest.raises(GiteaAPIError) as exc_info:
        await fast_client.get_list("/repos/o/r/issues")
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_put_retries_like_get(
    fast_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """PUT is idempotent and should follow the same retry policy as GET."""
    httpx_mock.add_response(
        method="PUT",
        url="https://gitea.example.com/api/v1/repos/o/r/issues/1/labels",
        status_code=502,
        text="bad gateway",
    )
    httpx_mock.add_response(
        method="PUT",
        url="https://gitea.example.com/api/v1/repos/o/r/issues/1/labels",
        json=[{"id": 1, "name": "bug"}],
    )
    result = await fast_client.put_list(
        "/repos/o/r/issues/1/labels", json={"labels": [1]}
    )
    assert result == [{"id": 1, "name": "bug"}]


# ---- POST and PATCH do NOT retry on 5xx -----------------------------------


@pytest.mark.asyncio
async def test_post_does_not_retry_on_503(
    fast_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """Retrying POST could create duplicate issues — must fail fast."""
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/o/r/issues",
        status_code=503,
        text="service unavailable",
    )
    with pytest.raises(GiteaAPIError) as exc_info:
        await fast_client.post_json("/repos/o/r/issues", json={"title": "x"})
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_patch_does_not_retry_on_502(
    fast_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="PATCH",
        url="https://gitea.example.com/api/v1/repos/o/r/issues/1",
        status_code=502,
        text="bad gateway",
    )
    with pytest.raises(GiteaAPIError) as exc_info:
        await fast_client.patch_json("/repos/o/r/issues/1", json={"title": "x"})
    assert exc_info.value.status_code == 502


# ---- 429 with Retry-After honored for any method --------------------------


@pytest.mark.asyncio
async def test_post_retries_on_429_with_retry_after(
    fast_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """Even POST retries on 429 because the server explicitly asked us to."""
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/o/r/issues",
        status_code=429,
        headers={"retry-after": "0"},
        text="rate limited",
    )
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/o/r/issues",
        json={"number": 1, "title": "x"},
    )
    result = await fast_client.post_json("/repos/o/r/issues", json={"title": "x"})
    assert result == {"number": 1, "title": "x"}


# ---- Network errors --------------------------------------------------------


@pytest.mark.asyncio
async def test_get_retries_on_connect_error(
    fast_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_exception(httpx.ConnectError("connection refused"))
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/o/r/issues",
        json=[{"number": 1}],
    )
    result = await fast_client.get_list("/repos/o/r/issues")
    assert result == [{"number": 1}]


@pytest.mark.asyncio
async def test_post_does_not_retry_on_connect_error(
    fast_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """A connect error on POST might mean the request never arrived OR it
    arrived and the response was lost — we can't tell, so we don't retry."""
    httpx_mock.add_exception(httpx.ConnectError("connection refused"))
    with pytest.raises(httpx.ConnectError):
        await fast_client.post_json("/repos/o/r/issues", json={"title": "x"})


# ---- Configuration ---------------------------------------------------------


@pytest.mark.asyncio
async def test_max_retries_zero_disables_retry(httpx_mock: HTTPXMock) -> None:
    c = GiteaClient(
        base_url="https://gitea.example.com",
        token="t",
        timeout=5.0,
        max_retries=0,
        retry_base_delay=0.0,
    )
    try:
        httpx_mock.add_response(
            method="GET",
            url="https://gitea.example.com/api/v1/repos/o/r/issues",
            status_code=503,
            text="x",
        )
        with pytest.raises(GiteaAPIError):
            await c.get_list("/repos/o/r/issues")
    finally:
        await c.close()


# ---- Typed-verb defensive shape checks (added in v0.2.0) ------------------


@pytest.mark.asyncio
async def test_get_json_rejects_array_response(
    fast_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """get_json expects an object; an array response should raise GiteaError."""
    from gitea_mcp.client import GiteaError

    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/o/r/issues/1",
        json=[{"number": 1}],  # wrong shape — list instead of object
    )
    with pytest.raises(GiteaError, match="expected a JSON object"):
        await fast_client.get_json("/repos/o/r/issues/1")


@pytest.mark.asyncio
async def test_get_list_rejects_object_response(
    fast_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    from gitea_mcp.client import GiteaError

    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/o/r/issues",
        json={"number": 1},  # wrong shape — object instead of list
    )
    with pytest.raises(GiteaError, match="expected a JSON array"):
        await fast_client.get_list("/repos/o/r/issues")
