"""Shared model base, field metadata and constrained types."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

SCHEMA_VERSION = 3
"""
Wire-format version, sent as `v` in every record. Bumped only on breaking changes;
the package itself is versioned separately with SemVer.
"""

MIN_SCHEMA_VERSION = 2
"""
Oldest version the header accepts. v1 was never deployed (no device or SD card wrote
it), so its readers were dropped instead of kept alongside v2.
"""

CAPTURE_TIMING_VERSION = 3
"""
Oldest version data and run start records accept: v3 replaced the run-wide capture
timing by one timing per capture and added data m.tcs3448[].gated. Kinds whose shape
v3 left unchanged still accept v2, so records device firmware 1.0.0 wrote stay valid.
"""

FORBID_EXTRA = "forbid_extra"
"""
Context flag for validation, runtime can ignore unknown keys to enable backwards compatibility of the readers.
"""


def meta(unit: str | None = None, since: int = 1) -> dict[str, Any]:
    """JSON-Schema extension keys."""
    extra: dict[str, Any] = {"x-since": since}
    if unit is not None:
        extra["x-unit"] = unit
    return extra


class SpecModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
        strict=True,
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _forbid_extra_on_request(cls, data: Any, info: ValidationInfo) -> Any:
        if isinstance(data, dict) and info.context and info.context.get(FORBID_EXTRA):
            known = set(cls.model_fields)
            known |= {f.alias for f in cls.model_fields.values() if f.alias}
            unknown = set(data) - known
            if unknown:
                raise ValueError(f"unknown fields: {sorted(unknown)}")
        return data


HexId16 = Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]
"""64-bit ID as 16 lowercase hex chars (machine.unique_id(), DS18B20 ROM)."""

UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

Uuid = Annotated[str, Field(pattern=UUID_PATTERN)]
"""UUID in canonical lowercase form, e.g. str(uuid.uuid4()). str, not uuid.UUID: strict
mode would reject plain strings when validating dicts."""

Fraction = Annotated[float, Field(ge=0.0, le=1.0)]
Count = Annotated[int, Field(ge=0)]
Uint16 = Annotated[int, Field(ge=0, le=65535)]

# SemVer 2.0.0 (official regex, groups made non-capturing).
SEMVER_PATTERN = (
    r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*)?"
    r"(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?$"
)
