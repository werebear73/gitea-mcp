"""Unit tests for the `gitea-mcp serve` transport-selectable runner."""

from __future__ import annotations

from typing import Any

import pytest

from gitea_mcp import serve


@pytest.fixture(autouse=True)
def _clear_serve_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wipe any GITEA_MCP_* env vars so tests start from defaults regardless
    of the host shell's environment."""
    for var in ("GITEA_MCP_TRANSPORT", "GITEA_MCP_HOST", "GITEA_MCP_PORT", "GITEA_MCP_PATH"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def _stub_run(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Stub out Config.from_env(), GiteaClient construction, and mcp.run so
    the serve flow can run end-to-end without env vars or a real network.

    Returns a dict that the test inspects to assert how mcp.run was called.
    """
    captured: dict[str, Any] = {}

    def fake_from_env() -> object:
        return type(
            "FakeConfig",
            (),
            {
                "base_url": "https://gitea.example.com",
                "token": "tok",
                "timeout": 30.0,
                "max_retries": 3,
                "retry_base_delay": 0.5,
            },
        )()

    monkeypatch.setattr(serve.Config, "from_env", classmethod(lambda cls: fake_from_env()))

    # GiteaClient construction is cheap (no network until a tool fires) — leave
    # it real so the close() call in the finally block doesn't break.

    def fake_run(*args: Any, **kwargs: Any) -> None:
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr(serve.mcp, "run", fake_run)
    return captured


def test_default_transport_is_stdio(_stub_run: dict[str, Any]) -> None:
    """No flags → stdio with no extra kwargs."""
    code = serve.main([])
    assert code == 0
    assert _stub_run["args"] == ()
    assert _stub_run["kwargs"] == {}


def test_explicit_stdio_runs_stdio(_stub_run: dict[str, Any]) -> None:
    code = serve.main(["--transport", "stdio"])
    assert code == 0
    assert _stub_run["kwargs"] == {}  # stdio path passes no kwargs


def test_http_transport_passes_host_port_path(_stub_run: dict[str, Any]) -> None:
    code = serve.main([
        "--transport", "http",
        "--host", "0.0.0.0",
        "--port", "9001",
        "--path", "/api/mcp",
    ])
    assert code == 0
    assert _stub_run["kwargs"] == {
        "transport": "http",
        "host": "0.0.0.0",
        "port": 9001,
        "path": "/api/mcp",
    }


def test_http_transport_uses_defaults_when_only_transport_set(
    _stub_run: dict[str, Any],
) -> None:
    code = serve.main(["--transport", "http"])
    assert code == 0
    assert _stub_run["kwargs"] == {
        "transport": "http",
        "host": "127.0.0.1",
        "port": 8000,
        "path": "/mcp",
    }


def test_env_var_defaults_apply_when_flags_absent(
    monkeypatch: pytest.MonkeyPatch, _stub_run: dict[str, Any]
) -> None:
    monkeypatch.setenv("GITEA_MCP_TRANSPORT", "http")
    monkeypatch.setenv("GITEA_MCP_HOST", "10.0.0.5")
    monkeypatch.setenv("GITEA_MCP_PORT", "7000")
    monkeypatch.setenv("GITEA_MCP_PATH", "/v1/mcp")

    code = serve.main([])
    assert code == 0
    assert _stub_run["kwargs"] == {
        "transport": "http",
        "host": "10.0.0.5",
        "port": 7000,
        "path": "/v1/mcp",
    }


def test_flags_override_env_vars(
    monkeypatch: pytest.MonkeyPatch, _stub_run: dict[str, Any]
) -> None:
    monkeypatch.setenv("GITEA_MCP_TRANSPORT", "http")
    monkeypatch.setenv("GITEA_MCP_PORT", "7000")

    # --port flag should win over GITEA_MCP_PORT env.
    code = serve.main(["--port", "9999"])
    assert code == 0
    # transport is still http (from env), but port came from flag.
    assert _stub_run["kwargs"]["port"] == 9999
    assert _stub_run["kwargs"]["transport"] == "http"
