from typing import Any, Literal

from pydantic import Field

from ._base import meta
from .header import RecordHeader
from .vocab import LogLevel


class LogRecord(RecordHeader):
    """
    Firmware log message. Separate from err: err reports module failures with a code,
    log is the general diagnostic stream.
    """

    kind: Literal["log"] = Field(alias="k", json_schema_extra=meta(since=2))
    level: LogLevel = Field(
        alias="lvl", description="Log level.", json_schema_extra=meta(since=2)
    )
    module: str = Field(
        description="Module of the firmware the message originates from.",
        json_schema_extra=meta(since=2),
    )
    msg: str = Field(
        description="Human-readable message.", json_schema_extra=meta(since=2)
    )
    ctx: dict[str, Any] | None = Field(
        default=None,
        description="Structured context as key/value pairs; not validated.",
        json_schema_extra=meta(since=2),
    )
