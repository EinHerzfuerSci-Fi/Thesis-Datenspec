"""
TCS3448 quantities that follow from the datasheet and the wire format alone.

Normalisation with the vendor calibration tables belongs to the analysis software.
"""

from dataclasses import dataclass

from datenspec.models import TcsCapture

GAIN_FACTORS: tuple[float, ...] = tuple(0.5 * 2**i for i in range(13))
"""Gain index 0..12 -> factor 0.5, 1, 2, ..., 2048."""

ASTEP_US = 2.78
"""Duration of one integration step."""

MAX_COUNT = 65535

NEAR_FULL_SCALE = 0.9
"""Default fraction of full scale above which a raw value is flagged."""


def gain_factor(index: int) -> float:
    return GAIN_FACTORS[index]


def integration_time_ms(atime: int, astep: int) -> float:
    return (atime + 1) * (astep + 1) * ASTEP_US / 1000


def full_scale(atime: int, astep: int) -> int:
    """Highest reachable count; short integrations saturate below the 16-bit limit."""
    return min(MAX_COUNT, (atime + 1) * (astep + 1))


@dataclass(frozen=True)
class CaptureFlags:
    saturated: bool
    """Sensor reported analog or digital saturation (sat)."""
    near_full_scale: tuple[str, ...]
    """Channels whose raw value is at or above the threshold."""

    @property
    def suspect(self) -> bool:
        return self.saturated or bool(self.near_full_scale)


def capture_flags(
    capture: TcsCapture, threshold: float = NEAR_FULL_SCALE
) -> CaptureFlags:
    """
    Flag saturation and, separately, raw values within `threshold` of full scale, so
    the analysis can keep a safety margin instead of relying on sat alone.
    """
    limit = threshold * full_scale(capture.atime, capture.astep)
    near = tuple(
        channel
        for channel, value in capture.raw.model_dump().items()
        if value is not None and value >= limit
    )
    return CaptureFlags(saturated=capture.saturated, near_full_scale=near)
