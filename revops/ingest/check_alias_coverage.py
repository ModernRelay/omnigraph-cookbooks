#!/usr/bin/env python3
"""Fail if a .gq query is not exposed through an omnigraph.yaml alias."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def query_names() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in sorted((ROOT / "queries").glob("*.gq")):
        text = path.read_text()
        for match in re.finditer(r"^query\s+(\w+)\s*\(", text, re.MULTILINE):
            found[match.group(1)] = str(path.relative_to(ROOT))
    return found


def alias_targets() -> set[str]:
    text = (ROOT / "omnigraph.yaml").read_text()
    return set(re.findall(r"^\s+name:\s+(\w+)\s*$", text, re.MULTILINE))


def main() -> int:
    queries = query_names()
    aliases = alias_targets()
    missing = sorted(name for name in queries if name not in aliases)
    if missing:
        print("Missing aliases:")
        for name in missing:
            print(f"  - {name} ({queries[name]})")
        return 1
    print(f"OK: {len(queries)} queries exposed through aliases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
