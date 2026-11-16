#!/usr/bin/env python3
"""Build code-graph JSONL from SCIP indexes.

With no arguments it builds the cookbook's files from the revisions fetch.py
checked out and indexed: seed.jsonl from the base revision and
examples/pr-5267.jsonl from the pull request, both limited to the slice in
source.json.

    python3 code-graph/sources/build_seed.py            # write the committed files
    python3 code-graph/sources/build_seed.py --check    # exit 1 if they differ from a fresh build

To graph another TypeScript repository, index it and convert the index:

    scip-typescript index --output index.scip           # in the repository
    python3 code-graph/sources/build_seed.py --index index.scip --checkout . \
        --revision "$(git rev-parse HEAD)" --repository https://example.com/repo.git \
        --out graph.jsonl [--slice src/]

Standard library only. Nodes are the global symbols the index defines; locals,
parameters and type parameters are left out. A References edge joins the
innermost definition whose enclosing range contains a reference to the symbol
it names; call is true when one of those references is followed by a call.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COOKBOOK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from scip_index import DEFINITION, read_index  # noqa: E402

# SCIP SymbolInformation.Kind values scip-typescript emits, mapped to the
# schema's closed vocabulary. Kinds missing here are not nodes.
KIND = {
    7: "class", 8: "constant", 9: "constructor", 11: "enum", 12: "enum_member",
    15: "field", 16: "module", 17: "function", 18: "getter", 21: "interface",
    26: "method", 29: "module", 30: "namespace", 41: "property", 45: "setter",
    54: "type_alias", 55: "type_alias", 61: "variable",
}
CALLABLE_KINDS = {"function", "method", "constructor", "getter", "setter"}
# Hover text of a constant, variable or property holding a function:
# `var f: () => any`, `(property) handle: <T>(c: Context<T>) => Response`.
FUNCTION_SIGNATURE = re.compile(r"^(?:\(\w+\)\s*)?(?:const|let|var|property)?\s*[\w$#]+\??\s*:\s*(?:<[^>]*>\s*)?\(")
CALL_SUFFIX = ("(", "`", "?.(", "<")
TYPES = ("Revision", "Symbol", "Location")
EDGES = ("DefinedAt", "MemberOf", "References", "Implements")
IDENTIFIER = re.compile(r"[\w+\-$]+")


def descriptors_of(symbol: str) -> str:
    """A global symbol is `scheme manager package version descriptors`; keep the descriptors."""
    parts = symbol.split(" ", 4)
    if len(parts) != 5:
        raise ValueError(f"not a global SCIP symbol: {symbol!r}")
    return parts[4]


def parse_descriptors(text: str) -> list[tuple[str, str, int]]:
    """Split SCIP descriptors into (name, suffix, end offset) following the SCIP grammar."""
    out, i, n = [], 0, len(text)

    def name_at(j: int) -> tuple[str, int]:
        if j < n and text[j] == "`":
            k, chars = j + 1, []
            while k < n:
                if text[k] == "`":
                    if k + 1 < n and text[k + 1] == "`":
                        chars.append("`")
                        k += 2
                        continue
                    return "".join(chars), k + 1
                chars.append(text[k])
                k += 1
            raise ValueError(f"unterminated escaped name in {text!r}")
        m = IDENTIFIER.match(text, j)
        if not m:
            raise ValueError(f"bad descriptor at {j} in {text!r}")
        return m.group(0), m.end()

    while i < n:
        if text[i] == "[":
            name, i = name_at(i + 1)
            if text[i] != "]":
                raise ValueError(f"bad type parameter in {text!r}")
            out.append((name, "type_parameter", i + 1))
            i += 1
            continue
        if text[i] == "(":
            name, i = name_at(i + 1)
            if text[i] != ")":
                raise ValueError(f"bad parameter in {text!r}")
            out.append((name, "parameter", i + 1))
            i += 1
            continue
        name, i = name_at(i)
        suffix = text[i]
        if suffix == "(":
            close = text.index(")", i)
            if text[close + 1:close + 2] != ".":
                raise ValueError(f"bad method descriptor in {text!r}")
            out.append((name, "method", close + 2))
            i = close + 2
        elif suffix in "/#.:!":
            kind = {"/": "namespace", "#": "type", ".": "term", ":": "meta", "!": "macro"}[suffix]
            out.append((name, kind, i + 1))
            i += 1
        else:
            raise ValueError(f"bad descriptor suffix {suffix!r} in {text!r}")
    return out


def signature(documentation: list[str]) -> str | None:
    if not documentation:
        return None
    text = re.sub(r"^```\w*\n?|\n?```$", "", documentation[0].strip()).strip()
    first = text.split("\n")[0].strip()
    return first[:300] or None


def contains(outer, inner) -> bool:
    return (outer[0], outer[1]) <= (inner[0], inner[1]) and (inner[2], inner[3]) <= (outer[2], outer[3])


def in_slice(path: str, slice_: list[str]) -> bool:
    return not slice_ or any(path == s or (s.endswith("/") and path.startswith(s)) for s in slice_)


def build(index_path: str, checkout: str, revision: str, repository: str, slice_: list[str]) -> list[dict]:
    idx = read_index(index_path)
    infos = {s.symbol: s for d in idx.documents for s in d.symbols if not s.symbol.startswith("local ")}
    sources: dict[str, list[str]] = {}

    def lines(path: str) -> list[str]:
        if path not in sources:
            with open(os.path.join(checkout, path), encoding="utf-8") as f:
                sources[path] = f.read().split("\n")
        return sources[path]

    nodes: dict[str, dict] = {}
    scopes: dict[str, list] = collections.defaultdict(list)  # path -> [(enclosing range, key)]
    for d in idx.documents:
        for o in d.occurrences:
            info = infos.get(o.symbol)
            if not o.roles & DEFINITION or info is None or info.kind not in KIND:
                continue
            key = descriptors_of(o.symbol)
            if o.enclosing_range:
                scopes[d.relative_path].append((o.enclosing_range, key))
            if key in nodes:
                continue
            kind = KIND[info.kind]
            sig = signature(info.documentation)
            callable_ = kind in CALLABLE_KINDS or bool(sig and FUNCTION_SIGNATURE.match(sig))
            span = o.enclosing_range or o.range
            digest = None
            if callable_ and o.enclosing_range:
                text = "\n".join(lines(d.relative_path)[span[0]:span[2] + 1])
                digest = hashlib.sha256(text.encode()).hexdigest()[:16]
            nodes[key] = {"symbol": key, "name": parse_descriptors(key)[-1][0], "kind": kind,
                          "callable": callable_, "path": d.relative_path, "signature": sig,
                          "digest": digest, "line": span[0] + 1, "end_line": span[2] + 1}

    references: dict[tuple[str, str], dict] = {}
    for d in idx.documents:
        doc_scopes = scopes.get(d.relative_path, [])
        for o in d.occurrences:
            if o.roles & DEFINITION or o.symbol not in infos:
                continue
            callee = descriptors_of(o.symbol)
            if callee not in nodes:
                continue
            # Enclosing ranges nest, so the innermost one that contains the
            # reference starts last and, on a tie, ends first.
            owners = [(r, k) for r, k in doc_scopes if contains(r, o.range)]
            if not owners:
                continue
            caller = max(owners, key=lambda e: ((e[0][0], e[0][1]), (-e[0][2], -e[0][3])))[1]
            text = lines(d.relative_path)
            after = text[o.range[2]][o.range[3]:].lstrip() if o.range[2] < len(text) else ""
            edge = references.setdefault((caller, callee), {"call": False, "sites": 0})
            edge["call"] = edge["call"] or (nodes[callee]["callable"] and after.startswith(CALL_SUFFIX))
            edge["sites"] += 1

    member_of = set()
    for key in nodes:
        parts = parse_descriptors(key)
        for depth in range(len(parts) - 1, 0, -1):
            parent = key[:parts[depth - 1][2]]
            if parent in nodes:
                member_of.add((key, parent))
                break

    implements = set()
    for sym, info in infos.items():
        src = descriptors_of(sym)
        for rel in info.relationships:
            if rel.is_implementation and not rel.symbol.startswith("local "):
                dst = descriptors_of(rel.symbol)
                if src in nodes and dst in nodes:
                    implements.add((src, dst))

    keep = {k for k, n in nodes.items() if in_slice(n["path"], slice_)}
    ordered_nodes = [nodes[k] for k in sorted(keep)]
    rows = [{"type": "Revision", "data": {"sha": revision, "repository": repository,
                                          "indexer": idx.tool_name, "indexer_version": idx.tool_version}}]
    rows += [{"type": "Symbol", "data": {k: v for k, v in n.items() if k not in ("line", "end_line")}}
             for n in ordered_nodes]
    rows += [{"type": "Location", "data": {"symbol": n["symbol"], "line": n["line"], "end_line": n["end_line"]}}
             for n in ordered_nodes]
    rows += [{"edge": "DefinedAt", "from": n["symbol"], "to": n["symbol"], "data": {}} for n in ordered_nodes]
    rows += [{"edge": "MemberOf", "from": a, "to": b, "data": {}} for a, b in sorted(member_of)
             if a in keep and b in keep]
    rows += [{"edge": "References", "from": a, "to": b, "data": e} for (a, b), e in sorted(references.items())
             if a in keep and b in keep]
    rows += [{"edge": "Implements", "from": a, "to": b, "data": {}} for a, b in sorted(implements)
             if a in keep and b in keep]
    return rows


def render(rows: list[dict]) -> str:
    return "".join(json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for r in rows)


def missing_types(rows: list[dict]) -> list[str]:
    present = {r.get("type") or r.get("edge") for r in rows}
    return [t for t in TYPES + EDGES if t not in present]


def pinned_builds() -> list[tuple[str, str]]:
    with open(os.path.join(HERE, "source.json")) as f:
        source = json.load(f)
    work = os.path.join(HERE, "work")
    out = []
    for rev in source["revisions"]:
        index = os.path.join(work, f"{rev['sha']}.scip")
        if not os.path.exists(index):
            sys.exit(f"{index} is missing: run fetch.py first")
        rows = build(index, os.path.join(work, rev["sha"]), rev["sha"], source["repository"], source["slice"])
        if missing_types(rows):
            sys.exit(f"{rev['name']} has no rows of {', '.join(missing_types(rows))}")
        out.append((os.path.join(COOKBOOK, rev["out"]), render(rows)))
    return out


def main():
    parser = argparse.ArgumentParser(description="Build code-graph JSONL from SCIP indexes.")
    parser.add_argument("--check", action="store_true", help="compare a fresh build with the committed files")
    parser.add_argument("--index", help="a SCIP index to convert instead of the pinned revisions")
    parser.add_argument("--checkout", help="the checkout the index was built from")
    parser.add_argument("--revision", help="the checkout's commit SHA")
    parser.add_argument("--repository", default="", help="the repository URL to record")
    parser.add_argument("--slice", nargs="*", default=[], help="keep only these paths (a trailing / means a directory)")
    parser.add_argument("--out", help="the JSONL file to write")
    args = parser.parse_args()

    if args.index:
        if not (args.checkout and args.revision and args.out):
            parser.error("--index needs --checkout, --revision and --out")
        rows = build(args.index, args.checkout, args.revision, args.repository, args.slice)
        empty = missing_types(rows)
        if empty:
            print(f"warning: no {', '.join(empty)} rows; an overwrite load keeps the old rows of a type "
                  "the file does not contain", file=sys.stderr)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(render(rows))
        counts = collections.Counter(r.get("type") or r.get("edge") for r in rows)
        print(f"wrote {args.out}: " + ", ".join(f"{counts[t]} {t}" for t in TYPES + EDGES))
        return

    builds = pinned_builds()
    if args.check:
        stale = []
        for path, text in builds:
            try:
                with open(path, encoding="utf-8") as f:
                    current = f.read()
            except FileNotFoundError:
                current = None
            if current != text:
                stale.append(os.path.relpath(path, COOKBOOK))
        if stale:
            sys.exit("differs from a fresh build: " + ", ".join(stale))
        print("the committed files match a fresh build")
        return
    for path, text in builds:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {os.path.relpath(path, COOKBOOK)}: {text.count(chr(10))} rows")


if __name__ == "__main__":
    main()
