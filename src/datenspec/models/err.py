from typing import Literal

from pydantic import Field

from ._base import meta
from .header import RecordHeader
from .vocab import ModuleState


class ErrRecord(RecordHeader):
    kind: Literal["err"] = Field(alias="k", json_schema_extra=meta())
    module: str = Field(
        description="Module of the firmware the error originates from.",
        json_schema_extra=meta(),
    )
    reason: str = Field(
        description="Human-readable error description.", json_schema_extra=meta()
    )
    code: int = Field(
        description="Error code; its meaning depends on the module.",
        json_schema_extra=meta(),
    )
    state: ModuleState | None = Field(
        default=None,
        description="State of the module at the time of the error. Only applicable if the module has a state.",
        json_schema_extra=meta(),
    )
