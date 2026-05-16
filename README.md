# gitea-mcp

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
| Repos | `list_repos`, `list_labels`, `list_milestones` |
| Releases | `list_releases`, `create_release` |

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

Add `gitea-mcp` to your MCP client configuration:

```json
{
  "mcpServers": {
    "gitea": {
      "command": "gitea-mcp",
      "env": {
        "GITEA_URL": "https://your-gitea-instance.example.com",
        "GITEA_TOKEN": "your-personal-access-token"
      }
    }
  }
}
```

See [`mcp.json`](mcp.json) for a complete example. The same shape works for Claude Desktop, VS Code, Cowork, Claude Code, and any other MCP-compatible client.

## Configuration

Configuration is read from environment variables.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `GITEA_URL` | Yes | — | Base URL of your Gitea instance (e.g., `https://gitea.example.com`) |
| `GITEA_TOKEN` | Yes | — | Personal Access Token from your Gitea user settings |
| `GITEA_TIMEOUT` | No | `30` | HTTP request timeout in seconds |

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
pytest
```

## Versioning

Semantic versioning, derived from git tags via `setuptools_scm`. See [`VERSIONING.md`](VERSIONING.md) for the release process.

## Contributing

Issues and pull requests welcome. For substantial changes, please open an issue first to discuss the approach.

## License

[MIT](LICENSE) — use it however you like, including commercial products.

---

Built by [Waretech Services](https://waretech.services).
