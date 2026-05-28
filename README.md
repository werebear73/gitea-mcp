# gitea-mcp

<!-- mcp-name: io.github.werebear73/gitea-mcp -->

A [Model Context Protocol](https://modelcontextprotocol.io) server for [Gitea](https://gitea.io) — lets AI assistants (Claude, ChatGPT, Copilot, and anything else that speaks MCP) read, create, and manage issues, repositories, and releases on any Gitea instance you can reach.

Also works against **[Forgejo](https://forgejo.org)** and **[Codeberg](https://codeberg.org)** (API-compatible).

## Why

Self-hosted Gitea is a popular GitHub alternative for solo developers, small teams, and privacy-conscious organizations. With this MCP server installed, your AI assistant can:

- File audit findings or refactor notes as Gitea issues without you leaving the chat
- Triage a repo's open issues in natural language
- Cut a release at the end of a coding session
- Comment on issues across multiple repos in one pass

## Features

| Resource | Tools |
| --- | --- |
| Issues | `create_issue`, `list_issues`, `get_issue`, `update_issue`, `add_comment` |
| Repos | `list_repos`, `list_labels`, `list_milestones`, `list_branches` |
| Pulls | `list_pull_requests`, `get_pull_request`, `add_comment_on_pr`, `create_pr`, `merge_pr` |
| Files | `read_file`, `commit_changes`, `create_branch` |
| Releases | `list_releases`, `create_release` |
| Meta | `get_server_info`, `get_server_version` |

- Bearer authentication via Personal Access Token (PAT)
- Async HTTP via `httpx` and `FastMCP`
- Works with self-hosted Gitea, Forgejo, and Codeberg

## Quick Start

### 1. Install

```bash
pip install gitea-mcp
```

Or with [`uv`](https://docs.astral.sh/uv/):

```bash
uv pip install gitea-mcp
```

### 2. Generate a Personal Access Token

In your Gitea instance, go to **Settings → Applications → Generate New Token** and grant at least:

- `read:repository`
- `write:issue`
- `read:user`

Add `write:repository` if you also want to create releases.

### 3. Configure your MCP client

**Claude Desktop (interactive):** run

```bash
gitea-mcp init
```

It prompts for the Gitea URL and Personal Access Token, verifies the connection, and writes (or merges into) the right `claude_desktop_config.json` for your OS. Restart Claude Desktop and you're done.

To check that the server can reach your Gitea instance at any time:

```bash
gitea-mcp doctor
```

`doctor` reads `GITEA_URL` and `GITEA_TOKEN` from the environment, runs a `GET /api/v1/user`, and reports the authenticated username plus the state of the MCP tool surface. Exit `0` = ready; exit `1` = connection/load failure; exit `2` = missing config.

**Any MCP client (manual):** add `gitea-mcp` to the client's MCP config. The recommended form uses `uvx` so the client launches the latest published wheel in an isolated env without needing `gitea-mcp` on its own PATH (this is what `gitea-mcp init` writes):

```json
{
  "mcpServers": {
    "gitea": {
      "command": "uvx",
      "args": ["gitea-mcp"],
      "env": {
        "GITEA_URL": "https://your-gitea-instance.example.com",
        "GITEA_TOKEN": "your-personal-access-token"
      }
    }
  }
}
```

If you'd rather use a globally pip-installed `gitea-mcp` binary, drop `args` and set `command` to `"gitea-mcp"` directly — works as long as the binary is on the MCP client's PATH at launch time.

See [`mcp.json`](mcp.json) for a complete example. The same shape works for Claude Desktop, VS Code, Cowork, Claude Code, and any other MCP-compatible client.

## Configuration

Configuration is read from environment variables.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `GITEA_URL` | Yes | — | Base URL of your Gitea instance (e.g., `https://gitea.example.com`) |
| `GITEA_TOKEN` | Yes | — | Personal Access Token from your Gitea user settings |
| `GITEA_TIMEOUT` | No | `30` | HTTP request timeout in seconds |
| `GITEA_MAX_RETRIES` | No | `3` | Max retries for transient failures on idempotent methods (`GET`/`PUT`/`DELETE`). Set to `0` to disable retries. `POST` and `PATCH` are never auto-retried — they could create duplicate issues, comments, or releases. `429 Too Many Requests` is retried for **any** method, honoring `Retry-After` when present. |
| `GITEA_RETRY_BASE_DELAY` | No | `0.5` | Base delay (seconds) for exponential backoff between retries. Effective delay grows as `base * 2^attempt` with jitter, capped at 4 seconds. |

## Self-hosting / HTTP transport

By default `gitea-mcp` runs in stdio mode — each MCP client (Claude Desktop, Cowork, etc.) launches its own subprocess on demand. For self-hosting one instance that multiple clients connect to over the network, use the streamable-HTTP transport:

```bash
gitea-mcp serve --transport http --host 0.0.0.0 --port 8000 --path /mcp
```

All four flags can also be provided via environment variables (handy for Docker / systemd units):

| Variable                  | Default      | Flag           |
| ------------------------- | ------------ | -------------- |
| `GITEA_MCP_TRANSPORT`     | `stdio`      | `--transport`  |
| `GITEA_MCP_HOST`          | `127.0.0.1`  | `--host`       |
| `GITEA_MCP_PORT`          | `8000`       | `--port`       |
| `GITEA_MCP_PATH`          | `/mcp`       | `--path`       |

MCP clients connect to the resulting URL (e.g. `https://gitea-mcp.example.com/mcp`) just like they would to a local stdio server, except they share the one running instance.

**Auth model (this release).** The server reads `GITEA_TOKEN` from its own environment, so any client that reaches the URL acts as that one Gitea user. Run it for yourself behind your own access controls (firewall, reverse-proxy auth, VPN, Tailscale). Multi-tenant bring-your-own-token is on the roadmap.

The no-args invocation (`gitea-mcp` with no subcommand) still runs in stdio mode, so existing Claude Desktop / Cowork / Claude Code integrations are unaffected by this addition.

## Compatibility

| Server | Status |
| --- | --- |
| Gitea (self-hosted) | ✅ Primary target |
| Forgejo | ✅ Expected to work (API-compatible) |
| Codeberg | ✅ Expected to work (Codeberg runs Forgejo) |

## Development

```bash
git clone https://github.com/werebear73/gitea-mcp.git
cd gitea-mcp
pip install -e ".[dev]"
pre-commit install                       # commit-stage hooks (ruff + mypy)
pre-commit install --hook-type pre-push  # push-stage hooks (pytest + build check)
pytest
```

The two-stage pre-commit policy keeps the commit loop snappy (lint + type only) while making `git push` block on the slow stuff that's actually caught CI/release bugs in the past — the full test suite and `python -m build && twine check dist/*`, which surfaces `setuptools_scm` version surprises before they reach a tag push.

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for what's shipped, what's next, and what's out of scope.

## Publishing

- MCP Registry metadata is tracked in [`server.json`](server.json).
- Smithery + MCP Registry publication steps are documented in [`docs/PUBLISHING.md`](docs/PUBLISHING.md).

## Versioning

Semantic versioning, derived from git tags via `setuptools_scm`. See [`VERSIONING.md`](VERSIONING.md) for the release process.

## Contributing

Issues and pull requests welcome. For substantial changes, please open an issue first to discuss the approach.

## License

[MIT](LICENSE) — use it however you like, including commercial products.

---

Built by [Waretech Services](https://waretech.services).
