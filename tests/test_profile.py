"""The device's profile file: not a message, but validated with the same rules."""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaError
from pydantic import TypeAdapter, ValidationError

from datenspec.models import FORBID_EXTRA, CaptureConfig, CaptureStep, ProfileFile

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "schemas" / "profiles.schema.json").read_text(
        encoding="utf-8"
    )
)
ADAPTER = TypeAdapter(ProfileFile)

FIXED = {"mode": "fixed", "stages": None}


def step(
    ill: str, gap: int = 20, settle: int = 0, delay: int = 0, on: int = 0
) -> dict[str, Any]:
    return {
        "ill": ill,
        "gap_ms": gap,
        "settle_ms": settle,
        "delay_ms": delay,
        "on_ms": on,
    }


DARK = step("dark", gap=100)
NIR = step("nir", settle=20, on=100)
GATED_BLUE = step("blue", settle=50, delay=20)

PROFILES: dict[str, Any] = {
    "turbidity": {
        "sample_interval_ms": 5000,
        "capture": {"captures": [DARK, NIR], "gain_control": FIXED},
    },
    "fluorescence": {
        "sample_interval_ms": 2000,
        "capture": {"captures": [DARK, NIR, GATED_BLUE], "gain_control": FIXED},
    },
}


def _capture(*steps: dict[str, Any]) -> CaptureConfig:
    return CaptureConfig.model_validate(
        {"captures": list(steps), "gain_control": FIXED}, context={FORBID_EXTRA: True}
    )


def _step(**fields: Any) -> CaptureStep:
    return CaptureStep.model_validate(fields, context={FORBID_EXTRA: True})


def test_profile_file_is_valid() -> None:
    profiles = ADAPTER.validate_python(PROFILES, context={FORBID_EXTRA: True})
    assert profiles["turbidity"].capture.captures[1].settle_ms == 20
    Draft202012Validator(SCHEMA).validate(PROFILES)


def test_profile_name_rejected_by_model_and_schema() -> None:
    bad = {"Turbidity": PROFILES["turbidity"]}
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(bad)
    with pytest.raises(SchemaError):
        Draft202012Validator(SCHEMA).validate(bad)


def test_profile_needs_exactly_one_dark_capture() -> None:
    bad = {
        "nir_only": PROFILES["turbidity"]
        | {"capture": {"captures": [NIR], "gain_control": FIXED}}
    }
    with pytest.raises(ValidationError, match="exactly one dark"):
        ADAPTER.validate_python(bad)


def test_two_dark_steps_are_rejected() -> None:
    with pytest.raises(ValidationError, match="exactly one dark capture, got 2"):
        _capture(DARK, NIR, DARK)


def test_gated_step_does_not_count_as_dark() -> None:
    # Integrating with the LEDs off does not make a capture the ambient reference.
    with pytest.raises(ValidationError, match="got 0"):
        _capture(GATED_BLUE, NIR)


def test_sequence_is_derived_and_not_serialised() -> None:
    capture = _capture(DARK, NIR, GATED_BLUE)
    assert capture.sequence == ["dark", "nir", "blue"]
    assert "sequence" not in capture.model_dump()
    assert "sequence" not in json.dumps(SCHEMA)


def test_old_run_wide_timing_is_rejected() -> None:
    old = {
        "sequence": ["dark", "nir"],
        "settle_ms": 20,
        "on_ms": 100,
        "gain_control": FIXED,
    }
    with pytest.raises(ValidationError):
        CaptureConfig.model_validate(old)
    with pytest.raises(SchemaError):
        Draft202012Validator(SCHEMA).validate(
            {"old": {"sample_interval_ms": 5000, "capture": old}}
        )


def test_gated_property() -> None:
    assert _step(**GATED_BLUE).gated
    assert not _step(**NIR).gated
    assert not _step(**DARK).gated


def test_dark_step_with_long_gap_is_valid() -> None:
    assert _step(**step("dark", gap=5000)).gap_ms == 5000


@pytest.mark.parametrize("field", ["settle_ms", "delay_ms", "on_ms"])
def test_dark_step_has_no_led_phase(field: str) -> None:
    with pytest.raises(ValidationError, match="dark capture has no LED phase"):
        _step(**DARK | {field: 5})


def test_lit_step_without_gate_needs_on_ms() -> None:
    with pytest.raises(ValidationError, match="needs on_ms > 0"):
        _step(**NIR | {"on_ms": 0})


def test_lit_step_may_switch_on_at_integration_start() -> None:
    assert _step(**NIR | {"settle_ms": 0}).settle_ms == 0


def test_gated_step_needs_a_pulse() -> None:
    with pytest.raises(ValidationError, match="needs settle_ms > 0"):
        _step(**GATED_BLUE | {"settle_ms": 0})


def test_gated_step_keeps_led_off_during_integration() -> None:
    with pytest.raises(ValidationError, match="never switches during an integration"):
        _step(**GATED_BLUE | {"on_ms": 10})


@pytest.mark.parametrize("field", ["gap_ms", "settle_ms", "delay_ms", "on_ms"])
def test_negative_timing_rejected_by_model_and_schema(field: str) -> None:
    bad_step = NIR | {field: -1}
    with pytest.raises(ValidationError):
        _step(**bad_step)
    bad = {
        "t": PROFILES["turbidity"]
        | {"capture": {"captures": [DARK, bad_step], "gain_control": FIXED}}
    }
    with pytest.raises(SchemaError):
        Draft202012Validator(SCHEMA).validate(bad)
