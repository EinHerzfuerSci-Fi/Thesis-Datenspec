"""
MQTT topics. Single source for the Pico constants and the AsyncAPI file.

device_name is the configurable name, not the hardware ID in `dev`.
"""

from dataclasses import dataclass

TOPIC_PREFIX = "platform/{device_name}"


@dataclass(frozen=True)
class Topic:
    name: str
    template: str
    qos: int
    retain: bool
    description: str


TOPICS: tuple[Topic, ...] = (
    Topic(
        "data",
        f"{TOPIC_PREFIX}/data",
        qos=1,
        retain=False,
        description="One measurement cycle per message.",
    ),
    Topic(
        "alert",
        f"{TOPIC_PREFIX}/alert/{{alarm_id}}",
        qos=1,
        # One sub-topic per alarm so the retained message is that alarm's current state.
        retain=True,
        description="Sent on raised/cleared transitions only.",
    ),
    Topic(
        "tele",
        f"{TOPIC_PREFIX}/tele",
        qos=1,
        retain=False,
        description="Periodic health snapshot, about every 60 s.",
    ),
    Topic(
        "info",
        f"{TOPIC_PREFIX}/info",
        qos=1,
        retain=True,
        description="Boot-time configuration, once per boot.",
    ),
    Topic(
        "err",
        f"{TOPIC_PREFIX}/err",
        qos=1,
        retain=False,
        description="Module errors.",
    ),
    Topic(
        "status",
        f"{TOPIC_PREFIX}/status",
        qos=1,
        retain=True,
        description='Plain text "online" | "offline"; also the MQTT Last Will.',
    ),
)
