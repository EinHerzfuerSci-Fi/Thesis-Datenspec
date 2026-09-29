"""Minimal valid wire dicts per record kind; tests override only what they exercise."""

import copy
from collections.abc import Callable
from typing import Any

import pytest

from datenspec.models import FORBID_EXTRA, Record, TcsCapture, validate_record

HEADER: dict[str, Any] = {
    "v": 2,
    "dev": "e6614104032b5a2c",
    "fw": "0.4.1+17b375f",
    "boot": 3,
    "run": 7,
    "seq": 0,
    "up": 10.0,
    "ts": None,
}

BASE_CHANNELS = [
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "fz",
    "fy",
    "fxl",
    "nir",
    "vis",
]
RAW = dict.fromkeys(BASE_CHANNELS, 100)


def capture(ill: str = "dark", **overrides: Any) -> dict[str, Any]:
    duty = {"nir": 0.0, "blue": 0.0, "vis": 0.0}
    if ill != "dark":
        duty[ill] = 0.5
    return {
        "ill": ill,
        "led": duty,
        "dt": 0,
        "gain": 9,
        "atime": 29,
        "astep": 599,
        "raw": dict(RAW),
        "sat": False,
    } | overrides


BODIES: dict[str, dict[str, Any]] = {
    "data": {
        "m": {
            "ds18b20": {"28ff641e8016043c": 21.5},
            "dht22": {"t": 22.0, "rh": 0.45},
            "tcs3448": [capture("dark"), capture("nir")],
        }
    },
    "alert": {
        "id": "temp_high",
        "state": "raised",
        "src": "ds18b20:28ff641e8016043c",
        "val": 42.5,
        "thr": 42.0,
        "sev": "warn",
        "ref_seq": 0,
    },
    "tele": {
        "sys": {"mem_free": 81234, "cpu_temp": 31.2, "vsys": 4.9},
        "wlan": {"rssi": -61, "ssid": "lab"},
        "mqtt": {"state": "CONNECTED", "reconnects": 0, "pub_ok": 10, "pub_fail": 0},
        "sd": {"state": "CONNECTED"},
        "buf": {"fill": 0, "cap": 64},
        "ntp": None,
    },
    "err": {"module": "storage", "reason": "write failed", "code": 5},
    "info": {
        "sys": {
            "device_name": "pico-a",
            "reset_cause": "PWRON_RESET",
            "sample_interval_ms": 10000,
        },
        "sensors": {"ds18b20": True, "dht22": True, "tcs3448": True},
        "ds18b20": {"resolution_bits": 12, "rom": "28ff641e8016043c"},
        "tcs3448": {"smux_mode": 18, "agc": False},
        "leds": [
            {"id": "nir", "peak_nm": 850, "pin": 2},
            {"id": "blue", "peak_nm": 450, "pin": 3},
            {"id": "vis", "peak_nm": None, "pin": 4},
        ],
        "capture": {"sequence": ["dark", "nir"], "settle_ms": 5, "on_ms": 120},
        "pio": {"hz": 1_000_000, "prog": "1.0"},
        "pwm": {"hz": 20_000, "sync": True},
        "sd": {"total": 32_000_000_000, "free": 31_000_000_000},
    },
    "log": {"lvl": "info", "module": "main", "msg": "boot complete"},
    "run": {"ev": "start", "dur": 3600, "session": None, "cmd_id": None},
    "ack": {
        "cmd_id": "3f2b8c1e-6d4a-4e2f-9b1a-7c5d0e8f2a91",
        "res": "ok",
        "msg": None,
    },
}


def wire(kind: str = "data", **overrides: Any) -> dict[str, Any]:
    # v and k first, as the firmware writes them; dict merge keeps their position.
    header = {"v": HEADER["v"], "k": kind} | HEADER
    return header | copy.deepcopy(BODIES[kind]) | overrides


@pytest.fixture
def make_record() -> Callable[..., Record]:
    def make(kind: str = "data", **overrides: Any) -> Record:
        return validate_record(wire(kind, **overrides), forbid_extra=True)

    return make


@pytest.fixture
def make_capture() -> Callable[..., TcsCapture]:
    def make(ill: str = "dark", **overrides: Any) -> TcsCapture:
        return TcsCapture.model_validate(
            capture(ill, **overrides), context={FORBID_EXTRA: True}
        )

    return make
