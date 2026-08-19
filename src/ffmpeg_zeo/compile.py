"""Compile a Graph IR into ffmpeg argv."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from ffmpeg_zeo.escape import escape_chars, escape_filter_token
from ffmpeg_zeo.ir import FilterNode, Graph, InputNode, OutputNode, StreamRef


def kwargs_to_cli(kwargs: Mapping[str, Any]) -> list[str]:
    args: list[str] = []
    for key in sorted(kwargs):
        value = kwargs[key]
        if isinstance(value, Iterable) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            for item in value:
                args.append(f"-{key}")
                if item is not None:
                    args.append(str(item))
            continue
        args.append(f"-{key}")
        if value is not None:
            args.append(str(value))
    return args


def _video_size(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Iterable):
        seq = list(value)
        return f"{seq[0]}x{seq[1]}"
    return str(value)


def _input_args(node: InputNode) -> list[str]:
    kwargs = dict(node.kwargs)
    args: list[str] = []
    fmt = kwargs.pop("format", None)
    video_size = kwargs.pop("video_size", None)
    if fmt is not None:
        args += ["-f", str(fmt)]
    if video_size is not None:
        args += ["-video_size", _video_size(video_size)]
    args += kwargs_to_cli(kwargs)
    args += ["-i", node.filename]
    return args


def _format_stream(
    stream_name: dict[tuple[str, int | str | None], str],
    ref: StreamRef,
    *,
    input_ids: set[str],
    is_final: bool = False,
) -> str:
    prefix = stream_name[(ref.node_id, ref.pad)]
    suffix = f":{ref.selector}" if ref.selector else ""
    if is_final and ref.node_id in input_ids:
        return f"{prefix}{suffix}"
    return f"[{prefix}{suffix}]"


def _output_args(
    node: OutputNode,
    stream_name: dict[tuple[str, int | str | None], str],
    input_ids: set[str],
) -> list[str]:
    args: list[str] = []
    if not node.inputs:
        raise ValueError(f"Output node {node.id} has no mapped streams")
    for ref in node.inputs:
        name = _format_stream(stream_name, ref, input_ids=input_ids, is_final=True)
        if name != "0" or len(node.inputs) > 1:
            args += ["-map", name]
    kwargs = dict(node.kwargs)
    if "format" in kwargs:
        args += ["-f", str(kwargs.pop("format"))]
    if "video_bitrate" in kwargs:
        args += ["-b:v", str(kwargs.pop("video_bitrate"))]
    if "audio_bitrate" in kwargs:
        args += ["-b:a", str(kwargs.pop("audio_bitrate"))]
    if "video_size" in kwargs:
        args += ["-video_size", _video_size(kwargs.pop("video_size"))]
    args += kwargs_to_cli(kwargs)
    args += [node.filename]
    return args


def _topo_filters(graph: Graph) -> list[FilterNode]:
    by_id = {node.id: node for node in graph.filters}
    ordered: list[FilterNode] = []
    seen: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in seen or node_id not in by_id:
            return
        node = by_id[node_id]
        for ref in node.inputs:
            visit(ref.node_id)
        seen.add(node_id)
        ordered.append(node)

    for out in graph.outputs:
        for ref in out.inputs:
            visit(ref.node_id)
    for node in graph.filters:
        visit(node.id)
    return ordered


def _pad_sort_key(pad: int | str | None) -> tuple[int, int | str]:
    if pad is None:
        return (0, 0)
    if isinstance(pad, int):
        return (1, pad)
    return (2, pad)


def _outgoing_pads(graph: Graph) -> dict[str, list[int | str | None]]:
    used: dict[str, set[int | str | None]] = defaultdict(set)
    for filt in graph.filters:
        for ref in filt.inputs:
            used[ref.node_id].add(ref.pad)
    for out in graph.outputs:
        for ref in out.inputs:
            used[ref.node_id].add(ref.pad)
    return {node_id: sorted(pads, key=_pad_sort_key) for node_id, pads in used.items()}


def _filter_spec(
    node: FilterNode,
    outgoing: list[int | str | None],
    stream_name: dict[tuple[str, int | str | None], str],
    input_ids: set[str],
) -> str:
    args = list(node.args)
    kwargs = dict(node.kwargs)
    if node.name in {"split", "asplit"}:
        args = [len(outgoing)]

    arg_params = [escape_filter_token(v) for v in args]
    kwarg_params = [
        f"{escape_filter_token(k)}={escape_filter_token(kwargs[k])}"
        for k in sorted(kwargs)
    ]
    params = arg_params + kwarg_params
    params_text = escape_filter_token(node.name)
    if params:
        params_text += "=" + ":".join(params)
    params_text = escape_chars(params_text, "\\'[],;")

    inputs = "".join(
        _format_stream(stream_name, ref, input_ids=input_ids) for ref in node.inputs
    )
    outputs = "".join(f"[{stream_name[(node.id, pad)]}]" for pad in outgoing)
    return f"{inputs}{params_text}{outputs}"


def _maybe_auto_split(graph: Graph) -> Graph:
    """Insert split/asplit when a filter pad fans out more than once."""
    uses: dict[tuple[str, int | str | None, str | None], list[tuple[str, str, int]]] = (
        defaultdict(list)
    )
    for filt in graph.filters:
        if filt.name in {"split", "asplit"}:
            continue
        for idx, ref in enumerate(filt.inputs):
            uses[(ref.node_id, ref.pad, ref.selector)].append(("filter", filt.id, idx))
    for out in graph.outputs:
        for idx, ref in enumerate(out.inputs):
            uses[(ref.node_id, ref.pad, ref.selector)].append(("output", out.id, idx))

    filter_ids = {filt.id for filt in graph.filters}
    splits: list[FilterNode] = []
    replacements: dict[tuple[str, str, int], StreamRef] = {}
    split_i = 0

    for key, consumers in uses.items():
        if len(consumers) <= 1:
            continue
        node_id, pad, selector = key
        if node_id not in filter_ids:
            continue
        src = next(filt for filt in graph.filters if filt.id == node_id)
        split_name = "asplit" if src.name.startswith("a") else "split"
        sid = f"autosplit{split_i}"
        split_i += 1
        splits.append(
            FilterNode(
                id=sid,
                name=split_name,
                inputs=[StreamRef(node_id=node_id, pad=pad, selector=selector)],
            )
        )
        for out_pad, consumer in enumerate(consumers):
            replacements[consumer] = StreamRef(node_id=sid, pad=out_pad)

    if not splits:
        return graph

    new_filters: list[FilterNode] = []
    for filt in graph.filters:
        new_inputs = [
            replacements.get(("filter", filt.id, idx), ref)
            for idx, ref in enumerate(filt.inputs)
        ]
        new_filters.append(filt.model_copy(update={"inputs": new_inputs}))
    new_filters.extend(splits)

    new_outputs = []
    for out in graph.outputs:
        new_inputs = [
            replacements.get(("output", out.id, idx), ref)
            for idx, ref in enumerate(out.inputs)
        ]
        new_outputs.append(out.model_copy(update={"inputs": new_inputs}))

    return graph.model_copy(update={"filters": new_filters, "outputs": new_outputs})


def get_args(graph: Graph, *, overwrite: bool | None = None) -> list[str]:
    graph = _maybe_auto_split(graph)
    ordered = _topo_filters(graph)
    outgoing = _outgoing_pads(graph)
    input_ids = {node.id for node in graph.inputs}

    stream_name: dict[tuple[str, int | str | None], str] = {}
    for i, node in enumerate(graph.inputs):
        stream_name[(node.id, None)] = str(i)

    stream_count = 0
    for filt in ordered:
        for pad in outgoing.get(filt.id, []):
            stream_name[(filt.id, pad)] = f"s{stream_count}"
            stream_count += 1

    args: list[str] = []
    for node in graph.inputs:
        args += _input_args(node)

    specs = [
        _filter_spec(node, outgoing.get(node.id, []), stream_name, input_ids)
        for node in ordered
        if outgoing.get(node.id)
    ]
    if specs:
        args += ["-filter_complex", ";".join(specs)]

    for node in graph.outputs:
        args += _output_args(node, stream_name, input_ids)

    args += list(graph.global_args)
    use_overwrite = overwrite
    if use_overwrite is None:
        use_overwrite = graph.overwrite == "always"
    if use_overwrite:
        args += ["-y"]
    elif graph.overwrite == "never":
        args += ["-n"]
    return args


def compile_graph(
    graph: Graph,
    *,
    cmd: str | list[str] = "ffmpeg",
    overwrite: bool | None = None,
) -> list[str]:
    if isinstance(cmd, str):
        prefix = [cmd]
    else:
        prefix = list(cmd)
    return prefix + get_args(graph, overwrite=overwrite)
