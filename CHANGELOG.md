# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.2] - 2026-05-18

Closes out the two items deferred from v0.2.1.

### Added

- **MCP `ToolAnnotations` on all 10 tools** (restored — see v0.2.1 `### Deferred`). Read tools (`list_issues`, `get_issue`, `list_repos`, `list_labels`, `list_milestones`, `list_releases`) have `readOnlyHint=True` so MCP clients can auto-approve them. Write tools (`create_issue`, `add_comment`, `create_release`) have `readOnlyHint=False` with `destructiveHint=False`. `update_issue` has `destructiveHint=True` because closing an issue and clearing labels are reversible-but-user-visible side effects worth gating on confirmation. All tools have `openWorldHint=True` (they hit a remote Gitea instance). The v0.2.1 investigation cleared annotations of any blame for the subprocess test failure — that was always a test-side stdin race.

### Fixed

- **`tests/test_subprocess_launch.py` rewritten** to use a reader thread + queue instead of `subprocess.Popen.communicate()`. The old pattern wrote all JSON-RPC messages then immediately closed stdin; FastMCP 2.x's stdio reader sometimes saw EOF and shut down before processing the queued `tools/list` call. The new pattern keeps stdin open until the `tools/list` response (id=2) arrives in the queue, then closes stdin and waits for the server to exit cleanly. Removes the `xfail` marker — the test now passes deterministically on both Windows and Linux CI, restoring the dual-load regression guard.

## [0.2.1] - 2026-05-17

> Note on version numbering: This is the **first published** 0.2.x release.
> The `v0.2.0` git tag was initially placed on the `v0.1.2` commit due to a
> failed-commit-but-tag-pushed-anyway slip. The release workflow built and
> uploaded `gitea_mcp-0.2.0-py3-none-any.whl` (containing v0.1.2's code with
> a 0.2.0 version label) before reporting `400 Bad Request`. PyPI's file-name
> reuse policy then permanently blocked re-uploading `0.2.0` with the correct
> code, so we skip to `0.2.1`. The bad `0.2.0` upload has been yanked.

Hardening release. No new tools or user-facing CLI surface; this is foundational work that the next round of tool additions (Phase 2 PR reads, Phase 3 file ops) will build on. The minor-version bump reflects the change to the `GiteaClient` public surface — new typed verb methods are added, and the constructor accepts two new optional parameters. Existing callers using the untyped verbs continue to work unchanged.

### Added

