# ffmpeg-zeo

Typed FFmpeg **filter graphs** for Python, a Typer CLI, and coding agents (Cursor / Claude Code MCP).

Inspired by [ffmpeg-python](https://github.com/kkroening/ffmpeg-python) (DAG compilation) and [pyffmpeg](https://github.com/deuteronomy-works/pyffmpeg) (zero-install DX). This is a new library, not a drop-in fork.

Requires **Python 3.12+**. Does not bundle GPL FFmpeg in the Apache wheel. System `ffmpeg`/`ffprobe` on `PATH`, `FFMPEG_BINARY` / `FFPROBE_BINARY`, or `ffmpeg-zeo doctor --download` (LGPL static builds on Linux/Windows).

## Install

```bash
uv add ffmpeg-zeo
# or
pip install ffmpeg-zeo
```

## Python

```python
from ffmpeg_zeo import input, convert, probe

info = probe("in.mp4")
print(info.duration_seconds, info.width, info.height)

convert("in.mp4", "out.mp3")  # recipe → Graph → ffmpeg

(
    input("in.mp4")
    .filter("scale", 1280, -2)
    .output("out.mp4", vcodec="libx264")
    .overwrite("always")
    .run()
)
```

Graphs are Pydantic models and round-trip through JSON for agents.

## CLI

```bash
ffmpeg-zeo doctor
ffmpeg-zeo probe in.mp4 --json
ffmpeg-zeo convert in.mp4 out.mp3
ffmpeg-zeo compile graph.json
ffmpeg-zeo run graph.json --json
ffmpeg-zeo catalog filters
```

## Agents

- Cursor skill: `.cursor/skills/ffmpeg-zeo/`
- Claude Code plugin: `plugin/ffmpeg-zeo/`
- MCP: `uv run ffmpeg-zeo-mcp` (stdio; log on stderr only)

## License

Apache-2.0 for ffmpeg-zeo. FFmpeg binaries you install or download have their own licenses (prefer LGPL/essentials builds). See [NOTICE](NOTICE).
