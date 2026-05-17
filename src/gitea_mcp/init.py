"""Interactive setup for adding gitea-mcp to Claude Desktop's config.

Run via ``gitea-mcp init``. Prompts for the Gitea instance URL and Personal
Access Token, optionally verifies the connection, then merges a ``gitea``
entry into the user's ``claude_desktop_config.json``. The existing file is
backed up with a timestamped ``.bak.*`` suffix before any write, and other
MCP servers in the same file are preserved.

Non-interactive use: pass ``--url``, ``--token``, and ``--yes`` to skip the
prompts and confirmation (useful for CI or dotfile bootstrap scripts).
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

# ---- Config path detection -------------------------------------------------


def claude_desktop_config_path() -> Path:
    """Return the OS-specific path to Claude Desktop's config file.

    Windows: ``%APPDATA%\\Claude\\claude_desktop_config.json``
    macOS:   ``~/Library/Application Support/Claude/claude_desktop_config.json``
    Linux:   ``~/.config/Claude/claude_desktop_config.json``

    Neither the file nor its parent directory are guaranteed to exist; callers
    must handle creation. The path is returned even on platforms where Claude
    Desktop is not officially supported.
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "Claude" / "claude_desktop_config.json"
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


# ---- Command auto-detection ------------------------------------------------


def detect_command(prefer: str | None = None) -> tuple[str, list[str]]:
    """Choose the ``(command, args)`` pair Claude Desktop should use to launch
    gitea-mcp.

    Resolution order:

    1. If ``prefer == "uvx"``: return ``("uvx", ["gitea-mcp"])`` unconditionally.
    2. If ``gitea-mcp`` is on PATH (the console script installed in a venv):
       return its absolute path. This is the most reliable option on Windows,
       where Claude Desktop's launch environment frequently does not match the
       PATH the user sees in their shell.
    3. Fallback: ``(sys.executable, ["-m", "gitea_mcp.server"])``. Works
       wherever the package itself is importable from the chosen Python.
    """
    if prefer == "uvx":
        return "uvx", ["gitea-mcp"]
    on_path = shutil.which("gitea-mcp")
    if on_path:
        return on_path, []
    return sys.executable, ["-m", "gitea_mcp.server"]


# ---- Connection check ------------------------------------------------------


def check_connection(url: str, token: str, timeout: float = 10.0) -> str:
    """Verify the Gitea URL + PAT by calling ``GET /api/v1/user``.

    Returns the authenticated username on success. Raises ``RuntimeError`` with
    a user-readable message on any failure (network, auth, malformed response).
    """
    base = url.rstrip("/")
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                f"{base}/api/v1/user",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/json",
                },
            )
    except httpx.RequestError as exc:
        raise RuntimeError(f"Could not reach {base}: {exc}") from exc
    if response.status_code == 401:
        raise RuntimeError(
            f"Authentication failed at {base}. Check the Personal Access Token."
        )
    if not response.is_success:
        message = response.text.strip() or response.reason_phrase
        raise RuntimeError(f"{base} returned HTTP {response.status_code}: {message}")
    payload: Any = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("login"), str):
        raise RuntimeError(
            f"{base} responded but the payload did not look like a Gitea user "
            f"object (no 'login' field). Is the URL really a Gitea instance?"
        )
    username: str = payload["login"]
    return username


# ---- Config file manipulation ----------------------------------------------


def load_config(path: Path) -> dict[str, Any]:
    """Read an existing Claude Desktop config; return ``{}`` if missing or empty."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    loaded: Any = json.loads(text)
    if not isinstance(loaded, dict):
        raise RuntimeError(
            f"{path} exists but does not contain a JSON object at the top level."
        )
    result: dict[str, Any] = loaded
    return result


def backup_config(path: Path) -> Path:
    """Copy the existing config aside with a timestamped suffix.

    Returns the backup path. No-op (returns the original path unchanged) if the
    source file does not exist.
    """
    if not path.exists():
        return path
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.bak.{timestamp}")
    shutil.copy2(path, backup)
    return backup


def merge_server_entry(
    config: dict[str, Any],
    *,
    name: str,
    command: str,
    args: list[str],
    env: dict[str, str],
) -> dict[str, Any]:
    """Insert or replace the named server entry under ``mcpServers``.

    Other servers under ``mcpServers`` are preserved. The input dict is mutated
    in place and also returned for convenience.
    """
    servers_obj: Any = config.setdefault("mcpServers", {})
    if not isinstance(servers_obj, dict):
        raise RuntimeError(
            "Existing claude_desktop_config.json has an 'mcpServers' key that "
            "is not a JSON object. Refusing to overwrite — inspect and fix the "
            "file manually."
        )
    servers: dict[str, Any] = servers_obj
    entry: dict[str, Any] = {"command": command, "env": env}
    if args:
        entry["args"] = args
    servers[name] = entry
    return config


def write_config(path: Path, config: dict[str, Any]) -> None:
    """Write the config with two-space indent and a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


