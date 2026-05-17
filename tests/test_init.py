"""Unit tests for the ``gitea-mcp init`` interactive setup flow."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from gitea_mcp.init import (
    backup_config,
    check_connection,
    claude_desktop_config_path,
    detect_command,
    load_config,
    merge_server_entry,
    write_config,
)

# ---- claude_desktop_config_path -------------------------------------------


def test_config_path_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    path = claude_desktop_config_path()
    assert path == tmp_path / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"


def test_config_path_macos(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    path = claude_desktop_config_path()
    assert path == (
        tmp_path / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    )


def test_config_path_linux(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    path = claude_desktop_config_path()
    assert path == tmp_path / ".config" / "Claude" / "claude_desktop_config.json"


# ---- detect_command -------------------------------------------------------


def test_detect_command_prefers_uvx() -> None:
    command, args = detect_command(prefer="uvx")
    assert command == "uvx"
    assert args == ["gitea-mcp"]


def test_detect_command_uses_path_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("gitea_mcp.init.shutil.which", lambda name: "/usr/local/bin/gitea-mcp")
    command, args = detect_command()
    assert command == "/usr/local/bin/gitea-mcp"
    assert args == []


def test_detect_command_falls_back_to_python_m(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("gitea_mcp.init.shutil.which", lambda name: None)
    command, args = detect_command()
    assert command == sys.executable
    assert args == ["-m", "gitea_mcp.server"]


# ---- load_config ----------------------------------------------------------


def test_load_config_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_config(tmp_path / "nope.json") == {}


def test_load_config_existing(tmp_path: Path) -> None:
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"mcpServers": {"slack": {"command": "slack-mcp"}}}))
    config = load_config(path)
    assert config == {"mcpServers": {"slack": {"command": "slack-mcp"}}}


def test_load_config_rejects_top_level_array(tmp_path: Path) -> None:
    path = tmp_path / "cfg.json"
    path.write_text("[]")
    with pytest.raises(RuntimeError, match="does not contain a JSON object"):
        load_config(path)


# ---- backup_config --------------------------------------------------------


def test_backup_writes_timestamped_copy(tmp_path: Path) -> None:
    path = tmp_path / "cfg.json"
    path.write_text('{"hello": "world"}')
    backup = backup_config(path)
    assert backup != path
    assert backup.exists()
    assert backup.read_text() == '{"hello": "world"}'
    assert backup.name.startswith("cfg.json.bak.")


def test_backup_noop_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    result = backup_config(path)
    assert result == path
    assert not path.exists()


# ---- merge_server_entry ---------------------------------------------------


def test_merge_preserves_other_servers() -> None:
    config: dict[str, object] = {
        "mcpServers": {"slack": {"command": "slack-mcp", "env": {}}},
    }
    merge_server_entry(
        config,
        name="gitea",
        command="gitea-mcp",
        args=[],
        env={"GITEA_URL": "https://g.example.com", "GITEA_TOKEN": "tok"},
    )
    servers = config["mcpServers"]
    assert isinstance(servers, dict)
    assert set(servers.keys()) == {"slack", "gitea"}
    assert servers["gitea"]["command"] == "gitea-mcp"
    assert servers["gitea"]["env"]["GITEA_TOKEN"] == "tok"
    assert "args" not in servers["gitea"]


def test_merge_replaces_existing_entry() -> None:
    config: dict[str, object] = {
        "mcpServers": {"gitea": {"command": "old-binary", "env": {"GITEA_URL": "old"}}},
    }
    merge_server_entry(
        config,
        name="gitea",
        command=sys.executable,
        args=["-m", "gitea_mcp.server"],
        env={"GITEA_URL": "https://new.example.com", "GITEA_TOKEN": "new-tok"},
    )
    servers = config["mcpServers"]
    assert isinstance(servers, dict)
    assert servers["gitea"]["command"] == sys.executable
    assert servers["gitea"]["args"] == ["-m", "gitea_mcp.server"]
    assert servers["gitea"]["env"]["GITEA_URL"] == "https://new.example.com"


def test_merge_rejects_non_dict_mcpservers() -> None:
    config: dict[str, object] = {"mcpServers": []}
    with pytest.raises(RuntimeError, match="is not a JSON object"):
        merge_server_entry(
            config,
            name="gitea",
            command="x",
            args=[],
            env={},
        )


# ---- write_config round-trip ----------------------------------------------


def test_write_config_creates_parent_dirs(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "Claude" / "claude_desktop_config.json"
    write_config(path, {"mcpServers": {"gitea": {"command": "gitea-mcp"}}})
    assert path.exists()
    loaded = json.loads(path.read_text())
    assert loaded == {"mcpServers": {"gitea": {"command": "gitea-mcp"}}}


# ---- check_connection -----------------------------------------------------


def test_check_connection_success(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/user",
        json={"login": "alice", "id": 1},
    )
    username = check_connection("https://gitea.example.com", "tok")
    assert username == "alice"


def test_check_connection_auth_failure(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://gitea.example.com/api/v1/user",
        status_code=401,
        text="bad credentials",
    )
    with pytest.raises(RuntimeError, match="Authentication failed"):
        check_connection("https://gitea.example.com", "tok")


def test_check_connection_wrong_host_payload(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="GET",
        url="https://not-gitea.example.com/api/v1/user",
        json={"unexpected": "shape"},
    )
    with pytest.raises(RuntimeError, match="did not look like a Gitea user"):
        check_connection("https://not-gitea.example.com", "tok")
