"""Compile/argv tests ported from ffmpeg-python."""

from __future__ import annotations

import os

import pytest

import ffmpeg_zeo as ffmpeg

SAMPLE = os.path.join(os.path.dirname(__file__), "sample_data")
IN1 = os.path.join(SAMPLE, "in1.mp4")
OVERLAY = os.path.join(SAMPLE, "overlay.png")
OUT1 = os.path.join(SAMPLE, "out1.mp4")


def test_escape_chars() -> None:
    from ffmpeg_zeo.escape import escape_chars

    assert escape_chars("a:b", ":") == r"a\:b"
    assert escape_chars("a\\:b", ":\\") == "a\\\\\\:b"
    assert (
        escape_chars("a:b,c[d]e%{}f'g'h\\i", "\\':,[]%")
        == "a\\:b\\,c\\[d\\]e\\%{}f\\'g\\'h\\\\i"
    )
    assert escape_chars(123, ":\\") == "123"


def test_fluent_equality() -> None:
    base1 = ffmpeg.input("dummy1.mp4")
    base2 = ffmpeg.input("dummy1.mp4")
    base3 = ffmpeg.input("dummy2.mp4")
    t1 = base1.trim(start_frame=10, end_frame=20)
    t2 = base1.trim(start_frame=10, end_frame=20)
    t3 = base1.trim(start_frame=10, end_frame=30)
    t4 = base2.trim(start_frame=10, end_frame=20)
    t5 = base3.trim(start_frame=10, end_frame=20)
    assert t1 == t2
    assert t1 != t3
    assert t1 == t4
    assert t1 != t5


def test_get_args_simple() -> None:
    out = ffmpeg.input("dummy.mp4").output("dummy2.mp4")
    assert out.get_args() == ["-i", "dummy.mp4", "dummy2.mp4"]


def test_global_args() -> None:
    out = (
        ffmpeg.input("dummy.mp4")
        .output("dummy2.mp4")
        .global_args("-progress", "someurl")
    )
    assert out.get_args() == [
        "-i",
        "dummy.mp4",
        "dummy2.mp4",
        "-progress",
        "someurl",
    ]


def test_repeated_args() -> None:
    out = ffmpeg.input("dummy.mp4").output(
        "dummy2.mp4", streamid=["0:0x101", "1:0x102"]
    )
    assert out.get_args() == [
        "-i",
        "dummy.mp4",
        "-streamid",
        "0:0x101",
        "-streamid",
        "1:0x102",
        "dummy2.mp4",
    ]


def _complex() -> ffmpeg.Stream:
    split = ffmpeg.input(IN1).vflip().split()
    overlay_file = ffmpeg.crop(ffmpeg.input(OVERLAY), 10, 10, 158, 112)
    return (
        ffmpeg.concat(
            split[0].trim(start_frame=10, end_frame=20),
            split[1].trim(start_frame=30, end_frame=40),
        )
        .overlay(overlay_file.hflip())
        .drawbox(50, 50, 120, 120, color="red", thickness=5)
        .output(OUT1)
        .overwrite_output()
    )


def test_complex_filter_args() -> None:
    args = _complex().get_args()
    assert args == [
        "-i",
        IN1,
        "-i",
        OVERLAY,
        "-filter_complex",
        "[0]vflip[s0];"
        "[s0]split=2[s1][s2];"
        "[s1]trim=end_frame=20:start_frame=10[s3];"
        "[s2]trim=end_frame=40:start_frame=30[s4];"
        "[s3][s4]concat=n=2[s5];"
        "[1]crop=158:112:10:10[s6];"
        "[s6]hflip[s7];"
        "[s5][s7]overlay=eof_action=repeat[s8];"
        "[s8]drawbox=50:50:120:120:red:t=5[s9]",
        "-map",
        "[s9]",
        OUT1,
        "-y",
    ]


def test_combined_output() -> None:
    i1 = ffmpeg.input(IN1)
    i2 = ffmpeg.input(OVERLAY)
    out = ffmpeg.output(i1, i2, OUT1)
    assert out.get_args() == [
        "-i",
        IN1,
        "-i",
        OVERLAY,
        "-map",
        "0",
        "-map",
        "1",
        OUT1,
    ]


