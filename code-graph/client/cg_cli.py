"""cg: index a repository into the code-graph cookbook and review pull requests
as changes to its call graph.

cg is a thin client over the `omnigraph` CLI and needs only the Python standard
library. It reads through the cookbook's stored queries and writes only by
loading a generated revision with `--mode overwrite`, one graph commit per load.

Settings, from the environment or the matching flag:

  CG_TARGET   --target   operator target: a server target name, or a local graph path
  CG_GRAPH    --graph    graph id on a server target (default: code)
  CG_OMNIGRAPH           the omnigraph binary (default: the one on PATH)
  CG_INDEXER             the scip-typescript binary `cg index` runs

Exit status: 0 success; 1 failed with nothing changed; 2 a usage error or an
ambiguous name; 3 a write whose outcome is unknown, so check the branch before
loading again.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(os.path.realpath(__file__)).parent
BUNDLE = HERE.parent
QUERIES = BUNDLE / "queries" / "code.gq"
SOURCES = BUNDLE / "sources"
EXIT_FAILED, EXIT_USAGE, EXIT_UNKNOWN = 1, 2, 3
LINK_TYPES = {"References": "references", "ImplementedBy": "implementations", "MemberOf": "members"}
# How a changed Symbol property reads in a review.
FIELD_WORDS = {"digest": "code", "path": "file", "callable": "callability"}
# Each list read's `limit` in queries/code.gq (the tests check they agree). A
# read that returns exactly its limit may have been cut, and cg says so.
LIMITS = {"symbols_named": 1000, "symbols_named_in": 1000, "file_symbols": 2000, "members": 2000,
          "callers": 2000, "callees": 2000, "impact": 5000, "unreferenced_callables": 2000}
# What one load may stage before `write_max_bytes` refuses it. A local load of
# a larger file raises the setting to the file's size; a server's load request
# is capped at the same size and takes no settings.
WRITE_MAX_BYTES = 32 * 1024 * 1024


class CgError(Exception):
    def __init__(self, message: str, status: int = EXIT_FAILED):
        super().__init__(message)
        self.status = status


def _converter():
    sys.path.insert(0, str(SOURCES))
    import build_seed  # noqa: PLC0415  (only `load` and `index` need it)

    return build_seed


def omnigraph_binary() -> str:
    return os.environ.get("CG_OMNIGRAPH") or shutil.which("omnigraph") or "omnigraph"


def is_direct(target: str | None) -> bool:
    """A local graph path rather than the name of a server target."""
    return bool(target) and (target.startswith(("./", "../", "/", "file://")) or target.endswith(".omni"))


def parse_json(text: str) -> dict | None:
    """The JSON document in a CLI stream; diagnostic lines may come first."""
    text = text.strip()
    if not text:
        return None
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {"rows": value}
    except json.JSONDecodeError:
        start = text.find("\n{")
        return parse_json(text[start + 1:]) if start >= 0 else None


class Graph:
    """One code graph, reached through the omnigraph CLI. A server target owns
    its endpoint, TLS settings and token, so cg never handles a credential."""

    def __init__(self, target: str | None, graph: str):
        self.cmd = [omnigraph_binary()]
        self.target = target
        self.graph = graph
        self.direct = is_direct(target)

    def address(self) -> list[str]:
        args = ["--target", self.target] if self.target else []
        return args if self.direct else [*args, "--graph", self.graph]

    def run(self, argv: list[str], write: bool = False) -> dict:
        proc = subprocess.run([*self.cmd, *argv, *self.address(), "--json"], capture_output=True, text=True)
        payload = parse_json(proc.stdout) or parse_json(proc.stderr)
        if proc.returncode == 0 and payload is not None:
            return payload
        payload = payload or {}
        message = payload.get("error") or proc.stderr.strip() or proc.stdout.strip() or f"omnigraph {argv[0]} failed"
        effects = (payload.get("disposition") or {}).get("effects")
        if write and effects != "none":
            raise CgError(f"{message}\nThe load's outcome is {effects or 'unknown'}: check the branch "
                          "(cg revision --branch ...) before loading again.", EXIT_UNKNOWN)
        raise CgError(message)

    def query(self, name: str, params: dict | None = None, branch: str | None = None) -> list[dict]:
        argv = ["query", "--query", str(QUERIES), name] if self.direct else ["query", name]
        argv += ["--params", json.dumps(params or {})]
        if branch:
            argv += ["--branch", branch]
        return self.run(argv)["rows"]

    def branches(self) -> list[str]:
        return self.run(["branch", "list"])["branches"]

    def load(self, path: Path, branch: str, base: str) -> dict:
        size = path.stat().st_size if path.exists() else 0
        argv = ["load", "--data", str(path), "--mode", "overwrite", "--yes", "--branch", branch]
        if size > WRITE_MAX_BYTES:
            if not self.direct:
                raise CgError(f"{path} is {size / 2**20:.0f} MiB; a server load accepts at most "
                              f"{WRITE_MAX_BYTES // 2**20} MiB. Load it into a local graph, or index a "
                              "slice of the repository (--slice).", EXIT_USAGE)
            # A raised limit holds the load's largest type in memory as one batch.
            argv += ["--set", f"write_max_bytes={size}"]
        if branch != base and branch not in self.branches():
            argv += ["--from", base]
        return self.run(argv, write=True)

    def diff(self, branch: str, into: str) -> dict:
        return self.run(["branch", "diff", branch, "--into", into])


# ---------------------------------------------------------------------------
# Symbols


def display(key: str) -> str:
    """A key as a reader would write it: `src/router/utils.ts:createNullObject`,
    `src/router.ts:Router.add()`."""
    build_seed = _converter()
    try:
        parts = build_seed.parse_descriptors(key)
    except ValueError:
        return key
    module = max((i for i, (name, suffix, _) in enumerate(parts) if suffix == "namespace" and "." in name), default=None)
    if module is None:
        return "/".join(name for name, _, _ in parts)
    path = "/".join(name for name, _, _ in parts[:module + 1])
    rest = ".".join(f"{name}()" if suffix == "method" else name for name, suffix, _ in parts[module + 1:])
    return f"{path}:{rest}" if rest else path


def named(g: Graph, name: str, path: str | None = None, branch: str | None = None) -> tuple[str, list[dict]]:
    """The symbols with a name, in the file or directory `path` when given. The
    path filter runs in the query, so a name with more definitions than the
    read's limit is still found in its directory."""
    if not path:
        return "symbols_named", g.query("symbols_named", {"name": name}, branch)
    rows = g.query("symbols_named_in", {"name": name, "path": path.rstrip("/")}, branch)
    prefix = path.rstrip("/") + "/"
    return "symbols_named_in", [r for r in rows if r["s.path"] == path or r["s.path"].startswith(prefix)]


