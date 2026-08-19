"""Typed errors."""

from __future__ import annotations


class FFmpegError(Exception):
    """A subprocess (ffmpeg or ffprobe) failed or could not be started."""

    def __init__(
        self,
        cmd: str,
        *,
        argv: list[str] | None = None,
        returncode: int | None = None,
        stdout: bytes | None = None,
        stderr: bytes | None = None,
        message: str | None = None,
    ) -> None:
        self.cmd = cmd
        self.argv = argv or []
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        detail = message or f"{cmd} error (see stderr output for detail)"
        super().__init__(detail)


class BinaryNotFoundError(FFmpegError):
    """ffmpeg or ffprobe is not on PATH and no provider is configured."""

    def __init__(self, name: str) -> None:
        super().__init__(
            name,
            message=(
                f"{name} not found. Install FFmpeg, set {name.upper()}_BINARY, "
                "or run `ffmpeg-zeo doctor --download` on Linux or Windows."
            ),
        )
        self.name = name
