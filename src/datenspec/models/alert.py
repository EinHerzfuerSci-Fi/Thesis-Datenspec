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
    id: AlarmId = Field(json_schema_extra=meta())
    state: AlertState = Field(json_schema_extra=meta())
    source: str = Field(
        alias="src",
        description="Source of the alert.",
        json_schema_extra=meta(),
    )
    value: float | None = Field(
        default=None,
        alias="val",
        json_schema_extra=meta(),
    )
    threshold: float | None = Field(
        default=None,
        alias="thr",
        json_schema_extra=meta(),
    )
    severity: AlarmSeverity = Field(alias="sev", json_schema_extra=meta())
    ref_seq: Count = Field(
        description="seq of the data record that triggered the transition.",
        json_schema_extra=meta(),
    )

    @model_validator(mode="after")
    def _threshold_required_with_value(self) -> Self:
        if self.value is not None and self.threshold is None:
            raise ValueError("thr is required when val is set")
        return self
