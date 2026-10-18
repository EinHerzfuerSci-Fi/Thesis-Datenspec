"""Rules of the laptop messages that the example files do not cover on their own."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]

ANNOTATION = {
    "v": 2,
    "k": "annotation",
    "id": "9a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
    "ts": 1759141200,
    "text": "chamber door opened",
    "dev": "e6614104032b5a2c",
    "run": 7,
    "session": None,
}


def _schema(name: str) -> Draft202012Validator:
    path = REPO_ROOT / "schemas" / f"{name}.schema.json"
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


def test_annotation_schema_rejects_run_without_dev() -> None:
    # The model has this as a validator; the exported schema needs it as if/then.
    with pytest.raises(ValidationError):
        _schema("annotation").validate(ANNOTATION | {"dev": None})


def test_annotation_schema_accepts_dev_without_run() -> None:
    _schema("annotation").validate(ANNOTATION | {"run": None})


@pytest.mark.parametrize(
    ("act", "wrong"),
    [
        ("start", {"run": 7}),
        ("stop", {"run": None}),
        ("stop", {"dur": 60}),
        ("stop", {"profile": "turbidity"}),
    ],
)
def test_cmd_schema_enforces_fields_per_action(act: str, wrong: dict) -> None:
    cmd = {
        "v": 2,
        "k": "cmd",
        "id": "3f2b8c1e-6d4a-4e2f-9b1a-7c5d0e8f2a91",
        "act": act,
        "dur": 60 if act == "start" else None,
        "session": None,
        "profile": None,
        "run": None if act == "start" else 7,
        "ts": 1759140059.4,
    }
    _schema("cmd").validate(cmd)
    with pytest.raises(ValidationError):
        _schema("cmd").validate(cmd | wrong)
