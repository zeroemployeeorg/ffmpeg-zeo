"""stdio MCP server. Log only to stderr — stdout is the protocol wire."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from ffmpeg_zeo.bins import resolve_binaries
from ffmpeg_zeo.catalog import filter_help, list_codecs, list_filters
from ffmpeg_zeo.compile import compile_graph
from ffmpeg_zeo.errors import BinaryNotFoundError
from ffmpeg_zeo.ir import Graph
from ffmpeg_zeo.probe import probe
from ffmpeg_zeo.recipes import RECIPES, convert, run_recipe
from ffmpeg_zeo.run import run

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("ffmpeg_zeo.mcp")


def _server() -> Any:
    from mcp.server import MCPServer

    mcp = MCPServer("ffmpeg-zeo")

    @mcp.tool()
    def doctor() -> dict[str, Any]:
        """Resolve ffmpeg/ffprobe paths and report how they were found."""
        try:
            info = resolve_binaries(download=False)
        except BinaryNotFoundError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "ffmpeg": str(info.ffmpeg),
            "ffprobe": str(info.ffprobe),
            "source": info.source,
            "license": info.license,
        }

    @mcp.tool()
    def probe_file(path: str) -> dict[str, Any]:
        """Probe a media file with ffprobe and return typed JSON."""
        return probe(path).model_dump()

    @mcp.tool()
    def compile_graph_json(graph_json: str) -> dict[str, Any]:
        """Compile a Graph JSON document to an ffmpeg argv list (does not run)."""
        graph = Graph.model_validate_json(graph_json)
        return {"argv": compile_graph(graph)}

    @mcp.tool()
    def run_graph(graph_json: str) -> dict[str, Any]:
        """Run a Graph JSON document with ffmpeg."""
        graph = Graph.model_validate_json(graph_json)
        result = run(graph)
        return {"returncode": result.returncode, "argv": result.argv}

    @mcp.tool()
    def convert_file(src: str, dst: str) -> dict[str, Any]:
        """One-liner conversion via the convert recipe."""
        graph = convert(src, dst)
        result = run(graph)
        return {"path": dst, "returncode": result.returncode, "argv": result.argv}

    @mcp.tool()
    def list_ffmpeg_filters() -> list[dict[str, Any]]:
        """List filters from the installed ffmpeg binary. Do not invent names."""
        return [item.model_dump() for item in list_filters()]

    @mcp.tool()
    def list_ffmpeg_codecs() -> list[dict[str, Any]]:
        return [item.model_dump() for item in list_codecs()]

    @mcp.tool()
    def ffmpeg_filter_help(name: str) -> str:
        return filter_help(name)

    @mcp.tool()
    def list_recipes() -> list[str]:
        return sorted(RECIPES)

    @mcp.tool()
    def run_named_recipe(
        name: str, src: str, dst: str, extra_json: str = "{}"
    ) -> dict[str, Any]:
        extras = json.loads(extra_json) if extra_json else {}
        if not isinstance(extras, dict):
            raise TypeError("extra_json must be an object")
        graph = run_recipe(name, src=src, dst=dst, **extras)
        result = run(graph)
        return {"returncode": result.returncode, "argv": result.argv}

    return mcp


def main() -> None:
    mcp = _server()
    import asyncio

    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
