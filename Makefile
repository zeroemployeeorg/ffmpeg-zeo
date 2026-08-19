# ffmpeg-zeo development

.PHONY: setup format lint test check

setup:
	uv sync --extra dev --extra mcp

format:
	uv run ruff format src tests examples

lint:
	uv run ruff check src tests

test:
	uv run pytest

check: format lint test
