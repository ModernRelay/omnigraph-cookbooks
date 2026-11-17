#!/usr/bin/env python3
"""The agent benchmark at scale, on two VS Code releases; see scale-design.md.

    python3 code-graph/bench/scale.py fetch       # both releases as commits of one git repository
    python3 code-graph/bench/scale.py build       # index, convert, load into Omnigraph; compiler references
    python3 code-graph/bench/scale.py questions   # pick the questions by rule, write their keys, check them
    python3 code-graph/bench/agent.py --suite vscode setup|run|score ...

Everything is written under work/scale/, which git ignores; a step whose output
exists is skipped, so delete an output to rebuild it. The questions and their
keys go to scale-questions.json. Needs curl, git, Node.js 22.23.4 or later,
the locked indexer (`npm ci` in code-graph/sources/indexer), the 0.14.0
omnigraph CLI (OMNIGRAPH_BIN) and about 10 GB of memory per step.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
COOKBOOK = BENCH.parent
WORK = BENCH / "work" / "scale"
sys.path.insert(0, str(BENCH))
from common import load_implements, load_reference  # noqa: E402

REPO_URL = "https://github.com/microsoft/vscode.git"
TARBALL = "https://codeload.github.com/microsoft/vscode/tar.gz/refs/tags/{tag}"
PREVIOUS, CURRENT = RELEASES = ("1.145.0", "1.146.0")
PROJECT = "src/tsconfig.json"
SCOPE = "src/vs/"
QUESTIONS = BENCH / "scale-questions.json"
SEED = 20261117
PER_FAMILY = 4
INDEXER = COOKBOOK / "sources" / "indexer" / "node_modules" / ".bin" / "scip-typescript"
NODE_ENV = {**os.environ, "NODE_OPTIONS": "--max-old-space-size=32768"}
ANSWER_FORMAT = (
    "End your reply with one line that starts with ANSWER: followed by a JSON array of strings. "
    "Name each definition as path:Name for a top-level function, class, interface or constant, and as "
    "path:Class.member for a member of a class, with the path relative to the repository root, for example "
    "src/vs/platform/files/common/fileService.ts:FileService.readFile. For code that belongs to no named "
    "function, method or class, give the file path alone. Leave out test code: files under a test/ "
    "directory and files whose names end in .test.ts. Do not change any file.")


def sh(*args, cwd=None, env=None) -> str:
    proc = subprocess.run([str(a) for a in args], cwd=cwd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"{' '.join(map(str, args))[:200]} failed:\n{(proc.stderr or proc.stdout).strip()[-3000:]}")
    return proc.stdout.strip()


# The fixture repository's git reads no global or system configuration, so an
# LFS filter or line-ending setting on one machine cannot change its commits.
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def git(*args, env=None) -> str:
    return sh("git", f"--git-dir={WORK / 'repo.git'}", *args, env={**(env or os.environ), **GIT_ENV})


def timed(log: dict, name: str, fn):
    start = time.monotonic()
    fn()
    log[name] = round(time.monotonic() - start, 1)


# --- fetch -------------------------------------------------------------------

def fetch():
    """Both releases as two commits of one bare repository, tagged by release,
    so every arm's agent can read the previous release with git."""
    WORK.mkdir(parents=True, exist_ok=True)
    repo = WORK / "repo.git"
    if not repo.exists():
        sh("git", "init", "-q", "--bare", "-b", "main", repo, env={**os.environ, **GIT_ENV})
    parent = None
    for day, tag in enumerate(RELEASES, start=1):
        if git("tag", "--list", tag):
            parent = git("rev-parse", f"{tag}^{{commit}}")
            continue
        archive = WORK / f"vscode-{tag}.tar.gz"
        if not archive.exists() or subprocess.run(["gzip", "-t", archive]).returncode != 0:
            print(f"downloading {tag}", flush=True)
            for _ in range(5):
                if subprocess.run(["curl", "-sSL", "--retry", "5", "--retry-all-errors", "-C", "-", "-o", archive,
                                   TARBALL.format(tag=tag)]).returncode == 0:
                    break
            sh("gzip", "-t", archive)
        tree_dir = WORK / "trees" / tag
        shutil.rmtree(tree_dir, ignore_errors=True)
        tree_dir.mkdir(parents=True)
        sh("tar", "-xzf", archive, "-C", tree_dir, "--strip-components", "1")
        # A fixture commit of the release's source under a fixed identity and
        # date, so the same tarballs make the same commits on every machine.
        env = {**os.environ, "GIT_INDEX_FILE": str(WORK / f"index-{tag}"),
               "GIT_AUTHOR_NAME": "code-graph bench", "GIT_AUTHOR_EMAIL": "bench@localhost",
               "GIT_COMMITTER_NAME": "code-graph bench", "GIT_COMMITTER_EMAIL": "bench@localhost",
               "GIT_AUTHOR_DATE": f"2026-11-0{day}T00:00:00Z", "GIT_COMMITTER_DATE": f"2026-11-0{day}T00:00:00Z"}
        git(f"--work-tree={tree_dir}", "add", "-A", "-f", env=env)
        tree = git("write-tree", env=env)
        commit = git("commit-tree", tree, "--no-gpg-sign", "-m", f"VS Code {tag}",
                     *(["-p", parent] if parent else []), env=env)
        git("update-ref", "refs/heads/main", commit)
        git("tag", tag, commit)
        (WORK / f"index-{tag}").unlink()
        shutil.rmtree(tree_dir)
        parent = commit
        print(f"{tag}: {commit}", flush=True)
    shutil.rmtree(WORK / "trees", ignore_errors=True)


