"""Unit tests for the top-level ``gitea-mcp`` argv dispatcher in ``server.main``.

The Claude Desktop launch path (no args → run server) MUST stay byte-identical
to pre-v0.1.2; this is also guarded by ``tests/test_subprocess_launch.py``. The
tests here cover the new dispatch branches added in v0.1.2: ``--help``,
``--version``, ``init``, ``doctor``, and the unknown-subcommand error.
"""

from __future__ import annotations

import pytest

from gitea_mcp import __version__, server


def test_no_args_runs_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Claude Desktop launch path: no args, falls through to _run_server."""
    called: dict[str, bool] = {}

    def fake_run_server() -> None:
        called["ran"] = True

    monkeypatch.setattr(server, "_run_server", fake_run_server)
    monkeypatch.setattr("sys.argv", ["gitea-mcp"])
    server.main()
    assert called.get("ran") is True


def test_help_prints_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["gitea-mcp", "--help"])
    server.main()
    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "gitea-mcp init" in out
    assert "gitea-mcp doctor" in out
    assert "gitea-mcp serve" in out


def test_short_help_prints_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["gitea-mcp", "-h"])
    server.main()
    assert "Usage:" in capsys.readouterr().out


def test_version_prints_version(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["gitea-mcp", "--version"])
    server.main()
    out = capsys.readouterr().out.strip()
    assert out == f"gitea-mcp {__version__}"


def test_short_version(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["gitea-mcp", "-V"])
    server.main()
    assert capsys.readouterr().out.strip() == f"gitea-mcp {__version__}"


def test_init_dispatches_with_remainder(monkeypatch: pytest.MonkeyPatch) -> None:
    """`gitea-mcp init --foo bar` → init.main(['--foo', 'bar'])."""
    received: dict[str, list[str] | None] = {}

    def fake_init_main(argv: list[str] | None = None) -> int:
        received["argv"] = argv
        return 0

    import gitea_mcp.init as init_module

    monkeypatch.setattr(init_module, "main", fake_init_main)
    monkeypatch.setattr("sys.argv", ["gitea-mcp", "init", "--foo", "bar"])
    with pytest.raises(SystemExit) as exc_info:
        server.main()
    assert exc_info.value.code == 0
    assert received["argv"] == ["--foo", "bar"]


def test_doctor_dispatches_with_remainder(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, list[str] | None] = {}

    def fake_doctor_main(argv: list[str] | None = None) -> int:
        received["argv"] = argv
        return 0

    import gitea_mcp.doctor as doctor_module

    monkeypatch.setattr(doctor_module, "main", fake_doctor_main)
    monkeypatch.setattr("sys.argv", ["gitea-mcp", "doctor", "--url", "https://x"])
    with pytest.raises(SystemExit) as exc_info:
        server.main()
    assert exc_info.value.code == 0
    assert received["argv"] == ["--url", "https://x"]


def test_serve_dispatches_with_remainder(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, list[str] | None] = {}

    def fake_serve_main(argv: list[str] | None = None) -> int:
        received["argv"] = argv
        return 0

    import gitea_mcp.serve as serve_module

    monkeypatch.setattr(serve_module, "main", fake_serve_main)
    monkeypatch.setattr(
        "sys.argv",
        ["gitea-mcp", "serve", "--transport", "http", "--port", "8000"],
    )
    with pytest.raises(SystemExit) as exc_info:
        server.main()
    assert exc_info.value.code == 0
    assert received["argv"] == ["--transport", "http", "--port", "8000"]


def test_unknown_subcommand_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["gitea-mcp", "bogus"])
    with pytest.raises(SystemExit) as exc_info:
        server.main()
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "unknown subcommand 'bogus'" in err
    assert "--help" in err
