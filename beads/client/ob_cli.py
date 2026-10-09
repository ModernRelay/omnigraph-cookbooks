"""ob: a dependency-aware issue tracker for coding agents, built on OmniGraph.

ob speaks the beads (`bd`) workflow: create work, link dependencies, ask for
ready work, claim it, close it. The graph lives in OmniGraph; ob is a thin
client over the `omnigraph` CLI and needs nothing beyond the Python standard
library. Every command publishes at most one graph commit.

Run `ob --help`, or `ob onboard` for the agent instructions.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# tempfile, shutil, secrets, random and threading are imported where used:
# ob runs once per agent action, and on Python 3.14 those imports alone cost
# about as much as the OmniGraph call they wrap.

HERE = Path(os.path.realpath(__file__)).parent
BUNDLE = HERE.parent  # the cookbook: schema.pg, queries/, cluster.yaml
SCHEMA = BUNDLE / "schema.pg"
QUERY_DIR = BUNDLE / "queries"
CONFIG_DIR = ".ob"
CONFIG_FILE = "config.json"
EMBED_DIM = 1536
ID_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"  # Crockford base32, lowercase

KINDS = ["bug", "feature", "task", "epic", "chore", "decision", "spike", "story", "milestone"]
STATUSES = ["open", "in_progress", "deferred", "closed"]
OPEN_STATUSES = ["open", "in_progress", "deferred"]
EDITABLE = [
    "title", "description", "design", "acceptance", "notes", "kind", "status", "priority",
    "labels", "assignee", "defer_until", "due_at", "external_ref", "metadata",
]
# `ob dep add --type` spelling -> (link mutation suffix, schema edge name).
LINK_TYPES = {
    "blocks": ("blocks", "BlockedBy"),
    "parent": ("parent", "ChildOf"),
    "parent-child": ("parent", "ChildOf"),
    "related": ("related", "RelatesTo"),
    "relates-to": ("related", "RelatesTo"),
    "discovered-from": ("discovered_from", "DiscoveredFrom"),
    "duplicates": ("duplicates", "Duplicates"),
    "supersedes": ("supersedes", "Supersedes"),
}
EDGE_LABELS = {
    "BlockedBy": ("depends on", "blocks"),
    "ChildOf": ("parent", "child"),
    "RelatesTo": ("related", "related"),
    "DiscoveredFrom": ("discovered from", "led to"),
    "Duplicates": ("duplicates", "duplicated by"),
    "Supersedes": ("supersedes", "superseded by"),
}
ICONS = {"open": "○", "in_progress": "◐", "deferred": "❄", "closed": "✓", "blocked": "●"}

# A write that loses the race for the branch head is refused before it has
# any effect ("reprepare from the current branch state"). Every ob write is
# conditional or idempotent, so retrying from fresh state is always safe.
CONFLICT_RETRIES = 24
CONFLICT_BACKOFF_MAX = 0.4
TRANSPORT_RETRIES = 5
HTTP_API = "0.13"


class ObError(Exception):
    def __init__(self, message: str, payload: dict | None = None):
        super().__init__(message)
        self.payload = payload or {}


class KeyConflict(ObError):
    pass


class Conflict(ObError):
    pass


# ---------------------------------------------------------------------------
# Time, ids and small helpers


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


DURATION = re.compile(r"^(\d+)([smhdw])$")


def parse_when(text: str | None) -> str | None:
    """A duration from now (30m, 2h, 3d, 1w) or an ISO date or datetime."""
    if text is None or text in ("", "none", "null"):
        return None
    m = DURATION.match(text.strip())
    if m:
        unit = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}[m.group(2)]
        return iso(now() + dt.timedelta(**{unit: int(m.group(1))}))
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ObError(f"not a duration or ISO time: {text!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return iso(parsed)


def as_param_time(value: str) -> str:
    """Query results print DateTime without a zone; parameters take UTC with Z."""
    return value if value.endswith("Z") else value + "Z"


def check_json(text: str) -> str:
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        raise ObError(f"--metadata is invalid JSON: {exc}") from exc
    return text


def embedding_query(type_name: str, field: str, text: str) -> str:
    """Query text in the shape `omnigraph embed` gives stored documents.

    OmniGraph 0.13.0's offline pipeline embeds `type: <Type>\n<field>: <value>`,
    while a query-time `nearest(..., $q)` embeds `$q` verbatim; sending the
    same shape keeps both sides of the comparison in one text space.
    """
    return f"type: {type_name}\n{field}: {text}"


def new_id(prefix: str, length: int = 6) -> str:
    import secrets

    return f"{prefix}-" + "".join(secrets.choice(ID_ALPHABET) for _ in range(length))


def slugify(text: str, words: int = 5) -> str:
    tokens = re.findall(r"[a-z0-9]+", text.lower())[:words]
    return "-".join(tokens) or new_id("m")


def strip_row(row: dict) -> dict:
    """Turn `i.slug` style columns into `slug`; aliases are kept as written."""
    out = {}
    for key, value in row.items():
        out[key.split(".", 1)[1] if "." in key else key] = value
    return out


def split_csv(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for value in values or []:
        out.extend(v.strip() for v in value.split(",") if v.strip())
    return out


# ---------------------------------------------------------------------------
# Configuration


def find_config_dir(start: Path) -> Path | None:
    env = os.environ.get("OB_DIR")
    if env:
        return Path(env).resolve()
    for directory in [start, *start.parents]:
        candidate = directory / CONFIG_DIR
        if (candidate / CONFIG_FILE).is_file():
            return candidate
    return None


def load_config(args) -> tuple[Path | None, dict]:
    cfg_dir = Path(args.dir).resolve() if args.dir else find_config_dir(Path.cwd())
    cfg: dict = {}
    if cfg_dir and (cfg_dir / CONFIG_FILE).is_file():
        cfg = json.loads((cfg_dir / CONFIG_FILE).read_text())
    if os.environ.get("OB_STORE"):
        cfg = {**cfg, "store": os.environ["OB_STORE"]}
        cfg.pop("server", None)
    if os.environ.get("OB_SERVER"):
        cfg = {**cfg, "server": os.environ["OB_SERVER"], "graph": os.environ.get("OB_GRAPH", "beads")}
        cfg.pop("store", None)
    return cfg_dir, cfg


def default_actor(cfg: dict) -> str:
    for candidate in (os.environ.get("OB_ACTOR"), cfg.get("actor")):
        if candidate:
            return candidate
    try:
        email = subprocess.run(
            ["git", "config", "user.email"], capture_output=True, text=True, timeout=2
        ).stdout.strip()
        if email:
            return email
    except (OSError, subprocess.SubprocessError):
        pass
    return os.environ.get("USER") or "unknown"


# ---------------------------------------------------------------------------
# The OmniGraph client


def omnigraph_binary() -> str:
    found = os.environ.get("OB_OMNIGRAPH")
    if found:
        return found
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory, "omnigraph")
        if os.access(candidate, os.X_OK):
            return candidate
    return "omnigraph"


def query_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in sorted(QUERY_DIR.glob("*.gq")):
        for name in re.findall(r"^query\s+(\w+)\s*\(", path.read_text(), re.M):
            index[name] = path
    return index


class Graph:
    """One graph, addressed directly (`store`) or through a server (`server`).

    A local store and a server named in ~/.omnigraph/config.yaml go through
    the `omnigraph` CLI. A server given as an http(s) URL is called directly
    over HTTP, which saves a process start and a graph open per operation.
    """

    def __init__(self, cfg: dict, cfg_dir: Path | None, actor: str, branch: str | None):
        self.bin = omnigraph_binary()
        self.actor = actor
        self.branch = branch
        self.server = cfg.get("server")
        self.graph_id = cfg.get("graph") or "beads"
        self.http = self.server if self.server and self.server.startswith(("http://", "https://")) else None
        self.token = os.environ.get("OB_TOKEN") or os.environ.get("OMNIGRAPH_BEARER_TOKEN")
        store = cfg.get("store")
        if store and cfg_dir and "://" not in store and not os.path.isabs(store):
            store = str((cfg_dir / store).resolve())
        self.store = store
        self.embed = bool(cfg.get("embed"))
        # Set when a request was resent after a lost response, so its first
        # attempt may have landed. A conflict refusal never has an effect.
        self.resent = False
        self.queries = query_index()
        if not self.server and not self.store:
            raise ObError("no graph configured: run `ob init` (or set OB_DIR, OB_STORE or OB_SERVER)")

    # -- CLI transport ---------------------------------------------------
    def address(self) -> list[str]:
        if self.server:
            return ["--server", self.server, "--graph", self.graph_id]
        return ["--store", self.store]

    def _exec(self, argv: list[str]) -> dict:
        proc = subprocess.run([self.bin, *argv], capture_output=True, text=True)
        payload = _parse_json(proc.stdout) or _parse_json(proc.stderr)
        if proc.returncode == 0:
            if payload is None:
                raise ObError(f"omnigraph printed no JSON for {argv[0]}: {proc.stdout[:200]}")
            return payload
        raise _classify(payload, proc.stderr.strip() or proc.stdout.strip() or f"omnigraph {argv[0]} failed")

    def _source(self, name: str) -> list[str]:
        if self.server:
            return []  # a stored query on the server
        if name not in self.queries:
            raise ObError(f"unknown query {name}")
        return ["--query", str(self.queries[name])]

    # -- HTTP transport --------------------------------------------------
    def _request(self, method: str, path: str, body=None, query: dict | None = None) -> dict:
        import urllib.error  # imported lazily: ssl alone costs ~100 ms at startup
        import urllib.parse
        import urllib.request

        url = f"{self.http.rstrip('/')}/graphs/{urllib.parse.quote(self.graph_id)}{path}"
        if query:
            url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        headers = {"Omnigraph-Http-Api": HTTP_API, "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        import random

        delay = 0.05
        for attempt in range(TRANSPORT_RETRIES):
            try:
                request = urllib.request.Request(url, data=data, method=method, headers=headers)
                with urllib.request.urlopen(request, timeout=120) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                raw = exc.read()
                payload = _parse_json(raw.decode(errors="replace")) or {}
                if exc.code in (429, 502, 503, 504) and attempt < TRANSPORT_RETRIES - 1:
                    self.resent = True  # every ob write is conditional or idempotent: resend
                else:
                    raise _classify(payload, f"HTTP {exc.code} from {method} {path}") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt == TRANSPORT_RETRIES - 1:
                    raise ObError(f"cannot reach {self.http}: {exc}") from None
                self.resent = True
            time.sleep(delay + random.random() * delay)
            delay = min(delay * 2, 2.0)
        raise AssertionError("unreachable")

    # -- operations ------------------------------------------------------
    def _retrying(self, attempt):
        import random

        delay = 0.005
        for n in range(CONFLICT_RETRIES):
            try:
                return attempt()
            except Conflict:
                if n == CONFLICT_RETRIES - 1:
                    raise
                time.sleep(delay + random.random() * delay)
                delay = min(delay * 2, CONFLICT_BACKOFF_MAX)
        raise AssertionError("unreachable")

    def _invoke(self, name: str, params: dict, mutation: bool) -> dict:
        if self.http:
            body = {"params": params, "expect_mutation": mutation}
            if self.branch:
                body["branch"] = self.branch
            return self._request("POST", f"/queries/{name}", body)
        argv = ["mutate" if mutation else "query", name, *self._source(name), *self.address(),
                "--params", json.dumps(params), "--json"]
        if self.branch:
            argv += ["--branch", self.branch]
        if mutation:
            argv.append("--quiet")
            if not self.server:
                argv += ["--as", self.actor]
        return self._exec(argv)

    def query(self, name: str, params: dict | None = None) -> list[dict]:
        return [strip_row(r) for r in self._invoke(name, params or {}, False).get("rows", [])]

    def mutate(self, name: str, params: dict) -> dict:
        return self._retrying(lambda: self._invoke(name, params, True))

    def load(self, rows: list[dict], mode: str) -> dict:
        import tempfile

        with tempfile.TemporaryDirectory(prefix="ob-") as scratch:
            path = Path(scratch) / "rows.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            if self.embed:
                path = self._embed_file(path)
            if self.http:
                body = {"data": path.read_text(), "mode": mode}
                if self.branch:
                    body["branch"] = self.branch
                return self._retrying(lambda: self._request("POST", "/load", body))
            argv = ["load", "--data", str(path), "--mode", mode, *self.address(), "--json", "--quiet"]
            if self.branch:
                argv += ["--branch", self.branch]
            if not self.server:
                argv += ["--as", self.actor]
            return self._retrying(lambda: self._exec(argv))

    def changes_page(self, token: str | None) -> dict:
        if self.http:
            query = {"start": None if token else "beginning", "page_token": token, "limit": 8192,
                     "branch": self.branch}
            return self._request("GET", "/changes", query=query)
        argv = ["changes", "poll", *self.address(), "--json", "--limit", "8192"]
        argv += ["--page-token", token] if token else ["--start", "beginning"]
        if self.branch:
            argv += ["--branch", self.branch]
        return self._exec(argv)

    def branch_op(self, action: str, name: str | None, base: str) -> dict:
        if self.http:
            if action == "list":
                return self._request("GET", "/branches")
            if action == "create":
                return self._request("POST", "/branches", {"name": name, "from": base})
            if action == "merge":
                return self._request("POST", "/branches/merge", {"source": name, "target": base})
            from urllib.parse import quote

            return self._request("DELETE", f"/branches/{quote(name, safe='')}")
        argv = ["branch", action, *([name] if name else []), *self.address(), "--json"]
        if action == "create":
            argv += ["--from", base]
        if action == "merge":
            argv += ["--into", base]
        return self._exec(argv)

    def _embed_file(self, path: Path) -> Path:
        """Fill the declared embeddings with OmniGraph's offline pipeline."""
        spec = {
            "dimension": EMBED_DIM,
            "types": {
                "Issue": {"target": "embedding", "fields": ["title"]},
                "Memory": {"target": "embedding", "fields": ["body"]},
            },
        }
        spec_path = path.with_name("embed-spec.json")
        spec_path.write_text(json.dumps(spec))
        out = path.with_name(path.stem + ".embedded.jsonl")
        proc = subprocess.run(
            [self.bin, "embed", "--input", str(path), "--output", str(out), "--spec", str(spec_path)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise ObError(f"embedding failed: {proc.stderr.strip() or proc.stdout.strip()}")
        return out

    def embed_text(self, slug: str, title: str) -> list[float] | None:
        if not self.embed:
            return None
        import tempfile

        with tempfile.TemporaryDirectory(prefix="ob-") as scratch:
            path = Path(scratch) / "one.jsonl"
            path.write_text(json.dumps({"type": "Issue", "data": {"slug": slug, "title": title}}) + "\n")
            row = json.loads(self._embed_file(path).read_text().splitlines()[0])
            return row["data"].get("embedding")

    def raw(self, argv: list[str]) -> dict:
        return self._exec(argv)

    def parallel(self, calls: list[tuple[str, dict]]) -> list[list[dict]]:
        """Run independent reads concurrently (each waits on I/O, not the GIL)."""
        import threading

        results: list = [None] * len(calls)

        def run(i: int, name: str, params: dict):
            try:
                results[i] = self.query(name, params)
            except BaseException as exc:  # re-raised on the calling thread
                results[i] = exc

        threads = [threading.Thread(target=run, args=(i, *call)) for i, call in enumerate(calls)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for r in results:
            if isinstance(r, BaseException):
                raise r
        return results


def _classify(payload: dict | None, fallback: str) -> ObError:
    payload = payload or {}
    if "key_conflict" in payload and payload["key_conflict"]:
        return KeyConflict(payload.get("error", "key conflict"), payload)
    if "read_set_conflict" in payload and payload["read_set_conflict"]:
        return Conflict(payload.get("error", "conflict"), payload)
    return ObError(payload.get("error") or fallback, payload)


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {"rows": value}
    except json.JSONDecodeError:
        start = text.find("{")
        if start > 0:
            return _parse_json(text[start:])
        return None


# ---------------------------------------------------------------------------
# Output


class Out:
    def __init__(self, as_json: bool):
        self.as_json = as_json

    def emit(self, data, human=None):
        if self.as_json:
            print(json.dumps(data, indent=2, default=str))
        elif human is not None:
            text = human() if callable(human) else human
            if text:
                print(text)


def issue_line(row: dict, status: str | None = None) -> str:
    status = status or row.get("status") or "open"
    icon = ICONS.get(status, "?")
    parts = [f"{icon} {row.get('slug', ''):<14}", f"P{row.get('priority', '?')}",
             f"{row.get('kind', ''):<9}", row.get("title", "")]
    if row.get("assignee"):
        parts.append(f"@{row['assignee']}")
    if row.get("labels"):
        parts.append("[" + ", ".join(row["labels"]) + "]")
    return "  ".join(str(p) for p in parts)


# ---------------------------------------------------------------------------
# Commands


def cmd_init(args, out: Out):
    base = Path(args.dir or os.environ.get("OB_DIR") or Path.cwd() / CONFIG_DIR).resolve()
    cfg_path = base / CONFIG_FILE
    if cfg_path.exists():
        raise ObError(f"already initialized: {cfg_path}")
    base.mkdir(parents=True, exist_ok=True)
    # Resolve the default actor once, so later commands need not ask git.
    cfg: dict = {"prefix": args.prefix, "embed": bool(args.embed), "actor": args.actor or default_actor({})}
    binary = omnigraph_binary()
    if args.server:
        cfg.update({"server": args.server, "graph": args.graph})
        detail = f"served graph {args.graph} on {args.server}"
    else:
        cfg["store"] = args.store or "graph.omni"
        store = cfg["store"] if "://" in cfg["store"] or os.path.isabs(cfg["store"]) else str(base / cfg["store"])
        proc = subprocess.run([binary, "init", "--schema", str(SCHEMA), store], capture_output=True, text=True)
        if proc.returncode != 0:
            raise ObError(f"omnigraph init failed: {proc.stderr.strip() or proc.stdout.strip()}")
        detail = f"local graph {store}"
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
    (base / ".gitignore").write_text("*.omni/\ntmp/\n")
    out.emit({"config": str(cfg_path), **cfg}, f"initialized ob ({detail}); prefix {args.prefix}-")


def _require_issue(g: Graph, slug: str) -> dict:
    rows = g.query("show", {"id": slug})
    if not rows:
        raise ObError(f"no issue {slug}")
    return rows[0]["i"]


def cmd_create(args, out: Out, g: Graph, cfg: dict):
    prefix = cfg.get("prefix", "ob")
    created = iso(now())
    labels = split_csv(args.labels)
    data = {
        "title": args.title,
        "kind": args.type,
        "status": "open",
        "priority": args.priority,
        "created_by": g.actor,
        "created_at": created,
        "updated_at": created,
    }
    for key, value in (("description", args.description), ("design", args.design),
                       ("acceptance", args.acceptance), ("notes", args.notes),
                       ("assignee", args.assignee), ("external_ref", args.external_ref)):
        if value:
            data[key] = value
    if labels:
        data["labels"] = labels
    if args.defer:
        data["defer_until"] = parse_when(args.defer)
    if args.due:
        data["due_at"] = parse_when(args.due)
    if args.metadata:
        data["metadata"] = check_json(args.metadata)
    edges = []
    for dep in split_csv(args.deps):
        kind, _, target = dep.rpartition(":")
        mutation, edge = LINK_TYPES.get(kind or "blocks", (None, None))
        if edge is None:
            raise ObError(f"unknown dependency type {kind!r}")
        edges.append((edge, target))
    if args.parent:
        waits = {target for edge, target in edges if edge == "BlockedBy"}
        if waits:
            above = {args.parent} | {r["slug"] for r in g.query("lineage", {"id": args.parent})}
            if waits & above:
                raise ObError(_ANCESTOR_BLOCK.format(child="a new issue", ancestor=sorted(waits & above)[0]))
        edges.append(("ChildOf", args.parent))
    if args.discovered_from:
        edges.append(("DiscoveredFrom", args.discovered_from))

    # One strict append: the issue and all of its links publish as one commit,
    # and an id that already exists is refused rather than overwritten.
    for _ in range(5):
        slug = args.id or new_id(prefix)
        rows = [{"type": "Issue", "data": {"slug": slug, **data}}]
        rows += [{"edge": edge, "from": slug, "to": target} for edge, target in edges]
        try:
            receipt = g.load(rows, "append")
            break
        except KeyConflict:
            existing = g.query("show", {"id": slug})
            if existing and existing[0]["i"].get("created_at", "").startswith(created[:19]) \
                    and existing[0]["i"].get("title") == args.title:
                receipt = {"commit": None}  # an earlier attempt of ours landed
                break
            if args.id:
                raise ObError(f"issue {slug} already exists")
    else:
        raise ObError("could not allocate an unused id")
    out.emit({"id": slug, "commit": (receipt.get("commit") or {}).get("graph_commit_id")},
             f"created {slug}: {args.title}")


def cmd_show(args, out: Out, g: Graph, cfg: dict):
    results = []
    for slug in args.ids:
        issue, outs, ins, comments, ancestors, mems = g.parallel([
            ("show", {"id": slug}), ("out_links", {"id": slug}), ("in_links", {"id": slug}),
            ("comments", {"id": slug}), ("ancestor_blockers", {"id": slug}),
            ("memories_about", {"id": slug}),
        ])
        if not issue:
            raise ObError(f"no issue {slug}")
        row = issue[0]["i"]
        row.pop("@id", None)
        open_blockers = [o for o in outs if o["link"] == "BlockedBy" and o["status"] != "closed"]
        derived = row["status"]
        if derived == "open" and (open_blockers or ancestors):
            derived = "blocked"
        results.append({**row, "state": derived, "links_out": outs, "links_in": ins,
                        "inherited_blockers": ancestors, "comments": comments, "memories": mems})

    def human():
        lines = []
        for r in results:
            lines.append(issue_line(r, r["state"]))
            for key in ("description", "design", "acceptance", "notes"):
                if r.get(key):
                    lines.append(f"  {key}: {r[key]}")
            meta = [f"status {r['status']}", f"created {r.get('created_at', '')} by {r.get('created_by', '?')}"]
            if r.get("lease_expires_at"):
                meta.append(f"lease until {r['lease_expires_at']}")
            if r.get("defer_until"):
                meta.append(f"deferred until {r['defer_until']}")
            if r.get("closed_at"):
                meta.append(f"closed {r['closed_at']} ({r.get('close_reason') or 'no reason'})")
            lines.append("  " + " · ".join(meta))
            for link in r["links_out"]:
                lines.append(f"  {EDGE_LABELS[link['link']][0]}: {link['slug']} [{link['status']}] {link['title']}")
            for link in r["links_in"]:
                lines.append(f"  {EDGE_LABELS[link['link']][1]}: {link['slug']} [{link['status']}] {link['title']}")
            for a in r["inherited_blockers"]:
                lines.append(f"  blocked via ancestor {a['ancestor']}: {a['blocker']} [{a['status']}] {a['title']}")
            for c in r["comments"]:
                lines.append(f"  💬 {c.get('author', '?')} {c.get('created_at', '')}: {c['body']}")
            for m in r["memories"]:
                lines.append(f"  🧠 {m['slug']}: {m['body']}")
        return "\n".join(lines)

    out.emit(results if len(results) > 1 else results[0], human)


def _filter_rows(rows: list[dict], args, me: str) -> list[dict]:
    kinds = set(split_csv(getattr(args, "type", None)))
    excluded = set(split_csv(getattr(args, "exclude_type", None)))
    labels = split_csv(getattr(args, "label", None))
    assignee = getattr(args, "assignee", None)
    max_p = getattr(args, "priority_max", None)
    kept = []
    for r in rows:
        if kinds and r.get("kind") not in kinds:
            continue
        if r.get("kind") in excluded:
            continue
        if labels and not set(labels) <= set(r.get("labels") or []):
            continue
        if assignee == "none" and r.get("assignee"):
            continue
        if assignee and assignee not in ("none", "me") and r.get("assignee") != assignee:
            continue
        if assignee == "me" and r.get("assignee") != me:
            continue
        if max_p is not None and r.get("priority", 9) > max_p:
            continue
        kept.append(r)
    return kept


def cmd_ready(args, out: Out, g: Graph, cfg: dict):
    labels = split_csv(args.label)
    rows = g.query("ready_labeled", {"label": labels[0]}) if labels else g.query("ready")
    rows = _filter_rows(rows, args, g.actor)
    if args.claim:
        # Take the oldest top-priority issue. Agents that lose that race would
        # all chase the next one too, so after a loss each walks the rest of
        # every priority level in its own random order.
        import random

        candidates = [r for r in rows if r.get("assignee") in (None, g.actor)]
        ordered: list[dict] = candidates[:1]
        rest = candidates[1:]
        for priority in sorted({r["priority"] for r in rest}):
            level = [r for r in rest if r["priority"] == priority]
            random.shuffle(level)
            ordered += level
        for candidate in ordered:
            if _claim(g, candidate["slug"], args.lease, confirm=False):
                out.emit({"claimed": candidate["slug"], "issue": candidate},
                         f"claimed {candidate['slug']}: {candidate['title']}")
                return
        out.emit({"claimed": None}, "no ready work to claim")
        return
    rows = rows[: args.limit]
    out.emit(rows, lambda: "\n".join(issue_line(r) for r in rows) or "no ready work")


def cmd_list(args, out: Out, g: Graph, cfg: dict):
    statuses = split_csv(args.status) or (STATUSES if args.all else OPEN_STATUSES)
    rows = _filter_rows(g.query("list", {"statuses": statuses}), args, g.actor)[: args.limit]
    out.emit(rows, lambda: "\n".join(issue_line(r) for r in rows) or "no issues")


def cmd_blocked(args, out: Out, g: Graph, cfg: dict):
    direct, inherited, counts, unblocked = g.parallel(
        [("blocked", {}), ("blocked_by_ancestor", {}), ("stats", {}), ("unblocked_open_count", {})])
    open_total = sum(r["issues"] for r in counts if r["status"] == "open")
    expected = open_total - unblocked[0]["unblocked"]
    grouped: dict[str, dict] = {}
    for r in direct:
        entry = grouped.setdefault(r["slug"], {**r, "blockers": [], "via": []})
        entry["blockers"].append(r["blocker"])
    for r in inherited:
        entry = grouped.setdefault(r["slug"], {**r, "blockers": [], "via": []})
        entry["via"].append(f"{r['ancestor']}<-{r['blocker']}")
    rows = sorted(grouped.values(), key=lambda r: (r.get("priority", 9), r["slug"]))
    for r in rows:
        for k in ("blocker", "blocker_status", "ancestor"):
            r.pop(k, None)
    if sum(1 for r in rows if r["status"] == "open") < expected:
        print(f"ob: the listing is capped; {expected} open issues are blocked in all", file=sys.stderr)

    def human():
        lines = []
        for r in rows:
            why = []
            if r["blockers"]:
                why.append("by " + ", ".join(r["blockers"]))
            if r["via"]:
                why.append("via " + ", ".join(r["via"]))
            lines.append(f"{ICONS['blocked']} {r['slug']:<14} P{r.get('priority', '?')}  {r['title']}  ({'; '.join(why)})")
        return "\n".join(lines) or "nothing is blocked"

    out.emit(rows, human)


def _claim(g: Graph, slug: str, lease: str | None, confirm: bool = True) -> bool:
    g.resent = False
    receipt = g.mutate("claim", {"id": slug, "who": g.actor, "lease": parse_when(lease)})
    if receipt.get("affected_nodes"):
        return True
    if not confirm and not g.resent:
        return False  # someone else holds it; nothing of ours can have landed
    # Zero rows: someone else holds it, it is ours already, or a resent
    # request's first attempt landed. The row says which.
    rows = g.query("show", {"id": slug})
    if not rows:
        raise ObError(f"no issue {slug}")
    issue = rows[0]["i"]
    return issue.get("status") == "in_progress" and issue.get("assignee") == g.actor


def cmd_claim(args, out: Out, g: Graph, cfg: dict):
    if _claim(g, args.id, args.lease):
        out.emit({"claimed": args.id}, f"claimed {args.id}")
        return
    issue = _require_issue(g, args.id)
    raise ObError(f"{args.id} is {issue.get('status')}"
                  + (f", held by {issue['assignee']}" if issue.get("assignee") else ""), issue)


def cmd_release(args, out: Out, g: Graph, cfg: dict):
    receipt = g.mutate("release", {"id": args.id, "who": g.actor, "none": None, "never": None})
    if not receipt.get("affected_nodes"):
        raise ObError(f"{args.id} is not held by {g.actor}")
    out.emit({"released": args.id}, f"released {args.id}")


def cmd_renew(args, out: Out, g: Graph, cfg: dict):
    lease = parse_when(args.lease)
    receipt = g.mutate("renew", {"id": args.id, "who": g.actor, "lease": lease})
    if not receipt.get("affected_nodes"):
        raise ObError(f"{args.id} is not held by {g.actor}")
    out.emit({"renewed": args.id, "lease_expires_at": lease}, f"lease on {args.id} runs to {lease}")


def cmd_reclaim(args, out: Out, g: Graph, cfg: dict):
    expired = g.query("expired_leases")
    receipt = g.mutate("reclaim_expired", {"none": None, "never": None}) if expired else {}
    out.emit({"reclaimed": receipt.get("affected_nodes", 0), "issues": expired},
             lambda: "\n".join(f"reopened {r['slug']} (lease of {r.get('assignee')} expired {r['lease_expires_at']})"
                               for r in expired) or "no expired leases")


def cmd_close(args, out: Out, g: Graph, cfg: dict):
    if not getattr(args, "force", False):
        # beads' rule: work still waiting below or in front of an issue keeps it
        # open. Issues closed together may wait on each other.
        blockers, children = g.parallel([("open_blockers_of", {"ids": args.ids}),
                                         ("open_children_of", {"ids": args.ids})])
        closing = set(args.ids)
        problems = [f"{r['slug']} waits on open {r['other']}" for r in blockers if r["other"] not in closing]
        problems += [f"{r['slug']} has open child {r['other']}" for r in children if r["other"] not in closing]
        if problems:
            raise ObError("not closed: " + "; ".join(problems[:5]) + (" …" if len(problems) > 5 else "")
                          + " (use --force to close anyway)")
    receipt = g.mutate("close", {"ids": args.ids, "reason": args.reason, "never": None})
    out.emit({"closed": receipt.get("affected_nodes", 0), "ids": args.ids},
             f"closed {receipt.get('affected_nodes', 0)} of {len(args.ids)}")


def cmd_reopen(args, out: Out, g: Graph, cfg: dict):
    receipt = g.mutate("reopen", {"ids": args.ids, "none": None, "never": None})
    out.emit({"reopened": receipt.get("affected_nodes", 0)}, f"reopened {receipt.get('affected_nodes', 0)}")


def cmd_defer(args, out: Out, g: Graph, cfg: dict):
    receipt = g.mutate("defer", {"ids": args.ids, "until": parse_when(args.until)})
    out.emit({"deferred": receipt.get("affected_nodes", 0)}, f"deferred {receipt.get('affected_nodes', 0)}")


def cmd_undefer(args, out: Out, g: Graph, cfg: dict):
    receipt = g.mutate("undefer", {"ids": args.ids, "never": None})
    out.emit({"undeferred": receipt.get("affected_nodes", 0)}, f"undeferred {receipt.get('affected_nodes', 0)}")


def _edit(g: Graph, slug: str, change) -> dict:
    """Read-modify-write guarded by the issue's own updated_at (per-issue CAS)."""
    import random

    for _ in range(CONFLICT_RETRIES):
        issue = _require_issue(g, slug)
        fields = {k: issue.get(k) for k in EDITABLE}
        before = dict(fields)
        change(fields)
        if fields == before:
            return {"changed": False}
        params = {"id": slug, "expected": as_param_time(issue["updated_at"]), **fields}
        name = "edit"
        if g.embed and fields["title"] != before["title"]:
            params["embedding"] = g.embed_text(slug, fields["title"])
            name = "edit_embedded"
        if g.mutate(name, params).get("affected_nodes"):
            return {"changed": True, "before": before, "after": fields}
        time.sleep(random.random() * 0.02)  # someone edited it first: re-read
    raise ObError(f"{slug} kept changing underneath the edit; try again")


def cmd_update(args, out: Out, g: Graph, cfg: dict):
    if args.status == "closed":
        return cmd_close(argparse.Namespace(ids=[args.id], reason=args.reason, force=False), out, g, cfg)
    sets = {}
    for key in ("title", "description", "design", "acceptance", "notes", "assignee", "external_ref"):
        value = getattr(args, key)
        if value is not None:
            sets[key] = value or None
    if args.type:
        sets["kind"] = args.type
    if args.status:
        sets["status"] = args.status
    if args.priority is not None:
        sets["priority"] = args.priority
    if args.defer is not None:
        sets["defer_until"] = parse_when(args.defer)
    if args.due is not None:
        sets["due_at"] = parse_when(args.due)
    if args.metadata is not None:
        sets["metadata"] = check_json(args.metadata) if args.metadata else None
    add, remove = split_csv(args.add_label), set(split_csv(args.remove_label))

    def change(fields):
        fields.update(sets)
        labels = [l for l in (fields.get("labels") or []) if l not in remove]
        labels += [l for l in add if l not in labels]
        fields["labels"] = labels or None

    result = {"changed": False}
    if sets or add or remove:
        result = _edit(g, args.id, change)
    if args.claim:
        if not _claim(g, args.id, args.lease):
            raise ObError(f"could not claim {args.id}")
        result["claimed"] = True
    out.emit({"id": args.id, **result}, f"updated {args.id}" if result.get("changed") or result.get("claimed")
             else f"{args.id} unchanged")


def cmd_label(args, out: Out, g: Graph, cfg: dict):
    ns = argparse.Namespace(id=args.id, status=None, claim=False, lease=None, reason=None, type=None,
                            priority=None, defer=None, due=None, metadata=None,
                            add_label=args.labels if args.action == "add" else None,
                            remove_label=args.labels if args.action == "rm" else None,
                            **{k: None for k in ("title", "description", "design", "acceptance",
                                                 "notes", "assignee", "external_ref")})
    cmd_update(ns, out, g, cfg)


def cmd_dep(args, out: Out, g: Graph, cfg: dict):
    if args.action in ("list", "tree"):
        slug = args.issue
        if args.action == "list":
            outs, ins = g.parallel([("out_links", {"id": slug}), ("in_links", {"id": slug})])
            data = {"out": outs, "in": ins}
            out.emit(data, lambda: "\n".join(
                [f"{EDGE_LABELS[l['link']][0]}: {l['slug']} [{l['status']}] {l['title']}" for l in outs]
                + [f"{EDGE_LABELS[l['link']][1]}: {l['slug']} [{l['status']}] {l['title']}" for l in ins])
                or "no links")
        else:
            up, down = g.parallel([("upstream", {"id": slug}), ("downstream", {"id": slug})])
            out.emit({"waits_on": up, "waited_on_by": down}, lambda: "\n".join(
                [f"waits on   {r['slug']} [{r['status']}] {r['title']}" for r in up]
                + [f"blocks     {r['slug']} [{r['status']}] {r['title']}" for r in down]) or "no dependencies")
        return
    mutation, edge = LINK_TYPES.get(args.type, (None, None))
    if mutation is None:
        raise ObError(f"unknown dependency type {args.type!r}; use one of {', '.join(sorted(LINK_TYPES))}")
    src, dst = args.issue, args.target
    if not dst:
        raise ObError("dep add/rm needs two issues")
    if args.action == "add":
        if src == dst:
            raise ObError("an issue cannot depend on itself")
        if edge == "BlockedBy":
            cycle, above_src, above_dst = g.parallel([("reaches", {"from": dst, "to": src}),
                                                      ("lineage", {"id": src}), ("lineage", {"id": dst})])
            if cycle:
                raise ObError(f"{dst} already waits on {src}; adding this dependency would form a cycle")
            if dst in {r["slug"] for r in above_src}:
                raise ObError(_ANCESTOR_BLOCK.format(child=src, ancestor=dst))
            if src in {r["slug"] for r in above_dst}:
                raise ObError(_DESCENDANT_BLOCK.format(parent=src, descendant=dst))
        if edge == "ChildOf":
            lineage, outs = g.parallel([("lineage", {"id": dst}), ("out_links", {"id": src})])
            above = {dst} | {r["slug"] for r in lineage}
            waits = {o["slug"] for o in outs if o["link"] == "BlockedBy"} & above
            if waits:
                raise ObError(_ANCESTOR_BLOCK.format(child=src, ancestor=sorted(waits)[0]))
            on_root, on_subtree = g.parallel([("waits_on_root", {"ids": sorted(above), "root": src}),
                                              ("waits_on_subtree", {"ids": sorted(above), "root": src})])
            if on_root or on_subtree:
                hit = (on_root or on_subtree)[0]
                raise ObError(_DESCENDANT_BLOCK.format(parent=hit["slug"], descendant=hit["other"]))
        receipt = g.mutate(f"link_{mutation}", {"src": src, "dst": dst})
        verb = "linked"
    else:
        receipt = g.mutate(f"unlink_{mutation}", {"src": src, "dst": dst})
        verb = "unlinked" if receipt.get("affected_edges") else "no such link"
    out.emit({"action": args.action, "type": edge, "from": src, "to": dst,
              "affected": receipt.get("affected_edges", 0)}, f"{verb}: {src} {EDGE_LABELS[edge][0]} {dst}")


# An ancestor cannot close while a descendant is open, so a descendant that
# waits on it would wait forever. beads refuses this link for the same reason.
_ANCESTOR_BLOCK = ("{child} cannot wait on its own ancestor {ancestor}: the ancestor cannot close "
                   "until its descendants do")
# The parent-child link already makes a parent wait for its descendants, so
# an explicit block from a parent onto its own descendant is refused too.
_DESCENDANT_BLOCK = ("{parent} cannot wait on its own descendant {descendant}: a parent already "
                     "waits for its children to close")


def cmd_comment(args, out: Out, g: Graph, cfg: dict):
    slug = new_id("c", 10)
    g.mutate("comment", {"slug": slug, "id": args.id, "body": args.text, "author": g.actor})
    out.emit({"comment": slug, "id": args.id}, f"commented on {args.id}")


def cmd_search(args, out: Out, g: Graph, cfg: dict):
    rows = g.query("search", {"q": args.query})
    out.emit(rows, lambda: "\n".join(issue_line(r) for r in rows) or "no matches")


def cmd_similar(args, out: Out, g: Graph, cfg: dict):
    if not g.embed:
        raise ObError("similar needs embeddings: `ob init --embed`, and an embedding provider (see README)")
    text = args.text
    if re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*-[a-z0-9.]+$", text):
        found = g.query("show", {"id": text})
        if found:
            text = found[0]["i"]["title"]
    rows = g.query("similar", {"q": embedding_query("Issue", "title", text)})
    out.emit(rows, lambda: "\n".join(f"{r['distance']:.3f}  {issue_line(r)}" for r in rows))


def cmd_remember(args, out: Out, g: Graph, cfg: dict):
    key = args.key or slugify(args.text)
    params = {"slug": key, "body": args.text, "who": g.actor}
    if g.embed:
        row = {"type": "Memory", "data": {"slug": key, "body": args.text, "created_by": g.actor,
                                          "updated_at": iso(now())}}
        rows = [row] + ([{"edge": "MemoryAbout", "from": key, "to": args.about}] if args.about else [])
        g.load(rows, "merge")
    elif args.about:
        g.mutate("remember_about", {**params, "id": args.about})
    else:
        g.mutate("remember", params)
    out.emit({"key": key}, f"remembered {key}")


def cmd_recall(args, out: Out, g: Graph, cfg: dict):
    if not args.query:
        rows = g.query("memories")
    elif g.embed and args.semantic:
        rows = g.query("recall_semantic", {"q": embedding_query("Memory", "body", args.query)})
    else:
        rows = g.query("recall", {"q": args.query})
    out.emit(rows, lambda: "\n".join(f"{r['slug']}: {r['body']}" for r in rows) or "no memories")


def cmd_forget(args, out: Out, g: Graph, cfg: dict):
    receipt = g.mutate("forget", {"slug": args.key})
    out.emit({"forgot": args.key, "affected": receipt.get("affected_nodes", 0)},
             f"forgot {args.key}" if receipt.get("affected_nodes") else f"no memory {args.key}")


def cmd_stats(args, out: Out, g: Graph, cfg: dict):
    counts, ready, unblocked = g.parallel([("stats", {}), ("ready_count", {}), ("unblocked_open_count", {})])
    by_status = {r["status"]: r["issues"] for r in counts}
    data = {"by_status": by_status, "ready": ready[0]["ready"],
            "blocked": by_status.get("open", 0) - unblocked[0]["unblocked"]}
    out.emit(data, lambda: "  ".join(f"{k}: {v}" for k, v in by_status.items())
             + f"\nready: {data['ready']}  blocked: {data['blocked']}")


def cmd_history(args, out: Out, g: Graph, cfg: dict):
    """Who changed an issue, when, and how, from the commit history itself."""
    events = []
    token = None
    while True:
        page = g.changes_page(token)
        for block in page.get("blocks", []):
            cause = block.get("cause", {})
            for change in block.get("changes", []):
                ends = change.get("after", change.get("before", {})).get("endpoints") or {}
                if change.get("id") != args.id and args.id not in (ends.get("from"), ends.get("to")):
                    continue
                before = (change.get("before") or {}).get("properties") or {}
                after = (change.get("after") or {}).get("properties") or {}
                diff = {k: [before.get(k), after.get(k)] for k in sorted(set(before) | set(after))
                        if before.get(k) != after.get(k) and k not in ("updated_at", "embedding")}
                events.append({
                    "commit": cause.get("graph_commit_id"),
                    "actor": cause.get("actor") or cause.get("actor_id"),
                    "at": iso(dt.datetime.fromtimestamp(cause.get("authored_at", 0) / 1e6, dt.timezone.utc)),
                    "type": change["type"]["name"], "op": change["op"],
                    "endpoints": ends or None, "changed": diff,
                })
        token = page.get("next_page_token")
        if not token:
            break

    def human():
        lines = []
        for e in events:
            what = e["type"] + " " + e["op"]
            if e["endpoints"]:
                what += f" {e['endpoints']['from']} -> {e['endpoints']['to']}"
            detail = ", ".join(f"{k}: {v[0]!r} -> {v[1]!r}" for k, v in e["changed"].items()
                               if e["op"] == "update")
            lines.append(f"{e['at']}  {e['actor'] or '-':<24} {what}" + (f"  ({detail})" if detail else ""))
        return "\n".join(lines) or f"no history for {args.id}"

    out.emit(events, human)


def cmd_prime(args, out: Out, g: Graph, cfg: dict):
    mine, ready, total, memories = g.parallel(
        [("assigned", {"who": g.actor}), ("ready", {}), ("ready_count", {}), ("memories", {})])
    data = {"actor": g.actor, "in_progress": mine, "ready": ready[:10], "ready_total": total[0]["ready"],
            "memories": memories}

    def human():
        lines = [ONBOARD.strip(), "", f"You are {g.actor}."]
        if mine:
            lines += ["", "In progress (yours):"] + ["  " + issue_line(r, "in_progress") for r in mine]
        lines += ["", f"Ready ({data['ready_total']}):"] + ["  " + issue_line(r) for r in ready[:10]]
        if memories:
            lines += ["", "Project memories:"] + [f"  - {m['slug']}: {m['body']}" for m in memories]
        return "\n".join(lines)

    out.emit(data, human)


ONBOARD = """
This project tracks work with ob (beads on OmniGraph). Do not keep markdown TODO lists.
- `ob ready` lists claimable work; `ob ready --claim` takes the top item atomically.
- `ob show <id>` shows an issue, its links, comments and memories.
- `ob create "title" -t bug|task|feature|epic -p 0-4 [--deps <id>] [--parent <id>]` files work;
  file anything you discover with `--discovered-from <current id>`.
- `ob dep add <issue> <blocker>` orders work; `ob close <id> --reason "..."` finishes it.
- `ob remember "insight"` stores a durable project fact that `ob prime` shows every session.
- Add `--json` to any command for machine-readable output.
"""


def cmd_onboard(args, out: Out):
    out.emit({"instructions": ONBOARD.strip()}, ONBOARD.strip())


# -- bd interchange ---------------------------------------------------------

BD_STATUS = {"open": "open", "in_progress": "in_progress", "hooked": "in_progress", "blocked": "open",
             "deferred": "deferred", "closed": "closed", "pinned": "open"}


def bd_to_rows(path: Path) -> tuple[list[dict], dict]:
    nodes, edges, skipped = [], [], {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        bead = json.loads(line)
        kind = bead.get("issue_type") or "task"
        labels = list(bead.get("labels") or [])
        if kind not in KINDS:
            labels.append(f"bd-type:{kind}")
            kind = "task"
        status = bead.get("status") or "open"
        if status == "blocked":
            labels.append("bd-status:blocked")
        created = bead.get("created_at") or iso(now())
        data = {
            "slug": bead["id"], "title": bead.get("title") or bead["id"], "kind": kind,
            "status": BD_STATUS.get(status, "open"),
            "priority": min(max(int(bead.get("priority", 2)), 0), 4),
            "created_at": created, "updated_at": bead.get("updated_at") or created,
        }
        mapping = {"description": "description", "design": "design", "acceptance_criteria": "acceptance",
                   "notes": "notes", "assignee": "assignee", "created_by": "created_by",
                   "started_at": "started_at", "closed_at": "closed_at", "close_reason": "close_reason",
                   "defer_until": "defer_until", "due_at": "due_at", "external_ref": "external_ref"}
        for src, dst in mapping.items():
            if bead.get(src):
                data[dst] = bead[src]
        if bead.get("metadata"):
            data["metadata"] = json.dumps(bead["metadata"]) if not isinstance(bead["metadata"], str) else bead["metadata"]
        if labels:
            data["labels"] = labels
        nodes.append({"type": "Issue", "data": data})
        for dep in bead.get("dependencies") or []:
            dtype = dep.get("type", "blocks")
            target = dep.get("depends_on_id")
            _, edge = LINK_TYPES.get(dtype, (None, None))
            if edge is None or not target or str(target).startswith("external:"):
                skipped[dtype] = skipped.get(dtype, 0) + 1
                continue
            edges.append({"edge": edge, "from": bead["id"], "to": target})
    return nodes + edges, skipped


def cmd_import(args, out: Out, g: Graph, cfg: dict):
    rows, skipped = bd_to_rows(Path(args.file))
    nodes = [r for r in rows if "type" in r]
    edges = [r for r in rows if "edge" in r]
    parent = {e["from"]: e["to"] for e in edges if e["edge"] == "ChildOf"}

    def ancestors(slug: str) -> set[str]:
        seen: set[str] = set()
        while slug in parent and parent[slug] not in seen:
            slug = parent[slug]
            seen.add(slug)
        return seen

    kept = []
    for e in edges:
        if e["edge"] == "BlockedBy" and e["to"] in ancestors(e["from"]):
            skipped["blocks-on-ancestor"] = skipped.get("blocks-on-ancestor", 0) + 1
            continue
        if e["edge"] == "BlockedBy" and e["from"] in ancestors(e["to"]):
            skipped["blocks-on-descendant"] = skipped.get("blocks-on-descendant", 0) + 1
            continue
        kept.append(e)
    edges = kept
    # One commit per chunk. A load is bounded (8,192 entities and 32 MiB of
    # Arrow per type); a nullable Vector(1536) still costs ~6 KiB per row, so
    # start at 2,000 rows and halve a chunk the engine refuses as too large.
    commits = 0

    def load_chunks(rows: list[dict], size: int):
        nonlocal commits
        i = 0
        while i < len(rows):
            chunk = rows[i:i + size]
            try:
                g.load(chunk, "merge")
            except ObError as exc:
                if "resource limit" not in str(exc) or size == 1:
                    raise
                size //= 2
                continue
            commits += 1
            i += len(chunk)

    load_chunks(nodes, 2000)
    load_chunks(edges, 8000)
    # Build the declared indexes now: until a table's first full-text index
    # exists, unindexed full-text search matches case-sensitively.
    if g.store:
        g.raw(["optimize", "--store", g.store, "--json"])
    out.emit({"issues": len(nodes), "links": len(edges), "skipped_links": skipped, "commits": commits},
             f"imported {len(nodes)} issues and {len(edges)} links in {commits} commit(s)"
             + (f"; skipped {skipped}" if skipped else ""))


def cmd_export(args, out: Out, g: Graph, cfg: dict):
    issues, links = g.parallel([("list", {"statuses": STATUSES}), ("all_links", {})])
    full = g.query("show_many", {"ids": [r["slug"] for r in issues]}) if issues else []
    reverse = {edge: name for name, (_, edge) in LINK_TYPES.items()
               if name in ("blocks", "parent-child", "related", "discovered-from", "duplicates", "supersedes")}
    outgoing: dict[str, list[dict]] = {}
    for link in links:
        outgoing.setdefault(link["src"], []).append({"slug": link["dst"], "link": link["link"]})
    beads = []
    for row in full:
        issue = row["i"]
        outs = outgoing.get(issue["slug"], [])
        beads.append({
            "id": issue["slug"], "title": issue["title"], "description": issue.get("description"),
            "design": issue.get("design"), "acceptance_criteria": issue.get("acceptance"),
            "notes": issue.get("notes"), "status": issue["status"], "priority": issue["priority"],
            "issue_type": issue["kind"], "assignee": issue.get("assignee"), "labels": issue.get("labels"),
            "created_at": issue.get("created_at"), "created_by": issue.get("created_by"),
            "updated_at": issue.get("updated_at"), "closed_at": issue.get("closed_at"),
            "close_reason": issue.get("close_reason"), "started_at": issue.get("started_at"),
            "defer_until": issue.get("defer_until"), "due_at": issue.get("due_at"),
            "external_ref": issue.get("external_ref"),
            "metadata": json.loads(issue["metadata"]) if issue.get("metadata") else None,
            "dependencies": [{"issue_id": issue["slug"], "depends_on_id": o["slug"], "type": reverse[o["link"]]}
                             for o in outs],
        })
    # OmniGraph prints DateTime in UTC without a zone; bd requires RFC 3339.
    for bead in beads:
        for key in ("created_at", "updated_at", "closed_at", "started_at", "defer_until", "due_at"):
            if bead.get(key):
                bead[key] = as_param_time(bead[key])
    text = "\n".join(json.dumps({k: v for k, v in b.items() if v not in (None, [])}) for b in beads)
    if args.output:
        Path(args.output).write_text(text + "\n")
        print(f"exported {len(beads)} issues to {args.output}", file=sys.stderr)
    else:
        print(text)


def cmd_branch(args, out: Out, g: Graph, cfg: dict):
    if args.action != "list" and not args.name:
        raise ObError(f"branch {args.action} needs a name")
    data = g.branch_op(args.action, args.name, args.base)
    out.emit(data, json.dumps(data, indent=2))


def cmd_maintain(args, out: Out, g: Graph, cfg: dict):
    if g.server:
        raise ObError("maintenance runs against storage; run it where the cluster storage is reachable")
    report = {"optimize": g.raw(["optimize", "--store", g.store, "--json"])}
    if args.cleanup:
        report["cleanup"] = g.raw(["cleanup", "--store", g.store, "--keep", str(args.keep),
                                   "--confirm", "--json"])
    out.emit(report, "optimized" + (f"; kept the newest {args.keep} commits" if args.cleanup else ""))


# ---------------------------------------------------------------------------
# Entry point


def build_parser() -> argparse.ArgumentParser:
    # Colored help costs a 30 ms import on every run; ob is called in tight agent loops.
    plain = {"color": False} if sys.version_info >= (3, 14) else {}
    p = argparse.ArgumentParser(prog="ob", description="Beads on OmniGraph: issue tracking for coding agents.",
                                **plain)
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--dir", help="ob directory (default: nearest .ob/, or $OB_DIR)")
    p.add_argument("--as", dest="actor", help="actor for this command (default: $OB_ACTOR, config, git email)")
    p.add_argument("--branch", help="read and write a graph branch instead of main")
    subparsers = p.add_subparsers(dest="command", required=True)

    class _Sub:  # every subcommand parser opts out of color too
        @staticmethod
        def add_parser(name, **kw):
            return subparsers.add_parser(name, **plain, **kw)

    sub = _Sub()

    s = sub.add_parser("init", help="create a local graph, or point at a served one")
    s.add_argument("--prefix", default="ob")
    s.add_argument("--store", help="graph URI (default .ob/graph.omni); file://, s3:// or az://")
    s.add_argument("--server", help="omnigraph server name or URL (served mode)")
    s.add_argument("--graph", default="beads", help="graph id on the server")
    s.add_argument("--embed", action="store_true", help="store title and memory embeddings")
    s.set_defaults(fn=cmd_init, needs_graph=False)

    s = sub.add_parser("onboard", help="print agent instructions for AGENTS.md")
    s.set_defaults(fn=cmd_onboard, needs_graph=False)

    s = sub.add_parser("prime", help="session context: your work, ready work, memories")
    s.set_defaults(fn=cmd_prime)

    s = sub.add_parser("create", help="file an issue (one commit, links included)")
    s.add_argument("title")
    s.add_argument("-t", "--type", default="task", choices=KINDS)
    s.add_argument("-p", "--priority", type=int, default=2, choices=range(5))
    s.add_argument("-d", "--description")
    s.add_argument("--design")
    s.add_argument("--acceptance")
    s.add_argument("--notes")
    s.add_argument("-a", "--assignee")
    s.add_argument("-l", "--labels", action="append")
    s.add_argument("--deps", action="append", help="ids this waits on; type:id for other links")
    s.add_argument("--parent")
    s.add_argument("--discovered-from")
    s.add_argument("--defer", help="hide from ready until (2h, 3d, ISO time)")
    s.add_argument("--due")
    s.add_argument("--external-ref")
    s.add_argument("--metadata", help="JSON object")
    s.add_argument("--id", help="explicit id")
    s.set_defaults(fn=cmd_create)

    s = sub.add_parser("show", help="an issue with its links, comments and memories")
    s.add_argument("ids", nargs="+")
    s.set_defaults(fn=cmd_show)

    def filters(sp):
        sp.add_argument("-t", "--type", action="append")
        sp.add_argument("--exclude-type", action="append")
        sp.add_argument("-l", "--label", action="append")
        sp.add_argument("-a", "--assignee", help="name, 'me' or 'none'")
        sp.add_argument("--priority-max", type=int)
        sp.add_argument("-n", "--limit", type=int, default=50)

    s = sub.add_parser("ready", help="claimable work")
    filters(s)
    s.add_argument("--claim", action="store_true", help="atomically claim the first match")
    s.add_argument("--lease", help="claim lease, e.g. 2h")
    s.set_defaults(fn=cmd_ready)

    s = sub.add_parser("list", help="issues by status")
    filters(s)
    s.add_argument("-s", "--status", action="append")
    s.add_argument("--all", action="store_true", help="include closed")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("blocked", help="issues waiting on open work, and why")
    s.set_defaults(fn=cmd_blocked)

    s = sub.add_parser("update", help="edit fields (per-issue compare-and-swap)")
    s.add_argument("id")
    for flag in ("title", "description", "design", "acceptance", "notes", "assignee", "external_ref",
                 "metadata"):
        s.add_argument(f"--{flag.replace('_', '-')}")
    s.add_argument("-t", "--type", choices=KINDS)
    s.add_argument("-s", "--status", choices=STATUSES)
    s.add_argument("-p", "--priority", type=int, choices=range(5))
    s.add_argument("--defer")
    s.add_argument("--due")
    s.add_argument("--add-label", action="append")
    s.add_argument("--remove-label", action="append")
    s.add_argument("--claim", action="store_true")
    s.add_argument("--lease")
    s.add_argument("--reason")
    s.set_defaults(fn=cmd_update)

    s = sub.add_parser("claim", help="atomically take an open issue")
    s.add_argument("id")
    s.add_argument("--lease", help="e.g. 2h; `ob reclaim` reopens it after expiry")
    s.set_defaults(fn=cmd_claim)

    s = sub.add_parser("release", help="give back an issue you hold")
    s.add_argument("id")
    s.set_defaults(fn=cmd_release)

    s = sub.add_parser("renew", help="extend your lease on an issue")
    s.add_argument("id")
    s.add_argument("--lease", default="2h")
    s.set_defaults(fn=cmd_renew)

    s = sub.add_parser("reclaim", help="reopen issues whose lease expired")
    s.set_defaults(fn=cmd_reclaim)

    s = sub.add_parser("close", help="finish issues (one commit)")
    s.add_argument("ids", nargs="+")
    s.add_argument("-r", "--reason")
    s.add_argument("-f", "--force", action="store_true", help="close despite open blockers or children")
    s.set_defaults(fn=cmd_close)

    s = sub.add_parser("reopen")
    s.add_argument("ids", nargs="+")
    s.set_defaults(fn=cmd_reopen)

    s = sub.add_parser("defer", help="put issues on ice")
    s.add_argument("ids", nargs="+")
    s.add_argument("--until")
    s.set_defaults(fn=cmd_defer)

    s = sub.add_parser("undefer")
    s.add_argument("ids", nargs="+")
    s.set_defaults(fn=cmd_undefer)

    s = sub.add_parser("label", help="add or remove labels")
    s.add_argument("action", choices=["add", "rm"])
    s.add_argument("id")
    s.add_argument("labels", nargs="+")
    s.set_defaults(fn=cmd_label)

    s = sub.add_parser("dep", help="link issues: `dep add A B` means A waits on B")
    s.add_argument("action", choices=["add", "rm", "list", "tree"])
    s.add_argument("issue")
    s.add_argument("target", nargs="?")
    s.add_argument("--type", default="blocks", help=", ".join(sorted(LINK_TYPES)))
    s.set_defaults(fn=cmd_dep)

    s = sub.add_parser("comment", help="comment on an issue")
    s.add_argument("id")
    s.add_argument("text")
    s.set_defaults(fn=cmd_comment)

    s = sub.add_parser("search", help="full-text search")
    s.add_argument("query")
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("similar", help="semantically similar issues (needs embeddings)")
    s.add_argument("text", help="an issue id or free text")
    s.set_defaults(fn=cmd_similar)

    s = sub.add_parser("remember", help="store a durable project memory")
    s.add_argument("text")
    s.add_argument("--key")
    s.add_argument("--about", help="link the memory to an issue")
    s.set_defaults(fn=cmd_remember)

    s = sub.add_parser("recall", help="list or search memories")
    s.add_argument("query", nargs="?")
    s.add_argument("--semantic", action="store_true", help="rank by meaning (needs embeddings)")
    s.set_defaults(fn=cmd_recall)
    s = sub.add_parser("memories", help="list memories")
    s.set_defaults(fn=cmd_recall, query=None, semantic=False)

    s = sub.add_parser("forget", help="delete a memory")
    s.add_argument("key")
    s.set_defaults(fn=cmd_forget)

    s = sub.add_parser("history", help="who changed an issue, from commit history")
    s.add_argument("id")
    s.set_defaults(fn=cmd_history)

    s = sub.add_parser("stats", help="counts by status, ready and blocked")
    s.set_defaults(fn=cmd_stats)

    s = sub.add_parser("import", help="import a bd (beads) JSONL export")
    s.add_argument("file")
    s.set_defaults(fn=cmd_import)

    s = sub.add_parser("export", help="export issues as bd-compatible JSONL")
    s.add_argument("-o", "--output")
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("branch", help="plan on a branch, merge after review")
    s.add_argument("action", choices=["list", "create", "merge", "delete"])
    s.add_argument("name", nargs="?")
    s.add_argument("--base", default="main", help="fork from / merge into")
    s.set_defaults(fn=cmd_branch)

    s = sub.add_parser("maintain", help="compact storage; --cleanup also drops old versions")
    s.add_argument("--cleanup", action="store_true")
    s.add_argument("--keep", type=int, default=100)
    s.set_defaults(fn=cmd_maintain)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = Out(args.json)
    try:
        if not getattr(args, "needs_graph", True):
            args.fn(args, out)
            return 0
        cfg_dir, cfg = load_config(args)
        g = Graph(cfg, cfg_dir, args.actor or default_actor(cfg), args.branch)
        args.fn(args, out, g, cfg)
        return 0
    except ObError as exc:
        if args.json:
            print(json.dumps({"error": str(exc), **({"detail": exc.payload} if exc.payload else {})}, indent=2))
        else:
            print(f"ob: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
