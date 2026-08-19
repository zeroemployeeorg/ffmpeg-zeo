"""CLI smoke tests that do not require ffmpeg."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import ffmpeg_zeo.cli as cli
from ffmpeg_zeo import __version__
from ffmpeg_zeo.errors import FFmpegError

runner = CliRunner()


def test_version_json() -> None:
    result = runner.invoke(cli.app, ["version"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["ffmpeg-zeo"] == __version__


def test_main_serializes_ffmpeg_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail() -> None:
        raise FFmpegError(
            "ffmpeg", returncode=2, stderr=b"invalid media", message="failed"
        )

    monkeypatch.setattr(cli, "app", fail)

    with pytest.raises(SystemExit, match="2"):
        cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "ok": False,
        "error": "failed",
        "returncode": 2,
        "stderr": "invalid media",
    }
