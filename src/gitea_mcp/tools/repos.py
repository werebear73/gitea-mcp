"""MCP tools for Gitea repository metadata."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from gitea_mcp._app import get_client, mcp
from gitea_mcp.client import GiteaAPIError


@mcp.tool()
async def list_repos(
    owner: Annotated[
        str | None,
        Field(
            description=(
                "Username or organization to list repos for. "
                "Leave empty to list repositories accessible to the authenticated user."
            ),
        ),
    ] = None,
    page: Annotated[int, Field(description="Page number (1-indexed)")] = 1,
    limit: Annotated[int, Field(description="Items per page (max 50)")] = 30,
) -> list[dict[str, Any]]:
    """List repositories.

    Three modes:

    - ``owner`` empty: returns repositories accessible to the authenticated user
      (``GET /user/repos``).
    - ``owner`` is a user: returns that user's repositories
      (``GET /users/{owner}/repos``).
    - ``owner`` is an organization: returns that org's repositories
      (``GET /orgs/{owner}/repos`` — automatically tried as a fallback when the
      user endpoint 404s, so callers don't need to know which it is).
    """
    client = get_client()
    params: dict[str, Any] = {"page": page, "limit": limit}

    if not owner:
        return await client.get_list("/user/repos", params=params)

    try:
        return await client.get_list(f"/users/{owner}/repos", params=params)
    except GiteaAPIError as e:
        if e.status_code == 404:
            # Owner is likely an organization — fall back transparently.
            return await client.get_list(f"/orgs/{owner}/repos", params=params)
        raise


@mcp.tool()
async def list_labels(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    page: Annotated[int, Field(description="Page number (1-indexed)")] = 1,
    limit: Annotated[int, Field(description="Items per page (max 50)")] = 30,
) -> list[dict[str, Any]]:
    """List labels defined in a repository.

    Returns the standard Gitea Label object: ``{id, name, color, description, ...}``.
    Use the ``id`` values when calling tools that take ``label_ids`` directly;
    most tools accept label *names* and resolve to IDs internally.
    """
    return await get_client().get_list(
        f"/repos/{owner}/{repo}/labels",
        params={"page": page, "limit": limit},
    )


@mcp.tool()
async def list_milestones(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    state: Annotated[
        str, Field(description="Filter by state: 'open', 'closed', or 'all'")
    ] = "open",
    page: Annotated[int, Field(description="Page number (1-indexed)")] = 1,
    limit: Annotated[int, Field(description="Items per page (max 50)")] = 30,
) -> list[dict[str, Any]]:
    """List milestones in a repository, optionally filtered by state."""
    return await get_client().get_list(
        f"/repos/{owner}/{repo}/milestones",
        params={"state": state, "page": page, "limit": limit},
    )