@pytest.mark.parametrize("use_shorthand", [True, False])
def test_filter_with_selector(use_shorthand: bool) -> None:
    i = ffmpeg.input(IN1)
    if use_shorthand:
        v1 = i.video.hflip()
        a1 = i.audio.filter("aecho", 0.8, 0.9, 1000, 0.3)
    else:
        v1 = i["v"].hflip()
        a1 = i["a"].filter("aecho", 0.8, 0.9, 1000, 0.3)
    out = ffmpeg.output(a1, v1, OUT1)
    assert out.get_args() == [
        "-i",
        IN1,
        "-filter_complex",
        "[0:a]aecho=0.8:0.9:1000:0.3[s0];[0:v]hflip[s1]",
        "-map",
        "[s0]",
        "-map",
        "[s1]",
        OUT1,
    ]


def test_get_item_with_bad_selectors() -> None:
    stream = ffmpeg.input(IN1)
    with pytest.raises(ValueError, match="Stream already has a selector"):
        stream["a"]["a"]
    with pytest.raises(TypeError, match="Expected string index"):
        stream[5]  # type: ignore[index]


def test_concat_video_only() -> None:
    args = (
        ffmpeg.concat(ffmpeg.input("in1.mp4"), ffmpeg.input("in2.mp4"))
        .output("out.mp4")
        .get_args()
    )
    assert args == [
        "-i",
        "in1.mp4",
        "-i",
        "in2.mp4",
        "-filter_complex",
        "[0][1]concat=n=2[s0]",
        "-map",
        "[s0]",
        "out.mp4",
    ]


def test_concat_audio_only() -> None:
    args = (
        ffmpeg.concat(ffmpeg.input("in1.mp4"), ffmpeg.input("in2.mp4"), v=0, a=1)
        .output("out.mp4")
        .get_args()
    )
    assert args == [
        "-i",
        "in1.mp4",
        "-i",
        "in2.mp4",
        "-filter_complex",
        "[0][1]concat=a=1:n=2:v=0[s0]",
        "-map",
        "[s0]",
        "out.mp4",
    ]


def test_concat_audio_video() -> None:
    in1 = ffmpeg.input("in1.mp4")
    in2 = ffmpeg.input("in2.mp4")
    joined = ffmpeg.concat(in1.video, in1.audio, in2.hflip(), in2["a"], v=1, a=1).node
    args = ffmpeg.output(joined[0], joined[1], "out.mp4").get_args()
    assert args == [
        "-i",
        "in1.mp4",
        "-i",
        "in2.mp4",
        "-filter_complex",
        "[1]hflip[s0];[0:v][0:a][s0][1:a]concat=a=1:n=2:v=1[s1][s2]",
        "-map",
        "[s1]",
        "-map",
        "[s2]",
        "out.mp4",
    ]


def test_concat_wrong_stream_count() -> None:
    in1 = ffmpeg.input("in1.mp4")
    in2 = ffmpeg.input("in2.mp4")
    with pytest.raises(ValueError, match="Expected concat input streams"):
        ffmpeg.concat(in1.video, in1.audio, in2.hflip(), v=1, a=1)


def test_bitrate() -> None:
    args = (
        ffmpeg.input("in")
        .output("out", video_bitrate=1000, audio_bitrate=200)
        .get_args()
    )
    assert args == ["-i", "in", "-b:v", "1000", "-b:a", "200", "out"]


@pytest.mark.parametrize("video_size", [(320, 240), "320x240"])
def test_video_size(video_size: object) -> None:
    args = ffmpeg.input("in").output("out", video_size=video_size).get_args()
    assert args == ["-i", "in", "-video_size", "320x240", "out"]


def test_custom_filter() -> None:
    stream = ffmpeg.filter(
        ffmpeg.input("dummy.mp4"), "custom_filter", "a", "b", kwarg1="c"
    )
    out = ffmpeg.output(stream, "dummy2.mp4")
    assert out.get_args() == [
        "-i",
        "dummy.mp4",
        "-filter_complex",
        "[0]custom_filter=a:b:kwarg1=c[s0]",
        "-map",
        "[s0]",
        "dummy2.mp4",
    ]