- **Typed verb methods on `GiteaClient`:** `get_json`, `get_list`, `post_json`, `patch_json`, `put_json`, `put_list`. Each wraps the corresponding untyped verb and asserts the response shape, raising `GiteaError` on mismatch. Lets tool implementations return their result directly without the typed-intermediate variable pattern that PR #4 had to apply to every tool to satisfy strict mypy. The 10 existing tools have been migrated to use the typed wrappers; the untyped `get` / `post` / etc. remain for cases that don't care about the shape.
- **Retry-with-backoff in `GiteaClient`:** transient failures on idempotent methods (`GET`, `PUT`, `DELETE`) now retry automatically. Retries on `502` / `503` / `504` responses and on `httpx.ConnectError` / `ReadTimeout` / `WriteTimeout`. `429 Too Many Requests` is retried for **any** method, honoring the `Retry-After` header if present. `POST` and `PATCH` are deliberately **not** retried on 5xx or network errors (could create duplicate issues, comments, or releases). Exponential backoff with jitter, capped at 4 seconds. Configurable via `GITEA_MAX_RETRIES` (default `3`; set to `0` to disable) and `GITEA_RETRY_BASE_DELAY` (default `0.5`).
- **Two-stage pre-commit hook config** (`.pre-commit-config.yaml`): `ruff` + `mypy` on the `commit` stage (fast — keeps the commit loop snappy); `pytest` + `python -m build && twine check dist/*` on the `pre-push` stage (catches the build-time `setuptools_scm` surprises that bit `v0.1.0`'s accidental `.dev0` publish). New dev dependencies: `pre-commit`, `build`, `twine`. README's Development section documents the install steps.
- Two new env vars on `Config`: `GITEA_MAX_RETRIES` and `GITEA_RETRY_BASE_DELAY` (see Retry above).

### Deferred

- **MCP `ToolAnnotations` on the 10 tools.** Initially included in this release; reverted before tag because they triggered an investigation into the subprocess regression test (see next bullet). Annotations themselves are not at fault — the test was already racing on FastMCP 2.x. Will revisit alongside the test rewrite in v0.2.2.
- **`tests/test_subprocess_launch.py` marked `xfail`.** The test uses `subprocess.Popen.communicate()` which closes stdin after writing the full payload. FastMCP 2.x's stdio reader sometimes sees EOF and shuts down before processing the queued `tools/list` call. The test passes intermittently in isolation but fails consistently in the full suite (both Windows and Linux CI). Needs a rewrite using a writer thread that keeps stdin open until the response arrives. Tracked for v0.2.2; the dual-load bug the test guards against is still verifiable end-to-end via `uvx gitea-mcp` against a real MCP client.

### Changed

- `GiteaClient.__init__` accepts two new optional keyword arguments: `max_retries` (default `3`) and `retry_base_delay` (default `0.5`). Existing callers are unaffected — both have defaults that match the previous behavior of "no retries, no backoff" plus the new retry policy.
- All 10 tool implementations now use the typed verb wrappers (`get_json`, `get_list`, `post_json`, `patch_json`, `put_list`) instead of the typed-intermediate-variable pattern. Behaviorally identical from the MCP client's perspective.
- **Pinned `fastmcp` to `>=2.0,<3.0`.** FastMCP 3.x introduced stdin/EOF-handling changes that drop messages queued behind `notifications/initialized` when the client closes stdin (e.g. an immediately-following `tools/list` call), which breaks the subprocess regression test that guards the dual-load fix. Migration to FastMCP 3.x is tracked as a separate v0.3.0 task.

## [0.1.2] - 2026-05-17

### Added

- **`gitea-mcp doctor` subcommand:** preflight check that verifies `GITEA_URL` + Personal Access Token against the Gitea instance (via `GET /api/v1/user`) and then imports every tool module to confirm the MCP surface loads cleanly. Reuses the `check_connection()` helper introduced for `init`. Reads `GITEA_URL` / `GITEA_TOKEN` from environment by default; `--url` and `--token` flags override. Exits `0` on success, `1` on connection or load failure, `2` on missing configuration. Useful before wiring Claude Desktop at the server, or when an MCP client reports an empty tools list and you need to know whether the problem is the connection or the integration.
- Top-level CLI now supports `--help` / `-h` (lists subcommands with a one-line description of each) and `--version` / `-V` (prints `gitea-mcp <version>`).

### Fixed

- **`gitea-mcp --help` previously started the server instead of printing help.** The v0.1.1 top-level dispatcher only intercepted `init` and let everything else (including `--help`) reach `_run_server()`. On a system with `GITEA_URL` + `GITEA_TOKEN` already in the environment the server would actually start; without them it crashed with a confusing "GITEA_URL is required" message instead of usage text. The new dispatcher in `server.py:main()` handles `--help` / `--version` / `init` / `doctor` explicitly, errors on unknown subcommands with exit `2`, and preserves the no-args behavior (Claude Desktop's launch invocation is byte-identical, and the `tests/test_subprocess_launch.py` regression test continues to pass).

## [0.1.1] - 2026-05-17

> Note on version numbering: The `v0.1.0` tag fired the release workflow and
> published to PyPI as `0.1.1.dev0` rather than `0.1.0`, because
> `src/gitea_mcp/_version.py` was committed to git — `setuptools_scm`
> regenerates that file on every build and saw the regeneration as a "dirty"
> working tree, which bumps the version to the next patch with a `.devN`
> suffix. The file is now `.gitignore`d. The `0.1.1.dev0` release on PyPI
> has been yanked. This `0.1.1` release is the real first published build.

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
- Unit test suite using `pytest-httpx` to mock the Gitea API: full coverage for all 10 MVP tools plus the `init` subcommand and a subprocess-launch regression test guarding the dual-load fix. 49 tests total.
