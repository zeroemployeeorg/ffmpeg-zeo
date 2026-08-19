# Changelog

All notable changes to ffmpeg-zeo are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the project is below 1.0, minor releases may include breaking API changes.

## [Unreleased]

## [0.1.0] - 2026-08-19

### Added

- Typed Pydantic graph IR for inputs, filters, outputs, stream references,
  global arguments, and explicit overwrite policies.
- Fluent Python API with stream selectors, multi-input filters, graph merging,
  and automatic `split` / `asplit` insertion for fan-out.
- Deterministic compilation from graph IR to FFmpeg argv.
- Synchronous and asynchronous runners with typed results, errors, timeouts,
  captured output, and progress events.
- Typed ffprobe models with convenience properties for duration, dimensions,
  codecs, bitrate, frame rate, and stream presence.
- Nine reusable recipes for conversion, thumbnails, H.264 transcoding, audio
  and cover extraction, scaling, clipping, subtitle burning, and concatenation.
- JSON-first Typer CLI for probing, compiling, running, recipes, catalogs,
  filter help, binary diagnostics, and version information.
- Optional stdio MCP server with tools for probing, graph compilation and
  execution, conversion, recipes, and FFmpeg capability discovery.
- FFmpeg and ffprobe resolution through environment variables, `PATH`, cache,
  or explicit BtbN LGPL binary download on supported Linux and Windows hosts.
- PEP 561 `py.typed` marker and Apache-2.0 package licensing.
- GitHub Actions CI and Trusted Publishing workflows for TestPyPI and PyPI.
- Full installation, Python, CLI, Graph JSON, MCP, architecture, and
  contributor documentation.

### Known limitations

- Python 3.12 or newer is required.
- macOS requires system-provided FFmpeg; automatic binary download is only
  available for supported Linux and Windows architectures.
- FFmpeg features vary by build. Use the live catalog and filter-help commands
  instead of assuming a codec or filter is present.
- ffmpeg-zeo is inspired by ffmpeg-python but is not a drop-in replacement.

[Unreleased]: https://github.com/zeroemployeeorg/ffmpeg-zeo/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/zeroemployeeorg/ffmpeg-zeo/releases/tag/v0.1.0
