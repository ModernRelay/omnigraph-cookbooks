"""Shared helpers for the code-graph benchmarks: one identity space for the
reference, the cookbook and the tools compared with it.

An identity is `path:Container.member`, the form reference.mjs writes, with
no line numbers. SCIP's special names are normalized to TypeScript's:
`<constructor>` is `constructor`, `<get>x` and `<set>x` are `x`.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
COOKBOOK = BENCH.parent
sys.path.insert(0, str(COOKBOOK / "sources"))
import build_seed  # noqa: E402

SPECIAL = re.compile(r"^<(get|set)>")
TYPE_LITERAL = re.compile(r"^typeLiteral\d+$")


def normalize_name(name: str) -> str:
    if name == "<constructor>":
        return "constructor"
    return SPECIAL.sub("", name)


def identity_from_key(key: str) -> str | None:
    """A cookbook Symbol key as a reference identity."""
    try:
        parts = build_seed.parse_descriptors(key)
    except ValueError:
        return None
    module = max((i for i, (name, suffix, _) in enumerate(parts) if suffix == "namespace" and "." in name),
                 default=None)
    if module is None:
        return None
    path = "/".join(name for name, _, _ in parts[:module + 1])
    tail = parts[module + 1:]
    # SCIP names an object-literal member with a numbered meta descriptor
    # (`hash0:`); it is not a definition, so it has no identity.
    if tail and tail[-1][1] == "meta" and not TYPE_LITERAL.match(tail[-1][0]):
        return None
    # An anonymous type literal adds a synthetic `typeLiteralN:` container.
    rest = [normalize_name(name) for name, suffix, _ in tail
            if suffix != "parameter" and not (suffix == "meta" and TYPE_LITERAL.match(name))]
    return f"{path}:{'.'.join(rest)}" if rest else path


def load_reference(path: Path) -> tuple[dict, dict]:
    ref = json.loads(Path(path).read_text())
    edges = {}
    for key, e in ref["edges"].items():
        a, b = key.split("\u0000")
        edges[(a, b)] = e
    return ref["nodes"], edges


def load_implements(path: Path) -> dict[str, set[str]]:
    """member identity -> the identities of the members that implement or override it."""
    impl: dict[str, set[str]] = {}
    for member, target in json.loads(Path(path).read_text()).get("implements", []):
        impl.setdefault(target, set()).add(member)
    return impl


def load_cookbook_rows(rows: list[dict]) -> tuple[dict, dict]:
    """Nodes and References edges of a cookbook revision, in identity space; `call`
    says whether a Calls edge joins the same ends."""
    nodes, edges = {}, {}
    locations = {}
    for r in rows:
        if r.get("type") == "Location":
            locations[r["data"]["symbol"]] = r["data"]
    for r in rows:
        if r.get("type") == "Symbol":
            d = r["data"]
            ident = identity_from_key(d["symbol"])
            if ident is None:
                continue
            loc = locations.get(d["symbol"], {})
            nodes.setdefault(ident, {"kind": d["kind"], "callable": d["callable"], "digest": d.get("digest"),
                                     "path": d["path"], "line": loc.get("line"), "end_line": loc.get("end_line"),
                                     "keys": []})["keys"].append(d["symbol"])
        elif r.get("edge") in ("References", "Calls"):
            a, b = identity_from_key(r["from"]), identity_from_key(r["to"])
            if a and b:
                e = edges.setdefault((a, b), {"call": False, "sites": 0})
                if r["edge"] == "Calls":  # every Calls edge has a References edge with the same ends
                    e["call"] = True
                else:
                    e["sites"] += r["data"]["sites"]
    return nodes, edges


def load_cookbook(path: Path) -> tuple[dict, dict]:
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    return load_cookbook_rows(rows)


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    # Undefined when either is; zero when both are and nothing matched.
    f = None if p is None or r is None else 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f}
