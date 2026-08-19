"""Convert a file with the one-liner recipe."""

from ffmpeg_zeo import convert, probe

SRC = "in.mp4"
DST = "out.mp3"

print(probe(SRC).model_dump())
graph = convert(SRC, DST)
print(graph.model_dump_json(indent=2))
