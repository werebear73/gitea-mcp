"""Unit tests for the server-introspection tools (server_info.py)."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from gitea_mcp import __version__
from gitea_mcp.client import GiteaAPIError, GiteaClient
from gitea_mcp.tools.server_info import get_server_info, get_server_version

# ---- get_server_version ----------------------------------------------------


@pytest.mark.asyncio
async def test_get_server_version_returns_package_version() -> None:
    """No network call — just reports the gitea_mcp.__version__ string."""
    result = await get_server_version.fn()
    assert result == {"gitea_mcp_version": __version__}


# ---- get_server_info -------------------------------------------------------


@pytest.mark.asyncio
async def test_get_server_info_happy_path(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """Mocks both /user and /version; asserts all four fields populated."""
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/user",
        json={"login": "werebear73", "id": 1, "full_name": "Sam"},
    )
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/version",
        json={"version": "1.21.0"},
    )
    result = await get_server_info.fn()
    assert result == {
        "gitea_mcp_version": __version__,
        "gitea_url": "https://gitea.example.com",
        "gitea_user": "werebear73",
        "gitea_version": "1.21.0",
    }


@pytest.mark.asyncio
async def test_get_server_info_falls_back_when_version_unavailable(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """If /version 404s (older Gitea, or PAT lacks scope), gitea_version → None
    rather than failing the whole introspection."""
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/user",
        json={"login": "werebear73", "id": 1},
    )
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/version",
        status_code=404,
        json={"message": "not found"},
    )
    result = await get_server_info.fn()
    assert result["gitea_user"] == "werebear73"
    assert result["gitea_version"] is None


@pytest.mark.asyncio
async def test_get_server_info_propagates_auth_failure(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """/user returning 401 is a real problem — propagate the error rather than
    silently returning a half-populated dict."""
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/user",
        status_code=401,
        json={"message": "bad credentials"},
    )
    with pytest.raises(GiteaAPIError) as exc_info:
        await get_server_info.fn()
    assert exc_info.value.status_code == 401