def resolve(g: Graph, text: str, path: str | None = None, branch: str | None = None) -> str:
    """A symbol key from a key or a name; a name must match one symbol."""
    if "/" in text:
        return text
    _, rows = named(g, text, path, branch)
    if len(rows) == 1:
        return rows[0]["s.symbol"]
    where = f" under {path}" if path else ""
    if not rows:
        raise CgError(f"no symbol named {text!r}{where}", EXIT_USAGE)
    lines = "\n".join(f"  {r['s.symbol']}  ({r['s.kind']}, {r['s.path']}:{r['l.line']})" for r in rows)
    raise CgError(f"{len(rows)} symbols are named {text!r}{where}; pass a key or --path:\n{lines}", EXIT_USAGE)


# ---------------------------------------------------------------------------
# Diff


def summarize(diff: dict) -> dict:
    """The branch diff as a review: symbols added, removed and changed, links
    added and removed, and how many definitions only moved."""
    out = {"from_revision": None, "to_revision": None, "added": [], "removed": [], "changed": [], "moved": 0,
           **{name: {"added": [], "removed": [], "changed": []} for name in LINK_TYPES.values()}}
    moved = []
    for change in diff["changes"]:
        kind, op = change["type"]["name"], change["op"]
        before = (change.get("before") or {}).get("properties") or {}
        after = (change.get("after") or {}).get("properties") or {}
        if kind == "Revision":
            if op in ("delete", "update"):
                out["from_revision"] = before.get("sha")
            if op in ("insert", "update"):
                out["to_revision"] = after.get("sha")
        elif kind == "Symbol":
            props = before if op == "delete" else after
            row = {"symbol": change["id"], "kind": props.get("kind"), "path": props.get("path")}
            if op == "insert":
                out["added"].append(row)
            elif op == "delete":
                out["removed"].append(row)
            else:
                fields = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
                out["changed"].append({**row, "fields": fields})
        elif kind == "Location" and op == "update":
            moved.append(change["id"])
        elif kind in LINK_TYPES:
            side = change.get("before" if op == "delete" else "after") or {}
            ends = side.get("endpoints") or {}
            row = {"from": ends.get("from"), "to": ends.get("to"), **(side.get("properties") or {})}
            if op == "update":
                row["before"] = before
            out[LINK_TYPES[kind]][{"insert": "added", "delete": "removed", "update": "changed"}[op]].append(row)
    touched = {r["symbol"] for r in out["added"] + out["removed"] + out["changed"]}
    out["moved"] = sum(1 for key in moved if key not in touched)
    for name in ("added", "removed", "changed"):
        out[name].sort(key=lambda r: r["symbol"])
    for links in (out[n] for n in LINK_TYPES.values()):
        for rows in links.values():
            rows.sort(key=lambda r: (r["from"], r["to"]))
    return out


