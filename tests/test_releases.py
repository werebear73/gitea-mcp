"""Unit tests for the release tools."""

from __future__ import annotations

import json as _json

import pytest
from pytest_httpx import HTTPXMock

from gitea_mcp.client import GiteaClient
from gitea_mcp.tools.releases import create_release, list_releases

# ---- list_releases ---------------------------------------------------------


@pytest.mark.asyncio
async def test_list_releases_defaults(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/releases?page=1&limit=30",
        json=[
            {"id": 1, "tag_name": "v1.0.0", "draft": False, "prerelease": False},
            {"id": 2, "tag_name": "v0.9.0", "draft": False, "prerelease": False},
        ],
    )
    result = await list_releases(owner="acme", repo="widget")
    assert [r["tag_name"] for r in result] == ["v1.0.0", "v0.9.0"]


@pytest.mark.asyncio
async def test_list_releases_pagination_params(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/releases?page=2&limit=10",
        json=[],
    )
    await list_releases(owner="acme", repo="widget", page=2, limit=10)


# ---- create_release --------------------------------------------------------


@pytest.mark.asyncio
async def test_create_release_minimal(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    expected = {
        "id": 42,
        "tag_name": "v1.0.0",
        "name": "First Stable",
        "draft": False,
        "prerelease": False,
    }
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/releases",
        json=expected,
    )
    result = await create_release(
        owner="acme", repo="widget", tag_name="v1.0.0", name="First Stable"
    )
    assert result == expected
    request = httpx_mock.get_request()
    assert request is not None
    body = _json.loads(request.content)
    # target_commitish should be omitted when None (lets Gitea use default branch).
    assert body == {
        "tag_name": "v1.0.0",
        "name": "First Stable",
        "body": "",
        "draft": False,
        "prerelease": False,
    }


@pytest.mark.asyncio
async def test_create_release_all_params(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/releases",
        json={"id": 99, "tag_name": "v2.0.0-rc.1"},
    )
    await create_release(
        owner="acme",
        repo="widget",
        tag_name="v2.0.0-rc.1",
        name="2.0.0 Release Candidate 1",
        body="## What's new\n- everything",
        target_commitish="develop",
        draft=False,
        prerelease=True,
    )
    request = httpx_mock.get_request()
    assert request is not None
    body = _json.loads(request.content)
    assert body == {
        "tag_name": "v2.0.0-rc.1",
        "name": "2.0.0 Release Candidate 1",
        "body": "## What's new\n- everything",
        "target_commitish": "develop",
        "draft": False,
        "prerelease": True,
    }


@pytest.mark.asyncio
async def test_create_release_as_draft(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/releases",
        json={"id": 100, "tag_name": "v1.0.0", "draft": True},
    )
    await create_release(
        owner="acme",
        repo="widget",
        tag_name="v1.0.0",
        name="Draft Release",
        draft=True,
    )
    request = httpx_mock.get_request()
    assert request is not None
    body = _json.loads(request.content)
    assert body["draft"] is True
    assert body["prerelease"] is False
