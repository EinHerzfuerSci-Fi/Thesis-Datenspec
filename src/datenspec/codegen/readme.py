"""
Generate the field and topic reference in README.md.

Only the block between the markers is generated; the prose around it is hand-written.
Rows come from the exported JSON Schemas so the README shows what consumers see.
"""

import json
from collections.abc import Iterator
from typing import Any

from datenspec.models._base import SEMVER_PATTERN
from datenspec.topics import TOPICS

from . import schemas

OUTPUT = "README.md"
BEGIN = "<!-- BEGIN GENERATED: reference (python -m datenspec.codegen) -->"
END = "<!-- END GENERATED: reference -->"

type Schema = dict[str, Any]


def _cell(text: str) -> str:
    # Pipes would split the Markdown table cell.
    return " ".join(text.split()).replace("|", "\\|")


def _resolve(node: Schema, defs: Schema) -> Schema:
    ref = node.get("$ref")
    return defs[ref.removeprefix("#/$defs/")] if ref else node


def _range(node: Schema) -> str:
    lo, hi = node.get("minimum"), node.get("maximum")
    if lo is not None and hi is not None:
        return f" ({lo}…{hi})"
    if lo is not None:
        return f" (≥ {lo})"
    if node.get("exclusiveMinimum") is not None:
        return f" (> {node['exclusiveMinimum']})"
    return ""


def _type(node: Schema) -> str:
    if "$ref" in node:
        return "object"
    if "anyOf" in node:
        return " | ".join(_type(n) for n in node["anyOf"])
    if "const" in node:
        return json.dumps(node["const"])
    if "enum" in node:
        return " | ".join(json.dumps(v) for v in node["enum"])
    kind = node.get("type", "any")
    if kind == "array":
        return f"array of {_type(node['items'])}"
    if kind == "object" and "patternProperties" in node:
        ((pattern, value),) = node["patternProperties"].items()
        inner = _type(value)
        # Parenthesised so a nullable value is not confused with a nullable map.
        return (
            f"map `{pattern}` → ({inner})"
            if "|" in inner
            else f"map `{pattern}` → {inner}"
        )
    if kind == "string" and "pattern" in node:
        return (
            "string (SemVer)"
            if node["pattern"] == SEMVER_PATTERN
            else (f"string `{node['pattern']}`")
        )
    return kind + _range(node)


def _nested(node: Schema, defs: Schema) -> tuple[Schema, str] | None:
    """The model a field contains, and the path suffix to reach its fields."""
    for option in node.get("anyOf", [node]):
        if "$ref" in option:
            return _resolve(option, defs), "."
        if option.get("type") == "array" and "$ref" in option["items"]:
            return _resolve(option["items"], defs), "[]."
    return None


def _rows(model: Schema, defs: Schema, prefix: str, skip: set[str]) -> Iterator[str]:
    required = set(model.get("required", []))
    for name, prop in model["properties"].items():
        if name in skip:
            continue
        nested = _nested(prop, defs)
        description = prop.get("description") or (
            nested[0].get("description", "") if nested else ""
        )
        yield (
            "| "
            + " | ".join(
                [
                    f"`{prefix}{name}`",
                    _cell(_type(prop)),
                    _cell(prop.get("x-unit", "")),
                    "required" if name in required else "optional",
                    _cell(description),
                    str(prop.get("x-since", "")),
                ]
            )
            + " |"
        )
        if nested:
            yield from _rows(nested[0], defs, f"{prefix}{name}{nested[1]}", set())


HEAD = (
    "| Field | Type | Unit | Required | Description | Since v |\n"
    "|---|---|---|---|---|---|"
)


def _field_tables() -> list[str]:
    header = schemas.TARGETS["header"].model_json_schema(by_alias=True)
    header_fields = set(header["properties"])
    out = ["### Header (every record)", "", HEAD]
    out += _rows(header, header.get("$defs", {}), "", set())
    for name, model in schemas.TARGETS.items():
        if name == "header":
            continue
        schema = model.model_json_schema(by_alias=True)
        out += ["", f'### `{name}` (`"k": "{name}"`)', "", HEAD]
        out += _rows(schema, schema.get("$defs", {}), "", header_fields)
    return out


def _topic_table() -> list[str]:
    out = [
        "| Topic | QoS | Retain | Payload | Description |",
        "|---|---|---|---|---|",
    ]
    for t in TOPICS:
        payload = "text/plain" if t.name == "status" else f"`{t.name}` record"
        out.append(
            f"| `{t.template}` | {t.qos} | {'yes' if t.retain else 'no'} | {payload} "
            f"| {_cell(t.description)} |"
        )
    return out


def render_block() -> str:
    lines = [
        BEGIN,
        "",
        "## MQTT topics",
        "",
        *_topic_table(),
        "",
        "## Field reference",
        "",
        (
            "Nested fields use dotted paths; `[]` marks list elements. `Since v` is "
            "the schema version that introduced the field."
        ),
        "",
        *_field_tables(),
        "",
        END,
    ]
    return "\n".join(lines)


def update(text: str) -> str:
    """Replace the generated block in the README text, leaving the prose untouched."""
    start, end = text.find(BEGIN), text.find(END)
    if start < 0 or end < start:
        raise ValueError(f"{OUTPUT} needs the markers {BEGIN!r} and {END!r}")
    return text[:start] + render_block() + text[end + len(END) :]
