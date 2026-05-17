# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Empty tools list when launched via `python -m gitea_mcp.server`.** The
  `FastMCP` singleton lived in `gitea_mcp.server`, which Python loads twice
  when invoked via `-m` (once as `__main__`, once under its real name when a
  tool module imports `from gitea_mcp.server import mcp`). The tool decorators
  registered against the second instance while the entry point ran the first,
  resulting in `tools/list` returning `[]`. The singleton has moved to a new
  internal module `gitea_mcp._app`, which loads exactly once regardless of how
  the entry point is invoked. Tool modules now import `mcp` and `get_client`
  from `gitea_mcp._app`. `tests/test_subprocess_launch.py` spawns the real
  entry point and asserts all 10 tools are exposed, locking the fix in.

### Added

- **`gitea-mcp init` subcommand:** interactive setup that writes (or merges into) the user's `claude_desktop_config.json`, removing the need to hand-edit JSON or look up the Claude Desktop config location per OS. Prompts for the Gitea URL and Personal Access Token, performs a `GET /api/v1/user` connection check, backs up the existing config to a timestamped `.bak.*` file, and merges a `gitea` entry under `mcpServers` (preserving any other servers already configured). The launch `command` written to the config is auto-detected: the absolute path to the `gitea-mcp` console script if it's on PATH (most reliable on Windows where Claude Desktop's PATH differs from the user's shell), or `sys.executable -m gitea_mcp.server` as a fallback; `--command uvx` opts into the post-PyPI `uvx gitea-mcp` form. Non-interactive use is supported via `--url`, `--token`, and `--yes`. `--name` lets users with multiple Gitea instances pick a unique server key. `--config-path` overrides the default OS-specific path. `--skip-check` bypasses the connection check.
- Initial project scaffolding.
- **Issue tools fully implemented:** `create_issue`, `list_issues`, `get_issue`, `update_issue`, `add_comment`. Label names are resolved to Gitea label IDs automatically (Gitea's issue API requires IDs, not names); unknown label names fail cleanly with the list of valid names. `get_issue` returns the issue object plus a `comments_list` field with the full comment thread. `update_issue` supports replace-semantics for labels and assignees, milestone clearing via `milestone=0`, and atomic partial updates of any combination of title/body/state/labels/assignees/milestone.
- **Repo metadata tools fully implemented:** `list_repos`, `list_labels`, `list_milestones`. `list_repos` handles three modes — authenticated-user (no owner), user-owned, or organization-owned — with automatic fallback from the user endpoint to the org endpoint on 404 so callers don't need to know which it is. `list_labels` and `list_milestones` are straightforward paginated reads.
- **Release tools fully implemented:** `list_releases`, `create_release`. `create_release` includes a warning in its docstring about Gitea's side-effect behavior of creating the underlying git tag even for drafts. All MVP fields supported: `tag_name`, `name`, `body`, `target_commitish`, `draft`, `prerelease`.
- `GiteaClient` async HTTP wrapper (PAT auth via `Authorization: token <PAT>`, httpx, raises typed errors). Supports GET, POST, PUT, PATCH, DELETE.
- `Config` dataclass loading from `GITEA_URL` / `GITEA_TOKEN` / `GITEA_TIMEOUT` environment variables.
- `gitea-mcp` console-script entry point.
- `setuptools_scm` tag-driven versioning.
- `mcp.json` template for MCP client configuration.
- `README.md` with quick start, configuration, and tool reference.
- `VERSIONING.md` documenting the semver / tag / release flow.
- GitHub Actions workflows: CI (lint + type-check + tests on Python 3.11/3.12/3.13) and Release (publish to PyPI on `v*` tag push).
- Unit test suite using `pytest-httpx` to mock the Gitea API. Issue tools have full coverage (12 tests); repo and release tools covered only by smoke tests pending Pass B-2/B-3.
