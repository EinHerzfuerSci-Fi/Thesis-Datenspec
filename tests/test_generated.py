"""Committed generated artefacts must match the current models."""

import ast
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from datenspec.codegen import asyncapi, pico, readme, schemas
from datenspec.topics import TOPICS

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"
PICO_FILE = REPO_ROOT / pico.OUTPUT
ASYNCAPI_FILE = REPO_ROOT / asyncapi.OUTPUT
REGENERATE = "run: python -m datenspec.codegen"


@pytest.mark.parametrize("name", schemas.TARGETS)
def test_schema_file_up_to_date(name: str) -> None:
    path = SCHEMAS_DIR / f"{name}.schema.json"
    assert path.exists(), f"{path.name} missing; {REGENERATE}"
    committed = path.read_text(encoding="utf-8")
    assert committed == schemas.render(schemas.TARGETS[name]), (
        f"{path.name} is stale; {REGENERATE}"
    )


def test_no_orphaned_schema_files() -> None:
    # A removed or renamed record kind would otherwise leave a schema nobody validates.
    expected = {f"{name}.schema.json" for name in schemas.TARGETS}
    present = {p.name for p in SCHEMAS_DIR.glob("*.schema.json")}
    assert present - expected == set()


@pytest.mark.parametrize("name", schemas.TARGETS)
def test_schema_is_valid_json_schema(name: str) -> None:
    # Consumers without Python (e.g. AsyncAPI tooling) rely on these files alone.
    schema = json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


def test_pico_file_up_to_date() -> None:
    assert PICO_FILE.exists(), f"{pico.OUTPUT} missing; {REGENERATE}"
    committed = PICO_FILE.read_text(encoding="utf-8")
    assert committed == pico.render(), f"{pico.OUTPUT} is stale; {REGENERATE}"


def _pico_constants() -> dict[str, object]:
    tree = ast.parse(PICO_FILE.read_text(encoding="utf-8"))
    constants: dict[str, object] = {}
    for stmt in tree.body:
        # Anything beyond NAME = literal would cost RAM or fail on MicroPython.
        assert isinstance(stmt, ast.Assign), ast.dump(stmt)
        assert len(stmt.targets) == 1
        target = stmt.targets[0]
        assert isinstance(target, ast.Name)
        assert target.id.isupper(), target.id
        assert isinstance(stmt.value, ast.Constant), target.id
        assert type(stmt.value.value) in {str, int, bool}, target.id
        assert target.id not in constants, f"duplicate constant {target.id}"
        constants[target.id] = stmt.value.value
    return constants


def test_pico_file_is_plain_constants() -> None:
    constants = _pico_constants()
    assert constants["SCHEMA_VERSION"] == pico.SCHEMA_VERSION


@pytest.mark.skipif(
    shutil.which("micropython") is None, reason="micropython not installed"
)
def test_pico_file_imports_on_micropython() -> None:
    # CPython accepting the file does not prove MicroPython does; run the real thing.
    script = (
        "import datenspec_const as c\n"
        "for n in sorted(dir(c)):\n"
        "    if not n.startswith('_'): print(n, repr(getattr(c, n)))\n"
    )
    result = subprocess.run(  # noqa: S603 - fixed executable and script
        [shutil.which("micropython"), "-c", script],
        capture_output=True,
        text=True,
        check=True,
        env=os.environ | {"MICROPYPATH": str(PICO_FILE.parent)},
    )
    expected = [f"{n} {v!r}" for n, v in sorted(_pico_constants().items())]
    assert result.stdout.splitlines() == expected


def test_asyncapi_file_up_to_date() -> None:
    assert ASYNCAPI_FILE.exists(), f"{asyncapi.OUTPUT} missing; {REGENERATE}"
    committed = ASYNCAPI_FILE.read_text(encoding="utf-8")
    assert committed == asyncapi.render(), f"{asyncapi.OUTPUT} is stale; {REGENERATE}"


def _refs(node: object) -> list[str]:
    if isinstance(node, dict):
        own = [node["$ref"]] if isinstance(node.get("$ref"), str) else []
        return own + [r for v in node.values() for r in _refs(v)]
    if isinstance(node, list):
        return [r for v in node for r in _refs(v)]
    return []


def test_asyncapi_refs_resolve() -> None:
    # A dangling ref only shows up in AsyncAPI tooling, which the tests do not run.
    doc = yaml.safe_load(ASYNCAPI_FILE.read_text(encoding="utf-8"))
    for ref in _refs(doc):
        if ref.startswith("#/"):
            node = doc
            for part in ref[2:].split("/"):
                assert part in node, f"dangling ref {ref}"
                node = node[part]
        else:
            assert (ASYNCAPI_FILE.parent / ref).resolve().is_file(), f"missing file {ref}"


def test_asyncapi_covers_every_topic() -> None:
    doc = yaml.safe_load(ASYNCAPI_FILE.read_text(encoding="utf-8"))
    addresses = {c["address"] for c in doc["channels"].values()}
    assert addresses == {t.template for t in TOPICS}


def test_readme_reference_up_to_date() -> None:
    text = (REPO_ROOT / readme.OUTPUT).read_text(encoding="utf-8")
    assert text == readme.update(text), f"README reference is stale; {REGENERATE}"


def test_readme_reference_has_no_empty_description() -> None:
    # The field table is the human-facing spec; an undocumented field is a gap in it.
    block = readme.render_block()
    rows = [r for r in block.splitlines() if r.startswith("| `")]
    empty = [r.split(" | ")[0] for r in rows if r.split(" | ")[4] == ""]
    assert not empty, f"add a description to: {empty}"
