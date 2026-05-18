"""MCP tools for Gitea issues."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.types import ToolAnnotations
from pydantic import Field

from gitea_mcp._app import get_client, mcp
from gitea_mcp.client import GiteaClient, GiteaError

# ---- Internal helpers ------------------------------------------------------


async def _list_all_labels(
    client: GiteaClient, owner: str, repo: str
) -> list[dict[str, Any]]:
    """Page through every label defined in a repository."""
    all_labels: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = await client.get_list(
            f"/repos/{owner}/{repo}/labels",
            params={"page": page, "limit": 50},
        )
        if not batch:
            break
        all_labels.extend(batch)
        if len(batch) < 50:
            break
        page += 1
    return all_labels


async def _resolve_label_ids(
    client: GiteaClient, owner: str, repo: str, label_names: list[str]
) -> list[int]:
    """Resolve a list of label names to the integer IDs Gitea's issue API expects.

    Gitea's create-issue and replace-issue-labels endpoints take ``labels`` as a
    list of integer IDs, not names. This helper fetches the repo's labels once
    and maps the names in. Raises :class:`GiteaError` if any name doesn't match
    a defined label, including the available label names in the error message
    so the caller knows what's valid.
    """
    if not label_names:
        return []
    all_labels = await _list_all_labels(client, owner, repo)
    name_to_id = {label["name"]: label["id"] for label in all_labels}
    missing = [name for name in label_names if name not in name_to_id]
    if missing:
        raise GiteaError(
            f"Labels not found in {owner}/{repo}: {missing}. "
            f"Available labels: {sorted(name_to_id.keys())}"
        )
    return [name_to_id[name] for name in label_names]


# ---- Tools -----------------------------------------------------------------


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        openWorldHint=True,
    )
)
async def create_issue(
    owner: Annotated[str, Field(description="Repository owner (user or organization name)")],
    repo: Annotated[str, Field(description="Repository name")],
    title: Annotated[str, Field(description="Issue title")],
    body: Annotated[str, Field(description="Issue body in Markdown")] = "",
    labels: Annotated[
        list[str] | None,
        Field(description="Label names to apply to the new issue (resolved to IDs automatically)"),
    ] = None,
    assignees: Annotated[
        list[str] | None,
        Field(description="Usernames to assign to the new issue"),
    ] = None,
    milestone: Annotated[int | None, Field(description="Milestone ID to attach")] = None,
) -> dict[str, Any]:
    """Create a new issue in a Gitea repository.

    Returns the full Gitea Issue object including the assigned number, URL, and
    metadata. Label names are resolved to IDs against the repository's label
    set; an unknown label name fails the call cleanly with the list of valid
    names.
    """
    client = get_client()
    payload: dict[str, Any] = {"title": title, "body": body}
    if assignees:
        payload["assignees"] = assignees
    if milestone is not None:
        payload["milestone"] = milestone
    if labels:
        payload["labels"] = await _resolve_label_ids(client, owner, repo, labels)
    return await client.post_json(f"/repos/{owner}/{repo}/issues", json=payload)


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True)
)
async def list_issues(
    owner: Annotated[str, Field(description="Repository owner (user or organization name)")],
    repo: Annotated[str, Field(description="Repository name")],
    state: Annotated[
        str, Field(description="Filter by state: 'open', 'closed', or 'all'")
    ] = "open",
    labels: Annotated[
        str | None,
        Field(description="Comma-separated label names to filter by"),
    ] = None,
    assignee: Annotated[
        str | None,
        Field(description="Filter to issues assigned to this username"),
    ] = None,
    page: Annotated[int, Field(description="Page number (1-indexed)")] = 1,
    limit: Annotated[int, Field(description="Items per page (max 50)")] = 30,
) -> list[dict[str, Any]]:
    """List issues in a Gitea repository.

    Pull requests are excluded; only true issues are returned. Filters compose
    (state AND labels AND assignee).
    """
    client = get_client()
    params: dict[str, Any] = {
        "state": state,
        "type": "issues",  # exclude pull requests
        "page": page,
        "limit": limit,
    }
    if labels:
        params["labels"] = labels
    if assignee:
        params["assigned_by"] = assignee
    return await client.get_list(f"/repos/{owner}/{repo}/issues", params=params)


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True)
)
async def get_issue(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    issue_number: Annotated[int, Field(description="Issue number (the #N in the URL)")],
) -> dict[str, Any]:
    """Get a single issue by number, including all of its comments.

    The returned object is the standard Gitea Issue payload, with an additional
    ``comments_list`` field containing the full list of Comment objects. The
    existing top-level ``comments`` integer field (comment count) is preserved.
    """
    client = get_client()
    issue = await client.get_json(f"/repos/{owner}/{repo}/issues/{issue_number}")
    issue["comments_list"] = await client.get_list(
        f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
    )
    return issue


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        # Can close the issue and clear labels — both reversible but
        # user-visible side effects, so clients should gate on confirmation
        # rather than auto-approve.
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def update_issue(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    issue_number: Annotated[int, Field(description="Issue number")],
    title: Annotated[str | None, Field(description="New title")] = None,
    body: Annotated[str | None, Field(description="New body (Markdown)")] = None,
    state: Annotated[
        str | None,
        Field(description="New state: 'open' or 'closed'"),
    ] = None,
    labels: Annotated[
        list[str] | None,
        Field(description="Replace labels with this exact set (names; pass [] to clear)"),
    ] = None,
    assignees: Annotated[
        list[str] | None,
        Field(description="Replace assignees with this exact set of usernames"),
    ] = None,
    milestone: Annotated[
        int | None,
        Field(description="Milestone ID to attach; pass 0 to clear the milestone"),
    ] = None,
) -> dict[str, Any]:
    """Update an existing issue's title, body, state, assignees, milestone, or labels.

    Each argument is independent — pass only the fields you want to change.
    Labels are replaced atomically against the new set (passing ``[]`` removes
    all labels). Other list fields (assignees) follow the same replace semantics.
    """
    client = get_client()
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if state is not None:
        payload["state"] = state
    if assignees is not None:
        payload["assignees"] = assignees
    if milestone is not None:
        # Gitea convention: milestone=0 in the request clears the milestone.
        # We send null in that case, which Gitea also accepts and is unambiguous.
        payload["milestone"] = milestone if milestone > 0 else None

    if payload:
        issue = await client.patch_json(
            f"/repos/{owner}/{repo}/issues/{issue_number}", json=payload
        )
    else:
        # No PATCH-level changes — fetch the current issue so the caller still
        # gets the up-to-date object after the labels update below.
        issue = await client.get_json(f"/repos/{owner}/{repo}/issues/{issue_number}")

    if labels is not None:
        label_ids = await _resolve_label_ids(client, owner, repo, labels)
        issue["labels"] = await client.put_list(
            f"/repos/{owner}/{repo}/issues/{issue_number}/labels",
            json={"labels": label_ids},
        )

    return issue


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        openWorldHint=True,
    )
)
async def add_comment(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    issue_number: Annotated[int, Field(description="Issue number")],
    body: Annotated[str, Field(description="Comment body (Markdown)")],
) -> dict[str, Any]:
    """Add a comment to an existing issue. Returns the created Comment object."""
    return await get_client().post_json(
        f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
        json={"body": body},
    )
