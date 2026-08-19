"""Binary discovery and doctor helpers."""

from __future__ import annotations

from pathlib import Path

from ffmpeg_zeo.bins import cache_dir, resolve_binaries
from ffmpeg_zeo.errors import BinaryNotFoundError


def test_cache_dir(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    path = cache_dir()
    assert path == tmp_path / "ffmpeg-zeo"
    assert path.is_dir()


def test_resolve_from_env(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    ffmpeg = tmp_path / "ffmpeg"
    ffprobe = tmp_path / "ffprobe"
    ffmpeg.write_text("x")
    ffprobe.write_text("x")
    monkeypatch.setenv("FFMPEG_BINARY", str(ffmpeg))
    monkeypatch.setenv("FFPROBE_BINARY", str(ffprobe))
    info = resolve_binaries()
    assert info.ffmpeg == ffmpeg
    assert info.ffprobe == ffprobe
    assert info.source == "env"


def test_missing_binary(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("FFMPEG_BINARY", raising=False)
    monkeypatch.delenv("FFPROBE_BINARY", raising=False)
    monkeypatch.setattr("ffmpeg_zeo.bins._which", lambda name: None)
    monkeypatch.setattr("ffmpeg_zeo.bins._cached_bins", lambda: None)
    try:
        resolve_binaries(download=False)
    except BinaryNotFoundError:
        return
    raise AssertionError("expected BinaryNotFoundError")
