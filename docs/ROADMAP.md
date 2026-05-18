# gitea-mcp Roadmap

A public-facing view of what's shipped, what's actively in flight, and what's planned. For the day-to-day project tracker see [CHANGELOG.md](../CHANGELOG.md).

Items marked **shipped** are live on [PyPI](https://pypi.org/project/gitea-mcp/) and reflected in the current version. Items in **Next up** are the near-term work queue. **Future** items are committed in principle but not yet scheduled. **Considered, not committed** are ideas being weighed but may never ship.

This roadmap is non-binding — priorities can shift as user needs emerge. PRs welcome on anything here.

---

## Shipped

### v0.5.x (current)

- **Streamable-HTTP transport via `gitea-mcp serve`** — self-host one instance for multiple MCP clients to share. CLI flags + env vars (`GITEA_MCP_TRANSPORT`, `GITEA_MCP_HOST`, `GITEA_MCP_PORT`, `GITEA_MCP_PATH`). Single-user auth model.
- **Server introspection** — `get_server_info` and `get_server_version` MCP tools so clients can ask the server about itself (which gitea-mcp version, which Gitea instance, which authenticated user).

### v0.4.x

- **File operations and PR creation** — `read_file`, `create_branch`, `commit_changes` (auto-detects create vs update), `create_pr`. Enables LLMs to change code, not just discuss it.

### v0.3.x

- **Branches and PR reads** — `list_branches`, `list_pull_requests`, `get_pull_request` (with comments), `add_comment_on_pr`.

### v0.2.x

- **Hardened client** — typed verb methods on `GiteaClient` (`get_json` / `get_list` / `post_json` / `patch_json` / `put_json` / `put_list`) with defensive shape checks; retry-with-backoff on idempotent methods (GET/PUT/DELETE on 502/503/504 + network errors) honoring `Retry-After` on 429.
- **MCP tool annotations** on every tool (`readOnlyHint`, `destructiveHint`, `openWorldHint`) so clients can auto-approve safe calls and gate destructive ones.
- **Two-stage pre-commit hooks** — ruff + mypy on commit, pytest + build/twine check on push.

### v0.1.x

- **MVP tool surface** — 10 tools covering issues (`create_issue`, `list_issues`, `get_issue`, `update_issue`, `add_comment`), repository metadata (`list_repos`, `list_labels`, `list_milestones`), and releases (`list_releases`, `create_release`).
- **Setup + diagnostics CLI** — `gitea-mcp init` writes the MCP client config interactively; `gitea-mcp doctor` verifies the connection.
- **PyPI publishing via PyPI Trusted Publishing** with sigstore attestations.

---

## Next up

Near-term work, committed in principle:

- **`merge_pr` tool** — close the write-side PR workflow. Today you can `create_pr` and `add_comment_on_pr` but not actually merge. Add a tool that calls `POST /repos/{owner}/{repo}/pulls/{pull_number}/merge` with merge-style options (`merge`, `rebase`, `rebase-merge`, `squash`), optional merge commit message and title. Likely tagged `destructiveHint=True` so MCP clients gate it on user confirmation.
- **Smithery URL publishing** — list gitea-mcp on [smithery.ai](https://smithery.ai) using the streamable-HTTP transport added in v0.5.0. Provides distribution, analytics, and auto-generated OAuth UI for new users.
- **Official MCP Registry listing** — list gitea-mcp on [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io) (the Linux Foundation MCP project's canonical catalog).

---

## Future

Committed for some later release, not yet scheduled:

- **Dockerfile + `docker-compose.yml`** — make self-hosting the HTTP transport a one-liner.
- **`.mcpb` Desktop Extension bundle** — Anthropic's drag-and-drop installer format for local stdio use. Complements (doesn't replace) the `uvx gitea-mcp` install path.
- **Multi-tenant auth for HTTP transport** — bring-your-own-token model so a single hosted instance can serve multiple users, each with their own Gitea credentials. Likely involves the MCP OAuth flow + per-request `GiteaClient`. Real auth-integration project.
- **`search_issues` / `search_repos`** — wrap Gitea's search API for "any open issue about X?" / "is there a repo called Y?" queries.
- **Forgejo / Codeberg test matrix in CI** — gitea-mcp works against both today (the API is compatible), but it's worth proving via CI.
- **MkDocs documentation site** — promote the README + roadmap + tool reference into a proper docs site.

---

## Considered, not committed

Ideas in the air. May or may not ever ship — listed here so they're not lost.

- **Webhook receiver helpers** — let an LLM react to Gitea webhook events (new issue, PR opened) rather than just polling. Speculative; depends on a real consumer asking.
- **Inline PR review comments** — read/write diff-line comments via `/pulls/{n}/reviews` endpoints. Different shape from conversation comments; only useful if an LLM is doing actual code review.
- **Repository creation / deletion tools** — `create_repo`, `delete_repo`, `fork_repo`. Useful but destructive — would need careful annotation design.
- **Gitea Actions integration** — list / inspect / re-run workflow runs. Big surface; would only ship if there's clear demand.

---

## Out of scope

Things explicitly *not* planned, with reasoning:

- **Wrapping the full Gitea admin API** (user creation, org management, system-level operations). gitea-mcp is for *developer workflow* tools, not server administration. Admin tooling is a different audience.
- **Embedding a Gitea client library for Python** — gitea-mcp is an MCP server, not a general-purpose Gitea SDK. If you want to call Gitea from Python directly, use the lower-level Gitea REST API or community libraries like `pygitea`.
- **GitHub / GitLab / Bitbucket support in the same package.** Cross-host abstraction sounds nice but ends up being lowest-common-denominator. Separate `github-mcp` / `gitlab-mcp` servers exist or could exist.

---

## How to influence this roadmap

- **Open an issue** at https://github.com/werebear73/gitea-mcp/issues with the use case you're trying to solve. "I'm trying to do X and it would help if Y" is more useful than "please add feature Y."
- **Open a PR** with the change if you've already built it. See [CHANGELOG.md](../CHANGELOG.md) and `tests/` for the style.
- **Discussions** for broader "should we...?" conversations welcome via the same issue tracker.