# --- build -------------------------------------------------------------------

def checkout(tag: str) -> Path:
    path = WORK / "checkouts" / tag
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        git("worktree", "add", "--quiet", "--detach", path, tag)
    return path


def build():
    """Index and convert each release, run the compiler reference on each, and
    load both into one Omnigraph graph: the current release on main, the
    previous on branch v<previous>."""
    times = json.loads((WORK / "build.json").read_text()) if (WORK / "build.json").exists() else {}
    for tag in RELEASES:
        co = checkout(tag)
        sha = git("rev-parse", f"{tag}^{{commit}}")
        index, rows, ref = WORK / f"index-{tag}.scip", WORK / f"graph-{tag}.jsonl", WORK / f"ref-{tag}.json"
        if not index.exists():
            timed(times, f"index {tag}", lambda: sh(INDEXER, "index", PROJECT, "--no-progress-bar",
                                                    "--output", index, cwd=co, env=NODE_ENV))
        if not rows.exists():
            timed(times, f"convert {tag}", lambda: sh(
                sys.executable, "-I", COOKBOOK / "sources" / "build_seed.py", "--index", index, "--checkout", co,
                "--revision", sha, "--repository", REPO_URL, "--out", rows))
        if not ref.exists():
            timed(times, f"reference {tag}", lambda: sh("node", BENCH / "reference.mjs", co, ref, "--project",
                                                        PROJECT, "--scope", SCOPE, env=NODE_ENV))
    graph, done = WORK / "graph.omni", WORK / "graph.omni.done"
    if not done.exists():
        # A graph records its own absolute path, so it cannot be built aside
        # and renamed; a graph without the marker is a failed build.
        partial = graph
        shutil.rmtree(partial, ignore_errors=True)
        og = os.environ.get("OMNIGRAPH_BIN") or shutil.which("omnigraph")
        (WORK / "og").mkdir(exist_ok=True)
        env = {**os.environ, "OMNIGRAPH_HOME": str(WORK / "og"), "CG_TARGET": str(partial), "CG_OMNIGRAPH": og}
        cg = [sys.executable, COOKBOOK / "client" / "cg"]
        sh(og, "init", "--schema", COOKBOOK / "schema.pg", partial, env=env)
        timed(times, f"load {PREVIOUS}", lambda: sh(*cg, "load", WORK / f"graph-{PREVIOUS}.jsonl", "--branch", "main",
                                                    env=env))
        sh(og, "branch", "create", f"v{PREVIOUS}", "--from", "main", "--target", partial, "--json", env=env)
        timed(times, f"load {CURRENT}", lambda: sh(*cg, "load", WORK / f"graph-{CURRENT}.jsonl", "--branch", "main",
                                                   env=env))
        done.write_text(json.dumps({"main": CURRENT, f"v{PREVIOUS}": PREVIOUS}) + "\n")
    (WORK / "build.json").write_text(json.dumps(times, indent=2) + "\n")
    print(json.dumps(times, indent=2))


# --- questions ---------------------------------------------------------------

def is_test(path: str) -> bool:
    return "/test/" in path or bool(re.search(r"\.test\.tsx?$", path))


def owner_lift(nodes: dict):
    """The agent benchmark's answer granularity (agent.py owner_lift)."""
    import agent  # noqa: PLC0415
    return agent.owner_lift(nodes)