def test_compile() -> None:
    out = ffmpeg.input("dummy.mp4").output("dummy2.mp4")
    assert out.compile() == ["ffmpeg", "-i", "dummy.mp4", "dummy2.mp4"]
    assert out.compile(cmd="ffmpeg.old") == [
        "ffmpeg.old",
        "-i",
        "dummy.mp4",
        "dummy2.mp4",
    ]


def test_input_start_time() -> None:
    assert ffmpeg.input("in", ss=10.5).output("out").get_args() == [
        "-ss",
        "10.5",
        "-i",
        "in",
        "out",
    ]


def test_merge_outputs() -> None:
    in_ = ffmpeg.input("in.mp4")
    out1 = in_.output("out1.mp4")
    out2 = in_.output("out2.mp4")
    assert ffmpeg.merge_outputs(out1, out2).get_args() == [
        "-i",
        "in.mp4",
        "out1.mp4",
        "out2.mp4",
    ]
    assert ffmpeg.get_args([out1, out2]) == ["-i", "in.mp4", "out2.mp4", "out1.mp4"]


def test_multi_passthrough() -> None:
    out1 = ffmpeg.input("in1.mp4").output("out1.mp4")
    out2 = ffmpeg.input("in2.mp4").output("out2.mp4")
    out = ffmpeg.merge_outputs(out1, out2)
    assert ffmpeg.get_args(out) == [
        "-i",
        "in1.mp4",
        "-i",
        "in2.mp4",
        "out1.mp4",
        "-map",
        "1",
        "out2.mp4",
    ]
    assert ffmpeg.get_args([out1, out2]) == [
        "-i",
        "in2.mp4",
        "-i",
        "in1.mp4",
        "out2.mp4",
        "-map",
        "1",
        "out1.mp4",
    ]


def test_passthrough_selectors() -> None:
    i1 = ffmpeg.input(IN1)
    args = ffmpeg.output(i1["1"], i1["2"], OUT1).get_args()
    assert args == ["-i", IN1, "-map", "0:1", "-map", "0:2", OUT1]


def test_mixed_passthrough_selectors() -> None:
    i1 = ffmpeg.input(IN1)
    args = ffmpeg.output(i1["1"].hflip(), i1["2"], OUT1).get_args()
    assert args == [
        "-i",
        IN1,
        "-filter_complex",
        "[0:1]hflip[s0]",
        "-map",
        "[s0]",
        "-map",
        "0:2",
        OUT1,
    ]


def test_pipe_args() -> None:
    width, height = 32, 32
    out = (
        ffmpeg.input(
            "pipe:0",
            format="rawvideo",
            pixel_format="rgb24",
            video_size=(width, height),
            framerate=10,
        )
        .trim(start_frame=2)
        .output("pipe:1", format="rawvideo")
    )
    assert out.get_args() == [
        "-f",
        "rawvideo",
        "-video_size",
        "32x32",
        "-framerate",
        "10",
        "-pixel_format",
        "rgb24",
        "-i",
        "pipe:0",
        "-filter_complex",
        "[0]trim=start_frame=2[s0]",
        "-map",
        "[s0]",
        "-f",
        "rawvideo",
        "pipe:1",
    ]


def test_drawtext_escape() -> None:
    args = ffmpeg.input("in").drawtext("test", font="a:b").output("out").get_args()
    assert args[:3] == ["-i", "in", "-filter_complex"]
    assert "drawtext=" in args[3]


def test_graph_json_roundtrip() -> None:
    graph = ffmpeg.input("in.mp4").hflip().output("out.mp4").overwrite("always").build()
    restored = ffmpeg.Graph.model_validate_json(graph.model_dump_json())
    assert ffmpeg.get_args(restored) == ffmpeg.get_args(graph)


def test_convert_recipe_args() -> None:
    graph = ffmpeg.convert("a.mp4", "a.mp3")
    args = ffmpeg.get_args(graph)
    assert args[:4] == ["-i", "a.mp4", "a.mp3", "-y"]
