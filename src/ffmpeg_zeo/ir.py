"""Pydantic graph IR — the shared lingua franca for Python, CLI, and MCP."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

OverwritePolicy = Literal["always", "never"]


class StreamRef(BaseModel):
    """A labeled edge into a downstream node."""

    node_id: str
    pad: int | str | None = None
    selector: str | None = None

    model_config = {"frozen": True}


class InputNode(BaseModel):
    id: str
    filename: str
    kwargs: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class FilterNode(BaseModel):
    id: str
    name: str
    inputs: list[StreamRef]
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class OutputNode(BaseModel):
    id: str
    filename: str
    inputs: list[StreamRef]
    kwargs: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class Graph(BaseModel):
    """Serializable FFmpeg filter graph."""

    inputs: list[InputNode] = Field(default_factory=list)
    filters: list[FilterNode] = Field(default_factory=list)
    outputs: list[OutputNode] = Field(default_factory=list)
    global_args: list[str] = Field(default_factory=list)
    overwrite: OverwritePolicy | None = None

    @field_validator("inputs", "filters", "outputs")
    @classmethod
    def _unique_ids(cls, nodes: list[Any]) -> list[Any]:
        seen: set[str] = set()
        for node in nodes:
            if node.id in seen:
                raise ValueError(f"duplicate node id: {node.id}")
            seen.add(node.id)
        return nodes

    def node_map(self) -> dict[str, InputNode | FilterNode | OutputNode]:
        mapping: dict[str, InputNode | FilterNode | OutputNode] = {}
        for node in (*self.inputs, *self.filters, *self.outputs):
            mapping[node.id] = node
        return mapping
