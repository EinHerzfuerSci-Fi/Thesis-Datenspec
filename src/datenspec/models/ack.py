from typing import Literal

from pydantic import Field

from ._base import Uuid, meta
from .header import RecordHeader
from .vocab import AckResult


class AckRecord(RecordHeader):
    """
    Answer to a cmd, one per device that received it (so one per Pico for a cmd to all).
    The header's run is the run after handling the command: the new run for an accepted
    start, the stopped run for an accepted stop.
    """

    kind: Literal["ack"] = Field(alias="k", json_schema_extra=meta(since=2))
    cmd_id: Uuid = Field(
        description="id of the acknowledged cmd.", json_schema_extra=meta(since=2)
    )
    result: AckResult = Field(
        alias="res",
        description="ok: executed; rejected: not applicable in the current state (e.g. "
        "start while a run is active, stop with a non-matching run); error: failed "
        "while executing.",
        json_schema_extra=meta(since=2),
    )
    msg: str | None = Field(
        description="Human-readable detail for rejected or error; null if none.",
        json_schema_extra=meta(since=2),
    )
