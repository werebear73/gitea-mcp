"""Unit tests for the ``gitea-mcp doctor`` preflight subcommand."""

from __future__ import annotations

import pytest

from gitea_mcp import doctor


def _make_args(url: str | None = None, token: str | None = None) -> object:
    """Build the argparse-namespace shape doctor.run expects."""
    return doctor.build_parser().parse_args(
        [arg for pair in (("--url", url), ("--token", token)) if pair[1] for arg in pair]
    )


def test_missing_url_returns_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GITEA_URL", raising=False)
    monkeypatch.setenv("GITEA_TOKEN", "tok")
    code = doctor.run(_make_args())
    assert code == 2
    err = capsys.readouterr().err
    assert "GITEA_URL not set" in err


def test_missing_token_returns_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITEA_URL", "https://g.example.com")
    monkeypatch.delenv("GITEA_TOKEN", raising=False)
    code = doctor.run(_make_args())
    assert code == 2
    err = capsys.readouterr().err
    assert "GITEA_TOKEN not set" in err


def test_flag_overrides_env(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """--url and --token take precedence over GITEA_URL / GITEA_TOKEN."""
    monkeypatch.setenv("GITEA_URL", "https://from-env.example.com")
    monkeypatch.setenv("GITEA_TOKEN", "env-token")

    seen: dict[str, object] = {}

    def fake_check(url: str, token: str, timeout: float = 10.0) -> str:
        seen["url"] = url
        seen["token"] = token
        return "alice"

    monkeypatch.setattr(doctor, "check_connection", fake_check)
    code = doctor.run(_make_args(url="https://from-flag.example.com", token="flag-token"))
    assert code == 0
    assert seen["url"] == "https://from-flag.example.com"
    assert seen["token"] == "flag-token"
    out = capsys.readouterr().out
    assert "authenticated as 'alice'" in out


def test_connection_failure_returns_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITEA_URL", "https://g.example.com")
    monkeypatch.setenv("GITEA_TOKEN", "tok")

    def fake_check(url: str, token: str, timeout: float = 10.0) -> str:
        raise RuntimeError("Authentication failed at https://g.example.com.")

    monkeypatch.setattr(doctor, "check_connection", fake_check)
    code = doctor.run(_make_args())
    assert code == 1
    err = capsys.readouterr().err
    assert "Authentication failed" in err


def test_success_path_returns_0(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITEA_URL", "https://g.example.com")
    monkeypatch.setenv("GITEA_TOKEN", "tok")
    monkeypatch.setattr(doctor, "check_connection", lambda url, token, timeout=10.0: "alice")
    code = doctor.run(_make_args())
    assert code == 0
    out = capsys.readouterr().out
    assert "[1/2] Verifying connection" in out
    assert "[2/2] Loading MCP tool modules" in out
    assert "All checks passed" in out


def test_url_trailing_slash_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITEA_URL", "https://g.example.com/")
    monkeypatch.setenv("GITEA_TOKEN", "tok")

    seen: dict[str, object] = {}

    def fake_check(url: str, token: str, timeout: float = 10.0) -> str:
        seen["url"] = url
        return "alice"

    monkeypatch.setattr(doctor, "check_connection", fake_check)
    code = doctor.run(_make_args())
    assert code == 0
    assert seen["url"] == "https://g.example.com"
