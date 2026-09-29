from typing import Annotated

from pydantic import Field

from ._base import (
    MIN_SCHEMA_VERSION,
    SCHEMA_VERSION,
    SEMVER_PATTERN,
    Count,
    HexId16,
    SpecModel,
    meta,
)
from .vocab import LaptopKind, RecordKind


class MessageHeader(SpecModel):
    """Fields present in every JSON message, from the Pico and from the laptop."""

    schema_version: Annotated[int, Field(ge=MIN_SCHEMA_VERSION, le=SCHEMA_VERSION)] = (
        Field(
            alias="v",
            description="Version of the schema. Increased only on breaking changes.",
            json_schema_extra=meta(),
        )
    )
    kind: RecordKind | LaptopKind = Field(
        alias="k",
        description="Message kind.",
        json_schema_extra=meta(),
    )


class RecordHeader(MessageHeader):
    """Fields present in every record sent by the Pico."""

    kind: RecordKind = Field(
        alias="k",
        description="Record kind.",
        json_schema_extra=meta(),
    )
    device_id: HexId16 = Field(
        alias="dev",
        description="Hardware ID of the microcontroller",
        json_schema_extra=meta(),
    )
    firmware: str = Field(
        alias="fw",
        pattern=SEMVER_PATTERN,
        description="Firmware version (optionally containing the git commit hash)",
        json_schema_extra=meta(),
    )
    boot: Count = Field(
        description="Boot counter, stored on flash memory of the microcontroller.",
        json_schema_extra=meta(),
    )
    run: Count | None = Field(
        description="ID of the run (measurement series) this record belongs to; null "
        "outside a run. Unique per device: a counter stored on flash like boot, "
        "incremented and written before the run's start record, so a power loss can "
        "skip an ID but never reuse one. (dev, run) identifies a run.",
        json_schema_extra=meta(since=2),
    )
    seq: Count = Field(
        description="Sequence number per record kind, for dedup (QoS 1, SD replay) and "
        "gap detection per kind. For data it counts per run and restarts at 0 with "
        "every run; for all other kinds it counts per boot. Unique key: (dev, run, seq) "
        "for data, (dev, boot, k, seq) for all other kinds.",
        json_schema_extra=meta(),
    )
    uptime: Annotated[float, Field(ge=0.0)] = Field(
        alias="up",
        description="Monotonic seconds since boot, ms resolution. Time of measurement/event, "
        "not of sending. Use for intervals: ts may jump on re-sync.",
        json_schema_extra=meta(unit="s"),
    )
    timestamp: Annotated[int, Field(ge=0)] | None = Field(
        alias="ts",
        description="Unix seconds UTC after NTP sync, captured together with up. "
        "null while unsynced; key is mandatory.",
        json_schema_extra=meta(unit="s"),
    )
