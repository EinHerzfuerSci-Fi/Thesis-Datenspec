from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ._base import Count, HexId16, SpecModel, meta
from .header import RecordHeader
from .profile import ProfileName
from .vocab import LedId


class SensorsFound(SpecModel):
    """Sensors detected at boot. Sensors added later are optional."""

    ds18b20: bool = Field(
        description="The DS18B20 was found on the bus.", json_schema_extra=meta()
    )
    dht22: bool = Field(description="DHT22 responded.", json_schema_extra=meta())
    tcs3448: bool = Field(description="TCS3448 responded.", json_schema_extra=meta())


class LedInfo(SpecModel):
    """One illumination LED."""

    id: LedId = Field(
        description="LED ID; also the key in data led.", json_schema_extra=meta()
    )
    peak_nm: Annotated[int, Field(gt=0)] | None = Field(
        description="Peak wavelength; null for the broadband 'vis' LED.",
        json_schema_extra=meta(unit="nm"),
    )
    pin: Annotated[int, Field(ge=0)] = Field(
        description="GPIO number.", json_schema_extra=meta()
    )

    @model_validator(mode="after")
    def _vis_has_no_peak(self) -> Self:
        if self.id == "vis" and self.peak_nm is not None:
            raise ValueError("peak_nm must be null for the broadband vis LED")
        return self


class InfoSys(SpecModel):
    """Device identity."""

    device_name: str = Field(
        description="Configurable device name used for better readability",
        json_schema_extra=meta(),
    )
    reset_cause: str = Field(
        description="Cause of the last reset.", json_schema_extra=meta()
    )


class InfoDs18b20(SpecModel):
    """DS18B20 configuration."""

    resolution_bits: Annotated[int, Field(ge=9, le=12)] = Field(
        description="Configured conversion resolution.", json_schema_extra=meta()
    )
    rom: HexId16 | None = Field(
        description="ROM ID of the device's only DS18B20; also the key in data "
        "m.ds18b20. null if none was found.",
        json_schema_extra=meta(since=2),
    )


class InfoTcs3448(SpecModel):
    """TCS3448 configuration."""

    smux_mode: int = Field(
        description="SMUX mode of the TCS3448.", json_schema_extra=meta()
    )
    automatic_gain_control: bool = Field(
        alias="agc",
        description="Gain control mode of the tcs3448 sensor.",
        json_schema_extra=meta(),
    )


class InfoProfiles(SpecModel):
    """
    Measurement profiles on the device. Their settings are not repeated here: they can
    change per run, so each run's start record carries them as cfg.
    """

    names: list[ProfileName] = Field(
        description="Profiles a start command can name, without duplicates.",
        json_schema_extra=meta(since=2),
    )
    default: ProfileName = Field(
        description="Profile used when the start command names none, or the run is "
        "started on the device; one of names.",
        json_schema_extra=meta(since=2),
    )

    @model_validator(mode="after")
    def _default_listed_names_unique(self) -> Self:
        if len(set(self.names)) != len(self.names):
            raise ValueError("names contains duplicates")
        if self.default not in self.names:
            raise ValueError("default is not one of names")
        return self


class InfoPio(SpecModel):
    """PIO program that drives the LEDs in sync with the TCS3448."""

    hz: Annotated[int, Field(gt=0)] = Field(
        description="PIO state machine clock.", json_schema_extra=meta(unit="Hz")
    )
    prog: str = Field(description="PIO program version.", json_schema_extra=meta())


class InfoPwm(SpecModel):
    """PWM dimming of the LEDs."""

    hz: Annotated[int, Field(gt=0)] = Field(
        description="LED dimming PWM frequency.", json_schema_extra=meta(unit="Hz")
    )
    sync: bool = Field(
        description="Whether integration and PWM are phase-locked.",
        json_schema_extra=meta(),
    )


class InfoSd(SpecModel):
    """SD card size at boot."""

    total: Count = Field(description="Card capacity.", json_schema_extra=meta(unit="B"))
    free: Count = Field(description="Free space.", json_schema_extra=meta(unit="B"))

    @model_validator(mode="after")
    def _free_within_total(self) -> Self:
        if self.free > self.total:
            raise ValueError("free exceeds total")
        return self


class InfoRecord(RecordHeader):
    """
    Configuration that is fixed for the lifetime of a boot. Sent once per boot, retained.
    Grouped per subsystem like tele; new subsystems are added as optional groups.
    """

    kind: Literal["info"] = Field(alias="k", json_schema_extra=meta())
    sys: InfoSys = Field(json_schema_extra=meta())
    sensors: SensorsFound = Field(
        description="Sensors detected at boot. Firmware does not rescan, so this is not "
        "updated during the boot; data records show which sensors actually respond. "
        "Sensor configuration is in the per-sensor groups regardless of detection.",
        json_schema_extra=meta(),
    )
    ds18b20: InfoDs18b20 = Field(json_schema_extra=meta())
    tcs3448: InfoTcs3448 = Field(json_schema_extra=meta())
    leds: list[LedInfo] = Field(
        description="Illumination LEDs fitted to the device.", json_schema_extra=meta()
    )
    profiles: InfoProfiles = Field(json_schema_extra=meta(since=2))
    pio: InfoPio = Field(json_schema_extra=meta())
    pwm: InfoPwm = Field(json_schema_extra=meta())
    sd: InfoSd | None = Field(
        description="null if no SD card is mounted.", json_schema_extra=meta()
    )

    @model_validator(mode="after")
    def _rom_iff_ds18b20_found(self) -> Self:
        if self.sensors.ds18b20 != (self.ds18b20.rom is not None):
            raise ValueError(
                "ds18b20.rom must be set exactly when sensors.ds18b20 is true"
            )
        return self
