"""MCP tools for Gitea file operations and pull-request creation.

This is the surface that lets the LLM actually *change code* via gitea-mcp,
not just read and discuss it. Four tools form a complete edit workflow:

1. :func:`read_file` — read a file's current content (optionally pinned to a
   specific branch or commit).
2. :func:`create_branch` — open a feature branch off the default branch (or
   any specified base).
3. :func:`commit_changes` — write a single file's new content on a branch;
   automatically detects whether the file is new or existing (GET to fetch
   the current SHA; 404 → POST create; existing → PUT update).
4. :func:`create_pr` — open a pull request from the feature branch back to
   the base.

Multi-file commits via the Git Trees API are deliberately out of scope for
this MVP — single-file `commit_changes` is the simpler, safer pattern.
"""

from __future__ import annotations

import base64
from typing import Annotated, Any

from mcp.types import ToolAnnotations
from pydantic import Field

from gitea_mcp._app import get_client, mcp
from gitea_mcp.client import GiteaAPIError

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)


@mcp.tool(annotations=_READ_ONLY)
async def read_file(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    path: Annotated[
        str,
        Field(description="Path within the repository, e.g. 'src/gitea_mcp/server.py'"),
    ],
    ref: Annotated[
        str | None,
        Field(
            description=(
                "Branch name, tag name, or commit SHA to read from. "
                "Omit to read from the repository's default branch."
            ),
        ),
    ] = None,
) -> dict[str, Any]:
    """Read a file's content from a Gitea repository.

    Returns Gitea's ``ContentsResponse`` shape extended with a ``text`` field
    containing the decoded file content as a UTF-8 string (or ``None`` if the
    content isn't valid UTF-8 — binary file). The raw base64 ``content`` and
    Gitea's ``encoding`` are preserved so callers can re-decode if needed.

    The ``sha`` field in the response is what :func:`commit_changes` would
    need to update this file — but ``commit_changes`` fetches it internally,
    so callers don't usually need to pass it forward.
    """
    params: dict[str, Any] = {}
    if ref is not None:
        params["ref"] = ref
    response = await get_client().get_json(
        f"/repos/{owner}/{repo}/contents/{path}",
        params=params or None,
    )
    text: str | None = None
    encoding = response.get("encoding")
    content = response.get("content")
    if encoding == "base64" and isinstance(content, str):
        try:
            text = base64.b64decode(content).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            text = None
    response["text"] = text
    return response


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        openWorldHint=True,
    )
)
async def create_branch(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    new_branch_name: Annotated[
        str,
        Field(description="Name for the new branch (must not already exist)"),
    ],
    old_branch_name: Annotated[
        str | None,
        Field(
            description=(
                "Existing branch to fork from. Omit to use the repository's "
                "default branch."
            ),
        ),
    ] = None,
) -> dict[str, Any]:
    """Create a new branch in a repository.

    Returns the created Gitea Branch object. Fails cleanly via
    :class:`GiteaAPIError` if the new branch name already exists.
    """
    payload: dict[str, Any] = {"new_branch_name": new_branch_name}
    if old_branch_name is not None:
        payload["old_branch_name"] = old_branch_name
    return await get_client().post_json(
        f"/repos/{owner}/{repo}/branches",
        json=payload,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        # Overwrites existing file content (when updating). Reversible via git,
        # but a user-visible state change worth gating on confirmation.
        destructiveHint=True,
        openWorldHint=True,
    )
)
async def commit_changes(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    branch: Annotated[
        str,
        Field(description="Branch to commit to (must exist; use create_branch first)"),
    ],
    path: Annotated[
        str,
        Field(description="File path within the repository, e.g. 'README.md'"),
    ],
    content: Annotated[
        str,
        Field(description="New file content (UTF-8 text; binary files not supported)"),
    ],
    message: Annotated[str, Field(description="Commit message")],
) -> dict[str, Any]:
    """Create or update a single file on a branch in one commit.

    Auto-detects whether the file exists:

    - **File does not exist on the branch:** Gitea returns 404 to the SHA
      lookup; we ``POST`` to create the file.
    - **File exists:** we use its current SHA and ``PUT`` to update it.

    Returns Gitea's ``FileResponse`` shape (the resulting commit + content
    metadata). Raises :class:`GiteaAPIError` on conflicts (e.g. concurrent
    update changed the SHA between our lookup and our write — caller should
    re-read and retry).

    Single-file only. Multi-file commits would require Gitea's Git Trees
    API and are deliberately out of scope for this tool.
    """
    client = get_client()
    encoded_content = base64.b64encode(content.encode("utf-8")).decode("ascii")
    payload: dict[str, Any] = {
        "content": encoded_content,
        "message": message,
        "branch": branch,
    }

    # SHA lookup — determines create vs update.
    existing_sha: str | None = None
    try:
        existing = await client.get_json(
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": branch},
        )
        sha_value = existing.get("sha")
        if isinstance(sha_value, str):
            existing_sha = sha_value
    except GiteaAPIError as exc:
        if exc.status_code != 404:
            raise
        # 404 = file doesn't exist; fall through to create.

    if existing_sha is not None:
        payload["sha"] = existing_sha
        return await client.put_json(
            f"/repos/{owner}/{repo}/contents/{path}",
            json=payload,
        )
    return await client.post_json(
        f"/repos/{owner}/{repo}/contents/{path}",
        json=payload,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        openWorldHint=True,
    )
)
async def create_pr(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    head: Annotated[
        str,
        Field(
            description=(
                "Source branch (the branch containing your changes). "
                "Same-repo only; cross-fork PRs not supported by this tool."
            ),
        ),
    ],
    base: Annotated[
        str,
        Field(description="Target branch (where the PR should merge into, e.g. 'main')"),
    ],
    title: Annotated[str, Field(description="Pull request title")],
    body: Annotated[str, Field(description="PR description in Markdown")] = "",
    draft: Annotated[
        bool,
        Field(description="Open as a draft PR (cannot be merged until marked ready)"),
    ] = False,
) -> dict[str, Any]:
    """Open a new pull request from ``head`` into ``base``.

    Returns the created Gitea PullRequest object (including the assigned
    number, URL, and merge status). Raises :class:`GiteaAPIError` if the
    head branch doesn't exist, there are no commits between head and base,
    or an open PR already exists for this branch pair.
    """
    payload: dict[str, Any] = {
        "head": head,
        "base": base,
        "title": title,
        "body": body,
    }
    if draft:
        payload["draft"] = True
    return await get_client().post_json(
        f"/repos/{owner}/{repo}/pulls",
        json=payload,
    )
