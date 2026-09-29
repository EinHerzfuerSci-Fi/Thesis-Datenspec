from typing import Annotated

from pydantic import Field

from ._base import SCHEMA_VERSION, SEMVER_PATTERN, Count, HexId16, SpecModel, meta
from .vocab import RecordKind


class RecordHeader(SpecModel):
    """Fields present in every JSON record."""

    schema_version: Annotated[int, Field(ge=1, le=SCHEMA_VERSION)] = Field(
        alias="v",
        description="Version of the schema. Increased only on breaking changes.",
        json_schema_extra=meta(),
    )
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
    seq: Count = Field(
        description="Sequence number per boot. (dev, boot, seq) is the unique key for "
        "dedup (QoS 1, SD replay) and gap detection.",
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
