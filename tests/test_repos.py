"""Unit tests for the repo metadata tools."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from gitea_mcp.client import GiteaAPIError, GiteaClient
from gitea_mcp.tools.repos import list_labels, list_milestones, list_repos

# ---- list_repos ------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_repos_no_owner_uses_user_endpoint(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/user/repos?page=1&limit=30",
        json=[{"name": "my-first-repo"}, {"name": "my-second-repo"}],
    )
    result = await list_repos()
    assert [r["name"] for r in result] == ["my-first-repo", "my-second-repo"]


@pytest.mark.asyncio
async def test_list_repos_user_owner(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/users/alice/repos?page=1&limit=30",
        json=[{"name": "alice-repo"}],
    )
    result = await list_repos(owner="alice")
    assert result == [{"name": "alice-repo"}]


@pytest.mark.asyncio
async def test_list_repos_org_owner_falls_back_after_404(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    # User endpoint 404s — owner is actually an org. Fallback should succeed.
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/users/acme-org/repos?page=1&limit=30",
        status_code=404,
        json={"message": "user does not exist"},
    )
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/orgs/acme-org/repos?page=1&limit=30",
        json=[{"name": "acme-widget"}, {"name": "acme-gadget"}],
    )
    result = await list_repos(owner="acme-org")
    assert [r["name"] for r in result] == ["acme-widget", "acme-gadget"]


@pytest.mark.asyncio
async def test_list_repos_non_404_error_propagates(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/users/alice/repos?page=1&limit=30",
        status_code=500,
        json={"message": "internal server error"},
    )
    with pytest.raises(GiteaAPIError) as exc_info:
        await list_repos(owner="alice")
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_list_repos_pagination_params(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/user/repos?page=3&limit=10",
        json=[],
    )
    await list_repos(page=3, limit=10)


# ---- list_labels -----------------------------------------------------------


@pytest.mark.asyncio
async def test_list_labels(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/labels?page=1&limit=30",
        json=[
            {"id": 1, "name": "bug", "color": "ee0701"},
            {"id": 2, "name": "enhancement", "color": "84b6eb"},
        ],
    )
    result = await list_labels(owner="acme", repo="widget")
    assert [label["name"] for label in result] == ["bug", "enhancement"]
    assert result[0]["id"] == 1


@pytest.mark.asyncio
async def test_list_labels_pagination_params(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/labels?page=2&limit=50",
        json=[],
    )
    await list_labels(owner="acme", repo="widget", page=2, limit=50)


# ---- list_milestones -------------------------------------------------------


@pytest.mark.asyncio
async def test_list_milestones_defaults_to_open(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://gitea.example.com/api/v1/repos/acme/widget/milestones"
            "?state=open&page=1&limit=30"
        ),
        json=[{"id": 1, "title": "v1.0", "state": "open"}],
    )
    result = await list_milestones(owner="acme", repo="widget")
    assert result[0]["title"] == "v1.0"


@pytest.mark.asyncio
async def test_list_milestones_filters_by_state(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://gitea.example.com/api/v1/repos/acme/widget/milestones"
            "?state=closed&page=1&limit=30"
        ),
        json=[{"id": 99, "title": "v0.9", "state": "closed"}],
    )
    result = await list_milestones(owner="acme", repo="widget", state="closed")
    assert result[0]["state"] == "closed"
