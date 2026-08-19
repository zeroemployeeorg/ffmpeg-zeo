from __future__ import annotations

from ffmpeg_zeo.compile import get_args
from ffmpeg_zeo.recipes import list_recipes, scale, thumbnail, transcode_h264


def test_list_recipes() -> None:
    names = list_recipes()
    assert "convert" in names
    assert "thumbnail" in names


def test_thumbnail_args() -> None:
    args = get_args(thumbnail("a.mp4", "a.jpg", time=2.5))
    assert "-ss" in args
    assert "2.5" in args
    assert "-y" in args


def test_scale_and_h264() -> None:
    joined = " ".join(get_args(scale("a.mp4", "b.mp4", 640, -2)))
    assert "scale=640:-2" in joined
    joined = " ".join(get_args(transcode_h264("a.mp4", "b.mp4")))
    assert "libx264" in joined
