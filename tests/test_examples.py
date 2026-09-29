"""
Example records in examples/.

valid/<kind>.jsonl: one wire record per line, as the firmware writes them to SD.
invalid/<kind>.jsonl: one test case per line, {"case", "loc", "record", "strict_only"?}.
`loc` is where the error must be; every reported error has to lie below it, so a case
cannot pass by failing for an unrelated reason (e.g. a typo elsewhere in the record).
`strict_only` cases are rejected only with forbid_extra and accepted at runtime.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from datenspec.codegen import schemas
from datenspec.models import parse_record, validate_record

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
KINDS = [name for name in schemas.TARGETS if name != "header"]
CASE_KEYS = {"case", "loc", "record", "strict_only"}


def _lines(folder: str) -> list[Any]:
    params = []
    for kind in KINDS:
        path = EXAMPLES / folder / f"{kind}.jsonl"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                params.append(pytest.param(kind, line, id=f"{kind}:{number}"))
    return params


def _strict_only_cases() -> list[Any]:
    return [p for p in _lines("invalid") if json.loads(p.values[1]).get("strict_only")]


def _schema(name: str) -> Draft202012Validator:
    path = REPO_ROOT / "schemas" / f"{name}.schema.json"
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("folder", ["valid", "invalid"])
def test_every_kind_has_examples(folder: str) -> None:
    for kind in KINDS:
        path = EXAMPLES / folder / f"{kind}.jsonl"
        assert path.read_text(encoding="utf-8").strip(), f"no examples in {path}"


@pytest.mark.parametrize(("kind", "line"), _lines("valid"))
def test_valid_example_passes_models(kind: str, line: str) -> None:
    record = parse_record(line, forbid_extra=True)
    assert record.kind == kind, "example is in the wrong file"


@pytest.mark.parametrize(("kind", "line"), _lines("valid"))
def test_valid_example_passes_json_schemas(kind: str, line: str) -> None:
    # Guards the export: a consumer using only the .schema.json files must agree.
    wire = json.loads(line)
    _schema(kind).validate(wire)
    _schema("header").validate(wire)


@pytest.mark.parametrize(("kind", "line"), _lines("valid"))
def test_valid_example_round_trips(kind: str, line: str) -> None:
    # Serialising must reproduce the wire names; defaults are not written back.
    record = parse_record(line)
    assert json.loads(record.model_dump_json(exclude_unset=True)) == json.loads(line)


@pytest.mark.parametrize(("kind", "line"), _lines("invalid"))
def test_invalid_example_is_rejected_at_its_loc(kind: str, line: str) -> None:
    case = json.loads(line)
    assert set(case) <= CASE_KEYS, f"unknown keys {set(case) - CASE_KEYS}"
    expected = tuple(case["loc"])

    with pytest.raises(ValidationError) as exc_info:
        validate_record(case["record"], forbid_extra=True)

    locs = [tuple(e["loc"]) for e in exc_info.value.errors()]
    stray = [loc for loc in locs if loc[: len(expected)] != expected]
    assert not stray, f"{case['case']!r}: errors outside {expected}: {stray}"


@pytest.mark.parametrize(("kind", "line"), _strict_only_cases())
def test_strict_only_example_is_accepted_at_runtime(kind: str, line: str) -> None:
    case = json.loads(line)
    # Runtime must tolerate unknown fields so older readers survive newer firmware.
    validate_record(case["record"])