def _short(sha: str | None) -> str:
    return sha[:8] if sha else "none"


def render(summary: dict, branch: str, into: str, markdown: bool = False) -> str:
    refs = summary["references"]
    head = (f"{branch} against {into}, revision {_short(summary['from_revision'])}.."
            f"{_short(summary['to_revision'])}: {len(summary['added'])} symbols added, "
            f"{len(summary['removed'])} removed, {len(summary['changed'])} changed; "
            f"{len(refs['added'])} references added, {len(refs['removed'])} removed, "
            f"{len(refs['changed'])} changed; {summary['moved']} definitions only moved.")
    code = (lambda s: f"`{s}`") if markdown else (lambda s: s)
    lines = [f"### Code graph: {head}" if markdown else head]

    def section(title: str, rows: list[str]):
        if rows:
            lines.append("")
            lines.append(f"**{title}**" if markdown else f"{title}:")
            lines.extend(f"- {r}" if markdown else f"  {r}" for r in rows)

    section("Added", [f"{code(display(r['symbol']))} ({r['kind']})" for r in summary["added"]])
    section("Removed", [f"{code(display(r['symbol']))} ({r['kind']})" for r in summary["removed"]])
    section("Changed", [f"{code(display(r['symbol']))} ({r['kind']}): "
                        f"{', '.join(FIELD_WORDS.get(f, f) for f in r['fields'])} changed"
                        for r in summary["changed"]])

    def links(rows: list[dict], verb_call: str, verb_ref: str) -> list[str]:
        by_caller = collections.defaultdict(list)
        for r in rows:
            verb = verb_call if r.get("call") else verb_ref
            by_caller[r["from"]].append(f"{verb} {code(display(r['to']))}")
        return [f"{code(display(caller))} {'; '.join(targets)}" for caller, targets in sorted(by_caller.items())]

    section("References added", links(refs["added"], "now calls", "now names"))
    section("References removed", links(refs["removed"], "no longer calls", "no longer names"))
    section("References changed", [f"{code(display(r['from']))} to {code(display(r['to']))}: "
                                   f"call {r['before'].get('call')} to {r.get('call')}, "
                                   f"sites {r['before'].get('sites')} to {r.get('sites')}"
                                   for r in refs["changed"]])
    # Both read "X of Y": an implementation of the member it implements, a
    # member of its container. ImplementedBy runs from Y to X, MemberOf from X to Y.
    for name, title, flip in (("implementations", "Implementations", True), ("members", "Members", False)):
        for op in ("added", "removed"):
            section(f"{title} {op}", [f"{code(display(r['to' if flip else 'from']))} of "
                                      f"{code(display(r['from' if flip else 'to']))}" for r in summary[name][op]])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Loading


