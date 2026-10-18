"""
Start and end of a run (measurement series). The firmware decides when a run starts and
ends; one kind with the event in ev, so both travel on the same topic.

A run never spans a reboot: a run interrupted by a reboot is not resumed, and the
pipeline marks it aborted.
"""

from typing import Annotated, Literal

from pydantic import Field

from ._base import Count, Uuid, meta
from .header import RecordHeader
from .profile import ProfileName, RunConfig
from .vocab import RunEndReason


class _RunRecord(RecordHeader):
    kind: Literal["run"] = Field(alias="k", json_schema_extra=meta(since=2))
    run: Count = Field(
        description="ID of the run that starts or ends.",
        json_schema_extra=meta(since=2),
    )


class RunStartRecord(_RunRecord):
    """Start of a run; sent before its first data record."""

    event: Literal["start"] = Field(
        alias="ev", description="Run event.", json_schema_extra=meta(since=2)
    )
    duration: Annotated[int, Field(gt=0)] | None = Field(
        alias="dur",
        description="Planned duration; null = unlimited, runs until stopped.",
        json_schema_extra=meta(unit="s", since=2),
    )
    session: Uuid | None = Field(
        description="Session this run belongs to, taken from the start command; null if "
        "none.",
        json_schema_extra=meta(since=2),
    )
    cmd_id: Uuid | None = Field(
        description="id of the cmd that started the run; null if started on the device.",
        json_schema_extra=meta(since=2),
    )
    profile: ProfileName = Field(
        description="Profile the run measures with: the one named in the start command, "
        "or the device's default profile if the command named none or the run was "
        "started on the device.",
        json_schema_extra=meta(since=2),
    )
    cfg: RunConfig = Field(
        description="Settings of profile as resolved at the start, fixed for the whole "
        "run. Read these instead of the profile file, which may have changed since.",
        json_schema_extra=meta(since=2),
    )


class RunEndRecord(_RunRecord):
    """
    End of a run; sent after its last data record, in the same boot as the start record.
    Its up is greater than or equal to, and its seq greater than, those of the start
    record. This relates two records, so the models cannot check it.
    """

    event: Literal["end"] = Field(
        alias="ev", description="Run event.", json_schema_extra=meta(since=2)
    )
    cmd_id: Uuid | None = Field(
        description="id of the cmd that stopped the run; null if not ended by a command.",
        json_schema_extra=meta(since=2),
    )
    reason: RunEndReason = Field(
        description="Why the run ended: duration elapsed, manual stop (command or on "
        "the device), or error in the firmware. A run without an end record is marked "
        "aborted by the pipeline; the device never sends that.",
        json_schema_extra=meta(since=2),
    )
    n_data: Count = Field(
        description="Number of data records produced in this run. data seq starts at 0, "
        "so the run's data seq values are 0 to n_data - 1.",
        json_schema_extra=meta(since=2),
    )


RunRecord = Annotated[RunStartRecord | RunEndRecord, Field(discriminator="event")]
