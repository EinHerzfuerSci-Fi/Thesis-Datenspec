"""Rules of data captures and the per-kind schema version (v3)."""

import json
from pathlib import Path

import pytest
from conftest import capture, wire
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaError
from pydantic import ValidationError

from datenspec.models import (
    CAPTURE_TIMING_VERSION,
    MIN_SCHEMA_VERSION,
    SCHEMA_VERSION,
    TcsCapture,
    validate_record,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _schema(name: str) -> Draft202012Validator:
    path = REPO_ROOT / "schemas" / f"{name}.schema.json"
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


def test_gated_capture_is_valid(make_capture) -> None:
    assert make_capture("blue", gated=True).gated


def test_gated_is_required() -> None:
    raw = capture("nir")
    del raw["gated"]
    with pytest.raises(ValidationError, match="gated"):
        TcsCapture.model_validate(raw)
    record = wire("data")
    del record["m"]["tcs3448"][1]["gated"]
    with pytest.raises(SchemaError):
        _schema("data").validate(record)


def test_dark_capture_cannot_be_gated(make_capture) -> None:
    with pytest.raises(ValidationError, match="dark capture cannot be gated"):
        make_capture("dark", gated=True)


def test_dark_capture_needs_leds_off(make_capture) -> None:
    with pytest.raises(ValidationError, match="duty cycles to be 0"):
        make_capture("dark", led={"nir": 0.1, "blue": 0.0, "vis": 0.0})


def test_gated_capture_does_not_count_as_dark(make_record) -> None:
    cycle = [capture("dark"), capture("blue", gated=True)]
    record = make_record("data", m=wire("data")["m"] | {"tcs3448": cycle})
    assert [c.gated for c in record.measurements.tcs3448] == [False, True]
    only_gated = [capture("blue", gated=True)]
    with pytest.raises(ValidationError, match="at least one dark capture, got 0"):
        make_record("data", m=wire("data")["m"] | {"tcs3448": only_gated})


def test_one_dark_capture_per_setting_is_valid(make_record) -> None:
    # Each dark subtracts exactly only at its own gain and integration.
    long = {"gain": 8, "astep": 1199}
    cycle = [
        capture("dark", **long),
        capture("nir", **long),
        capture("dark", gain=10),
        capture("blue", gain=10),
        capture("vis", gain=10),
    ]
    record = make_record("data", m=wire("data")["m"] | {"tcs3448": cycle})
    darks = [c for c in record.measurements.tcs3448 if c.illumination == "dark"]
    assert [(c.gain, c.astep) for c in darks] == [(8, 1199), (10, 599)]
    _schema("data").validate(wire("data", m=wire("data")["m"] | {"tcs3448": cycle}))


def test_every_dark_capture_needs_leds_off(make_record) -> None:
    lit_dark = capture("dark", led={"nir": 0.0, "blue": 0.1, "vis": 0.0})
    cycle = [capture("dark"), capture("nir"), lit_dark, capture("blue")]
    with pytest.raises(ValidationError, match="duty cycles to be 0") as exc_info:
        make_record("data", m=wire("data")["m"] | {"tcs3448": cycle})
    assert {e["loc"][-2:] for e in exc_info.value.errors()} == {("tcs3448", 2)}


def test_every_dark_capture_must_not_be_gated(make_record) -> None:
    cycle = [capture("dark"), capture("nir"), capture("dark", gated=True)]
    with pytest.raises(ValidationError, match="dark capture cannot be gated"):
        make_record("data", m=wire("data")["m"] | {"tcs3448": cycle})


def test_versions() -> None:
    assert (MIN_SCHEMA_VERSION, CAPTURE_TIMING_VERSION, SCHEMA_VERSION) == (2, 3, 3)


@pytest.mark.parametrize("kind", ["data", "run"])
def test_v2_rejected_where_captures_changed(make_record, kind: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        make_record(kind, v=2)
    assert {e["loc"][-1] for e in exc_info.value.errors()} == {"v"}
    with pytest.raises(SchemaError):
        _schema(kind).validate(wire(kind, v=2))


@pytest.mark.parametrize("kind", ["alert", "tele", "err", "info", "log", "ack"])
@pytest.mark.parametrize("v", [2, 3])
def test_unchanged_kinds_accept_v2_and_v3(make_record, kind: str, v: int) -> None:
    assert make_record(kind, v=v).schema_version == v
    _schema(kind).validate(wire(kind, v=v))
    _schema("header").validate(wire(kind, v=v))


def test_run_end_accepts_v2(make_record) -> None:
    end = {
        "ev": "end",
        "cmd_id": None,
        "reason": "duration",
        "n_data": 3,
    }
    record = wire("run", v=2) | end
    for key in ("dur", "session", "profile", "cfg"):
        del record[key]
    assert validate_record(record, forbid_extra=True).schema_version == 2
    _schema("run").validate(record)
