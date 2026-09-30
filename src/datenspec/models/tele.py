"""
Periodic health snapshot, grouped per subsystem.

A group is null when its subsystem has nothing to report (no WLAN association, no NTP
sync yet). Groups whose state is itself the information (mqtt, sd) are never null.
New subsystems are added as optional groups so v need not change.
"""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ._base import Count, SpecModel, meta
from .header import RecordHeader
from .vocab import ModuleState


class TeleSys(SpecModel):
    """Microcontroller health."""

    mem_free: Count = Field(
        description="Free heap memory.", json_schema_extra=meta(unit="B")
    )
    cpu_temp: float = Field(
        description="Chip temperature.", json_schema_extra=meta(unit="°C")
    )
    vsys: float | None = Field(
        description="null if not measurable on this board.",
        json_schema_extra=meta(unit="V"),
    )


class TeleWlan(SpecModel):
    rssi: int = Field(
        description="Signal strength of the access point.",
        json_schema_extra=meta(unit="dBm"),
    )
    ssid: str = Field(description="SSID of the access point.", json_schema_extra=meta())


class TeleMqtt(SpecModel):
    """MQTT client state and counters."""

    state: ModuleState = Field(
        description="Connection state of the MQTT client.", json_schema_extra=meta()
    )
    reconnects: Count = Field(
        description="Number of reconnects to the broker.", json_schema_extra=meta()
    )
    pub_ok: Count = Field(description="Successful publishes.", json_schema_extra=meta())
    pub_fail: Count = Field(description="Failed publishes.", json_schema_extra=meta())


class TeleSd(SpecModel):
    """SD card storage."""

    state: ModuleState = Field(
        description="State of the SD card storage.", json_schema_extra=meta()
    )


class TeleBuf(SpecModel):
    """RAM buffer of records."""

    fill: Count = Field(
        description="Records currently held in the RAM buffer.", json_schema_extra=meta()
    )
    cap: Count = Field(
        description="RAM buffer capacity in records.", json_schema_extra=meta()
    )

    @model_validator(mode="after")
    def _fill_within_cap(self) -> Self:
        if self.fill > self.cap:
            raise ValueError("fill exceeds cap")
        return self


class TeleNtp(SpecModel):
    last_up: Annotated[float, Field(ge=0.0)] = Field(
        description="up at the last successful NTP sync.",
        json_schema_extra=meta(unit="s"),
    )
    last_corr: float = Field(
        description="Clock correction applied at the last NTP sync.",
        json_schema_extra=meta(unit="s"),
    )


class TeleRecord(RecordHeader):
    """Periodic health snapshot (~60 s)."""

    kind: Literal["tele"] = Field(alias="k", json_schema_extra=meta())
    sys: TeleSys = Field(json_schema_extra=meta())
    wlan: TeleWlan | None = Field(
        description="null while not associated with an access point.",
        json_schema_extra=meta(),
    )
    mqtt: TeleMqtt = Field(json_schema_extra=meta())
    sd: TeleSd = Field(json_schema_extra=meta())
    buf: TeleBuf = Field(json_schema_extra=meta())
    ntp: TeleNtp | None = Field(
        description="null until the first successful NTP sync of this boot.",
        json_schema_extra=meta(),
    )

    @model_validator(mode="after")
    def _ntp_sync_not_after_snapshot(self) -> Self:
        if self.ntp is not None and self.ntp.last_up > self.uptime:
            raise ValueError("ntp.last_up is after up")
        return self