# ---- CLI -------------------------------------------------------------------


def _prompt(label: str) -> str:
    """Read a non-empty line from stdin, re-prompting on empty input."""
    while True:
        raw = input(f"{label}: ").strip()
        if raw:
            return raw
        print("  (value is required)")


def run(args: argparse.Namespace) -> int:
    """Execute the init flow. Returns a process exit code."""
    url = (args.url or _prompt("Gitea base URL (e.g. https://gitea.example.com)")).rstrip("/")
    if args.token:
        token = args.token
    else:
        token = getpass.getpass("Personal Access Token (input hidden): ").strip()
        if not token:
            print("Error: no token provided.", file=sys.stderr)
            return 2

    config_path = Path(args.config_path) if args.config_path else claude_desktop_config_path()
    server_name: str = args.name
    prefer = None if args.command == "auto" else args.command
    command, command_args = detect_command(prefer=prefer)

    if not args.skip_check:
        print(f"Checking {url} ...")
        try:
            username = check_connection(url, token)
        except RuntimeError as exc:
            print(f"  Connection check FAILED: {exc}", file=sys.stderr)
            print("  Re-run with --skip-check to write the config anyway.", file=sys.stderr)
            return 1
        print(f"  OK — authenticated as '{username}'.")

    env = {"GITEA_URL": url, "GITEA_TOKEN": token}

    print()
    print(f"Will write the following entry to {config_path}:")
    print(f"  mcpServers.{server_name}.command = {command}")
    if command_args:
        print(f"  mcpServers.{server_name}.args    = {command_args}")
    print(f"  mcpServers.{server_name}.env     = {{GITEA_URL=..., GITEA_TOKEN=***}}")
    if not args.yes:
        confirm = input("Proceed? [y/N]: ").strip().lower()
        if confirm not in {"y", "yes"}:
            print("Aborted.")
            return 0

    try:
        config = load_config(config_path)
    except (json.JSONDecodeError, RuntimeError) as exc:
        print(f"Error reading {config_path}: {exc}", file=sys.stderr)
        return 1

    backup = backup_config(config_path)
    merge_server_entry(
        config,
        name=server_name,
        command=command,
        args=command_args,
        env=env,
    )
    write_config(config_path, config)

    print()
    if backup != config_path:
        print(f"Backed up existing config to {backup}.")
    print(f"Wrote {config_path}.")
    print(
        "Note: GITEA_TOKEN is stored in plaintext at the path above. "
        "Restrict file permissions if this is a shared machine."
    )
    print("Restart Claude Desktop to load the new server.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """argparse parser for the ``init`` subcommand."""
    parser = argparse.ArgumentParser(
        prog="gitea-mcp init",
        description=(
            "Add gitea-mcp to Claude Desktop's claude_desktop_config.json. "
            "Prompts interactively unless --url, --token, and --yes are provided."
        ),
    )
    parser.add_argument("--url", help="Gitea base URL (e.g. https://gitea.example.com)")
    parser.add_argument("--token", help="Personal Access Token")
    parser.add_argument(
        "--name",
        default="gitea",
        help="Server key under mcpServers (default: gitea). Use a unique value "
        "if you run multiple Gitea instances.",
    )
    parser.add_argument(
        "--command",
        choices=["auto", "uvx"],
        default="auto",
        help="Launch command to write. 'auto' (default) uses the gitea-mcp "
        "console script if on PATH, else 'python -m gitea_mcp.server'. "
        "'uvx' writes 'uvx gitea-mcp' (requires gitea-mcp on PyPI).",
    )
    parser.add_argument(
        "--config-path",
        help="Override the Claude Desktop config path (default: OS-specific).",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip the GET /api/v1/user connection check before writing.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip the final confirmation prompt.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``gitea-mcp init``."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
