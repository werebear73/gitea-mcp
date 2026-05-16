"""MCP tools for Gitea issues."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from gitea_mcp.server import get_client, mcp


@mcp.tool()
async def create_issue(
    owner: Annotated[str, Field(description="Repository owner (user or organization name)")],
    repo: Annotated[str, Field(description="Repository name")],
    title: Annotated[str, Field(description="Issue title")],
    body: Annotated[str, Field(description="Issue body in Markdown")] = "",
    labels: Annotated[
        list[str] | None,
        Field(description="Label names to apply to the new issue"),
    ] = None,
    assignees: Annotated[
        list[str] | None,
        Field(description="Usernames to assign to the new issue"),
    ] = None,
    milestone: Annotated[int | None, Field(description="Milestone ID to attach")] = None,
) -> dict[str, Any]:
    """Create a new issue in a Gitea repository."""
    raise NotImplementedError(
        "Phase 1 Pass B: implement against POST /repos/{owner}/{repo}/issues"
    )


@mcp.tool()
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
    """List issues in a Gitea repository with optional filters."""
    raise NotImplementedError(
        "Phase 1 Pass B: implement against GET /repos/{owner}/{repo}/issues"
    )


@mcp.tool()
async def get_issue(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    issue_number: Annotated[int, Field(description="Issue number (the #N in the URL)")],
) -> dict[str, Any]:
    """Get a single issue by number, including its comments."""
    raise NotImplementedError(
        "Phase 1 Pass B: implement against GET /repos/{owner}/{repo}/issues/{index}"
    )


@mcp.tool()
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
        Field(description="Replace labels with this exact set"),
    ] = None,
    assignees: Annotated[
        list[str] | None,
        Field(description="Replace assignees with this exact set"),
    ] = None,
    milestone: Annotated[
        int | None,
        Field(description="Milestone ID to attach; 0 to clear the milestone"),
    ] = None,
) -> dict[str, Any]:
    """Update an existing issue's title, body, state, labels, assignees, or milestone."""
    raise NotImplementedError(
        "Phase 1 Pass B: implement against PATCH /repos/{owner}/{repo}/issues/{index}"
    )


@mcp.tool()
async def add_comment(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    issue_number: Annotated[int, Field(description="Issue number")],
    body: Annotated[str, Field(description="Comment body (Markdown)")],
) -> dict[str, Any]:
    """Add a comment to an existing issue."""
    raise NotImplementedError(
        "Phase 1 Pass B: implement against POST /repos/{owner}/{repo}/issues/{index}/comments"
    )
