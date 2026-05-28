# Publishing (Smithery + MCP Registry)

This project now includes the baseline assets needed for both publishing tracks:

- MCP Registry metadata file: `server.json`
- MCP ownership marker for PyPI verification: `mcp-name` in `README.md`

This runbook covers the manual, account-scoped steps that must be executed by a maintainer.

## Smithery URL Publishing

Reference: https://smithery.ai/docs/build/publish

1. Deploy `gitea-mcp` in HTTP mode to a public HTTPS endpoint.

```bash
gitea-mcp serve --transport http --host 0.0.0.0 --port 8000 --path /mcp
```

2. Put the endpoint behind TLS (for example, `https://<your-domain>/mcp`).
3. Open https://smithery.ai/new and publish using the public URL.
4. If scanning fails with `403`, allow Smithery's crawler (`User-Agent: SmitheryBot/1.0 (+https://smithery.ai)`) in your WAF/CDN rules.
5. Complete verification in Smithery server settings.

Notes:
- URL publishing expects streamable HTTP transport.
- If your endpoint requires auth, follow MCP auth semantics (`401` for unauthenticated discovery, not `403`).

## MCP Registry Publishing

References:
- Quickstart: https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx
- Package types: https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx

### 1. Verify local metadata

- `server.json` exists at repo root and uses server name `io.github.werebear73/gitea-mcp`.
- `README.md` contains a hidden marker:

```markdown
<!-- mcp-name: io.github.werebear73/gitea-mcp -->
```

This marker is used by the MCP Registry to verify ownership for PyPI package listings.

### 2. Keep versions in sync before publishing

Before running `mcp-publisher publish`, update the version values in:

- `server.json` top-level `version`
- `server.json` packages[0].version

They should match the release being published.

### 3. Install and authenticate `mcp-publisher`

```powershell
# Windows (amd64/arm64 auto-select)
$arch = if ([System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -eq "Arm64") { "arm64" } else { "amd64" }
Invoke-WebRequest -Uri "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_windows_$arch.tar.gz" -OutFile "mcp-publisher.tar.gz"
tar xf mcp-publisher.tar.gz mcp-publisher.exe
# Move mcp-publisher.exe to a directory in PATH
```

```bash
mcp-publisher login github
```

### 4. Publish

From repo root:

```bash
mcp-publisher publish
```

### 5. Verify listing

```bash
curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.werebear73/gitea-mcp"
```

## Maintenance Checklist

- Update `server.json` version fields on each release.
- Keep `README.md` `mcp-name` marker unchanged unless the registry server name changes.
- If package name or namespace changes, update both `server.json` and README marker together.
