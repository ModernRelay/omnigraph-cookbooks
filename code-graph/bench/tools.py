#!/usr/bin/env python3
"""Map other code-graph tools' call edges into the benchmark's identity space.

    python3 code-graph/bench/tools.py REFERENCE.json NAME RAW.tsv OUT.json

RAW.tsv has one edge per line: caller file, caller name, caller line, callee
file, callee name, callee line, as each tool's own export reports them (lines
1-based). An endpoint maps to the reference definition in the same file with
the same name, the one whose range contains the line when names repeat. A
callee that is a class maps to its declared constructor as well, since that
is what an executed `new` enters.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_reference  # noqa: E402


def clean(name: str) -> str:
    name = re.sub(r"\(\)$", "", name.strip()).lstrip(".")
    return re.split(r"[.:]", name)[-1] if re.search(r"[.:]", name) else name


def main():
    ref_path, tool, raw, out = sys.argv[1:]
    nodes, _ = load_reference(Path(ref_path))
    by_name = collections.defaultdict(list)
    for ident, n in nodes.items():
        if n["kind"] == "module":
            continue
        by_name[(n["path"], n["name"])].append(ident)
        if n["name"].startswith("#"):
            by_name[(n["path"], n["name"][1:])].append(ident)
    constructors = {i.rsplit(".", 1)[0]: i for i, n in nodes.items() if n["kind"] == "constructor"}

    def resolve(path: str, name: str, line: str) -> str | None:
        cands = by_name.get((path, clean(name)))
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        try:
            ln = int(float(line))
        except ValueError:
            return None

        def rank(i):
            n = nodes[i]
            inside = n["line"] - 25 <= ln <= n["end_line"]
            return (0 if inside else 1, abs(ln - n["line"]))

        return min(cands, key=rank)

    by_path = collections.defaultdict(list)
    for ident, n in nodes.items():
        if n["kind"] != "module":
            by_path[n["path"]].append(ident)
    NON_OWNER = {"getter", "setter", "property", "variable", "enum_member"}

    def owner(ident: str) -> str:
        """The definition that owns code written in `ident`, by the benchmark's
        ownership rules: members without a range of their own belong to their
        container, as do constants that hold no function."""
        n = nodes[ident]
        while n["kind"] in NON_OWNER or (n["kind"] == "constant" and not n["callable"]):
            parent = ident.rsplit(".", 1)[0] if "." in ident.split(":", 1)[-1] else n["path"]
            if parent not in nodes or parent == ident:
                return n["path"]
            ident, n = parent, nodes[parent]
        return ident

    def resolve_caller(path: str, name: str, line: str) -> str | None:
        """A caller may be a local function the reference folds into its
        enclosing definition: fall back to the innermost one holding the line."""
        found = resolve(path, name, line)
        if found is None:
            try:
                ln = int(float(line))
            except ValueError:
                return None
            holding = [i for i in by_path.get(path, ()) if nodes[i]["line"] <= ln <= nodes[i]["end_line"]]
            if not holding:
                return path if path in nodes else None
            found = min(holding, key=lambda i: nodes[i]["end_line"] - nodes[i]["line"])
        return owner(found)

    edges, unmapped = set(), 0
    for line in open(raw):
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 6:
            continue
        a, b = resolve_caller(*parts[:3]), resolve(*parts[3:6])
        if not a or not b:
            unmapped += 1
            continue
        edges.add((a, b))
        if nodes[b]["kind"] == "class" and b in constructors:
            edges.add((a, constructors[b]))
    Path(out).write_text(json.dumps({"name": tool, "edges": sorted(edges), "unmapped": unmapped}))
    print(f"{tool}: {len(edges)} edges in identity space, {unmapped} raw edges not mapped")


if __name__ == "__main__":
    main()
