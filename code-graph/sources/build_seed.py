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

Standard library only, plus Node.js to run indexer/extents.mjs. Nodes are the
global symbols the index defines; locals, parameters and type parameters are
left out. A References edge joins the innermost definition whose range
contains a reference to the symbol it names; call is true when one of those
references is followed by a call. A definition's range is the indexer's
enclosing range, or, for the definitions the indexer gives none (a constant
holding something other than a function, a class field, a getter or setter),
the one extents.mjs reads with the TypeScript parser.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COOKBOOK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from scip_index import DEFINITION, read_index  # noqa: E402

# SCIP SymbolInformation.Kind values scip-typescript emits, mapped to the
# schema's closed vocabulary. Kinds missing here are not nodes. A static
# method or property (80, 81) is a member like any other; scip-typescript
# gives a static and an instance member of the same name one symbol, so they
# are one definition.
KIND = {
    7: "class", 8: "constant", 9: "constructor", 11: "enum", 12: "enum_member",
    15: "field", 16: "module", 17: "function", 18: "getter", 21: "interface",
    26: "method", 29: "module", 30: "namespace", 41: "property", 45: "setter",
    54: "type_alias", 55: "type_alias", 61: "variable", 80: "method", 81: "property",
}
CALLABLE_KINDS = {"function", "method", "constructor", "getter", "setter"}
# A constant, variable or class field whose initializer is a function is
# callable whatever its declared type: `const getCookie: GetCookie = (c) =>
# {...}`. Without one, as for `const verify = Jwt.verify` or a property
# declared in an interface, the declared type in the hover text decides:
# `var f: () => any`, `(property) handle: <T>(c: Context<T>) => Response`.
VALUE_KINDS = {"constant", "variable", "property", "field"}
DECLARED_TYPE = re.compile(r"^(?:\(\w+\)\s*)?(?:const|let|var|property)?\s*[\w$#]+\??\s*:\s*")
NULLISH_UNION = re.compile(r"^(?:\|\s*(?:undefined|null)\s*)+$")
CALL_SUFFIX = ("(", "`", "?.(", "<")
TYPES = ("Revision", "Symbol", "Location")
EDGES = ("DefinedAt", "MemberOf", "References", "ImplementedBy")
IDENTIFIER = re.compile(r"[\w+\-$]+")
TYPE_LITERAL = re.compile(r"^typeLiteral\d+$")


def descriptors_of(symbol: str) -> str:
    """A symbol's key: the descriptors of `scheme manager package version descriptors`.

    scip-typescript puts the members of an anonymous type literal under a
    `typeLiteralN:` container numbered by position in the file, so adding one
    earlier in the file renames every later member. The key leaves those
    containers out, so a member keeps its key while it keeps its name and place.
    """
    parts = symbol.split(" ", 4)
    if len(parts) != 5:
        raise ValueError(f"not a global SCIP symbol: {symbol!r}")
    text = parts[4]
    if "typeLiteral" not in text:
        return text
    kept, start = [], 0
    for name, suffix, end in parse_descriptors(text):
        if not (suffix == "meta" and TYPE_LITERAL.match(name)):
            kept.append(text[start:end])
        start = end
    return "".join(kept)


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


def escape_name(name: str) -> str:
    """A name as a SCIP descriptor spells it: backticks around anything that is
    not a plain identifier, with backticks inside doubled."""
    if IDENTIFIER.fullmatch(name):
        return name
    return "`" + name.replace("`", "``") + "`"


def project_prefix(documents, infos) -> str:
    """The folder of the indexed project, relative to the repository, as
    namespace descriptors: `src/` when the tsconfig lives in `src/`.

    scip-typescript writes a file's path in a symbol relative to the project
    but a document's path relative to the directory it ran in, so a key would
    otherwise not start with its file's path. The folder is read from each
    module's definition: the document's path minus the module's own path.
    """
    prefixes = collections.Counter()
    for d in documents:
        for o in d.occurrences:
            info = infos.get(o.symbol)
            if not o.roles & DEFINITION or info is None or KIND.get(info.kind) != "module":
                continue
            module = "/".join(name for name, suffix, _ in parse_descriptors(descriptors_of(o.symbol))
                              if suffix == "namespace")
            if d.relative_path == module or d.relative_path.endswith("/" + module):
                prefixes[d.relative_path[:len(d.relative_path) - len(module)]] += 1
    if len(prefixes) > 1:
        raise ValueError(f"modules disagree on the project folder: {dict(prefixes)}")
    folder = next(iter(prefixes), "")
    return "".join(escape_name(part) + "/" for part in folder.strip("/").split("/") if part)


def signature(documentation: list[str]) -> str | None:
    if not documentation:
        return None
    text = re.sub(r"^```\w*\n?|\n?```$", "", documentation[0].strip()).strip()
    first = text.split("\n")[0].strip()
    return first[:300] or None


def is_function_type(text: str) -> bool:
    """Whether a TypeScript type, as hover text spells it, is a function type.

    A type that opens with `<` is a generic function type. One that opens with
    `(` is a function type when `=>` follows the matching parenthesis, so
    `("br" | "gzip")[]` is not one, and an optional `(() => void) | undefined`
    is one. Hover text keeps only its first line, so a parameter list cut off
    there counts as a function.
    """
    text = text.strip()
    if text.startswith("<"):
        return True
    if not text.startswith("("):
        return False
    depth = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                after = text[i + 1:].strip()
                if after.startswith("=>"):
                    return True
                return bool(NULLISH_UNION.match(after)) and is_function_type(text[1:i])
    return True


