"""Unit tests for the file-ops and PR-creation tools (files.py)."""

from __future__ import annotations

import base64
import json as _json

import pytest
from pytest_httpx import HTTPXMock

from gitea_mcp.client import GiteaAPIError, GiteaClient
from gitea_mcp.tools.files import commit_changes, create_branch, create_pr, read_file

# ---- read_file -------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_file_default_branch_decodes_base64(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """Without a ref, GET /contents/{path} (no query string) and decode."""
    plaintext = "hello, world\n"
    encoded = base64.b64encode(plaintext.encode()).decode()
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/contents/README.md",
        json={
            "path": "README.md",
            "sha": "abc123",
            "size": len(plaintext),
            "encoding": "base64",
            "content": encoded,
        },
    )
    result = await read_file.fn(owner="acme", repo="widget", path="README.md")
    assert result["text"] == plaintext
    assert result["sha"] == "abc123"
    assert result["content"] == encoded  # raw preserved


@pytest.mark.asyncio
async def test_read_file_with_ref_passes_ref_param(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/contents/src/x.py?ref=develop",
        json={
            "path": "src/x.py",
            "sha": "def456",
            "encoding": "base64",
            "content": base64.b64encode(b"# x\n").decode(),
        },
    )
    result = await read_file.fn(
        owner="acme", repo="widget", path="src/x.py", ref="develop"
    )
    assert result["text"] == "# x\n"


@pytest.mark.asyncio
async def test_read_file_binary_content_returns_none_text(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """Non-UTF-8 content (binary file) should give text=None, raw content intact."""
    binary_payload = bytes(range(256))  # not valid UTF-8
    encoded = base64.b64encode(binary_payload).decode()
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/contents/img.bin",
        json={
            "path": "img.bin",
            "sha": "bbb",
            "encoding": "base64",
            "content": encoded,
        },
    )
    result = await read_file.fn(owner="acme", repo="widget", path="img.bin")
    assert result["text"] is None
    assert result["content"] == encoded


# ---- create_branch ---------------------------------------------------------


@pytest.mark.asyncio
async def test_create_branch_default_base(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """Without old_branch_name, omit it from the payload — Gitea defaults to main."""
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/branches",
        json={"name": "feature/x", "commit": {"id": "abc"}, "protected": False},
    )
    result = await create_branch.fn(
        owner="acme", repo="widget", new_branch_name="feature/x"
    )
    assert result["name"] == "feature/x"
    request = httpx_mock.get_request()
    assert request is not None
    assert _json.loads(request.content) == {"new_branch_name": "feature/x"}


@pytest.mark.asyncio
async def test_create_branch_explicit_base(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/branches",
        json={"name": "hotfix/x", "commit": {"id": "def"}, "protected": False},
    )
    await create_branch.fn(
        owner="acme",
        repo="widget",
        new_branch_name="hotfix/x",
        old_branch_name="release-1.0",
    )
    request = httpx_mock.get_request()
    assert request is not None
    body = _json.loads(request.content)
    assert body == {"new_branch_name": "hotfix/x", "old_branch_name": "release-1.0"}


# ---- commit_changes --------------------------------------------------------


@pytest.mark.asyncio
async def test_commit_changes_creates_new_file_on_404(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """File doesn't exist on the branch → GET 404 → POST to create."""
    # 1. SHA lookup returns 404
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/contents/NEW.md?ref=feature/x",
        status_code=404,
        json={"message": "not found"},
    )
    # 2. POST creates the file
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/contents/NEW.md",
        json={"content": {"path": "NEW.md", "sha": "new123"}, "commit": {"sha": "c1"}},
    )
    result = await commit_changes.fn(
        owner="acme",
        repo="widget",
        branch="feature/x",
        path="NEW.md",
        content="# new\n",
        message="add NEW.md",
    )
    assert result["content"]["path"] == "NEW.md"
    post_request = httpx_mock.get_request(method="POST")
    assert post_request is not None
    body = _json.loads(post_request.content)
    assert body["branch"] == "feature/x"
    assert body["message"] == "add NEW.md"
    assert "sha" not in body  # create path — no sha sent
    assert base64.b64decode(body["content"]).decode() == "# new\n"


@pytest.mark.asyncio
async def test_commit_changes_updates_existing_file(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """File exists → GET returns sha → PUT with that sha."""
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/contents/README.md?ref=feature/x",
        json={"path": "README.md", "sha": "old-sha", "encoding": "base64", "content": ""},
    )
    httpx_mock.add_response(
        method="PUT",
        url="https://gitea.example.com/api/v1/repos/acme/widget/contents/README.md",
        json={"content": {"path": "README.md", "sha": "new-sha"}, "commit": {"sha": "c2"}},
    )
    result = await commit_changes.fn(
        owner="acme",
        repo="widget",
        branch="feature/x",
        path="README.md",
        content="updated\n",
        message="docs: update README",
    )
    assert result["content"]["sha"] == "new-sha"
    put_request = httpx_mock.get_request(method="PUT")
    assert put_request is not None
    body = _json.loads(put_request.content)
    assert body["sha"] == "old-sha"  # update path — sha sent
    assert body["branch"] == "feature/x"


@pytest.mark.asyncio
async def test_commit_changes_propagates_non_404_on_lookup(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    """Lookup errors that aren't 404 (e.g. 500) should propagate, not be swallowed."""
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/repos/acme/widget/contents/F.md?ref=feature/x",
        status_code=500,
        json={"message": "server error"},
    )
    with pytest.raises(GiteaAPIError) as exc_info:
        await commit_changes.fn(
            owner="acme",
            repo="widget",
            branch="feature/x",
            path="F.md",
            content="x",
            message="m",
        )
    assert exc_info.value.status_code == 500


# ---- create_pr -------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pr_minimal(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/pulls",
        json={"number": 42, "title": "Add x", "state": "open"},
    )
    result = await create_pr.fn(
        owner="acme",
        repo="widget",
        head="feature/x",
        base="main",
        title="Add x",
    )
    assert result["number"] == 42
    request = httpx_mock.get_request()
    assert request is not None
    body = _json.loads(request.content)
    # draft omitted when False (the default).
    assert body == {
        "head": "feature/x",
        "base": "main",
        "title": "Add x",
        "body": "",
    }


@pytest.mark.asyncio
async def test_create_pr_with_body_and_draft(
    patched_server_client: GiteaClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://gitea.example.com/api/v1/repos/acme/widget/pulls",
        json={"number": 43, "title": "WIP", "state": "open", "draft": True},
    )
    await create_pr.fn(
        owner="acme",
        repo="widget",
        head="feature/wip",
        base="main",
        title="WIP",
        body="## still working\n- x\n- y",
        draft=True,
    )
    request = httpx_mock.get_request()
    assert request is not None
    body = _json.loads(request.content)
    assert body["draft"] is True
    assert body["body"] == "## still working\n- x\n- y"
