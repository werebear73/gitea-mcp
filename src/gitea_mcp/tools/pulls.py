"""MCP tools for Gitea branches and pull requests.

Grouped together because the workflow is shared: inspecting branches, listing
PRs against them, reading a PR's discussion thread, and adding a comment to
move the conversation forward.

A note on the Gitea API: pull requests and issues share the same number
namespace and the same comments endpoint (``/repos/{owner}/{repo}/issues/{n}/comments``).
That's why ``add_comment_on_pr`` posts to ``/issues/{pull_number}/comments``
rather than a hypothetical ``/pulls/{pull_number}/comments`` — Gitea simply
doesn't have one for non-review comments. Inline review comments (those
attached to specific diff lines) live under ``/pulls/{n}/reviews`` and are
out of scope for this MVP.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.types import ToolAnnotations
from pydantic import Field

from gitea_mcp._app import get_client, mcp

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)


@mcp.tool(annotations=_READ_ONLY)
async def list_branches(
    owner: Annotated[str, Field(description="Repository owner (user or organization name)")],
    repo: Annotated[str, Field(description="Repository name")],
    page: Annotated[int, Field(description="Page number (1-indexed)")] = 1,
    limit: Annotated[int, Field(description="Items per page (max 50)")] = 30,
) -> list[dict[str, Any]]:
    """List branches in a repository.

    Returns the standard Gitea Branch object array: ``[{name, commit: {id, ...},
    protected, ...}]``. Useful for inspecting available targets before creating
    a release, opening a PR, or filing a fix against a specific branch.
    """
    return await get_client().get_list(
        f"/repos/{owner}/{repo}/branches",
        params={"page": page, "limit": limit},
    )


@mcp.tool(annotations=_READ_ONLY)
async def list_pull_requests(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    state: Annotated[
        str, Field(description="Filter by state: 'open', 'closed', or 'all'")
    ] = "open",
    sort: Annotated[
        str | None,
        Field(
            description=(
                "Sort order: 'oldest', 'newest', 'leastupdate', 'mostupdate', "
                "'leastcomment', 'mostcomment', 'priority'. Omit for Gitea's default."
            ),
        ),
    ] = None,
    page: Annotated[int, Field(description="Page number (1-indexed)")] = 1,
    limit: Annotated[int, Field(description="Items per page (max 50)")] = 30,
) -> list[dict[str, Any]]:
    """List pull requests in a repository, optionally filtered by state.

    Returns Gitea PullRequest objects (not Issue-style — the PR endpoint
    returns richer head/base/mergeable info than the issues endpoint does
    even when issues are filtered to ``type=pulls``).
    """
    params: dict[str, Any] = {
        "state": state,
        "page": page,
        "limit": limit,
    }
    if sort is not None:
        params["sort"] = sort
    return await get_client().get_list(
        f"/repos/{owner}/{repo}/pulls",
        params=params,
    )


@mcp.tool(annotations=_READ_ONLY)
async def get_pull_request(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    pull_number: Annotated[int, Field(description="Pull request number (the #N in the URL)")],
) -> dict[str, Any]:
    """Get a single pull request by number, including its discussion comments.

    Mirrors :func:`gitea_mcp.tools.issues.get_issue`'s shape: returns the full
    Gitea PullRequest object with an additional ``comments_list`` field
    containing the issue-style comment thread. Inline review comments (those
    attached to specific diff lines) are NOT included — those live under
    ``/pulls/{n}/reviews`` and are out of scope for this tool.
    """
    client = get_client()
    pr = await client.get_json(f"/repos/{owner}/{repo}/pulls/{pull_number}")
    pr["comments_list"] = await client.get_list(
        f"/repos/{owner}/{repo}/issues/{pull_number}/comments"
    )
    return pr


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        openWorldHint=True,
    )
)
async def add_comment_on_pr(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    pull_number: Annotated[int, Field(description="Pull request number")],
    body: Annotated[str, Field(description="Comment body (Markdown)")],
) -> dict[str, Any]:
    """Add a comment to a pull request's discussion thread.

    Posts to ``/repos/{owner}/{repo}/issues/{pull_number}/comments`` — Gitea's
    issue-comments endpoint also serves PR conversation comments (PRs and
    issues share the number namespace and comment infrastructure). For inline
    diff-line review comments, a separate ``/pulls/{n}/reviews``-based tool
    would be needed; that's deliberately out of scope here.
    """
    return await get_client().post_json(
        f"/repos/{owner}/{repo}/issues/{pull_number}/comments",
        json={"body": body},
    )
