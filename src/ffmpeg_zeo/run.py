"""Async/sync ffmpeg runner."""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path

from ffmpeg_zeo.bins import get_ffmpeg_bin
from ffmpeg_zeo.compile import compile_graph
from ffmpeg_zeo.errors import FFmpegError
from ffmpeg_zeo.ir import Graph, OverwritePolicy


@dataclass
class Progress:
    frame: int | None = None
    fps: float | None = None
    out_time_us: int | None = None
    total_size: int | None = None
    speed: str | None = None
    percent: float | None = None
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def out_time_seconds(self) -> float | None:
        if self.out_time_us is None:
            return None
        return self.out_time_us / 1_000_000


@dataclass
class RunResult:
    argv: list[str]
    returncode: int
    stdout: bytes | None
    stderr: bytes | None


def _parse_progress_block(block: str) -> Progress:
    raw: dict[str, str] = {}
    for line in block.strip().splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        raw[key.strip()] = value.strip()
    frame = int(raw["frame"]) if raw.get("frame", "").isdigit() else None
    fps = float(raw["fps"]) if raw.get("fps") not in {None, "", "N/A"} else None
    out_time_us = (
        int(raw["out_time_us"])
        if raw.get("out_time_us", "").lstrip("-").isdigit()
        else None
    )
    total_size = int(raw["total_size"]) if raw.get("total_size", "").isdigit() else None
    return Progress(
        frame=frame,
        fps=fps,
        out_time_us=out_time_us,
        total_size=total_size,
        speed=raw.get("speed"),
        raw=raw,
    )


def _progress_file_iter(path: Path) -> list[Progress]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks = text.split("progress=")
    events: list[Progress] = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        events.append(_parse_progress_block(chunk))
    return events


async def run_async(
    graph: Graph,
    *,
    cmd: str | list[str] | None = None,
    cwd: str | os.PathLike[str] | None = None,
    timeout: float | None = None,
    pipe_stdin: bool = False,
    pipe_stdout: bool = False,
    pipe_stderr: bool = False,
    capture_stdout: bool = False,
    capture_stderr: bool = False,
    input: bytes | None = None,
    overwrite: bool | OverwritePolicy | None = None,
    loglevel: str | None = None,
    on_progress: Callable[[Progress], None] | None = None,
    env: dict[str, str] | None = None,
) -> RunResult:
    ffmpeg_cmd: str | list[str]
    if cmd is None:
        ffmpeg_cmd = str(get_ffmpeg_bin())
    else:
        ffmpeg_cmd = cmd

    ow: bool | None
    if overwrite == "always" or overwrite is True:
        ow = True
    elif overwrite == "never":
        ow = False
        graph = graph.model_copy(update={"overwrite": "never"})
    elif overwrite is False:
        ow = False
    else:
        ow = None

    argv = compile_graph(graph, cmd=ffmpeg_cmd, overwrite=ow)
    if loglevel:
        argv[1:1] = ["-loglevel", loglevel]

    for output in graph.outputs:
        parent = Path(output.filename).parent
        if output.filename not in {"pipe:", "pipe:1", "-"} and str(parent) not in {
            "",
            ".",
        }:
            parent.mkdir(parents=True, exist_ok=True)

    progress_path: Path | None = None
    if on_progress is not None:
        tmp = tempfile.NamedTemporaryFile(
            prefix="ffmpeg-zeo-progress-", suffix=".txt", delete=False
        )
        progress_path = Path(tmp.name)
        tmp.close()
        argv[1:1] = ["-progress", str(progress_path)]

    stdin = subprocess.PIPE if pipe_stdin or input is not None else None
    stdout = subprocess.PIPE if pipe_stdout or capture_stdout else None
    stderr = subprocess.PIPE if pipe_stderr or capture_stderr else None

    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
        env=env,
    )

    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            process.communicate(input=input),
            timeout=timeout,
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    except asyncio.CancelledError:
        if process.stdin:
            try:
                process.stdin.write(b"q")
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                pass
        process.kill()
        await process.wait()
        raise

    if on_progress and progress_path:
        for event in _progress_file_iter(progress_path):
            on_progress(event)
        progress_path.unlink(missing_ok=True)

    if process.returncode != 0:
        raise FFmpegError(
            argv[0],
            argv=argv,
            returncode=process.returncode,
            stdout=stdout_b,
            stderr=stderr_b,
        )
    return RunResult(
        argv=argv,
        returncode=process.returncode or 0,
        stdout=stdout_b,
        stderr=stderr_b,
    )


def run(graph: Graph, **kwargs: object) -> RunResult:
    return asyncio.run(run_async(graph, **kwargs))  # type: ignore[arg-type]


async def iter_progress(graph: Graph, **kwargs: object) -> AsyncIterator[Progress]:
    queue: asyncio.Queue[Progress | None] = asyncio.Queue()

    def _push(event: Progress) -> None:
        queue.put_nowait(event)

    task = asyncio.create_task(run_async(graph, on_progress=_push, **kwargs))  # type: ignore[arg-type]
    try:
        while True:
            if task.done() and queue.empty():
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.05)
            except TimeoutError:
                continue
            if item is None:
                break
            yield item
        await task
    finally:
        if not task.done():
            task.cancel()
