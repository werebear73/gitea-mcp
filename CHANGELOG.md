# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial project scaffolding.
- MVP tool surface (stubs, not yet implemented): `create_issue`, `list_issues`, `get_issue`, `update_issue`, `add_comment`, `list_repos`, `list_labels`, `list_milestones`, `list_releases`, `create_release`.
- `GiteaClient` async HTTP wrapper skeleton (PAT auth via `Authorization: token <PAT>`, httpx, raises typed errors).
- `Config` dataclass loading from `GITEA_URL` / `GITEA_TOKEN` / `GITEA_TIMEOUT` environment variables.
- `gitea-mcp` console-script entry point.
- `setuptools_scm` tag-driven versioning.
- `mcp.json` template for MCP client configuration.
- `README.md` with quick start, configuration, and tool reference.
- `VERSIONING.md` documenting the semver / tag / release flow.
- GitHub Actions workflows: CI (lint + type-check + tests on Python 3.11/3.12/3.13) and Release (publish to PyPI on `v*` tag push).
- Smoke test asserting the package imports and all tool modules register without error.
