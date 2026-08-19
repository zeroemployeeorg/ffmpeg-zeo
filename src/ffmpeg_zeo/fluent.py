"""Fluent stream builder that emits Graph IR."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ffmpeg_zeo.compile import compile_graph as compile_ir
from ffmpeg_zeo.compile import get_args as get_args_ir
from ffmpeg_zeo.escape import escape_chars
from ffmpeg_zeo.ir import (
    FilterNode,
    Graph,
    InputNode,
    OutputNode,
    OverwritePolicy,
    StreamRef,
)
from ffmpeg_zeo.run import RunResult
from ffmpeg_zeo.run import run as run_graph
from ffmpeg_zeo.run import run_async as run_graph_async


@dataclass
class _Builder:
    inputs: list[InputNode] = field(default_factory=list)
    filters: list[FilterNode] = field(default_factory=list)
    outputs: list[OutputNode] = field(default_factory=list)
    global_args: list[str] = field(default_factory=list)
    overwrite: OverwritePolicy | None = None
    _seq: int = 0
    _merge_cache: dict[int, dict[str, str]] = field(default_factory=dict)

    def clone(self) -> _Builder:
        cloned = _Builder()
        cloned.inputs = list(self.inputs)
        cloned.filters = list(self.filters)
        cloned.outputs = list(self.outputs)
        cloned.global_args = list(self.global_args)
        cloned.overwrite = self.overwrite
        cloned._seq = self._seq
        return cloned

    def new_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}{self._seq}"

    def graph(self) -> Graph:
        return Graph(
            inputs=list(self.inputs),
            filters=list(self.filters),
            outputs=list(self.outputs),
            global_args=list(self.global_args),
            overwrite=self.overwrite,
        )

    def merge(self, other: _Builder) -> dict[str, str]:
        """Copy nodes from ``other``. Colliding ids are remapped.

        Returns a mapping of old id → id in this builder.
        """
        if other is self:
            return {}
        cached = self._merge_cache.get(id(other))
        if cached is not None:
            return cached
        existing = (
            {node.id for node in self.inputs}
            | {node.id for node in self.filters}
            | {node.id for node in self.outputs}
        )
        id_map: dict[str, str] = {}

        def take(old_id: str, prefix: str) -> str:
            if old_id not in existing:
                existing.add(old_id)
                id_map[old_id] = old_id
                return old_id
            new_id = self.new_id(prefix)
            existing.add(new_id)
            id_map[old_id] = new_id
            return new_id

        def remap_ref(ref: StreamRef) -> StreamRef:
            return ref.model_copy(
                update={"node_id": id_map.get(ref.node_id, ref.node_id)}
            )

        for node in other.inputs:
            found = next((item for item in self.inputs if item is node), None)
            if found is None:
                found = next(
                    (
                        item
                        for item in self.inputs
                        if item.filename == node.filename and item.kwargs == node.kwargs
                    ),
                    None,
                )
            if found is not None:
                id_map[node.id] = found.id
                continue
            new_id = take(node.id, "in")
            self.inputs.append(node.model_copy(update={"id": new_id}))
        for node in other.filters:
            found = next((item for item in self.filters if item is node), None)
            if found is not None:
                id_map[node.id] = found.id
                continue
            new_id = take(node.id, "f")
            self.filters.append(
                node.model_copy(
                    update={
                        "id": new_id,
                        "inputs": [remap_ref(ref) for ref in node.inputs],
                    }
                )
            )
        for node in other.outputs:
            found = next((item for item in self.outputs if item is node), None)
            if found is not None:
                id_map[node.id] = found.id
                continue
            new_id = take(node.id, "out")
            self.outputs.append(
                node.model_copy(
                    update={
                        "id": new_id,
                        "inputs": [remap_ref(ref) for ref in node.inputs],
                    }
                )
            )
        self.global_args.extend(other.global_args)
        if other.overwrite is not None:
            self.overwrite = other.overwrite
        self._seq = max(self._seq, other._seq)
        self._merge_cache[id(other)] = id_map
        return id_map


def _fingerprint_ref(builder: _Builder, ref: StreamRef) -> tuple[Any, ...]:
    return (
        _fingerprint_node(builder, ref.node_id),
        ref.pad,
        ref.selector,
    )


def _fingerprint_node(builder: _Builder, node_id: str) -> tuple[Any, ...]:
    for node in builder.inputs:
        if node.id == node_id:
            return ("input", node.filename, tuple(sorted(node.kwargs.items())))
    for node in builder.filters:
        if node.id == node_id:
            return (
                "filter",
                node.name,
                tuple(node.args),
                tuple(sorted(node.kwargs.items())),
                tuple(_fingerprint_ref(builder, item) for item in node.inputs),
            )
    for node in builder.outputs:
        if node.id == node_id:
            return (
                "output",
                node.filename,
                tuple(sorted(node.kwargs.items())),
                tuple(_fingerprint_ref(builder, item) for item in node.inputs),
            )
    return ("missing", node_id)


def _run_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    out = dict(kwargs)
    if "overwrite_output" in out:
        out["overwrite"] = out.pop("overwrite_output")
    return out


def get_args(
    spec: Stream | list[Stream] | tuple[Stream, ...] | Graph,
    overwrite_output: bool = False,
) -> list[str]:
    overwrite = True if overwrite_output else None
    if isinstance(spec, Graph):
        return get_args_ir(spec, overwrite=overwrite)
    if isinstance(spec, (list, tuple)):
        builder = spec[-1]._builder.clone()
        adopted = [_adopt(stream, builder) for stream in spec]
        graph = builder.graph()
        ids = [stream._ref.node_id for stream in adopted]
        by_id = {node.id: node for node in graph.outputs}
        graph = graph.model_copy(
            update={"outputs": [by_id[i] for i in reversed(ids) if i in by_id]}
        )
        return get_args_ir(graph, overwrite=overwrite)
    return spec.get_args(overwrite_output=overwrite_output)


def compile(
    spec: Stream | list[Stream] | Graph,
    cmd: str | list[str] = "ffmpeg",
    overwrite_output: bool = False,
) -> list[str]:
    prefix = cmd if isinstance(cmd, list) else [cmd]
    return prefix + get_args(spec, overwrite_output=overwrite_output)


class Stream:
    """A labeled edge in a building graph (filterable or output)."""

    def __init__(
        self,
        builder: _Builder,
        ref: StreamRef,
        *,
        kind: str = "filterable",
        multi: FilterNode | None = None,
    ) -> None:
        self._builder = builder
        self._ref = ref
        self._kind = kind
        self._multi = multi

    @property
    def node(self) -> Stream:
        """The producing filter, indexable for extra output pads."""
        if self._multi is not None:
            return Stream(
                self._builder,
                StreamRef(node_id=self._multi.id, pad=None),
                multi=self._multi,
            )
        return self

    def __getitem__(self, index: object) -> Stream:
        if isinstance(index, slice):
            raise TypeError("Expected string index (e.g. 'a')")
        if self._multi is not None and self._ref.pad is None:
            if not isinstance(index, (int, str)):
                raise TypeError("Expected string index (e.g. 'a')")
            return Stream(self._builder, StreamRef(node_id=self._multi.id, pad=index))
        if self._ref.selector is not None:
            raise ValueError(f"Stream already has a selector: {self}")
        if not isinstance(index, str):
            raise TypeError("Expected string index (e.g. 'a')")
        return Stream(
            self._builder,
            StreamRef(node_id=self._ref.node_id, pad=self._ref.pad, selector=index),
            kind=self._kind,
            multi=self._multi,
        )

    @property
    def audio(self) -> Stream:
        return self["a"]

    @property
    def video(self) -> Stream:
        return self["v"]

    def _fingerprint(self) -> tuple[Any, ...]:
        return _fingerprint_ref(self._builder, self._ref)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Stream):
            return NotImplemented
        return self._fingerprint() == other._fingerprint()

    def filter_multi_output(self, name: str, *args: Any, **kwargs: Any) -> Stream:
        return _filter_multi(self, name, args, kwargs)

    def filter(self, name: str, *args: Any, **kwargs: Any) -> Stream:
        return _filter_multi(self, name, args, kwargs)

    def split(self) -> Stream:
        return _filter_multi(self, "split", (), {})

    def asplit(self) -> Stream:
        return _filter_multi(self, "asplit", (), {})

    def hflip(self) -> Stream:
        return self.filter("hflip")

    def vflip(self) -> Stream:
        return self.filter("vflip")

    def trim(self, **kwargs: Any) -> Stream:
        return self.filter("trim", **kwargs)

    def setpts(self, expr: str) -> Stream:
        return self.filter("setpts", expr)

    def crop(self, x: Any, y: Any, width: Any, height: Any, **kwargs: Any) -> Stream:
        return _filter_multi(self, "crop", (width, height, x, y), kwargs)

    def drawbox(
        self,
        x: Any,
        y: Any,
        width: Any,
        height: Any,
        color: str,
        thickness: Any | None = None,
        **kwargs: Any,
    ) -> Stream:
        if thickness:
            kwargs["t"] = thickness
        return _filter_multi(self, "drawbox", (x, y, width, height, color), kwargs)

    def drawtext(
        self,
        text: str | None = None,
        x: int = 0,
        y: int = 0,
        *,
        escape_text: bool = True,
        **kwargs: Any,
    ) -> Stream:
        if text is not None:
            kwargs["text"] = escape_chars(text, "\\'%") if escape_text else text
        if x != 0:
            kwargs["x"] = x
        if y != 0:
            kwargs["y"] = y
        return self.filter("drawtext", **kwargs)

    def overlay(
        self, overlay: Stream, eof_action: str = "repeat", **kwargs: Any
    ) -> Stream:
        kwargs["eof_action"] = eof_action
        return _filter_n([self, overlay], "overlay", (), kwargs, max_inputs=2)

    def hue(self, **kwargs: Any) -> Stream:
        return self.filter("hue", **kwargs)

    def zoompan(self, **kwargs: Any) -> Stream:
        return self.filter("zoompan", **kwargs)

    def output(self, *args: Any, **kwargs: Any) -> Stream:
        streams: list[Stream] = [self]
        filename: str | None = None
        for arg in args:
            if isinstance(arg, Stream):
                streams.append(arg)
            elif isinstance(arg, str) and filename is None:
                filename = arg
            else:
                filename = str(arg)
        if filename is None:
            raise TypeError("output() requires a filename")
        return output(*streams, filename, **kwargs)

    def overwrite_output(self) -> Stream:
        self._builder.overwrite = "always"
        return self

    def overwrite(self, policy: OverwritePolicy = "always") -> Stream:
        self._builder.overwrite = policy
        return self

    def global_args(self, *args: str) -> Stream:
        self._builder.global_args.extend(args)
        return self

    def build(self) -> Graph:
        return self._builder.graph()

    def get_args(self, overwrite_output: bool = False) -> list[str]:
        overwrite = True if overwrite_output else None
        return get_args_ir(self.build(), overwrite=overwrite)

    def compile(
        self, cmd: str | list[str] = "ffmpeg", overwrite_output: bool = False
    ) -> list[str]:
        overwrite = True if overwrite_output else None
        return compile_ir(self.build(), cmd=cmd, overwrite=overwrite)

    def run(self, **kwargs: Any) -> RunResult:
        kwargs = _run_kwargs(kwargs)
        return run_graph(self.build(), **kwargs)

    def run_async(self, **kwargs: Any) -> Any:
        kwargs = _run_kwargs(kwargs)
        return run_graph_async(self.build(), **kwargs)


def _node_in_builder(
    builder: _Builder, node_id: str
) -> InputNode | FilterNode | OutputNode | None:
    for node in (*builder.inputs, *builder.filters, *builder.outputs):
        if node.id == node_id:
            return node
    return None


def _adopt(stream: Stream, builder: _Builder) -> Stream:
    if stream._builder is builder:
        return stream
    src = _node_in_builder(stream._builder, stream._ref.node_id)
    if src is not None and (
        src in builder.inputs or src in builder.filters or src in builder.outputs
    ):
        return Stream(builder, stream._ref, kind=stream._kind, multi=stream._multi)
    id_map = builder.merge(stream._builder)
    new_ref = stream._ref.model_copy(
        update={"node_id": id_map.get(stream._ref.node_id, stream._ref.node_id)}
    )
    multi = stream._multi
    if multi is not None:
        multi = multi.model_copy(update={"id": id_map.get(multi.id, multi.id)})
    adopted = Stream(builder, new_ref, kind=stream._kind, multi=multi)
    return adopted


def _filter_multi(
    stream: Stream, name: str, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> Stream:
    return _filter_n([stream], name, args, kwargs)


def _filter_n(
    streams: list[Stream],
    name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    max_inputs: int | None = None,
) -> Stream:
    if max_inputs is not None and len(streams) > max_inputs:
        raise ValueError(
            f"Expected at most {max_inputs} input stream(s); got {len(streams)}"
        )
    builder = streams[0]._builder.clone()
    adopted = [_adopt(stream, builder) for stream in streams]
    nid = builder.new_id("f")
    node = FilterNode(
        id=nid,
        name=name,
        inputs=[s._ref for s in adopted],
        args=list(args),
        kwargs=dict(kwargs),
    )
    builder.filters.append(node)
    return Stream(builder, StreamRef(node_id=nid, pad=None), multi=node)


def input(filename: str, **kwargs: Any) -> Stream:
    builder = _Builder()
    nid = builder.new_id("in")
    builder.inputs.append(InputNode(id=nid, filename=filename, kwargs=dict(kwargs)))
    return Stream(builder, StreamRef(node_id=nid, pad=None))


def output(*streams_and_file: Any, **kwargs: Any) -> Stream:
    streams: list[Stream] = []
    filename: str | None = None
    for item in streams_and_file:
        if isinstance(item, Stream):
            streams.append(item)
        else:
            filename = str(item)
    if filename is None or not streams:
        raise TypeError("output() requires at least one stream and a filename")
    builder = streams[0]._builder.clone()
    adopted = [_adopt(stream, builder) for stream in streams]
    nid = builder.new_id("out")
    node = OutputNode(
        id=nid,
        filename=filename,
        inputs=[s._ref for s in adopted],
        kwargs=dict(kwargs),
    )
    builder.outputs.append(node)
    return Stream(builder, StreamRef(node_id=nid, pad=None), kind="output")


def concat(*streams: Stream, **kwargs: Any) -> Stream:
    video_stream_count = int(kwargs.get("v", 1))
    audio_stream_count = int(kwargs.get("a", 0))
    stream_count = video_stream_count + audio_stream_count
    if stream_count and len(streams) % stream_count != 0:
        raise ValueError(
            f"Expected concat input streams to have length multiple of {stream_count} "
            f"(v={video_stream_count}, a={audio_stream_count}); got {len(streams)}"
        )
    kwargs = dict(kwargs)
    kwargs["n"] = int(len(streams) / stream_count) if stream_count else len(streams)
    return _filter_n(list(streams), "concat", (), kwargs)


def merge_outputs(*outputs: Stream) -> Stream:
    builder = outputs[0]._builder.clone()
    adopted = [_adopt(stream, builder) for stream in outputs]
    return Stream(builder, adopted[0]._ref, kind="output")


def filter_(stream: Stream, name: str, *args: Any, **kwargs: Any) -> Stream:
    return stream.filter(name, *args, **kwargs)


def filter_multi_output(
    stream_spec: Stream | list[Stream], name: str, *args: Any, **kwargs: Any
) -> Stream:
    streams = stream_spec if isinstance(stream_spec, list) else [stream_spec]
    return _filter_n(streams, name, args, kwargs)


def hflip(stream: Stream) -> Stream:
    return stream.hflip()


def vflip(stream: Stream) -> Stream:
    return stream.vflip()


def trim(stream: Stream, **kwargs: Any) -> Stream:
    return stream.trim(**kwargs)


def crop(
    stream: Stream, x: Any, y: Any, width: Any, height: Any, **kwargs: Any
) -> Stream:
    return stream.crop(x, y, width, height, **kwargs)


def overlay(
    main: Stream, overlay_stream: Stream, eof_action: str = "repeat", **kwargs: Any
) -> Stream:
    return main.overlay(overlay_stream, eof_action=eof_action, **kwargs)


def drawbox(
    stream: Stream,
    x: Any,
    y: Any,
    width: Any,
    height: Any,
    color: str,
    thickness: Any | None = None,
    **kwargs: Any,
) -> Stream:
    return stream.drawbox(x, y, width, height, color, thickness, **kwargs)


def drawtext(stream: Stream, text: str | None = None, **kwargs: Any) -> Stream:
    return stream.drawtext(text, **kwargs)
