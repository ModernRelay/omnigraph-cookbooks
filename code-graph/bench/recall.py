#!/usr/bin/env python3
"""Execution-recall benchmark: which executed calls does a static graph contain?

The executed edges come from running hono's tests on a copy instrumented by
instrument.mjs: `caller -> callee`, where callee is the definition a call
entered and caller the definition that owns the code that made it. This is
ground truth that does not come from the compiler, so it can score the
cookbook, whose references the compiler resolves, without circularity. It
measures recall only: an edge the tests never ran is not wrong.

    python3 code-graph/bench/recall.py TRACE_DIR COOKBOOK.jsonl REFERENCE.json [TOOL.json ...]

A TOOL.json is {"name": ..., "edges": [[caller, callee], ...]} in identity
space, written by tools.py.
"""
from __future__ import annotations

import collections
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_cookbook, load_reference  # noqa: E402


def executed(trace_dir: str) -> set[tuple[str, str]]:
    edges = set()
    for f in glob.glob(f"{trace_dir}/edges-*.txt"):
        for line in open(f):
            a, b = json.loads(line).split("\u0000")
            edges.add((a, b))
    return edges


def implementations(cook_rows_path: str) -> dict[str, set[str]]:
    """interface member identity -> identities of the members implementing it."""
    from common import identity_from_key  # noqa: PLC0415

    impl = collections.defaultdict(set)
    for line in open(cook_rows_path):
        r = json.loads(line)
        if r.get("edge") == "Implements":
            a, b = identity_from_key(r["from"]), identity_from_key(r["to"])
            if a and b:
                impl[b].add(a)
    return impl


def recall(dyn: set, static: set, nodes: set, impl: dict | None = None) -> dict:
    scored = {e for e in dyn if e[0] in nodes and e[1] in nodes}
    hit = {e for e in scored if e in static}
    via_impl = set()
    if impl:
        # A call through an interface member reaches the implementations the
        # graph records for it.
        reach = collections.defaultdict(set)
        for a, b in static:
            reach[a].update(impl.get(b, ()))
        via_impl = {e for e in scored - hit if e[1] in reach[e[0]]}
    return {"executed": len(dyn), "scored": len(scored), "unmodeled_endpoint": len(dyn) - len(scored),
            "found": len(hit), "found_via_implements": len(via_impl),
            "recall": len(hit) / len(scored) if scored else None,
            "recall_with_implements": (len(hit) + len(via_impl)) / len(scored) if scored else None,
            "missed": sorted(scored - hit - via_impl)}


def main():
    trace_dir, cook_path, ref_path, *tools = sys.argv[1:]
    dyn = executed(trace_dir)
    cn, ce = load_cookbook(Path(cook_path))
    rn, re_ = load_reference(Path(ref_path))
    impl = implementations(cook_path)
    results = {
        "reference": recall(dyn, set(re_), set(rn)),
        "cookbook": recall(dyn, set(ce), set(cn), impl),
        "cookbook_calls_only": recall(dyn, {e for e, v in ce.items() if v["call"]}, set(cn), impl),
    }
    graphs = {"reference": set(re_), "cookbook": set(ce),
              "cookbook_calls_only": {e for e, v in ce.items() if v["call"]}}
    for t in tools:
        spec = json.loads(Path(t).read_text())
        graphs[spec["name"]] = {tuple(e) for e in spec["edges"]}
        results[spec["name"]] = recall(dyn, graphs[spec["name"]], set(rn))
    # Like for like: tools record calls, so getter entries (property reads) are
    # reported apart from functions, methods and constructors.
    kind = lambda b: {"getter": "getter/setter", "setter": "getter/setter",  # noqa: E731
                      "constructor": "constructor"}.get(rn[b]["kind"], "function/method")
    scored = [e for e in dyn if e[0] in rn and e[1] in rn]
    by_kind = {}
    for name, edges in graphs.items():
        by_kind[name] = {}
        for k in ("function/method", "constructor", "getter/setter"):
            sub = [e for e in scored if kind(e[1]) == k]
            by_kind[name][k] = {"executed": len(sub), "found": sum(e in edges for e in sub),
                                "recall": sum(e in edges for e in sub) / len(sub) if sub else None}
    results["by_callee_kind"] = by_kind
    # Where name matching fails: a call to a class member, or to a name that
    # several definitions share, needs the receiver's type to resolve.
    names = collections.Counter(n["name"] for n in rn.values() if n["kind"] != "module")
    shapes = {
        "top-level function": lambda b: "." not in b.split(":", 1)[-1],
        "class member": lambda b: "." in b.split(":", 1)[-1],
        "unique name": lambda b: names[rn[b]["name"]] == 1,
        "name shared by 2-3": lambda b: 2 <= names[rn[b]["name"]] <= 3,
        "name shared by 4+": lambda b: names[rn[b]["name"]] >= 4,
    }
    functions = [e for e in scored if kind(e[1]) == "function/method"]
    by_shape = {}
    for name, edges in graphs.items():
        by_shape[name] = {}
        for s, test in shapes.items():
            sub = [e for e in functions if test(e[1])]
            found = sum(e in edges for e in sub)
            by_shape[name][s] = {"executed": len(sub), "found": found, "recall": found / len(sub) if sub else None}
    results["functions_by_call_shape"] = by_shape
    print(f"{'graph':<22} {'scored':>6} {'found':>6} {'recall':>7} {'+impl':>7} {'unmodeled':>9}")
    for name, r in results.items():
        if name in ("by_callee_kind", "functions_by_call_shape"):
            continue
        rc = f"{r['recall']:.3f}" if r["recall"] is not None else "-"
        ri = f"{r['recall_with_implements']:.3f}" if r["recall_with_implements"] is not None else "-"
        print(f"{name:<22} {r['scored']:>6} {r['found']:>6} {rc:>7} {ri:>7} {r['unmodeled_endpoint']:>9}")
    print(f"\n{'by callee kind':<22}" + "".join(f"{k:>17}" for k in ("function/method", "constructor", "getter/setter")))
    for name, kinds in by_kind.items():
        print(f"{name:<22}" + "".join(f"{(v['recall'] if v['recall'] is not None else 0):>17.3f}" for v in kinds.values()))
    print(f"\n{'functions by call shape':<24}" + "".join(f"{s:>20}" for s in shapes))
    for name, cells in by_shape.items():
        print(f"{name:<24}" + "".join(f"{(v['recall'] if v['recall'] is not None else 0):>20.3f}" for v in cells.values()))
    out = Path(__file__).resolve().parent / "results"
    out.mkdir(exist_ok=True)
    (out / "recall.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