def is_callable(kind: str, function_initializer: bool, sig: str | None) -> bool:
    if kind in CALLABLE_KINDS or (kind in VALUE_KINDS and function_initializer):
        return True
    declared = DECLARED_TYPE.match(sig or "")
    return bool(declared) and is_function_type(sig[declared.end():])


def contains(outer, inner) -> bool:
    return (outer[0], outer[1]) <= (inner[0], inner[1]) and (inner[2], inner[3]) <= (outer[2], outer[3])


def owner(scopes: list, rng) -> str | None:
    """The innermost definition whose range contains a reference's range.

    Ranges nest, so the innermost one that contains the reference starts last
    and, on a tie, ends first. None when no definition contains it.
    """
    owners = [(r, k) for r, k in scopes if contains(r, rng)]
    if not owners:
        return None
    return max(owners, key=lambda e: ((e[0][0], e[0][1]), (-e[0][2], -e[0][3])))[1]


EXTENTS_SCRIPT = os.path.join(HERE, "indexer", "extents.mjs")


def read_extents(checkout: str, paths: list[str]) -> dict:
    """Run extents.mjs over the files: {(path, name line, name character): (range, initializer is a function)}."""
    node = shutil.which("node")
    if not node or not os.path.isdir(os.path.join(HERE, "indexer", "node_modules", "typescript")):
        sys.exit("reading definition ranges needs Node.js and the locked TypeScript parser: "
                 "run `npm ci` in code-graph/sources/indexer")
    proc = subprocess.run([node, EXTENTS_SCRIPT], input=json.dumps({"root": checkout, "files": paths}),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"extents.mjs failed:\n{proc.stderr.strip()[-2000:]}")
    return {(path, e[0], e[1]): ((e[2], e[3], e[4], e[5]), e[6])
            for path, entries in json.loads(proc.stdout).items() for e in entries}


def in_slice(path: str, slice_: list[str]) -> bool:
    return not slice_ or any(path == s or (s.endswith("/") and path.startswith(s)) for s in slice_)


def build(index_path: str, checkout: str, revision: str, repository: str, slice_: list[str]) -> list[dict]:
    idx = read_index(index_path)
    extents = read_extents(checkout, [d.relative_path for d in idx.documents])
    infos = {s.symbol: s for d in idx.documents for s in d.symbols if not s.symbol.startswith("local ")}
    prefix = project_prefix(idx.documents, infos)

    def key_of(symbol: str) -> str:
        return prefix + descriptors_of(symbol)
    sources: dict[str, list[str]] = {}

    def lines(path: str) -> list[str]:
        if path not in sources:
            with open(os.path.join(checkout, path), encoding="utf-8") as f:
                sources[path] = f.read().split("\n")
        return sources[path]

    # One symbol can have several definitions: an overloaded function's
    # signatures and its implementation, or a static and an instance member of
    # one name. Each is collected, in index order, so the node covers them all.
    definitions: dict[str, list] = {}  # key -> [(info, path, definition range or None, name range, has a body)]
    scopes: dict[str, list] = collections.defaultdict(list)  # path -> [(definition range, key)]
    for d in idx.documents:
        for o in d.occurrences:
            info = infos.get(o.symbol)
            if not o.roles & DEFINITION or info is None or info.kind not in KIND:
                continue
            key = key_of(o.symbol)
            # The indexer's range when it gives one, which for a constant means
            # its initializer is a function; else the parser's.
            extent, function_initializer = extents.get((d.relative_path, o.range[0], o.range[1]), (None, False))
            defined = o.enclosing_range or extent
            if defined:
                scopes[d.relative_path].append((defined, key))
            definitions.setdefault(key, []).append(
                (info, d.relative_path, defined, o.range, bool(o.enclosing_range) or function_initializer))

    nodes: dict[str, dict] = {}
    for key, defs in definitions.items():
        info, path = defs[0][0], defs[0][1]
        kind = KIND[info.kind]
        sig = signature(info.documentation)
        callable_ = is_callable(kind, any(d[4] for d in defs), sig)
        # The location runs from the first definition to the last in the
        # first one's file, and the digest covers the text of every definition,
        # so a change to an overload's implementation changes the symbol.
        spans = [d[2] or d[3] for d in defs if d[1] == path]
        texts = ["\n".join(lines(p)[s[0]:s[2] + 1]) for _, p, s, _, _ in defs if s]
        digest = hashlib.sha256("\n".join(texts).encode()).hexdigest()[:16] if callable_ and texts else None
        nodes[key] = {"symbol": key, "name": parse_descriptors(key)[-1][0], "kind": kind,
                      "callable": callable_, "path": path, "signature": sig, "digest": digest,
                      "line": min(s[0] for s in spans) + 1, "end_line": max(s[2] for s in spans) + 1}

    references: dict[tuple[str, str], dict] = {}
    for d in idx.documents:
        doc_scopes = scopes.get(d.relative_path, [])
        for o in d.occurrences:
            if o.roles & DEFINITION or o.symbol not in infos:
                continue
            callee = key_of(o.symbol)
            if callee not in nodes:
                continue
            caller = owner(doc_scopes, o.range)
            if caller is None:
                continue
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

    # SCIP records the relationship on the implementing member; the edge runs
    # from the member it implements, the way a call through it goes.
    implemented_by = set()
    for sym, info in infos.items():
        member = key_of(sym)
        for rel in info.relationships:
            if rel.is_implementation and not rel.symbol.startswith("local "):
                implemented = key_of(rel.symbol)
                if member in nodes and implemented in nodes:
                    implemented_by.add((implemented, member))

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
    rows += [{"edge": "ImplementedBy", "from": a, "to": b, "data": {}} for a, b in sorted(implemented_by)
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
