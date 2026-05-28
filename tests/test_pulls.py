"""Unit tests for the branches + pull-request tools (pulls.py)."""

from __future__ import annotations

import json as _json

import pytest
from pytest_httpx import HTTPXMock

from gitea_mcp.client import GiteaClient
from gitea_mcp.tools.pulls import (
    add_comment_on_pr,
    get_pull_request,
    list_branches,
    list_pull_requests,
    merge_pr,
)

# ---- list_branches ---------------------------------------------------------


@pytest.mark.asyncio
async def test_list_branches_defaults(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/branches?page=1&limit=30",
        json=[
            {"name": "main", "commit": {"id": "abc123"}, "protected": True},
            {"name": "develop", "commit": {"id": "def456"}, "protected": False},
        ],
    )
    result = await list_branches.fn(owner="acme", repo="widget")
    assert [b["name"] for b in result] == ["main", "develop"]
    assert result[0]["protected"] is True


@pytest.mark.asyncio
async def test_list_branches_pagination_params(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/branches?page=2&limit=50",
        json=[],
    )
    await list_branches.fn(owner="acme", repo="widget", page=2, limit=50)


# ---- list_pull_requests ----------------------------------------------------


@pytest.mark.asyncio
async def test_list_pull_requests_defaults_to_open(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://gitea.example.com/api/v1/repos/acme/widget/pulls"
            "?state=open&page=1&limit=30"
        ),
        json=[{"number": 1, "title": "First PR", "state": "open"}],
    )
    result = await list_pull_requests.fn(owner="acme", repo="widget")
    assert result[0]["number"] == 1
    assert result[0]["state"] == "open"


@pytest.mark.asyncio
async def test_list_pull_requests_state_filter(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://gitea.example.com/api/v1/repos/acme/widget/pulls"
            "?state=closed&page=1&limit=30"
        ),
        json=[{"number": 5, "title": "Old PR", "state": "closed"}],
    )
    result = await list_pull_requests.fn(owner="acme", repo="widget", state="closed")
    assert result[0]["state"] == "closed"


@pytest.mark.asyncio
async def test_list_pull_requests_sort_param(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://gitea.example.com/api/v1/repos/acme/widget/pulls"
            "?state=all&page=1&limit=30&sort=mostupdate"
        ),
        json=[],
    )
    await list_pull_requests.fn(
        owner="acme", repo="widget", state="all", sort="mostupdate"
    )


# ---- get_pull_request ------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pull_request_includes_comments_list(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/pulls/7",
        json={
            "number": 7,
            "title": "Add foo",
            "state": "open",
            "head": {"ref": "feature/foo", "sha": "aaa"},
            "base": {"ref": "main", "sha": "bbb"},
            "mergeable": True,
            "comments": 2,
        },
    )
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues/7/comments",
        json=[
            {"id": 100, "body": "looks good"},
            {"id": 101, "body": "lgtm"},
        ],
    )
    result = await get_pull_request.fn(owner="acme", repo="widget", pull_number=7)
    assert result["number"] == 7
    assert result["head"]["ref"] == "feature/foo"
    assert result["comments"] == 2  # Gitea's own count preserved
    assert len(result["comments_list"]) == 2
    assert result["comments_list"][0]["body"] == "looks good"


# ---- add_comment_on_pr -----------------------------------------------------


@pytest.mark.asyncio
async def test_add_comment_on_pr_posts_to_issues_endpoint(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """PRs and issues share the comments endpoint in Gitea; assert we hit /issues/."""
    expected_comment = {"id": 999, "body": "great change"}
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues/7/comments",
        json=expected_comment,
    )
    result = await add_comment_on_pr.fn(
        owner="acme",
        repo="widget",
        pull_number=7,
        body="great change",
    )
    assert result == expected_comment
    request = httpx_mock.get_request()
    assert request is not None
    assert _json.loads(request.content) == {"body": "great change"}


# ---- merge_pr --------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_pr_defaults_to_merge_strategy(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    expected = {"sha": "abc123", "merged": True, "message": "Pull Request has been merged"}
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/pulls/7/merge",
        json=expected,
    )

    result = await merge_pr.fn(owner="acme", repo="widget", pull_number=7)

    assert result == expected
    request = httpx_mock.get_request()
    assert request is not None
    assert _json.loads(request.content) == {"Do": "merge"}


@pytest.mark.asyncio
async def test_merge_pr_with_optional_message_fields(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/pulls/8/merge",
        json={"sha": "def456", "merged": True, "message": "ok"},
    )

    await merge_pr.fn(
        owner="acme",
        repo="widget",
        pull_number=8,
        do="squash",
        merge_title_field="PR_TITLE",
        merge_message_field="PR_BODY",
    )

    request = httpx_mock.get_request()
    assert request is not None
    assert _json.loads(request.content) == {
        "Do": "squash",
        "MergeTitleField": "PR_TITLE",
        "MergeMessageField": "PR_BODY",
    }
