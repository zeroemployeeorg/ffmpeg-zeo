# ffmpeg-zeo development

.PHONY: setup format lint type test build check

setup:
	uv sync --extra dev --extra mcp

format:
	uv run ruff format src tests examples

lint:
	uv run ruff check src tests examples
	uv run ruff format --check src tests examples

type:
	uv run ty check

test:
	uv run pytest

build:
	uv build

check: lint type test build
