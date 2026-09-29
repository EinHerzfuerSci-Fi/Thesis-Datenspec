"""
Regenerate all derived artefacts from the models.

    uv run python -m datenspec.codegen           # write
    uv run python -m datenspec.codegen --check   # CI: fail if committed files are stale
"""

import argparse
import sys
from pathlib import Path

from . import pico, schemas

# Artefacts live in the repo, not in the installed package; resolve from this file so the
# result does not depend on the working directory.
REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_DIR = REPO_ROOT / "schemas"
PICO_FILE = REPO_ROOT / pico.OUTPUT


def _stale() -> list[str]:
    stale = [f"schemas/{name}.schema.json" for name in schemas.check(SCHEMAS_DIR)]
    if not PICO_FILE.exists() or PICO_FILE.read_text(encoding="utf-8") != pico.render():
        stale.append(pico.OUTPUT)
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m datenspec.codegen")
    parser.add_argument(
        "--check",
        action="store_true",
        help="only compare with the committed files, exit 1 if they differ",
    )
    args = parser.parse_args(argv)

    if args.check:
        stale = _stale()
        for path in stale:
            print(f"stale: {path}", file=sys.stderr)
        if stale:
            print("run: python -m datenspec.codegen", file=sys.stderr)
        return 1 if stale else 0

    SCHEMAS_DIR.mkdir(exist_ok=True)
    schemas.write(SCHEMAS_DIR)
    print(f"wrote {len(schemas.TARGETS)} schemas to {SCHEMAS_DIR}")

    PICO_FILE.parent.mkdir(exist_ok=True)
    PICO_FILE.write_text(pico.render(), encoding="utf-8")
    print(f"wrote {PICO_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
