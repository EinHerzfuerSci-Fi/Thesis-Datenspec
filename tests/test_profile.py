"""The device's profile file: not a message, but validated with the same rules."""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaError
from pydantic import TypeAdapter, ValidationError

from datenspec.models import FORBID_EXTRA, ProfileFile

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "schemas" / "profiles.schema.json").read_text(
        encoding="utf-8"
    )
)
ADAPTER = TypeAdapter(ProfileFile)

FIXED = {"mode": "fixed", "stages": None}

PROFILES: dict[str, Any] = {
    "turbidity": {
        "sample_interval_ms": 5000,
        "capture": {
            "sequence": ["dark", "nir"],
            "settle_ms": 20,
            "on_ms": 100,
            "gain_control": FIXED,
        },
    },
    "led_test": {
        "sample_interval_ms": 2000,
        "capture": {
            "sequence": ["dark", "nir"],
            "settle_ms": 20,
            "on_ms": 100,
            "gain_control": FIXED,
        },
    },
}


def test_profile_file_is_valid() -> None:
    profiles = ADAPTER.validate_python(PROFILES, context={FORBID_EXTRA: True})
    assert profiles["turbidity"].capture.settle_ms == 20
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
        | {
            "capture": {
                "sequence": ["nir"],
                "settle_ms": 20,
                "on_ms": 100,
                "gain_control": FIXED,
            }
        }
    }
    with pytest.raises(ValidationError, match="exactly one dark"):
        ADAPTER.validate_python(bad)
