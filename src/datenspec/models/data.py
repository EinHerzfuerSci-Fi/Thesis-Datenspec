from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ._base import Count, Fraction, HexId16, SpecModel, Uint16, meta
from .header import RecordHeader
from .vocab import Illumination

# Power-on register value: a conversion that never ran. Still valid on the wire, because
# rejecting it would discard the whole record and 85.0 can in principle be real.
DS18B20_POWER_ON_DEFAULT = 85.0

Ds18b20Temp = Annotated[float, Field(ge=-55.0, le=125.0)]


class Dht22(SpecModel):
    """Temperature and humidity; null as a whole if the sensor does not respond."""

    temperature: Annotated[float, Field(ge=-40.0, le=80.0)] | None = Field(
        alias="t", description="Air temperature.", json_schema_extra=meta(unit="°C")
    )
    relative_humidity: Fraction | None = Field(
        alias="rh",
        description="Relative humidity as fraction, not percent.",
        json_schema_extra=meta(unit="1"),
    )


_DUTY_DESC = (
    "PWM duty-cycle setpoint. Light output is neither linear in duty cycle nor "
    "independent of LED temperature."
)


class LedDuty(SpecModel):
    """Duty-cycle setpoint per LED. Model, not dict, so all three LEDs are required."""

    nir: Fraction = Field(description=_DUTY_DESC, json_schema_extra=meta(unit="1"))
    blue: Fraction = Field(description=_DUTY_DESC, json_schema_extra=meta(unit="1"))
    vis: Fraction = Field(description=_DUTY_DESC, json_schema_extra=meta(unit="1"))


_RAW_DESC = "Raw count of this spectral channel."


class TcsRaw(SpecModel):
    """Raw 16-bit counts per spectral channel. Flicker slots (5, 11, 17) are not sent."""

    f1: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    f2: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    f3: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    f4: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    f5: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    f6: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    f7: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    f8: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    fz: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    fy: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    fxl: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    nir: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    vis: Uint16 = Field(description=_RAW_DESC, json_schema_extra=meta(unit="counts"))
    vis_2: Uint16 | None = Field(
        default=None,
        description="VIS from the 2nd SMUX cycle; differs from vis if light changed mid-measurement.",
        json_schema_extra=meta(unit="counts"),
    )
    vis_3: Uint16 | None = Field(
        default=None,
        description="VIS from the 3rd SMUX cycle.",
        json_schema_extra=meta(unit="counts"),
    )


class TcsCapture(SpecModel):
    """One integration under one illumination."""

    illumination: Illumination = Field(
        alias="ill",
        description="Illumination during this capture; dark means all LEDs off.",
        json_schema_extra=meta(),
    )
    led: LedDuty = Field(json_schema_extra=meta())
    dt: int = Field(
        description="Start of integration relative to the record's up.",
        json_schema_extra=meta(unit="ms"),
    )
    gain: Annotated[int, Field(ge=0, le=12)] = Field(
        description="Gain index 0..12 (factor 0.5..2048) actually used; read back from the "
        "status register when AGC is active.",
        json_schema_extra=meta(),
    )
    atime: Annotated[int, Field(ge=0, le=255)] = Field(
        description="Integration time = (atime+1)*(astep+1)*2.78 us.",
        json_schema_extra=meta(),
    )
    astep: Annotated[int, Field(ge=0, le=65534)] = Field(
        description="See atime. Full scale = min(65535, (atime+1)*(astep+1)), computed, not sent.",
        json_schema_extra=meta(),
    )
    raw: TcsRaw = Field(json_schema_extra=meta())
    saturated: bool = Field(
        alias="sat",
        description="Analog or digital saturation.",
        json_schema_extra=meta(),
    )
    # Derived on the Pico with the vendor library; analysis relies on raw.
    lux: float | None = Field(
        default=None, description="Illuminance.", json_schema_extra=meta(unit="lx")
    )
    cct: float | None = Field(
        default=None,
        description="Correlated colour temperature.",
        json_schema_extra=meta(unit="K"),
    )
    cie_x: float | None = Field(
        default=None, description="CIE chromaticity x.", json_schema_extra=meta(unit="1")
    )
    cie_y: float | None = Field(
        default=None, description="CIE chromaticity y.", json_schema_extra=meta(unit="1")
    )

    @model_validator(mode="after")
    def _dark_means_leds_off(self) -> Self:
        if self.illumination == "dark" and any(self.led.model_dump().values()):
            raise ValueError("dark capture requires all LED duty cycles to be 0")
        return self


class Measurements(SpecModel):
    """
    One key per sensor; null means the sensor did not respond. Sensors added later are
    optional (default null).
    """

    ds18b20: (
        Annotated[dict[HexId16, Ds18b20Temp | None], Field(min_length=1, max_length=1)]
        | None
    ) = Field(
        description="Temperature keyed by ROM ID. Each device has exactly one DS18B20, "
        "so the map holds exactly this one key (info.ds18b20.rom). null if the bus "
        "does not respond. Firmware should send a failed conversion as null value; "
        "85.0 (power-on default) is accepted but flagged as suspect.",
        json_schema_extra=meta(unit="°C"),
    )
    dht22: Dht22 | None = Field(json_schema_extra=meta())
    tcs3448: list[TcsCapture] | None = Field(
        description="Captures in acquisition order, each under different illumination.",
        json_schema_extra=meta(),
    )

    def ds18b20_suspect(self) -> list[str]:
        """ROM IDs reporting the power-on default, i.e. likely a failed conversion."""
        if self.ds18b20 is None:
            return []
        return [rom for rom, t in self.ds18b20.items() if t == DS18B20_POWER_ON_DEFAULT]

    @model_validator(mode="after")
    def _one_dark_capture(self) -> Self:
        # Dark correction needs exactly one ambient reference per cycle.
        if self.tcs3448 is not None:
            n_dark = sum(c.illumination == "dark" for c in self.tcs3448)
            if n_dark != 1:
                raise ValueError(f"tcs3448 needs exactly one dark capture, got {n_dark}")
        return self


class DataRecord(RecordHeader):
    """One measurement cycle."""

    kind: Literal["data"] = Field(alias="k", json_schema_extra=meta())
    run: Count = Field(
        description="ID of the run this cycle belongs to; data exists only within a run.",
        json_schema_extra=meta(since=2),
    )
    measurements: Measurements = Field(alias="m", json_schema_extra=meta())
