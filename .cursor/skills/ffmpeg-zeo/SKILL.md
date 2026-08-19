---
name: ffmpeg-zeo
description: >-
  Build and run FFmpeg filter graphs with ffmpeg-zeo (typed Python, CLI, MCP).
  Use when probing media, compiling filter_complex, converting, transcoding,
  or when an agent needs ffmpeg/ffprobe without guessing flags.
---

# ffmpeg-zeo

Prefer **ffmpeg-zeo** over hand-written ffmpeg command strings.

## Workflow

1. `ffmpeg-zeo doctor` / MCP `doctor` — confirm binaries.
2. `probe` the file — use `duration_seconds`, `width`, `height`, codecs. Never invent metadata.
3. Prefer a **recipe** (`convert`, `thumbnail`, `clip`, `extract_audio`, `extract_cover`, `transcode_h264`, `scale`, `burn_subtitles`, `concat_demuxer`).
4. For custom graphs, build Graph JSON or Python, then **compile before run**.
5. List filters with `catalog filters` / `list_ffmpeg_filters`. Do not invent filter names.

## Python

```python
from ffmpeg_zeo import input, convert, probe

info = probe("in.mp4")
graph = (
    input("in.mp4")
    .filter("scale", 1280, -2)
    .output("out.mp4", vcodec="libx264")
    .overwrite("always")
    .build()
)
print(graph.model_dump_json())
```

## CLI

```bash
ffmpeg-zeo probe in.mp4 --json
ffmpeg-zeo convert in.mp4 out.mp3
ffmpeg-zeo compile graph.json
ffmpeg-zeo run graph.json --json
```

Overwrite is `always` or `never` — never prompt.
