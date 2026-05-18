"""Unit tests for the issue tools (pytest-httpx mocks the HTTP layer)."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from gitea_mcp.client import GiteaClient, GiteaError
from gitea_mcp.tools.issues import (
    _resolve_label_ids,
    add_comment,
    create_issue,
    get_issue,
    list_issues,
    update_issue,
)

# ---- _resolve_label_ids ----------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_label_ids_maps_names_to_ids(
    client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/labels?page=1&limit=50",
        json=[
            {"id": 1, "name": "bug"},
            {"id": 2, "name": "enhancement"},
            {"id": 3, "name": "wontfix"},
        ],
    )
    ids = await _resolve_label_ids(client, "acme", "widget", ["bug", "enhancement"])
    assert ids == [1, 2]


@pytest.mark.asyncio
async def test_resolve_label_ids_raises_on_missing(
    client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/labels?page=1&limit=50",
        json=[{"id": 1, "name": "bug"}],
    )
    with pytest.raises(GiteaError, match="Labels not found"):
        await _resolve_label_ids(client, "acme", "widget", ["bug", "nonexistent"])


@pytest.mark.asyncio
async def test_resolve_label_ids_pages_when_full(
    client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    # First page returns 50 labels, second page returns 1 more
    page_one = [{"id": i, "name": f"label-{i:02d}"} for i in range(1, 51)]
    page_two = [{"id": 51, "name": "label-51"}]
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/labels?page=1&limit=50",
        json=page_one,
    )
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/labels?page=2&limit=50",
        json=page_two,
    )
    ids = await _resolve_label_ids(client, "acme", "widget", ["label-51", "label-01"])
    assert ids == [51, 1]


# ---- create_issue ----------------------------------------------------------


@pytest.mark.asyncio
async def test_create_issue_minimal(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    expected_issue = {"id": 100, "number": 1, "title": "Hello", "state": "open"}
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues",
        json=expected_issue,
    )
    result = await create_issue.fn(owner="acme", repo="widget", title="Hello")
    assert result == expected_issue
    request = httpx_mock.get_request()
    assert request is not None
    assert request.headers["authorization"] == "token test-token"
    import json as _json

    body = _json.loads(request.content)
    assert body == {"title": "Hello", "body": ""}


@pytest.mark.asyncio
async def test_create_issue_resolves_label_names(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/labels?page=1&limit=50",
        json=[{"id": 7, "name": "bug"}, {"id": 8, "name": "p0"}],
    )
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues",
        json={"id": 200, "number": 2, "title": "Bug"},
    )
    await create_issue.fn(
        owner="acme",
        repo="widget",
        title="Bug",
        body="repro steps",
        labels=["bug", "p0"],
        assignees=["alice"],
        milestone=42,
    )
    # Second request is the POST — assert payload includes resolved label IDs
    post_request = httpx_mock.get_requests(
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues"
    )[-1]
    import json as _json

    body = _json.loads(post_request.content)
    assert body == {
        "title": "Bug",
        "body": "repro steps",
        "assignees": ["alice"],
        "milestone": 42,
        "labels": [7, 8],
    }


# ---- list_issues -----------------------------------------------------------


@pytest.mark.asyncio
async def test_list_issues_defaults_to_open_issues_only(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://gitea.example.com/api/v1/repos/acme/widget/issues"
            "?state=open&type=issues&page=1&limit=30"
        ),
        json=[{"number": 1}, {"number": 2}],
    )
    result = await list_issues.fn(owner="acme", repo="widget")
    assert [item["number"] for item in result] == [1, 2]


@pytest.mark.asyncio
async def test_list_issues_passes_filters(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://gitea.example.com/api/v1/repos/acme/widget/issues"
            "?state=closed&type=issues&page=2&limit=10&labels=bug,p0&assigned_by=alice"
        ),
        json=[],
    )
    await list_issues.fn(
        owner="acme",
        repo="widget",
        state="closed",
        labels="bug,p0",
        assignee="alice",
        page=2,
        limit=10,
    )


# ---- get_issue -------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_issue_includes_comments_list(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues/5",
        json={"number": 5, "title": "Something", "comments": 2},
    )
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues/5/comments",
        json=[{"id": 11, "body": "first"}, {"id": 12, "body": "second"}],
    )
    result = await get_issue.fn(owner="acme", repo="widget", issue_number=5)
    assert result["number"] == 5
    assert result["comments"] == 2  # Gitea's count preserved
    assert len(result["comments_list"]) == 2
    assert result["comments_list"][0]["body"] == "first"


# ---- update_issue ----------------------------------------------------------


@pytest.mark.asyncio
async def test_update_issue_state_and_title(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="PATCH",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues/5",
        json={"number": 5, "title": "Renamed", "state": "closed"},
    )
    result = await update_issue.fn(
        owner="acme",
        repo="widget",
        issue_number=5,
        title="Renamed",
        state="closed",
    )
    assert result["state"] == "closed"
    patch_request = httpx_mock.get_request(method="PATCH")
    assert patch_request is not None
    import json as _json

    body = _json.loads(patch_request.content)
    assert body == {"title": "Renamed", "state": "closed"}


@pytest.mark.asyncio
async def test_update_issue_clears_milestone_with_zero(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="PATCH",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues/5",
        json={"number": 5, "milestone": None},
    )
    await update_issue.fn(owner="acme", repo="widget", issue_number=5, milestone=0)
    patch_request = httpx_mock.get_request(method="PATCH")
    assert patch_request is not None
    import json as _json

    body = _json.loads(patch_request.content)
    assert body == {"milestone": None}


@pytest.mark.asyncio
async def test_update_issue_replaces_labels(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    # No payload-level fields — should skip PATCH, fetch the issue, then PUT labels.
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues/5",
        json={"number": 5, "labels": []},
    )
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/labels?page=1&limit=50",
        json=[{"id": 7, "name": "bug"}, {"id": 8, "name": "p0"}],
    )
    httpx_mock.add_response(
        method="PUT",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues/5/labels",
        json=[{"id": 7, "name": "bug"}, {"id": 8, "name": "p0"}],
    )
    result = await update_issue.fn(
        owner="acme", repo="widget", issue_number=5, labels=["bug", "p0"]
    )
    put_request = httpx_mock.get_request(method="PUT")
    assert put_request is not None
    import json as _json

    body = _json.loads(put_request.content)
    assert body == {"labels": [7, 8]}
    assert result["labels"] == [{"id": 7, "name": "bug"}, {"id": 8, "name": "p0"}]


@pytest.mark.asyncio
async def test_update_issue_clears_labels_with_empty_list(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues/5",
        json={"number": 5, "labels": [{"id": 7, "name": "bug"}]},
    )
    # _resolve_label_ids short-circuits when labels=[], so no labels endpoint fetch.
    httpx_mock.add_response(
        method="PUT",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues/5/labels",
        json=[],
    )
    await update_issue.fn(
        owner="acme", repo="widget", issue_number=5, labels=[]
    )
    put_request = httpx_mock.get_request(method="PUT")
    assert put_request is not None
    import json as _json

    assert _json.loads(put_request.content) == {"labels": []}


# ---- add_comment -----------------------------------------------------------


@pytest.mark.asyncio
async def test_add_comment(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    expected_comment = {"id": 999, "body": "thanks for the report"}
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/issues/5/comments",
        json=expected_comment,
    )
    result = await add_comment.fn(
        owner="acme",
        repo="widget",
        issue_number=5,
        body="thanks for the report",
    )
    assert result == expected_comment
    request = httpx_mock.get_request()
    assert request is not None
    import json as _json

    assert _json.loads(request.content) == {"body": "thanks for the report"}
