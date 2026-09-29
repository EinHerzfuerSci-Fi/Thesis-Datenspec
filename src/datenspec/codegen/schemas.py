import json
from pathlib import Path

from datenspec.models import RECORD_MODELS, SCHEMA_VERSION, RecordHeader

TARGETS = {"header": RecordHeader} | {
    m.model_fields["kind"].annotation.__args__[0]: m for m in RECORD_MODELS
}


def render(model) -> str:
    schema = model.model_json_schema(by_alias=True, mode="validation")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-schema-version": SCHEMA_VERSION,
    } | schema
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def write(out: Path) -> None:
    for name, model in TARGETS.items():
        (out / f"{name}.schema.json").write_text(render(model), encoding="utf-8")


def _read(path: Path) -> str | None:
    # Missing counts as stale: happens when a new record kind has not been generated yet.
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def check(out: Path) -> list[str]:
    """Names whose committed file differs from what the models produce."""
    return [n for n, m in TARGETS.items() if _read(out / f"{n}.schema.json") != render(m)]
