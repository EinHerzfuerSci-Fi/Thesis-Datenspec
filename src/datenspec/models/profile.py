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
        "dark: the gain of each lit capture predicted from the most recent dark capture "
        "before it in the cycle and the LED's share in the previous cycle.",
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


class CaptureStep(SpecModel):
    """
    One capture of the cycle and its timing. The fields are in the time order of the
    phases: gap (all LEDs off), settle (LED on), delay (LED off), then the integration,
    with the LED on for on_ms after its start. The LED never switches during an
    integration, so a gated capture (delay_ms > 0) integrates entirely in the dark.
    """

    illumination: Illumination = Field(
        alias="ill",
        description="LED of this capture; dark means none.",
        json_schema_extra=meta(since=3),
    )
    gap_ms: Count = Field(
        description="All LEDs off before this capture starts; the dark time of a dark "
        "capture.",
        json_schema_extra=meta(unit="ms", since=3),
    )
    settle_ms: Count = Field(
        description="LED on before the integration starts.",
        json_schema_extra=meta(unit="ms", since=3),
    )
    delay_ms: Count = Field(
        description="LED off between the end of settle_ms and the integration start. 0: "
        "the LED stays on into the integration; > 0: gated capture, integrating the "
        "light that lingers after the pulse.",
        json_schema_extra=meta(unit="ms", since=3),
    )
    on_ms: Count = Field(
        description="LED on after the integration starts.",
        json_schema_extra=meta(unit="ms", since=3),
    )

    @property
    def gated(self) -> bool:
        """The LEDs are off during the integration; data sends this as gated."""
        return self.delay_ms > 0

    @model_validator(mode="after")
    def _timing_matches_illumination(self) -> Self:
        if self.illumination == "dark":
            if self.settle_ms or self.delay_ms or self.on_ms:
                raise ValueError(
                    "a dark capture has no LED phase: settle_ms, delay_ms and on_ms "
                    "must be 0"
                )
        elif self.gated:
            if self.settle_ms == 0:
                raise ValueError("a gated capture needs settle_ms > 0, its pulse")
            if self.on_ms:
                raise ValueError(
                    "a gated capture needs on_ms 0: the LED never switches during an "
                    "integration"
                )
        elif self.on_ms == 0:
            raise ValueError("a lit capture that is not gated needs on_ms > 0")
        return self


class CaptureConfig(SpecModel):
    """Timing of one TCS3448 capture cycle."""

    captures: list[CaptureStep] = Field(
        description="Captures in acquisition order, each with its own timing; at least "
        "one dark. data m.tcs3448 holds one capture per step, in this order.",
        json_schema_extra=meta(since=3),
    )
    gain_control: GainControl = Field(json_schema_extra=meta(since=2))

    @property
    def sequence(self) -> list[Illumination]:
        """ill of every capture in order; derived, not sent (cfg.capture.sequence in v2)."""
        return [c.illumination for c in self.captures]

    @model_validator(mode="after")
    def _has_dark(self) -> Self:
        # A profile the data record could never satisfy is rejected where it is written.
        # Gated captures are lit (ill names their LED), so they never count as dark.
        # More than one dark is allowed: a dark subtracts exactly only at the gain and
        # integration of the captures it serves, so each setting needs its own.
        if "dark" not in self.sequence:
            raise ValueError("captures need at least one dark capture, got 0")
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
