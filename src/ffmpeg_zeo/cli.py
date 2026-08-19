"""Typer CLI — JSON in/out for humans and agents."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from ffmpeg_zeo.bins import (
    BinaryInfo,
    download_lgpl_binaries,
    get_ffmpeg_bin,
    get_ffprobe_bin,
    resolve_binaries,
)
from ffmpeg_zeo.catalog import filter_help, list_codecs, list_filters
from ffmpeg_zeo.compile import compile_graph, get_args
from ffmpeg_zeo.errors import BinaryNotFoundError, FFmpegError
from ffmpeg_zeo.ir import Graph
from ffmpeg_zeo.probe import probe
from ffmpeg_zeo.recipes import RECIPES, convert, run_recipe
from ffmpeg_zeo.run import run

app = typer.Typer(
    no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False
)


def _print_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str))


def _load_graph(source: str) -> Graph:
    text = (
        sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    )
    return Graph.model_validate_json(text)


@app.command("convert")
def convert_cmd(
    src: Path,
    dst: Path,
    overwrite: str = typer.Option("always"),
) -> None:
    """Convert a file using the one-liner recipe."""
    if overwrite not in {"always", "never"}:
        raise typer.BadParameter("must be 'always' or 'never'", param_hint="overwrite")
    graph = convert(str(src), str(dst), overwrite=overwrite)
    result = run(graph)
    _print_json(
        {"path": str(dst), "returncode": result.returncode, "argv": result.argv}
    )


@app.command("probe")
def probe_cmd(
    file: Path,
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    info = probe(str(file))
    if json_out:
        _print_json(info.model_dump())
        return
    typer.echo(f"duration_seconds={info.duration_seconds}")
    typer.echo(
        f"size={info.width}x{info.height} fps={info.fps} v={info.video_codec} a={info.audio_codec}"
    )


@app.command("compile")
def compile_cmd(
    graph_file: str = typer.Argument("-"),
    cmd: str = "ffmpeg",
) -> None:
    graph = _load_graph(graph_file)
    argv = compile_graph(graph, cmd=cmd)
    _print_json({"argv": argv, "args": get_args(graph)})


@app.command("run")
def run_cmd(
    graph_file: str = typer.Argument("-"),
    json_out: bool = typer.Option(True, "--json/--no-json"),
) -> None:
    graph = _load_graph(graph_file)
    result = run(graph)
    if json_out:
        _print_json(
            {
                "returncode": result.returncode,
                "argv": result.argv,
                "stdout": None
                if result.stdout is None
                else result.stdout.decode("utf-8", "replace"),
                "stderr": None
                if result.stderr is None
                else result.stderr.decode("utf-8", "replace"),
            }
        )


@app.command()
def recipe(
    name: str,
    params: list[str] | None = None,
) -> None:
    """Run a named recipe. Extra args are key=value pairs."""
    kwargs: dict[str, Any] = {}
    for item in params or []:
        key, _, value = item.partition("=")
        kwargs[key] = value
    graph = run_recipe(name, **kwargs)
    result = run(graph)
    _print_json({"recipe": name, "returncode": result.returncode, "argv": result.argv})


@app.command()
def catalog(
    kind: str = typer.Argument("filters", help="filters or codecs"),
) -> None:
    if kind == "codecs":
        _print_json([item.model_dump() for item in list_codecs()])
        return
    if kind == "recipes":
        _print_json(sorted(RECIPES))
        return
    _print_json([item.model_dump() for item in list_filters()])


@app.command("filter-help")
def filter_help_cmd(name: str) -> None:
    typer.echo(filter_help(name))


@app.command()
def doctor(
    download: bool = typer.Option(False, help="Fetch LGPL static binaries into cache"),
) -> None:
    try:
        info: BinaryInfo = (
            download_lgpl_binaries() if download else resolve_binaries(download=False)
        )
    except BinaryNotFoundError as exc:
        _print_json({"ok": False, "error": str(exc)})
        raise typer.Exit(code=1) from exc
    _print_json(
        {
            "ok": True,
            "ffmpeg": str(info.ffmpeg),
            "ffprobe": str(info.ffprobe),
            "source": info.source,
            "license": info.license,
        }
    )


@app.command()
def version() -> None:
    from ffmpeg_zeo import __version__

    payload: dict[str, Any] = {"ffmpeg-zeo": __version__}
    try:
        payload["ffmpeg"] = str(get_ffmpeg_bin())
        payload["ffprobe"] = str(get_ffprobe_bin())
    except BinaryNotFoundError as exc:
        payload["binary_error"] = str(exc)
    _print_json(payload)


def main() -> None:
    try:
        app()
    except FFmpegError as exc:
        _print_json(
            {
                "ok": False,
                "error": str(exc),
                "returncode": exc.returncode,
                "stderr": None
                if exc.stderr is None
                else exc.stderr.decode("utf-8", "replace")[-4000:],
            }
        )
        raise SystemExit(exc.returncode or 1) from exc
