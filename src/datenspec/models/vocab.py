"""Closed value sets.

Literals instead of Enum: strict mode would reject plain strings for Enum fields when
validating dicts, and the Pico generator only needs the values (typing.get_args).
"""

from typing import Literal

# Sent by the Pico, with the full record header.
RecordKind = Literal["data", "alert", "tele", "err", "info", "log", "run", "ack"]
# Sent by the laptop, with only v and k.
LaptopKind = Literal["cmd", "session", "annotation", "tag"]

LedId = Literal["nir", "blue", "vis"]
Illumination = Literal["dark", "nir", "blue", "vis"]

# How a run picks the TCS3448 gain per capture: fixed from the profile, the ams
# auto-gain search (AN001051), or predicted from the cycle's dark capture.
GainMode = Literal["fixed", "ams", "dark"]

AlarmId = Literal["temp_high", "temp_low", "humidity_high"]
AlarmSeverity = Literal["warn", "crit"]
AlertState = Literal["raised", "cleared"]

ModuleState = Literal["DISCONNECTED", "CONNECTED", "DEGRADED"]

# warn as in AlarmSeverity.
LogLevel = Literal["debug", "info", "warn", "error"]

RunEvent = Literal["start", "end"]
# No "aborted": only the pipeline sets that, when no end record arrives.
RunEndReason = Literal["duration", "manual", "error"]

CmdAction = Literal["start", "stop"]
AckResult = Literal["ok", "rejected", "error"]

SessionVariety = Literal["normal", "calibration", "functional", "flowrate"]

# Wire keys of the TCS3448 spectral channels (not SMUX slots).
TcsChannel = Literal[
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8",
    "fz", "fy", "fxl", "nir", "vis",
    "vis_2", "vis_3",
]  # fmt: skip

# Status topic is plain text, not JSON, so it has no model.
StatusPayload = Literal["online", "offline"]