class Release:
    """One release's reference: call edges by callee, lifted to answer granularity."""

    def __init__(self, tag: str):
        self.nodes, edges = load_reference(WORK / f"ref-{tag}.json")
        self.implementers = load_implements(WORK / f"ref-{tag}.json")
        self.lift = owner_lift(self.nodes)
        self.callers = collections.defaultdict(set)
        for (a, b), e in edges.items():
            if e["call"] and a in self.nodes and not is_test(self.nodes[a]["path"]):
                self.callers[b].add(a)
        live = [n for n in self.nodes.values() if n["kind"] != "module" and not is_test(n["path"])]
        self.names = collections.Counter(n["name"] for n in live)

    def direct(self, target: str) -> set[str]:
        return {self.lift(a) for a in self.callers.get(target, ())} - {self.lift(target)}

    def transitive(self, target: str, cap: int) -> tuple[set[str], int, set[str]]:
        """Every definition reaching the target through calls, the deepest hop,
        and the chain's own definitions; stops once more than `cap` are found."""
        seen, frontier, depth, found = {target}, [target], 0, set()
        while frontier and len(found) <= cap:
            nxt = []
            for x in frontier:
                for c in self.callers.get(x, ()):
                    if c not in seen:
                        seen.add(c)
                        nxt.append(c)
            if not nxt:
                break
            depth += 1
            found |= {self.lift(c) for c in nxt}
            frontier = nxt
        return found - {self.lift(target)}, depth, seen

    def bodies(self, member: str) -> set[str]:
        """Methods with a body that implement or override the member, at any depth."""
        out, todo = set(), [member]
        while todo:
            for m in self.implementers.get(todo.pop(), ()):
                if m not in out:
                    out.add(m)
                    todo.append(m)
        return {m for m in out if self.nodes[m].get("digest")}


def describe(nodes: dict, ident: str) -> str:
    """How a question names a definition: `the readFile method of IFileService,
    the interface in src/vs/...`, or `parse, defined in src/...`."""
    n = nodes[ident]
    tail = ident.split(":", 1)[1]
    if "." in tail:
        container, member = tail.rsplit(".", 1)
        # VS Code declares a service as a constant and an interface of one
        # name, so anything but a class or type alias reads as an interface.
        kind = nodes.get(f"{n['path']}:{container}", {}).get("kind")
        kind = {"class": "class", "type_alias": "type"}.get(kind, "interface")
        return f"the {member} method of {container}, the {kind} in {n['path']}"
    return f"{tail}, defined in {n['path']}"


class Source:
    """The current release's source outside tests, for checks and grep counts."""

    def __init__(self, root: Path):
        self.files = {}
        for path in (root / "src").rglob("*.ts"):
            rel = path.relative_to(root).as_posix()
            if not is_test(rel) and not rel.endswith(".d.ts"):
                self.files[rel] = path.read_text(errors="replace").split("\n")

    def lines(self, pattern: str) -> int:
        rx = re.compile(pattern)
        return sum(1 for text in self.files.values() for line in text if rx.search(line))

    def span(self, nodes: dict, ident: str) -> str:
        n = nodes.get(ident)
        text = self.files.get(n["path"] if n else ident, [])
        return "\n".join(text[n["line"] - 1:n["end_line"]] if n and ":" in ident else text)


def candidates(cur: Release, prev: Release) -> dict[str, list[dict]]:
    """Every question each family's rule admits, before the source check."""
    fam = collections.defaultdict(list)
    for ident, n in sorted(cur.nodes.items()):
        if is_test(n["path"]) or ":" not in ident:
            continue
        name, kind, callable_ = n["name"], n["kind"], n["callable"]
        if callable_ and kind in ("method", "function", "constant"):
            direct = cur.direct(ident)
            shared = cur.names[name]
            if kind == "method" and shared >= 50 and 5 <= len(direct) <= 30:
                fam["shared-name"].append({"target": ident, "answer": direct, "pattern": rf"\b{re.escape(name)}\s*\("})
            if shared == 1 and 3 <= len(direct) <= 10:
                fam["control"].append({"target": ident, "answer": direct, "pattern": rf"\b{re.escape(name)}\s*\("})
            if ident in prev.nodes and len(direct) <= 60:
                gained = direct - prev.direct(ident)
                if 3 <= len(gained) <= 15:
                    fam["release"].append({"target": ident, "answer": gained,
                                           "pattern": rf"\b{re.escape(name)}\s*\("})
            if 3 <= len(direct):
                reached, depth, chain = cur.transitive(ident, cap=40)
                if 10 <= len(reached) <= 40 and depth >= 4:
                    fam["transitive"].append({"target": ident, "answer": reached, "depth": depth, "chain": chain,
                                              "pattern": rf"\b{re.escape(name)}\s*\("})
        if kind == "method" and cur.implementers.get(ident) and cur.names[name] >= 20:
            bodies = cur.bodies(ident)
            if 3 <= len(bodies) <= 15:
                fam["dispatch"].append({"target": ident, "answer": bodies, "pattern": rf"\b{re.escape(name)}\s*\("})
        if kind == "class":
            ctor = f"{ident}.constructor"
            made = cur.direct(ctor if ctor in cur.nodes else ident)
            if 10 <= len(made) <= 40:
                fam["construction"].append({"target": ident, "answer": made, "pattern": rf"\bnew\s+{re.escape(name)}\b"})
    return fam


