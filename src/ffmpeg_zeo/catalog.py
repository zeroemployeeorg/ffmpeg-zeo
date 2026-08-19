"""Live catalog of filters and codecs from the installed ffmpeg binary."""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache

from pydantic import BaseModel

from ffmpeg_zeo.bins import get_ffmpeg_bin


class FilterInfo(BaseModel):
    name: str
    description: str = ""
    threading: str = ""
    io: str = ""


class CodecInfo(BaseModel):
    name: str
    kind: str
    description: str = ""
    decoding: bool = False
    encoding: bool = False


def _run_ffmpeg(*args: str) -> str:
    ffmpeg = str(get_ffmpeg_bin())
    completed = subprocess.run(
        [ffmpeg, *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout or completed.stderr or ""


@lru_cache(maxsize=1)
def list_filters() -> tuple[FilterInfo, ...]:
    text = _run_ffmpeg("-filters")
    filters: list[FilterInfo] = []
    for line in text.splitlines():
        match = re.match(r"^\s*([T.S.]{3})\s+(\S+)\s+(\S+)\s+(.*)$", line)
        if not match:
            continue
        flags, name, io, desc = match.groups()
        if name in {"Filters:", "filter"}:
            continue
        filters.append(
            FilterInfo(name=name, description=desc.strip(), threading=flags, io=io)
        )
    return tuple(filters)


@lru_cache(maxsize=1)
def list_codecs() -> tuple[CodecInfo, ...]:
    text = _run_ffmpeg("-codecs")
    codecs: list[CodecInfo] = []
    for line in text.splitlines():
        match = re.match(r"^\s*([D.])([E.])([VAS.])[A-Z.]*\s+(\S+)\s+(.*)$", line)
        if not match:
            continue
        decoding, encoding, kind_flag, name, desc = match.groups()
        kind = {"V": "video", "A": "audio", "S": "subtitle"}.get(kind_flag, "other")
        codecs.append(
            CodecInfo(
                name=name,
                kind=kind,
                description=desc.strip(),
                decoding=decoding == "D",
                encoding=encoding == "E",
            )
        )
    return tuple(codecs)


def filter_help(name: str) -> str:
    return _run_ffmpeg("-h", f"filter={name}")


def has_filter(name: str) -> bool:
    return any(item.name == name for item in list_filters())
