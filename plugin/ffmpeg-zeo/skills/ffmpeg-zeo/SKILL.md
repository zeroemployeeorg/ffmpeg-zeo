---
name: ffmpeg-zeo
description: >-
  Build and run FFmpeg filter graphs with ffmpeg-zeo. Probe first, compile before
  run, prefer recipes, never invent filter names.
---

# ffmpeg-zeo (Claude Code)

Same workflow as the Cursor skill: doctor → probe → recipe or Graph JSON → compile → run.

Python: `from ffmpeg_zeo import input, probe, convert`

CLI: `uv run ffmpeg-zeo probe FILE --json`

MCP tools: `doctor`, `probe_file`, `compile_graph_json`, `run_graph`, `convert_file`, `list_ffmpeg_filters`, `run_named_recipe`.