QUESTION_TEXT = {
    "shared-name": "Which functions and methods in src/ call {what}?",
    "control": "Which functions and methods in src/ call {what}?",
    "transitive": "Which functions and methods in src/ call {what}, either directly or through any chain of other calls?",
    "dispatch": ("Which methods in src/ implement or override {what}, directly or through another class or "
                 "interface? List only methods that have a body."),
    "construction": "Which functions and methods in src/ construct a {name}, the class in {path}?",
    "release": (f"Which functions and methods in src/ call {{what}} in release {CURRENT} but did not call it in "
                f"release {PREVIOUS}? The repository is at {CURRENT}; the git tag {PREVIOUS} is the previous "
                "release."),
}


def check(src: Source, cur: Release, family: str, item: dict) -> list[str]:
    """Key entries the source does not support: each must contain the target's
    name inside its own text (a method of that name, for dispatch; for a chain,
    the name of the target or of another definition on the chain)."""
    name = cur.nodes[item["target"]]["name"]
    chain_names = {cur.nodes[c]["name"] for c in item.get("chain", ())}
    bad = []
    for ident in item["answer"]:
        text = src.span(cur.nodes, ident)
        if family == "transitive":
            ok = any(re.search(rf"\b{re.escape(n)}\b", text) for n in chain_names)
        elif family == "dispatch":
            ok = cur.nodes.get(ident, {}).get("name") == name and bool(text)
        elif family == "construction":
            ok = re.search(rf"\bnew\s+{re.escape(name)}\b", text) is not None
        else:
            ok = re.search(rf"\b{re.escape(name)}\b", text) is not None
        if not ok:
            bad.append(ident)
    return bad


def questions(per_family: int):
    cur, prev = Release(CURRENT), Release(PREVIOUS)
    src = Source(checkout(CURRENT))
    fam = candidates(cur, prev)
    picked, report = [], {}
    for order, family in enumerate(("shared-name", "dispatch", "transitive", "construction", "release", "control")):
        pool = fam.get(family, [])
        random.Random(SEED + order).shuffle(pool)
        kept, rejected = [], 0
        for item in pool:
            if len(kept) == per_family:
                break
            if check(src, cur, family, item):
                rejected += 1
                continue
            kept.append(item)
        report[family] = {"candidates": len(pool), "rejected_by_source_check": rejected, "picked": len(kept)}
        for i, item in enumerate(kept, start=1):
            n = cur.nodes[item["target"]]
            text = QUESTION_TEXT[family].format(what=describe(cur.nodes, item["target"]), name=n["name"],
                                                path=n["path"])
            picked.append({"id": f"{family}-{i}", "family": family, "question": text,
                           "answer": sorted(item["answer"]), "target": item["target"],
                           "grep_lines": src.lines(item["pattern"]), "grep_pattern": item["pattern"],
                           **({"depth": item["depth"]} if "depth" in item else {})})
    spec = {"suite": "vscode", "revision": git("rev-parse", f"{CURRENT}^{{commit}}"),
            "previous": git("rev-parse", f"{PREVIOUS}^{{commit}}"), "releases": list(RELEASES), "seed": SEED,
            "answer_format": ANSWER_FORMAT, "families": report, "questions": picked}
    QUESTIONS.write_text(json.dumps(spec, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    for q in picked:
        print(f"{q['id']:<15} {len(q['answer']):>3} answers  {q['grep_lines']:>6} grep lines  {q['question'][:110]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    sub.add_parser("build")
    p = sub.add_parser("questions")
    p.add_argument("--per-family", type=int, default=PER_FAMILY)
    args = ap.parse_args()
    if args.cmd == "fetch":
        fetch()
    elif args.cmd == "build":
        build()
    else:
        questions(args.per_family)


if __name__ == "__main__":
    main()
