# gitea-mcp MCPB bundle source

Source files for the `gitea-mcp.mcpb` distributable, the [MCP Bundle](https://github.com/anthropics/dxt) format Claude Desktop uses for drag-and-drop install. The format was previously called `.dxt`; Anthropic renamed it to `.mcpb` upstream.

The bundle is built and attached to each GitHub Release automatically by [`.github/workflows/release.yml`](../.github/workflows/release.yml). You don't normally need to build it by hand.

## What's in here

| File | Purpose |
| --- | --- |
| `manifest.json` | Bundle metadata: `manifest_version: 0.4`, `server.type: uv` (host manages Python + deps), `user_config` declares `GITEA_URL` + `GITEA_TOKEN` prompts. |
| `server/main.py` | Thin entry point — imports and runs `gitea_mcp.server.main`. |
| `pyproject.toml` | Declares the runtime dependency `gitea-mcp>=<version>`; the UV runtime resolves it from PyPI at install time. |
| `.mcpbignore` | Excludes `.venv`, `__pycache__`, `server/lib/` from the packed bundle. |

## How it works at install time

1. User drags `gitea-mcp.mcpb` into Claude Desktop.
2. Claude Desktop prompts for `Gitea URL` and `Personal Access Token` (the `user_config` fields). The token is marked `sensitive` so input is masked and stored encrypted.
3. The UV runtime resolves `gitea-mcp>=<version>` from PyPI and provisions an isolated environment.
4. Claude Desktop launches `server/main.py` over stdio with `GITEA_URL` and `GITEA_TOKEN` set in the process environment.

No global Python install required on the user's machine — the UV runtime ships with Claude Desktop.

## Build locally

```bash
npm install -g @anthropic-ai/mcpb
cd mcpb
mcpb pack
# Heads-up: the mcpb CLI writes <directory-name>.mcpb (i.e. `mcpb.mcpb`) and
# misleadingly prints "filename: gitea-mcp-<version>.mcpb" in its summary.
# Rename to the user-facing form before distributing:
mv mcpb.mcpb "gitea-mcp-$(jq -r .version manifest.json).mcpb"
# (the release-mcpb CI job does this automatically)
```

## Release process

On `v*` tag push, the `release-mcpb` job in [`.github/workflows/release.yml`](../.github/workflows/release.yml):

1. Waits for the PyPI `publish` job to complete (the bundle's UV runtime needs the wheel on PyPI at install time).
2. Syncs `manifest.json` `version` and `pyproject.toml` `version` + `gitea-mcp` pin from the tag.
3. Runs `mcpb pack`.
4. Attaches the resulting `.mcpb` to the GitHub Release.

The `version` literals in this directory's `manifest.json` and `pyproject.toml` track the **last released** version — they get bumped each release the same way [`server.json`](../server.json) does. See [`docs/PUBLISHING.md`](../docs/PUBLISHING.md) for the full release flow.
