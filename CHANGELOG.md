# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial project scaffolding.
- **Issue tools fully implemented:** `create_issue`, `list_issues`, `get_issue`, `update_issue`, `add_comment`. Label names are resolved to Gitea label IDs automatically (Gitea's issue API requires IDs, not names); unknown label names fail cleanly with the list of valid names. `get_issue` returns the issue object plus a `comments_list` field with the full comment thread. `update_issue` supports replace-semantics for labels and assignees, milestone clearing via `milestone=0`, and atomic partial updates of any combination of title/body/state/labels/assignees/milestone.
- **Repo metadata tools fully implemented:** `list_repos`, `list_labels`, `list_milestones`. `list_repos` handles three modes — authenticated-user (no owner), user-owned, or organization-owned — with automatic fallback from the user endpoint to the org endpoint on 404 so callers don't need to know which it is. `list_labels` and `list_milestones` are straightforward paginated reads.
- Release tool stubs (not yet implemented): `list_releases`, `create_release`.
- `GiteaClient` async HTTP wrapper (PAT auth via `Authorization: token <PAT>`, httpx, raises typed errors). Supports GET, POST, PUT, PATCH, DELETE.
- `Config` dataclass loading from `GITEA_URL` / `GITEA_TOKEN` / `GITEA_TIMEOUT` environment variables.
- `gitea-mcp` console-script entry point.
- `setuptools_scm` tag-driven versioning.
- `mcp.json` template for MCP client configuration.
- `README.md` with quick start, configuration, and tool reference.
- `VERSIONING.md` documenting the semver / tag / release flow.
- GitHub Actions workflows: CI (lint + type-check + tests on Python 3.11/3.12/3.13) and Release (publish to PyPI on `v*` tag push).
- Unit test suite using `pytest-httpx` to mock the Gitea API. Issue tools have full coverage (12 tests); repo and release tools covered only by smoke tests pending Pass B-2/B-3.
