"""Shared model base, field metadata and constrained types."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

SCHEMA_VERSION = 1
"""
Wire-format version, sent as `v` in every record. Bumped only on breaking changes;
the package itself is versioned separately with SemVer.
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

Fraction = Annotated[float, Field(ge=0.0, le=1.0)]
Count = Annotated[int, Field(ge=0)]
Uint16 = Annotated[int, Field(ge=0, le=65535)]

# SemVer 2.0.0 (official regex, groups made non-capturing).
SEMVER_PATTERN = (
    r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*)?"
    r"(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?$"
)