def revision_types(path: Path) -> collections.Counter:
    counts = collections.Counter()
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                counts[row.get("type") or row.get("edge")] += 1
    return counts


def check_complete(counts: collections.Counter, allow_missing: bool) -> None:
    build_seed = _converter()
    missing = [t for t in build_seed.TYPES + build_seed.EDGES if not counts[t]]
    if missing and not allow_missing:
        raise CgError(f"the revision has no {', '.join(missing)} rows; an overwrite load keeps the branch's old rows "
                      "of a type the file does not contain. Pass --allow-missing to load it anyway.", EXIT_USAGE)


def git(checkout: Path, *args: str, required: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=checkout, capture_output=True, text=True)
    if proc.returncode != 0:
        if required:
            raise CgError(f"git {' '.join(args)} failed in {checkout}: {proc.stderr.strip()}")
        return ""
    return proc.stdout.strip()


def indexer_binary(explicit: str | None) -> str:
    for candidate in (explicit, os.environ.get("CG_INDEXER"),
                      str(SOURCES / "indexer" / "node_modules" / ".bin" / "scip-typescript")):
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    found = shutil.which("scip-typescript")
    if not found:
        raise CgError("no scip-typescript: run `npm ci` in code-graph/sources/indexer, put scip-typescript "
                      "on PATH, or set CG_INDEXER", EXIT_USAGE)
    return found


# ---------------------------------------------------------------------------
# Commands


def emit(args, data, human: str) -> None:
    print(json.dumps(data, indent=2) if args.json else human)


