"""Integration tests against a real ffmpeg/ffprobe binary."""

from __future__ import annotations

import os
import shutil

import pytest

import ffmpeg_zeo as ffmpeg

pytestmark = pytest.mark.integration

SAMPLE = os.path.join(os.path.dirname(__file__), "sample_data")
IN1 = os.path.join(SAMPLE, "in1.mp4")


def test_probe_sample() -> None:
    if shutil.which("ffprobe") is None and shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg/ffprobe not installed")
    data = ffmpeg.probe(IN1)
    assert data.duration_seconds is not None
    assert data.has_video


def test_run_true() -> None:
    stream = ffmpeg.input("dummy.mp4").output("dummy2.mp4")
    ffmpeg.run(stream, cmd="true")
