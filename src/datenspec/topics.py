"""
MQTT topics. Single source for the Pico constants and the AsyncAPI file.

device_id is the hardware ID sent as `dev`, so the broker ACL can bind a client to its
own topics. "all" and "laptop" cannot collide with it, because a device ID is 16 hex
chars. Topics the laptop sends for the pipeline only are named after the sender.
"""

from dataclasses import dataclass
from typing import Literal

TOPIC_PREFIX = "thesis/{device_id}"


@dataclass(frozen=True)
class Topic:
    name: str
    template: str
    qos: int
    retain: bool
    description: str
    payload: str
    """Schema name (k) of the payload, or "status" for the plain-text status."""
    sender: Literal["pico", "laptop"] = "pico"
    receiver: Literal["pipeline", "pico"] = "pipeline"


TOPICS: tuple[Topic, ...] = (
    Topic(
        "data",
        f"{TOPIC_PREFIX}/data",
        qos=1,
        retain=False,
        description="One measurement cycle per message.",
        payload="data",
    ),
    Topic(
        "tele",
        f"{TOPIC_PREFIX}/tele",
        qos=1,
        retain=False,
        description="Periodic health snapshot, about every 60 s.",
        payload="tele",
    ),
    Topic(
        "alert",
        f"{TOPIC_PREFIX}/alert/{{alarm_id}}",
        qos=1,
        # One sub-topic per alarm so the retained message is that alarm's current state.
        retain=True,
        description="Sent on raised/cleared transitions only.",
        payload="alert",
    ),
    Topic(
        "err",
        f"{TOPIC_PREFIX}/err",
        qos=1,
        retain=False,
        description="Module errors.",
        payload="err",
    ),
    Topic(
        "log",
        f"{TOPIC_PREFIX}/log",
        qos=1,
        retain=False,
        description="Firmware log messages.",
        payload="log",
    ),
    Topic(
        "info",
        f"{TOPIC_PREFIX}/info",
        qos=1,
        retain=True,
        description="Boot-time configuration, once per boot.",
        payload="info",
    ),
    Topic(
        "run",
        f"{TOPIC_PREFIX}/run",
        qos=1,
        retain=False,
        description="Start and end of a run.",
        payload="run",
    ),
    Topic(
        "status",
        f"{TOPIC_PREFIX}/status",
        qos=1,
        retain=True,
        description='Plain text "online" | "offline"; also the MQTT Last Will.',
        payload="status",
    ),
    Topic(
        "cmd",
        f"{TOPIC_PREFIX}/cmd",
        qos=1,
        # Not retained: a retained cmd would run again on every reconnect.
        retain=False,
        description="Command to one device.",
        payload="cmd",
        sender="laptop",
        receiver="pico",
    ),
    Topic(
        "cmd_all",
        "thesis/all/cmd",
        qos=1,
        retain=False,
        description="Command to all devices; each answers with its own ack.",
        payload="cmd",
        sender="laptop",
        receiver="pico",
    ),
    Topic(
        "ack",
        f"{TOPIC_PREFIX}/cmd/ack",
        qos=1,
        retain=False,
        description="Answer to a cmd.",
        payload="ack",
    ),
    Topic(
        "session",
        "thesis/laptop/session",
        qos=1,
        retain=False,
        description="Creates a session.",
        payload="session",
        sender="laptop",
    ),
    Topic(
        "annotation",
        "thesis/laptop/annotation",
        qos=1,
        retain=False,
        description="Time-stamped note.",
        payload="annotation",
        sender="laptop",
    ),
    Topic(
        "tag",
        "thesis/laptop/tag",
        qos=1,
        retain=False,
        description="Sets or deletes a key/value tag on a run.",
        payload="tag",
        sender="laptop",
    ),
)
