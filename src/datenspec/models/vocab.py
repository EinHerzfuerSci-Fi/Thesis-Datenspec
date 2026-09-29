"""Closed value sets.

Literals instead of Enum: strict mode would reject plain strings for Enum fields when
validating dicts, and the Pico generator only needs the values (typing.get_args).
"""

from typing import Literal

RecordKind = Literal["data", "alert", "tele", "err", "info"]

LedId = Literal["nir", "blue", "vis"]
Illumination = Literal["dark", "nir", "blue", "vis"]

AlarmId = Literal["temp_high", "temp_low", "humidity_high"]
AlarmSeverity = Literal["warn", "crit"]
AlertState = Literal["raised", "cleared"]

ModuleState = Literal["DISCONNECTED", "CONNECTED", "DEGRADED"]

# Wire keys of the TCS3448 spectral channels (not SMUX slots).
TcsChannel = Literal[
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8",
    "fz", "fy", "fxl", "nir", "vis",
    "vis_2", "vis_3",
]  # fmt: skip

# Status topic is plain text, not JSON, so it has no model.
StatusPayload = Literal["online", "offline"]
