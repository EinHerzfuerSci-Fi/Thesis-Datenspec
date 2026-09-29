from typing import Literal, Self

from pydantic import ConfigDict, Field, model_validator

from ._base import Count, meta
from .header import RecordHeader
from .vocab import AlarmId, AlarmSeverity, AlertState


class AlertRecord(RecordHeader):
    """
    Record of raised or cleared alarms.
    """

    model_config = ConfigDict(
        json_schema_extra={"dependentRequired": {"val": ["thr"]}},
    )

    kind: Literal["alert"] = Field(alias="k", json_schema_extra=meta())
    id: AlarmId = Field(
        description="Alarm that changed state; also the last topic level.",
        json_schema_extra=meta(),
    )
    state: AlertState = Field(
        description="New state. Sent only on transitions, with hysteresis in firmware.",
        json_schema_extra=meta(),
    )
    source: str = Field(
        alias="src",
        description="Source of the alert.",
        json_schema_extra=meta(),
    )
    value: float | None = Field(
        default=None,
        alias="val",
        description="Value that triggered the transition, in the unit of the monitored quantity.",
        json_schema_extra=meta(),
    )
    threshold: float | None = Field(
        default=None,
        alias="thr",
        description="Threshold that was crossed, same unit as val.",
        json_schema_extra=meta(),
    )
    severity: AlarmSeverity = Field(
        alias="sev", description="Severity of the alarm.", json_schema_extra=meta()
    )
    ref_seq: Count = Field(
        description="seq of the data record that triggered the transition.",
        json_schema_extra=meta(),
    )

    @model_validator(mode="after")
    def _threshold_required_with_value(self) -> Self:
        if self.value is not None and self.threshold is None:
            raise ValueError("thr is required when val is set")
        return self