def table(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return "(none)"
    cells = [[str(r.get(key, "")) for key, _ in columns] for r in rows]
    widths = [max(len(title), *(len(c[i]) for c in cells)) for i, (_, title) in enumerate(columns)]
    lines = ["  ".join(title.ljust(w) for (_, title), w in zip(columns, widths)).rstrip()]
    lines += ["  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in cells]
    return "\n".join(lines)


def cut_note(query: str, rows: list, hint: str = "") -> str:
    """A line for a read that returned exactly its limit, which may have cut it."""
    limit = LIMITS.get(query)
    if limit is None or len(rows) < limit:
        return ""
    return f"\n(the first {limit} rows: {query} stops at {limit}, so the list may be incomplete{hint})"


def cmd_find(args, g: Graph):
    query, rows = named(g, args.name, args.path, args.branch)
    data = [{"symbol": r["s.symbol"], "kind": r["s.kind"], "path": r["s.path"], "line": r["l.line"]} for r in rows]
    note = cut_note(query, rows, "; narrow it with --path")
    emit(args, {"rows": data, "cut": bool(note)},
         table(data, [("symbol", "symbol"), ("kind", "kind"), ("line", "line")]) + note)


READS = {
    # command: (stored query, result columns, human columns)
    "callers": ("callers", [("c.symbol", "caller"), ("c.kind", "kind"), ("r.call", "call"), ("r.sites", "sites")]),
    "callees": ("callees", [("t.symbol", "callee"), ("t.kind", "kind"), ("r.call", "call"), ("r.sites", "sites")]),
    "impact": ("impact", [("c.symbol", "reaches it"), ("c.kind", "kind")]),
    "implementers": ("implementers", [("i.symbol", "implementer")]),
    "members": ("members", [("m.symbol", "member"), ("m.kind", "kind"), ("l.line", "line")]),
}


def cmd_read(args, g: Graph):
    query, columns = READS[args.command]
    key = resolve(g, args.symbol, args.path, args.branch)
    rows = g.query(query, {"symbol": key}, args.branch)
    note = cut_note(query, rows)
    data = {"symbol": key, "rows": [{title: r.get(col) for col, title in columns} for r in rows], "cut": bool(note)}
    human = [{title: (display(v) if col.endswith(".symbol") else v) for (col, title), v in
              zip(columns, (r.get(col) for col, _ in columns))} for r in rows]
    emit(args, data, f"{display(key)}\n" + table(human, [(title, title) for _, title in columns]) + note)


def cmd_overview(args, g: Graph):
    if args.command == "hubs":
        rows = g.query("most_referenced", branch=args.branch)
        data = [{"symbol": r["t.symbol"], "kind": r["t.kind"], "referrers": r["referrers"]} for r in rows]
        human = [{**d, "symbol": display(d["symbol"])} for d in data]
        emit(args, data, table(human, [("referrers", "referrers"), ("symbol", "symbol"), ("kind", "kind")]))
    elif args.command == "unreferenced":
        rows = g.query("unreferenced_callables", branch=args.branch)
        data = [{"symbol": r["s.symbol"], "kind": r["s.kind"]} for r in rows]
        human = [{**d, "symbol": display(d["symbol"])} for d in data]
        note = cut_note("unreferenced_callables", rows)
        emit(args, {"rows": data, "cut": bool(note)}, table(human, [("symbol", "symbol"), ("kind", "kind")]) + note)
    else:
        rows = g.query("revision", branch=args.branch)
        data = rows[0] if rows else {}
        data = {k.split(".", 1)[-1]: v for k, v in data.items()}
        emit(args, data, f"{data.get('sha', 'no revision loaded')}  {data.get('repository', '')}  "
                         f"{data.get('indexer', '')} {data.get('indexer_version', '')}".rstrip())


def _load(args, g: Graph, path: Path) -> None:
    counts = revision_types(path)
    check_complete(counts, args.allow_missing)
    receipt = g.load(path, args.branch, args.base)
    commit = receipt.get("commit") or {}
    data = {"branch": args.branch, "commit": commit.get("graph_commit_id"), "rows": sum(counts.values())}
    emit(args, data, f"loaded {data['rows']} rows onto {args.branch} as commit {data['commit']}; "
                     f"review with `cg diff {args.branch}`")


def cmd_load(args, g: Graph):
    _load(args, g, Path(args.file))


def cmd_index(args, g: Graph):
    import tempfile

    build_seed = _converter()
    checkout = Path(args.checkout).resolve()
    if git(checkout, "status", "--porcelain", "--untracked-files=no") and not args.allow_dirty:
        raise CgError(f"{checkout} has uncommitted changes, so the graph would not match its commit; "
                      "commit them or pass --allow-dirty", EXIT_USAGE)
    revision = args.revision or git(checkout, "rev-parse", "HEAD")
    repository = args.repository or git(checkout, "remote", "get-url", "origin", required=False)
    with tempfile.TemporaryDirectory(prefix="cg-index-") as tmp:
        index = Path(tmp) / "index.scip"
        command = [indexer_binary(args.indexer), "index", *([args.project] if args.project else []),
                   "--no-progress-bar", "--output", str(index)]
        proc = subprocess.run(command, cwd=checkout, capture_output=True, text=True)
        if proc.returncode != 0 or not index.exists():
            raise CgError(f"the indexer failed in {checkout}:\n{(proc.stderr or proc.stdout).strip()[-2000:]}")
        rows = build_seed.build(str(index), str(checkout), revision, repository, args.slice)
        out = Path(args.keep) if args.keep else Path(tmp) / "revision.jsonl"
        out.write_text(build_seed.render(rows), encoding="utf-8")
        _load(args, g, out)


def cmd_diff(args, g: Graph):
    summary = summarize(g.diff(args.branch, args.into))
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(render(summary, args.branch, args.into, markdown=args.markdown))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cg", description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="Settings: CG_TARGET, CG_GRAPH, CG_OMNIGRAPH, CG_INDEXER.")
    parser.add_argument("--target", default=os.environ.get("CG_TARGET"),
                        help="operator target: a server target name, or a local graph path")
    parser.add_argument("--graph", default=os.environ.get("CG_GRAPH") or "code", help="graph id (default: code)")
    parser.add_argument("--json", action="store_true", help="print JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    add_parser = sub.add_parser

    def sub_parser(*a, **kw):
        p = add_parser(*a, **kw)
        # Also accept --json after the command; SUPPRESS keeps a global --json.
        p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="print JSON")
        return p

    sub.add_parser = sub_parser

    def reading(p):
        p.add_argument("--branch", help="read this branch instead of main")
        return p

    p = reading(sub.add_parser("find", help="symbols with a name, and their keys"))
    p.add_argument("name")
    p.add_argument("--path", help="only symbols in this file or directory")
    p.set_defaults(run=cmd_find)
    for name, text in (("callers", "definitions that call or name a symbol"),
                       ("callees", "what a symbol's code calls or names"),
                       ("impact", "everything within sixteen references or implementations of a symbol"),
                       ("implementers", "class members implementing or overriding a member"),
                       ("members", "what a module, class or interface declares")):
        p = reading(sub.add_parser(name, help=text))
        p.add_argument("symbol", help="a key, or a name that matches one symbol")
        p.add_argument("--path", help="the file or directory a name is in")
        p.set_defaults(run=cmd_read)
    for name, text in (("hubs", "the most referenced symbols"),
                       ("unreferenced", "callables nothing in the indexed code refers to"),
                       ("revision", "the commit a branch holds")):
        reading(sub.add_parser(name, help=text)).set_defaults(run=cmd_overview)

    def writing(p):
        p.add_argument("--branch", required=True, help="the branch to load onto, created from --base if missing")
        p.add_argument("--base", default="main", help="the branch a new branch starts from (default: main)")
        p.add_argument("--allow-missing", action="store_true", help="load a revision with an empty type")
        return p

    p = writing(sub.add_parser("load", help="load a revision file with --mode overwrite"))
    p.add_argument("file")
    p.set_defaults(run=cmd_load)
    p = writing(sub.add_parser("index", help="index a TypeScript checkout, convert it and load it"))
    p.add_argument("checkout", nargs="?", default=".")
    p.add_argument("--project", help="the tsconfig to index (default: the indexer's)")
    p.add_argument("--slice", nargs="*", default=[], help="keep only these paths; a trailing / means a directory")
    p.add_argument("--revision", help="the commit to record (default: HEAD)")
    p.add_argument("--repository", help="the repository URL to record (default: origin)")
    p.add_argument("--indexer", help="the scip-typescript binary")
    p.add_argument("--keep", help="also write the revision file here")
    p.add_argument("--allow-dirty", action="store_true", help="index uncommitted changes")
    p.set_defaults(run=cmd_index)
    p = sub.add_parser("diff", help="what a branch changed in the code, as a review")
    p.add_argument("branch")
    p.add_argument("--into", default="main", help="the branch it is compared against (default: main)")
    p.add_argument("--markdown", action="store_true", help="print Markdown, for a pull request comment")
    p.set_defaults(run=cmd_diff)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.run(args, Graph(args.target, args.graph))
        return 0
    except CgError as exc:
        print(f"cg: {exc}", file=sys.stderr)
        return exc.status
    except BrokenPipeError:
        return 0
