"""Named jobs that return Graph IR (also used by CLI and MCP)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ffmpeg_zeo.fluent import Stream, concat, input
from ffmpeg_zeo.ir import Graph


def convert(src: str, dst: str, *, overwrite: str = "always") -> Graph:
    return input(src).output(dst).overwrite(overwrite).build()  # type: ignore[arg-type]


def thumbnail(src: str, dst: str, *, time: float = 1.0) -> Graph:
    return input(src, ss=time).output(dst, vframes=1).overwrite("always").build()


def transcode_h264(
    src: str, dst: str, *, crf: int = 23, preset: str = "medium"
) -> Graph:
    return (
        input(src)
        .output(dst, vcodec="libx264", crf=crf, preset=preset, acodec="aac")
        .overwrite("always")
        .build()
    )


def extract_audio(src: str, dst: str, *, codec: str = "copy") -> Graph:
    return input(src).output(dst, vn=None, acodec=codec).overwrite("always").build()


def extract_cover(src: str, dst: str) -> Graph:
    return input(src).output(dst, an=None, vcodec="copy").overwrite("always").build()


def scale(src: str, dst: str, width: int = 1280, height: int = -2) -> Graph:
    return (
        input(src)
        .filter("scale", width, height)
        .output(dst)
        .overwrite("always")
        .build()
    )


def clip(
    src: str, dst: str, start: float | str, end: float | str | None = None
) -> Graph:
    kwargs: dict[str, float | str] = {"ss": start}
    if end is not None:
        kwargs["to"] = end
    return input(src, **kwargs).output(dst, c="copy").overwrite("always").build()


def burn_subtitles(src: str, dst: str, subtitles: str) -> Graph:
    return (
        input(src)
        .filter("subtitles", subtitles)
        .output(dst)
        .overwrite("always")
        .build()
    )


def concat_demuxer(paths: list[str], dst: str) -> Graph:
    streams = [input(path) for path in paths]
    joined: Stream = concat(*streams)
    return joined.output(dst).overwrite("always").build()


RECIPES: dict[str, Callable[..., Graph]] = {
    "convert": convert,
    "thumbnail": thumbnail,
    "transcode_h264": transcode_h264,
    "extract_audio": extract_audio,
    "extract_cover": extract_cover,
    "scale": scale,
    "clip": clip,
    "burn_subtitles": burn_subtitles,
    "concat_demuxer": concat_demuxer,
}


def list_recipes() -> list[str]:
    return sorted(RECIPES)


def run_recipe(name: str, **kwargs: object) -> Graph:
    if name not in RECIPES:
        raise KeyError(f"unknown recipe: {name}")
    return RECIPES[name](**kwargs)  # type: ignore[arg-type]


def convert_files(src: str | Path, dst: str | Path, **kwargs: object) -> Graph:
    return convert(str(src), str(dst), **kwargs)  # type: ignore[arg-type]
