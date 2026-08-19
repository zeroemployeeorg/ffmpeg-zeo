"""ffmpeg-zeo — typed FFmpeg graphs for Python, CLIs, and coding agents."""

from __future__ import annotations

from typing import Any

from ffmpeg_zeo.bins import get_ffmpeg_bin, get_ffprobe_bin, resolve_binaries
from ffmpeg_zeo.catalog import filter_help, has_filter, list_codecs, list_filters
from ffmpeg_zeo.errors import BinaryNotFoundError, FFmpegError
from ffmpeg_zeo.fluent import (
    Stream,
    compile,
    concat,
    crop,
    drawbox,
    drawtext,
    filter_,
    filter_multi_output,
    get_args,
    hflip,
    input,
    merge_outputs,
    output,
    overlay,
    trim,
    vflip,
)
from ffmpeg_zeo.ir import FilterNode, Graph, InputNode, OutputNode, StreamRef
from ffmpeg_zeo.probe import ProbeResult, probe, probe_async
from ffmpeg_zeo.recipes import convert, list_recipes, run_recipe
from ffmpeg_zeo.run import Progress, RunResult
from ffmpeg_zeo.run import run as run_graph
from ffmpeg_zeo.run import run_async as run_graph_async

__version__ = "0.1.0"

filter = filter_
compile_graph = compile


def _as_graph(spec: Stream | list[Stream] | Graph) -> Graph:
    if isinstance(spec, Graph):
        return spec
    if isinstance(spec, list):
        builder = spec[0]._builder
        for stream in spec[1:]:
            builder.merge(stream._builder)
        return builder.graph()
    return spec.build()


def run(spec: Stream | list[Stream] | Graph, **kwargs: Any) -> RunResult:
    if "overwrite_output" in kwargs:
        kwargs["overwrite"] = kwargs.pop("overwrite_output")
    return run_graph(_as_graph(spec), **kwargs)


def run_async(spec: Stream | list[Stream] | Graph, **kwargs: Any) -> Any:
    if "overwrite_output" in kwargs:
        kwargs["overwrite"] = kwargs.pop("overwrite_output")
    return run_graph_async(_as_graph(spec), **kwargs)


__all__ = [
    "BinaryNotFoundError",
    "FFmpegError",
    "FilterNode",
    "Graph",
    "InputNode",
    "OutputNode",
    "ProbeResult",
    "Progress",
    "RunResult",
    "Stream",
    "StreamRef",
    "compile",
    "compile_graph",
    "concat",
    "convert",
    "crop",
    "drawbox",
    "drawtext",
    "filter",
    "filter_",
    "filter_help",
    "filter_multi_output",
    "get_args",
    "get_ffmpeg_bin",
    "get_ffprobe_bin",
    "has_filter",
    "hflip",
    "input",
    "list_codecs",
    "list_filters",
    "list_recipes",
    "merge_outputs",
    "output",
    "overlay",
    "probe",
    "probe_async",
    "resolve_binaries",
    "run",
    "run_async",
    "run_recipe",
    "trim",
    "vflip",
]
