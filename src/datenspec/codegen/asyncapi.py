"""
Generate the AsyncAPI 3.0 description of the device's MQTT interface.

Topics, QoS and retain come from datenspec.topics; payloads reference the exported JSON
Schemas instead of inlining them, so the schemas stay the only payload definition.
Operations are seen from the device: it sends its records and receives cmd. Topics
between laptop and pipeline (session, annotation, tag) are channels without an operation,
because the device neither sends nor receives them.
"""

from importlib.metadata import version
from string import Formatter
from typing import Any, get_args

from datenspec.models import SCHEMA_VERSION
from datenspec.models.vocab import AlarmId, StatusPayload
from datenspec.topics import TOPICS, Topic

from . import schemas

OUTPUT = "asyncapi/asyncapi.yaml"
SCHEMAS_REL = "../schemas"  # relative to OUTPUT

MQTT_BINDING_VERSION = "0.2.0"
JSON_SCHEMA_FORMAT = "application/schema+json;version=2020-12"

LAST_WILL: StatusPayload = "offline"

PARAMETERS: dict[str, dict[str, Any]] = {
    "device_id": {
        "description": "Hardware ID of the device, the same as dev in its records.",
    },
    "alarm_id": {
        "description": "One sub-topic per alarm so the retained message is its state.",
        "enum": list(get_args(AlarmId)),
    },
}


def _topic_by_name(name: str) -> Topic:
    return next(t for t in TOPICS if t.name == name)


def _payload_summary(payload: str) -> str:
    # Several topics may share a payload (cmd); the first one describes it.
    return next(t.description for t in TOPICS if t.payload == payload)


def _parameters(template: str) -> list[str]:
    return [field for _, field, _, _ in Formatter().parse(template) if field]


def _message(payload: str) -> dict[str, Any]:
    if payload == "status":
        return {
            "name": "status",
            "title": "Online status",
            "summary": _payload_summary(payload),
            "contentType": "text/plain",
            "payload": {"type": "string", "enum": list(get_args(StatusPayload))},
        }
    return {
        "name": payload,
        "title": f"{payload} message",
        "summary": _payload_summary(payload),
        "contentType": "application/json",
        "payload": {
            "schemaFormat": JSON_SCHEMA_FORMAT,
            "schema": {"$ref": f"{SCHEMAS_REL}/{payload}.schema.json"},
        },
    }


def build() -> dict[str, Any]:
    unknown = {t.payload for t in TOPICS} - set(schemas.TARGETS) - {"status"}
    if unknown:
        raise ValueError(f"topics without a record schema: {sorted(unknown)}")

    status = _topic_by_name("status")
    channels: dict[str, Any] = {}
    operations: dict[str, Any] = {}
    for topic in TOPICS:
        channel: dict[str, Any] = {
            "address": topic.template,
            "description": topic.description,
            "messages": {
                topic.payload: {"$ref": f"#/components/messages/{topic.payload}"}
            },
        }
        if params := _parameters(topic.template):
            channel["parameters"] = {
                p: {"$ref": f"#/components/parameters/{p}"} for p in params
            }
        channels[topic.name] = channel
        if topic.sender == "pico":
            action = "send"
        elif topic.receiver == "pico":
            action = "receive"
        else:
            continue
        operations[f"{action}_{topic.name}"] = {
            "action": action,
            "channel": {"$ref": f"#/channels/{topic.name}"},
            "bindings": {
                "mqtt": {
                    "qos": topic.qos,
                    "retain": topic.retain,
                    "bindingVersion": MQTT_BINDING_VERSION,
                }
            },
        }

    return {
        "asyncapi": "3.0.0",
        "info": {
            "title": "datenspec measurement platform",
            "version": version("datenspec"),
            "description": (
                "MQTT interface of the Pico 2 W measurement device, seen from the "
                "device: it sends its records and receives commands. Payload units are "
                "defined in the JSON Schemas (x-unit), not in the messages."
            ),
            "x-schema-version": SCHEMA_VERSION,
        },
        "defaultContentType": "application/json",
        "servers": {
            "broker": {
                "host": "{host}",
                "protocol": "mqtt",
                "description": "Deployment-specific broker.",
                "variables": {"host": {"description": "Broker host[:port]."}},
                "bindings": {
                    "mqtt": {
                        "lastWill": {
                            "topic": status.template,
                            "qos": status.qos,
                            "message": LAST_WILL,
                            "retain": status.retain,
                        },
                        "bindingVersion": MQTT_BINDING_VERSION,
                    }
                },
            }
        },
        "channels": channels,
        "operations": operations,
        "components": {
            "messages": {
                p: _message(p) for p in dict.fromkeys(t.payload for t in TOPICS)
            },
            "parameters": PARAMETERS,
        },
    }


def render() -> str:
    # Imported here: PyYAML is a dev dependency, the runtime package must not need it.
    import yaml

    header = (
        "# Generated by datenspec.codegen.asyncapi - do not edit.\n"
        f"# datenspec {version('datenspec')}, schema version {SCHEMA_VERSION}\n"
    )
    body = yaml.safe_dump(build(), sort_keys=False, allow_unicode=True, width=88)
    return header + body
