#!/usr/bin/env python3
"""The agent benchmark at scale, on two VS Code releases; see scale-design.md.

    python3 code-graph/bench/scale.py fetch       # both releases as commits of one git repository
    python3 code-graph/bench/scale.py build       # index, convert, load into Omnigraph; compiler references
    python3 code-graph/bench/scale.py questions   # pick the questions by rule, write their keys, check them
    python3 code-graph/bench/scale.py regrade-pilot   # the pilot's answers against the current rules' keys
    python3 code-graph/bench/scale.py rekey       # the full run's questions with the current rules' keys
    python3 code-graph/bench/scale.py analyze     # per family, against no graph, and hypothesis 2
    python3 code-graph/bench/agent.py --suite vscode setup|run|score ...

Everything is written under work/scale/, which git ignores; a step whose output
exists is skipped, so delete an output to rebuild it. The questions and their
keys go to scale-questions.json, which now holds the set the full run asked:
`questions` would pick a different set under the current rules, so after the
run a rule change goes through `rekey`. Needs curl, git, Node.js 22.23.4 or later,
the locked indexer (`npm ci` in code-graph/sources/indexer), the 0.14.0
omnigraph CLI (OMNIGRAPH_BIN) and about 10 GB of memory per step.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import random
import os
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
SCOPE = "src/"  # what the questions ask about; the reference once covered src/vs/ only
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
        # member -> the members it implements or overrides, at every level
        self.overrides = collections.defaultdict(set)
        for target, members in self.implementers.items():
            for m in members:
                self.overrides[m].add(target)
        self.lift = owner_lift(self.nodes)
        self.callers = collections.defaultdict(set)
        for (a, b), e in edges.items():
            if e["call"] and a in self.nodes and not is_test(self.nodes[a]["path"]):
                self.callers[b].add(a)
        live = [n for n in self.nodes.values() if n["kind"] != "module" and not is_test(n["path"])]
        self.names = collections.Counter(n["name"] for n in live)

    def direct(self, target: str) -> set[str]:
        return {self.lift(a) for a in self.callers.get(target, ())} - {self.lift(target)}

    def runs_for(self, member: str) -> set[str]:
        """The member and every member a call to which can run it: those it
        implements or overrides, at every level."""
        out, todo = {member}, [member]
        while todo:
            for t in self.overrides.get(todo.pop(), ()):
                if t not in out:
                    out.add(t)
                    todo.append(t)
        return out

    def transitive(self, target: str, cap: int) -> tuple[set[str], int, set[str]]:
        """Every definition whose calls can run the target, directly or through
        a chain, the deepest hop, and the chain's own definitions; stops once
        more than `cap` are found. A call to an interface or base member can
        run each method that implements or overrides it, so a chain continues
        through it: VS Code calls its services through injected interfaces.
        Each hop is computed from whole sets, so the result does not depend on
        the order in which a set yields its members."""
        callees, callers, frontier, depth, found = set(), {target}, {target}, 0, set()
        while frontier and len(found) <= cap:
            called = set().union(*(self.runs_for(x) for x in frontier)) - callees
            callees |= called
            nxt = {c for t in called for c in self.callers.get(t, ())} - callers
            if not nxt:
                break
            callers |= nxt
            depth += 1
            found |= {self.lift(c) for c in nxt}
            frontier = nxt
        return found - {self.lift(target)}, depth, callees | callers

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
        # Ranked by a hash of the seed and the target, so changing a rule
        # moves only the candidates it admits or refuses, not the others.
        pool = sorted(fam.get(family, []),
                      key=lambda it: hashlib.sha256(f"{SEED}:{family}:{it['target']}".encode()).hexdigest())
        kept, rejected, ambiguous = [], 0, 0
        for item in pool:
            if len(kept) == per_family:
                break
            # A call to a method that implements another is also a call to that
            # one, so "which call X" would have two readings.
            if family in ("shared-name", "control", "release") and cur.overrides.get(item["target"]):
                ambiguous += 1
                continue
            if check(src, cur, family, item):
                rejected += 1
                continue
            kept.append(item)
        report[family] = {"candidates": len(pool), "rejected_as_overriding": ambiguous,
                          "rejected_by_source_check": rejected, "picked": len(kept)}
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


def key_for(cur: Release, prev: Release, family: str, target: str) -> set[str]:
    """The answer key the current rules give one question."""
    if family in ("shared-name", "control"):
        return cur.direct(target)
    if family == "release":
        return cur.direct(target) - prev.direct(target)
    if family == "transitive":
        return cur.transitive(target, cap=10**9)[0]
    if family == "dispatch":
        return cur.bodies(target)
    ctor = f"{target}.constructor"
    return cur.direct(ctor if ctor in cur.nodes else target)


FULL_RUN = "80e7ba1"  # the commit whose scale-questions.json the full run asked

# Entries the compiler reference cannot decide, each read in the source after
# the full run. `add` puts a definition in the key; `optional` makes one count
# neither way, where the question has two fair readings.
CORRECTIONS = {
    "shared-name-2": {
        "add": ["src/vs/platform/theme/common/tokenClassificationRegistry.ts:TokenStyle.equals"],
        "optional": ["src/vs/base/common/color.ts:Color.equals",
                     "src/vs/editor/browser/viewParts/overviewRuler/decorationsOverviewRuler.ts:Settings.equals"],
        "note": "Color declares a static and an instance method named equals, so the question has two readings. "
                "The static one, which calls the instance one, and Settings.equals, which calls only the static one, "
                "count neither way. TokenStyle.equals calls the instance method on a value of type any narrowed by "
                "instanceof, which the compiler reference does not resolve.",
    },
    "dispatch-1": {
        "optional": ["src/vs/editor/contrib/floatingMenu/browser/floatingMenu.ts",
                     "src/vs/editor/contrib/floatingMenu/browser/floatingMenu.ts:FloatingEditorToolbarWidget.constructor",
                     "src/vs/workbench/contrib/chat/browser/widget/input/chatInputPart.ts",
                     "src/vs/workbench/contrib/chat/browser/widget/input/chatInputPart.ts:ChatInputPart.render",
                     "src/vs/workbench/contrib/mcp/browser/mcpCommands.ts",
                     "src/vs/workbench/contrib/mcp/browser/mcpCommands.ts:MCPServerActionRendering.constructor",
                     "src/vs/workbench/contrib/sessions/browser/views/sessionsList.ts",
                     "src/vs/workbench/contrib/sessions/browser/views/sessionsList.ts:SessionItemRenderer.renderTemplate"],
        "note": "Four anonymous classes, `class extends MenuEntryActionViewItem` or a subclass inside a method, "
                "override render. The compiler reference does not model anonymous classes, and the answer format "
                "does not say whether to name one by its file or by the method around it, so both spellings count "
                "neither way.",
    },
    "dispatch-4": {
        "optional": ["src/vs/workbench/contrib/mcp/browser/mcpServerEditor.ts",
                     "src/vs/workbench/contrib/mcp/browser/mcpServerEditor.ts:McpServerEditor.createEditor"],
        "note": "An anonymous `class extends McpServerWidget` inside McpServerEditor.createEditor overrides render. "
                "The compiler reference does not model anonymous classes, and the answer format does not say whether "
                "to name one by its file or by the method around it, so both spellings count neither way.",
    },
    "transitive-4": {
        "drop": True,
        "note": "The chain to the target passes through `invokeFunction(resolveProtectedResourceAuthentication, ...)`, "
                "a call through dependency injection, which every session followed. Counting it, the chain then "
                "reaches BaseActionViewItem.render, and every call that can dispatch to an override of that, so "
                "44,328 definitions reach the target: the question has no answer to list, and it is left out of "
                "the scores.",
    },
    "release-3": {
        "optional": ["src/vs/workbench/contrib/sessionChanges/browser/changesView.ts:ChangesViewPane.getTreeSelection",
                     "src/vs/workbench/contrib/sessionChanges/browser/changesView.ts:ChangesViewPane.renderSidebarList"],
        "note": "changesView.ts moved from src/vs/sessions/contrib/changes/browser/ in 1.145.0 to "
                "src/vs/workbench/contrib/sessionChanges/browser/ in 1.146.0, and both methods called getSelection at "
                "the old path. By path they gained the call and by code they did not, so they count neither way.",
    },
}


def rekey():
    """Give the questions the full run asked the keys the current rules give,
    with CORRECTIONS applied; each keeps the key it was asked with as
    `asked_answer`. The sessions are then scored again from their transcripts."""
    ran = json.loads(subprocess.run(["git", "show", f"{FULL_RUN}:code-graph/bench/scale-questions.json"],
                                    cwd=BENCH, capture_output=True, text=True, check=True).stdout)
    cur, prev = Release(CURRENT), Release(PREVIOUS)
    questions = []
    for q in ran["questions"]:
        fix = CORRECTIONS.get(q["id"], {})
        optional = set(fix.get("optional", ()))
        key = (key_for(cur, prev, q["family"], q["target"]) | set(fix.get("add", ()))) - optional
        notes = [f"Asked with {len(q['answer'])} entries; the current rules give {len(key)}."] \
            if key != set(q["answer"]) else []
        notes += [fix["note"]] if fix else []
        if fix.get("drop"):
            # Too large to keep: the asked key stays, with the size the rules give.
            questions.append({**q, "asked_answer": q["answer"], "dropped": True, "current_rules_answers": len(key),
                              "note": fix["note"]})
            print(f"{q['id']:<15} {len(q['answer']):>3} -> {len(key):>3}  dropped")
            continue
        questions.append({**q, "answer": sorted(key), "asked_answer": q["answer"],
                          **({"optional": sorted(optional)} if optional else {}),
                          **({"note": " ".join(notes)} if notes else {})})
        print(f"{q['id']:<15} {len(q['answer']):>3} -> {len(key):>3}{'  optional ' + str(len(optional)) if optional else ''}")
    spec = {**ran, "questions": questions,
            "note": f"The questions the full run asked, from {FULL_RUN}, with keys from the current rules "
                    "and the corrections in scale.py."}
    QUESTIONS.write_text(json.dumps(spec, indent=2) + "\n")


PILOT_RUN = "be3e719"  # the commit whose scale-questions.json the pilot ran


def regrade_pilot():
    """Freeze the pilot's six questions with keys from the current rules, and
    grade each pilot session's answer against them. An answer is rebuilt from
    what scoring recorded: the old key less what it missed, plus what was wrong."""
    import agent  # noqa: PLC0415
    ran = json.loads(subprocess.run(["git", "show", f"{PILOT_RUN}:code-graph/bench/scale-questions.json"],
                                    cwd=BENCH, capture_output=True, text=True, check=True).stdout)
    results = json.loads((BENCH / "results" / "agent-scale-pilot.json").read_text())
    asked = {r["question"] for r in results["runs"]}
    cur, prev = Release(CURRENT), Release(PREVIOUS)
    questions = []
    for q in ran["questions"]:
        if q["id"] not in asked:
            continue
        key = sorted(key_for(cur, prev, q["family"], q["target"]))
        changed = {"note": f"The key the pilot ran with had {len(q['answer'])} entries; the current rules give "
                           f"{len(key)}."} if key != q["answer"] else {}
        questions.append({**q, "answer": key, "pilot_answer": q["answer"], **changed})
    pilot = {**ran, "questions": questions,
             "note": f"The pilot's questions, from {PILOT_RUN}, with keys from the current rules."}
    (BENCH / "scale-pilot-questions.json").write_text(json.dumps(pilot, indent=2) + "\n")
    keys = {q["id"]: set(q["answer"]) for q in questions}
    old = {q["id"]: set(q["pilot_answer"]) for q in questions}
    for r in results["runs"]:
        got = (old[r["question"]] - set(r["missed"])) | set(r["wrong"])
        g = agent.grade(sorted(got), keys[r["question"]], {}, lambda x: x)
        r["regraded"] = {k: g[k] for k in ("precision", "recall", "f1", "exact", "wrong", "missed")}
    summary = {}
    for arm in dict.fromkeys(r["arm"] for r in results["runs"]):
        rs = [r for r in results["runs"] if r["arm"] == arm]
        summary[arm] = {"exact": sum(r["regraded"]["exact"] for r in rs),
                        "mean_f1": round(sum(r["regraded"]["f1"] for r in rs) / len(rs), 3), "runs": len(rs)}
    results["regraded_summary"] = summary
    (BENCH / "results" / "agent-scale-pilot.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


def ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    var = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return round(cov / var, 3) if var else None


def analyze(results_path: Path, questions_path: Path):
    """The design's analysis: per family and arm, exactness, F1, cost and
    turns; against no graph, per question, the ratio of the arms' medians and
    their geometric mean with a 95% bootstrap interval over questions; and the
    rank correlation of each question's grep count with Omnigraph's ratio."""
    import math  # noqa: PLC0415
    import statistics  # noqa: PLC0415

    results = json.loads(results_path.read_text())
    spec = json.loads(questions_path.read_text())
    scored = [q for q in spec["questions"] if not q.get("dropped")]
    family = {q["id"]: q["family"] for q in scored}
    grep = {q["id"]: q["grep_lines"] for q in scored}
    runs = [r for r in results["runs"] if r["question"] in family]
    arms = list(dict.fromkeys(r["arm"] for r in runs))
    med = statistics.median

    def cell(rs):
        # A session without a result has no cost or turns, which are unknown,
        # not zero (agent.py score).
        cost = [r["cost_usd"] for r in rs if r["cost_usd"] is not None]
        turns = [r["turns"] for r in rs if r["turns"] is not None]
        return {"runs": len(rs), "exact": sum(r["exact"] for r in rs),
                "mean_f1": round(statistics.mean(r["f1"] for r in rs), 3),
                "median_cost_usd": round(med(cost), 4) if cost else None,
                "median_turns": med(turns) if turns else None,
                "median_wall_seconds": round(med(r["wall_seconds"] for r in rs), 1)}

    families = list(dict.fromkeys(family[q["id"]] for q in scored))
    table = {arm: {"all": cell([r for r in runs if r["arm"] == arm]),
                   **{f: cell(rs) for f in families
                      if (rs := [r for r in runs if r["arm"] == arm and family[r["question"]] == f])}}
             for arm in arms}

    def qmed(arm, q, key):
        xs = [r[key] for r in runs if r["arm"] == arm and r["question"] == q and r[key] is not None]
        return med(xs) if xs else None

    rng = random.Random(SEED)
    paired = {}
    for arm in arms:
        if arm == "bare":
            continue
        paired[arm] = {}
        for key in ("cost_usd", "turns", "output_tokens", "wall_seconds"):
            ratios = {q: qmed(arm, q, key) / qmed("bare", q, key) for q in family
                      if qmed(arm, q, key) and qmed("bare", q, key)}
            out = {}
            for scope in ["all", *families]:
                xs = [math.log(v) for q, v in ratios.items() if scope == "all" or family[q] == scope]
                if not xs:
                    continue
                boot = sorted(statistics.mean(rng.choices(xs, k=len(xs))) for _ in range(2000))
                out[scope] = {"geomean_ratio": round(math.exp(statistics.mean(xs)), 3),
                              "ci95": [round(math.exp(boot[50]), 3), round(math.exp(boot[1949]), 3)],
                              "questions_lower": sum(x < 0 for x in xs), "questions": len(xs)}
            paired[arm][key] = out
            if key == "cost_usd":
                qs = sorted(ratios)
                paired[arm]["grep_vs_cost_ratio_spearman"] = spearman([grep[q] for q in qs], [ratios[q] for q in qs])
    analysis = {"results": results_path.name, "questions": questions_path.name, "by_family": table,
                "vs_bare": paired}
    out_path = results_path.with_name(results_path.stem + "-analysis.json")
    out_path.write_text(json.dumps(analysis, indent=2) + "\n")
    print(f"{'arm':<10} {'family':<13} {'runs':>4} {'exact':>5} {'F1':>6} {'cost':>7} {'turns':>5} {'wall':>6}")
    for arm, cells in table.items():
        for f, c in cells.items():
            cost = "-" if c["median_cost_usd"] is None else f"{c['median_cost_usd']:.3f}"
            turns = "-" if c["median_turns"] is None else c["median_turns"]
            print(f"{arm:<10} {f:<13} {c['runs']:>4} {c['exact']:>5} {c['mean_f1']:>6.3f} {cost:>7} "
                  f"{turns:>5} {c['median_wall_seconds']:>6}")
    print("\nagainst no graph: geometric mean of per-question ratios [95% bootstrap interval], questions lower")
    for arm, keys in paired.items():
        for key in ("cost_usd", "turns", "output_tokens", "wall_seconds"):
            a = keys[key]["all"]
            print(f"{arm:<10} {key:<14} {a['geomean_ratio']:.2f}x [{a['ci95'][0]:.2f}, {a['ci95'][1]:.2f}] "
                  f"{a['questions_lower']}/{a['questions']}")
        print(f"{arm:<10} grep lines vs cost ratio, Spearman: {keys['grep_vs_cost_ratio_spearman']}")
    print(f"\nwrote {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    sub.add_parser("build")
    p = sub.add_parser("questions")
    p.add_argument("--per-family", type=int, default=PER_FAMILY)
    sub.add_parser("regrade-pilot")
    sub.add_parser("rekey")
    p = sub.add_parser("analyze")
    p.add_argument("--results", default=str(BENCH / "results" / "agent-scale.json"))
    p.add_argument("--questions", default=str(QUESTIONS))
    args = ap.parse_args()
    if args.cmd == "fetch":
        fetch()
    elif args.cmd == "build":
        build()
    elif args.cmd == "regrade-pilot":
        regrade_pilot()
    elif args.cmd == "rekey":
        rekey()
    elif args.cmd == "analyze":
        analyze(Path(args.results), Path(args.questions))
    else:
        questions(args.per_family)


if __name__ == "__main__":
    main()
