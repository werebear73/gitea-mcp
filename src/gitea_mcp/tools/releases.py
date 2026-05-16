"""MCP tools for Gitea releases."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from gitea_mcp.server import get_client, mcp


@mcp.tool()
async def list_releases(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    page: Annotated[int, Field(description="Page number (1-indexed)")] = 1,
    limit: Annotated[int, Field(description="Items per page (max 50)")] = 30,
) -> list[dict[str, Any]]:
    """List releases for a repository."""
    raise NotImplementedError(
        "Phase 1 Pass B: implement against GET /repos/{owner}/{repo}/releases"
    )


@mcp.tool()
async def create_release(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    tag_name: Annotated[
        str,
        Field(
            description="Tag this release is based on. If absent, the tag is created."
        ),
    ],
    name: Annotated[str, Field(description="Release title")],
    body: Annotated[str, Field(description="Release notes (Markdown)")] = "",
    target_commitish: Annotated[
        str | None,
        Field(
            description=(
                "Branch name or commit SHA the tag points at. "
                "Defaults to the repository's default branch."
            ),
        ),
    ] = None,
    draft: Annotated[
        bool,
        Field(description="Save as draft without publishing"),
    ] = False,
    prerelease: Annotated[
        bool,
        Field(description="Mark as a pre-release"),
    ] = False,
) -> dict[str, Any]:
    """Create a new release in a repository."""
    raise NotImplementedError(
        "Phase 1 Pass B: implement against POST /repos/{owner}/{repo}/releases"
    )
