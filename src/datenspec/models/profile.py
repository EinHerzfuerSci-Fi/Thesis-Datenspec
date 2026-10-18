"""
Measurement profiles: how a run measures, as opposed to when it runs.

The device keeps its profiles in a file (name -> RunConfig) and a start command picks
one by name. The run's start record carries the name and the resolved RunConfig, so a
run stays interpretable after the profile file changes or when no laptop started it.
"""

from typing import Annotated, Self

from pydantic import Field, model_validator

from ._base import Count, SpecModel, meta
from .vocab import GainMode, Illumination

ProfileName = Annotated[str, Field(pattern=r"^[a-z0-9_]+$")]
"""Same alphabet as tag keys: safe in file names, topics and CLI arguments."""


GainIndex = Annotated[int, Field(ge=0, le=12)]
"""TCS3448 gain index 0..12, factor 0.5..2048 as in data m.tcs3448[].gain."""


class GainControl(SpecModel):
    """How the run picks the gain of each capture."""

    mode: GainMode = Field(
        description="fixed: every capture uses the gain its profile names. ams: the "
        "auto-gain search of ams AN001051, per illumination from one cycle to the next. "
        "dark: the gain of each lit capture predicted from the cycle's dark capture and "
        "the LED's share in the previous cycle.",
        json_schema_extra=meta(since=2),
    )
    stages: list[GainIndex] | None = Field(
        description="Gain indices the regulation may choose from, ascending; every "
        "capture gain of the run is one of them. null exactly when mode is fixed.",
        json_schema_extra=meta(since=2),
    )

    @model_validator(mode="after")
    def _stages_match_mode(self) -> Self:
        if self.mode == "fixed":
            if self.stages is not None:
                raise ValueError("stages must be null when mode is fixed")
            return self
        if self.stages is None or len(self.stages) < 2:
            raise ValueError("a regulating mode needs at least two stages")
        if any(a >= b for a, b in zip(self.stages, self.stages[1:])):
            raise ValueError("stages must be strictly ascending")
        return self


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
    gain_control: GainControl = Field(json_schema_extra=meta(since=2))

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
