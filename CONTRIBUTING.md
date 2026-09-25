# Contributing to ffmpeg-zeo

Thanks for helping improve ffmpeg-zeo. Bug fixes, tests, documentation, and
focused feature proposals are welcome.

## Development setup

You need Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and FFmpeg
with ffprobe on `PATH`.

```bash
git clone https://github.com/zeroemployeeorg/ffmpeg-zeo.git
cd ffmpeg-zeo
uv sync --extra dev --extra mcp
uv run ffmpeg-zeo doctor
```

You can instead set `FFMPEG_BINARY` and `FFPROBE_BINARY` to executable paths.

## Make changes

- Keep the public import as `import ffmpeg_zeo`.
- Add type annotations to public and internal Python APIs.
- Prefer named recipes for common media operations.
- Represent custom jobs as graph IR and compile before running.
- Never assume an FFmpeg filter is available across builds.
- Keep overwrite behavior explicit and non-interactive.
- Add or update tests for every behavior change.
- Update the README and changelog when changing user-facing behavior.

## Checks

Run these checks locally before opening a pull request. The repository has no
GitHub Actions workflows: CI does not run on GitHub.

```bash
uv run ruff format --check src tests examples
uv run ruff check src tests examples
uv run ty check
uv run pytest
uv build
```

To apply formatting:

```bash
uv run ruff format src tests examples
uv run ruff check --fix src tests examples
```

Integration tests invoke real ffmpeg and ffprobe binaries. Keep generated
outputs out of the repository.

## Pull requests

Keep pull requests focused and explain:

1. The problem and intended behavior.
2. Any public API, graph JSON, CLI, or MCP compatibility impact.
3. The commands used to verify the change.
4. Relevant FFmpeg version or platform details.

Do not commit media that you cannot redistribute, generated distributions,
virtual environments, credentials, API tokens, or downloaded FFmpeg binaries.

## Versioning and releases

ffmpeg-zeo follows Semantic Versioning. Before 1.0, a minor release may
contain breaking API changes. The package version is sourced from
`src/ffmpeg_zeo/__init__.py`; the Claude plugin manifest is kept in sync.

The repository has no GitHub Actions workflows: CI and trusted publishing do not
run on GitHub (operator direction of 2026-09-25, under R-36). The steps below
describe the removed `publish.yml` workflow and stay for reference until a new
release path is set:

1. Update `CHANGELOG.md` and verify all checks.
2. Publish the candidate to TestPyPI with the manual workflow.
3. Verify installation from TestPyPI.
4. Push an annotated `vX.Y.Z` tag matching the package version.
5. Confirm Trusted Publishing to PyPI and create the GitHub release.

Never publish a locally rebuilt artifact after validation. Promote the exact
wheel and source distribution produced by the release workflow.

## Reporting issues

Open an issue at
<https://github.com/zeroemployeeorg/ffmpeg-zeo/issues>. Include a minimal
reproduction, compiled argv, platform, Python version, and FFmpeg version.
Remove private paths, media, and credentials first.
