"""CLI smoke tests that do not require ffmpeg."""

from __future__ import annotations

from typer.testing import CliRunner

from ffmpeg_zeo.cli import app

runner = CliRunner()


def test_version_json() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code in {0, 1}
    assert "ffmpeg-zeo" in result.stdout
