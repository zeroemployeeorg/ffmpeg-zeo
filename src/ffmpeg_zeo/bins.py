"""Resolve ffmpeg / ffprobe executables."""

from __future__ import annotations

import os
import platform
import shutil
import stat
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from ffmpeg_zeo.errors import BinaryNotFoundError

_CACHE_DIR_NAME = "ffmpeg-zeo"

# BtbN LGPL essentials (not GPL). macOS is not published there; we fall back to PATH.
_BTBN = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"
_DOWNLOADS: dict[tuple[str, str], tuple[str, str]] = {
    ("linux", "x86_64"): (
        f"{_BTBN}/ffmpeg-master-latest-linux64-lgpl.tar.xz",
        "lgpl",
    ),
    ("linux", "aarch64"): (
        f"{_BTBN}/ffmpeg-master-latest-linuxarm64-lgpl.tar.xz",
        "lgpl",
    ),
    ("win32", "amd64"): (
        f"{_BTBN}/ffmpeg-master-latest-win64-lgpl.zip",
        "lgpl",
    ),
    ("win32", "x86_64"): (
        f"{_BTBN}/ffmpeg-master-latest-win64-lgpl.zip",
        "lgpl",
    ),
}


@dataclass(frozen=True)
class BinaryInfo:
    ffmpeg: Path
    ffprobe: Path
    source: str
    license: str | None = None


def cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        root = Path(xdg)
    elif sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        root = Path(local) if local else Path.home() / "AppData" / "Local"
    else:
        root = Path.home() / ".cache"
    path = root / _CACHE_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _which(name: str) -> Path | None:
    found = shutil.which(name)
    return Path(found) if found else None


def _env_path(var: str) -> Path | None:
    value = os.environ.get(var)
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def _cached_bins() -> tuple[Path, Path] | None:
    ext = ".exe" if sys.platform == "win32" else ""
    ffmpeg = cache_dir() / f"ffmpeg{ext}"
    ffprobe = cache_dir() / f"ffprobe{ext}"
    if ffmpeg.exists() and ffprobe.exists():
        return ffmpeg, ffprobe
    if ffmpeg.exists() and not ffprobe.exists():
        return ffmpeg, ffmpeg
    return None


def _machine() -> str:
    lowered = platform.machine().lower()
    if lowered in {"x86_64", "amd64", "x64"}:
        return "x86_64" if sys.platform != "win32" else "amd64"
    if lowered in {"aarch64", "arm64"}:
        return "aarch64"
    return lowered


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=120) as response:
        dest.write_bytes(response.read())


def _make_executable(path: Path) -> None:
    if sys.platform != "win32":
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _extract_bins(archive: Path) -> tuple[Path, Path]:
    names = (
        ("ffmpeg.exe", "ffprobe.exe")
        if sys.platform == "win32"
        else ("ffmpeg", "ffprobe")
    )
    found: dict[str, Path] = {}
    dest_dir = cache_dir()

    if archive.suffix == ".zip" or archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                base = Path(info.filename).name
                if base in names:
                    target = dest_dir / base
                    target.write_bytes(zf.read(info))
                    found[base.replace(".exe", "")] = target
    else:
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                base = Path(member.name).name
                if base in names and member.isfile():
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        continue
                    target = dest_dir / base
                    target.write_bytes(extracted.read())
                    found[base] = target

    ffmpeg = found.get("ffmpeg")
    if ffmpeg is None:
        raise BinaryNotFoundError("ffmpeg")
    _make_executable(ffmpeg)
    ffprobe = found.get("ffprobe", ffmpeg)
    if ffprobe != ffmpeg:
        _make_executable(ffprobe)
    return ffmpeg, ffprobe


def download_lgpl_binaries() -> BinaryInfo:
    """Fetch LGPL static builds into the user cache (Linux/Windows)."""
    key = (sys.platform, _machine())
    spec = _DOWNLOADS.get(key)
    if spec is None:
        raise BinaryNotFoundError("ffmpeg")
    url, license_id = spec
    archive = cache_dir() / Path(url).name
    _download(url, archive)
    ffmpeg, ffprobe = _extract_bins(archive)
    return BinaryInfo(
        ffmpeg=ffmpeg, ffprobe=ffprobe, source="download", license=license_id
    )


def resolve_binaries(*, download: bool = False) -> BinaryInfo:
    """Discovery order: env → PATH → cache → optional download."""
    env_ffmpeg = _env_path("FFMPEG_BINARY")
    env_ffprobe = _env_path("FFPROBE_BINARY")
    path_ffmpeg = _which("ffmpeg")
    path_ffprobe = _which("ffprobe")

    ffmpeg = env_ffmpeg or path_ffmpeg
    ffprobe = env_ffprobe or path_ffprobe

    if ffmpeg and ffprobe:
        source = "env" if env_ffmpeg or env_ffprobe else "path"
        return BinaryInfo(ffmpeg=ffmpeg, ffprobe=ffprobe, source=source)

    cached = _cached_bins()
    if cached:
        return BinaryInfo(
            ffmpeg=cached[0], ffprobe=cached[1], source="cache", license="lgpl"
        )

    if ffmpeg and not ffprobe:
        return BinaryInfo(ffmpeg=ffmpeg, ffprobe=ffmpeg, source="path")

    if download:
        return download_lgpl_binaries()

    raise BinaryNotFoundError("ffmpeg")


def get_ffmpeg_bin(*, download: bool = False) -> Path:
    return resolve_binaries(download=download).ffmpeg


def get_ffprobe_bin(*, download: bool = False) -> Path:
    return resolve_binaries(download=download).ffprobe
