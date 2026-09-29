import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from datenspec.models import LAPTOP_KINDS, RECORD_KINDS, SCHEMA_VERSION, RecordHeader

# One file per k; a kind with variants (run, cmd) is exported as its discriminated union.
TARGETS: dict[str, Any] = {"header": RecordHeader} | RECORD_KINDS | LAPTOP_KINDS


def json_schema(target: Any) -> dict[str, Any]:
    return TypeAdapter(target).json_schema(by_alias=True, mode="validation")


def render(target: Any) -> str:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-schema-version": SCHEMA_VERSION,
    } | json_schema(target)
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def write(out: Path) -> None:
    for name, target in TARGETS.items():
        (out / f"{name}.schema.json").write_text(render(target), encoding="utf-8")


def _read(path: Path) -> str | None:
    # Missing counts as stale: happens when a new record kind has not been generated yet.
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def check(out: Path) -> list[str]:
    """Names whose committed file differs from what the models produce."""
    return [n for n, t in TARGETS.items() if _read(out / f"{n}.schema.json") != render(t)]
