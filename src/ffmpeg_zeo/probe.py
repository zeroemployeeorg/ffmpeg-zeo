"""ffprobe JSON → Pydantic models."""

from __future__ import annotations

import asyncio
import json
import subprocess
from functools import cached_property
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ffmpeg_zeo.bins import get_ffprobe_bin
from ffmpeg_zeo.compile import kwargs_to_cli
from ffmpeg_zeo.errors import FFmpegError


class ProbeStream(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int | None = None
    codec_name: str | None = None
    codec_type: str | None = None
    width: int | None = None
    height: int | None = None
    avg_frame_rate: str | None = None
    r_frame_rate: str | None = None
    duration: str | None = None
    bit_rate: str | None = None
    sample_rate: str | None = None
    channels: int | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    disposition: dict[str, Any] = Field(default_factory=dict)


class ProbeFormat(BaseModel):
    model_config = ConfigDict(extra="allow")

    filename: str | None = None
    nb_streams: int | None = None
    format_name: str | None = None
    duration: str | None = None
    size: str | None = None
    bit_rate: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class ProbeResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    format: ProbeFormat = Field(default_factory=ProbeFormat)
    streams: list[ProbeStream] = Field(default_factory=list)
    frames: list[dict[str, Any]] | None = None

    @cached_property
    def duration_seconds(self) -> float | None:
        raw = self.format.duration
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    @cached_property
    def bitrate_bps(self) -> int | None:
        raw = self.format.bit_rate
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def _first(self, codec_type: str) -> ProbeStream | None:
        for stream in self.streams:
            if stream.codec_type == codec_type:
                return stream
        return None

    @cached_property
    def video(self) -> ProbeStream | None:
        return self._first("video")

    @cached_property
    def audio(self) -> ProbeStream | None:
        return self._first("audio")

    @property
    def has_video(self) -> bool:
        return self.video is not None

    @property
    def has_audio(self) -> bool:
        return self.audio is not None

    @property
    def width(self) -> int | None:
        return None if self.video is None else self.video.width

    @property
    def height(self) -> int | None:
        return None if self.video is None else self.video.height

    @property
    def video_codec(self) -> str | None:
        return None if self.video is None else self.video.codec_name

    @property
    def audio_codec(self) -> str | None:
        return None if self.audio is None else self.audio.codec_name

    @cached_property
    def fps(self) -> float | None:
        stream = self.video
        if stream is None:
            return None
        rate = stream.avg_frame_rate or stream.r_frame_rate
        if not rate or rate in {"0/0", "N/A"}:
            return None
        if "/" in rate:
            num, _, den = rate.partition("/")
            try:
                return float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                return None
        try:
            return float(rate)
        except ValueError:
            return None


_probe_cache: dict[tuple[str, float | None], ProbeResult] = {}


def probe(
    filename: str,
    *,
    cmd: str | None = None,
    timeout: float | None = None,
    use_cache: bool = False,
    **kwargs: Any,
) -> ProbeResult:
    ffprobe = cmd or str(get_ffprobe_bin())
    mtime: float | None = None
    try:
        mtime = os_mtime(filename)
    except OSError:
        mtime = None
    cache_key = (filename, mtime)
    if use_cache and cache_key in _probe_cache:
        return _probe_cache[cache_key]

    argv = [ffprobe, "-show_format", "-show_streams", "-of", "json"]
    argv += kwargs_to_cli(kwargs)
    argv += [filename]
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    if process.returncode != 0:
        raise FFmpegError(
            "ffprobe",
            argv=argv,
            returncode=process.returncode,
            stdout=out,
            stderr=err,
            message="ffprobe error (see stderr output for detail)",
        )
    payload = json.loads(out.decode("utf-8"))
    result = ProbeResult.model_validate(payload)
    if use_cache:
        _probe_cache[cache_key] = result
    return result


def os_mtime(path: str) -> float:
    import os

    return os.path.getmtime(path)


async def probe_async(filename: str, **kwargs: Any) -> ProbeResult:
    return await asyncio.to_thread(probe, filename, **kwargs)
