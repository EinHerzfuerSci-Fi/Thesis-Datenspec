"""
Measurement profiles: how a run measures, as opposed to when it runs.

The device keeps its profiles in a file (name -> RunConfig) and a start command picks
one by name. The run's start record carries the name and the resolved RunConfig, so a
run stays interpretable after the profile file changes or when no laptop started it.
"""

from typing import Annotated, Self

from pydantic import Field, model_validator

from ._base import Count, SpecModel, meta
from .vocab import Illumination

ProfileName = Annotated[str, Field(pattern=r"^[a-z0-9_]+$")]
"""Same alphabet as tag keys: safe in file names, topics and CLI arguments."""


class CaptureConfig(SpecModel):
    """Timing of one TCS3448 capture cycle."""

    sequence: list[Illumination] = Field(
        description="illumination values in capture order; exactly one dark, as in "
        "data m.tcs3448.",
        json_schema_extra=meta(since=2),
    )
    settle_ms: Count = Field(
        description="LED settling time before integration starts.",
        json_schema_extra=meta(unit="ms", since=2),
    )
    on_ms: Count = Field(
        description="LED on-time per capture.", json_schema_extra=meta(unit="ms", since=2)
    )

    @model_validator(mode="after")
    def _one_dark(self) -> Self:
        # A profile the data record could never satisfy is rejected where it is written.
        n_dark = self.sequence.count("dark")
        if n_dark != 1:
            raise ValueError(f"sequence needs exactly one dark capture, got {n_dark}")
        return self


class RunConfig(SpecModel):
    """
    Measurement settings of a run, resolved from its profile. Also the value type of the
    device's profile file.
    """

    sample_interval_ms: Annotated[int, Field(gt=0)] = Field(
        description="Interval between measurement cycles.",
        json_schema_extra=meta(unit="ms", since=2),
    )
    capture: CaptureConfig = Field(json_schema_extra=meta(since=2))


ProfileFile = Annotated[
    dict[ProfileName, RunConfig],
    # Pydantic exports the key pattern as patternProperties, which alone lets any other
    # key through in JSON Schema; closing it makes an editor reject "Turbidity" too.
    Field(json_schema_extra={"additionalProperties": False}),
]
"""The device's profile file: profile name -> settings. Not sent on the wire."""
