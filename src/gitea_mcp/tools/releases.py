"""MCP tools for Gitea releases."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from gitea_mcp._app import get_client, mcp


@mcp.tool()
async def list_releases(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    page: Annotated[int, Field(description="Page number (1-indexed)")] = 1,
    limit: Annotated[int, Field(description="Items per page (max 50)")] = 30,
) -> list[dict[str, Any]]:
    """List releases for a repository.

    Returns the standard Gitea Release object array, including drafts and
    pre-releases. Sort order is newest first.
    """
    client = get_client()
    releases: list[dict[str, Any]] = await client.get(
        f"/repos/{owner}/{repo}/releases",
        params={"page": page, "limit": limit},
    )
    return releases


@mcp.tool()
async def create_release(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    tag_name: Annotated[
        str,
        Field(
            description=(
                "Tag this release is based on. If the tag does not already exist "
                "in the repository, Gitea creates it at the time of release."
            ),
        ),
    ],
    name: Annotated[str, Field(description="Release title")],
    body: Annotated[str, Field(description="Release notes in Markdown")] = "",
    target_commitish: Annotated[
        str | None,
        Field(
            description=(
                "Branch name or commit SHA the tag should point at. "
                "Defaults to the repository's default branch. "
                "Ignored if the tag already exists."
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
    """Create a new release in a repository.

    .. warning::

       Side effects: if ``tag_name`` does not already exist in the repository,
       Gitea creates the tag at the current ``target_commitish`` (or default
       branch). Creating a draft does NOT skip tag creation — both drafts and
       published releases will leave a tag in the repo.
    """
    client = get_client()
    payload: dict[str, Any] = {
        "tag_name": tag_name,
        "name": name,
        "body": body,
        "draft": draft,
        "prerelease": prerelease,
    }
    if target_commitish is not None:
        payload["target_commitish"] = target_commitish
    release: dict[str, Any] = await client.post(
        f"/repos/{owner}/{repo}/releases", json=payload
    )
    return release
