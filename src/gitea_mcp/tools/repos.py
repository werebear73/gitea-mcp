"""MCP tools for Gitea repository metadata."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from gitea_mcp.server import get_client, mcp


@mcp.tool()
async def list_repos(
    owner: Annotated[
        str | None,
        Field(
            description=(
                "Username or organization to list repos for. "
                "Leave empty to list repos accessible to the authenticated user."
            ),
        ),
    ] = None,
    page: Annotated[int, Field(description="Page number (1-indexed)")] = 1,
    limit: Annotated[int, Field(description="Items per page (max 50)")] = 30,
) -> list[dict[str, Any]]:
    """List repositories.

    If ``owner`` is empty, returns repositories accessible to the authenticated user.
    Otherwise lists repositories owned by the named user or organization.
    """
    raise NotImplementedError(
        "Phase 1 Pass B: implement against GET /user/repos (no owner), "
        "GET /users/{owner}/repos (user), or GET /orgs/{owner}/repos (org)."
    )


@mcp.tool()
async def list_labels(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
) -> list[dict[str, Any]]:
    """List labels defined in a repository."""
    raise NotImplementedError(
        "Phase 1 Pass B: implement against GET /repos/{owner}/{repo}/labels"
    )


@mcp.tool()
async def list_milestones(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    state: Annotated[
        str, Field(description="Filter by state: 'open', 'closed', or 'all'")
    ] = "open",
) -> list[dict[str, Any]]:
    """List milestones in a repository."""
    raise NotImplementedError(
        "Phase 1 Pass B: implement against GET /repos/{owner}/{repo}/milestones"
    )
