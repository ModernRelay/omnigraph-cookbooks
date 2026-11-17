#!/usr/bin/env python3
"""PR-diff benchmark: is a pull request's branch diff exactly what it changed?

For each sampled hono pull request, the base and the merge commit are indexed,
converted and loaded with `cg load`, and `cg diff` is scored twice:

- mechanics: against a plain set difference of the two converted files, which
  tests overwrite loads and `branch diff` and should be exact;
- accuracy: against the difference of two reference graphs built with the
  TypeScript compiler API (reference.mjs), over the definitions both model.

    python3 code-graph/bench/pr_diff.py [--count 40] [--before 2026-11-01]

The sample is pinned in pr-sample.json on the first run and reused after.
Needs git, Node.js 22.23.4+, the locked indexer (`npm ci` in
sources/indexer) and the 0.14.0 omnigraph CLI (OMNIGRAPH_BIN).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
COOKBOOK = BENCH.parent
WORK = BENCH / "work"
sys.path.insert(0, str(BENCH))
from common import load_cookbook, load_reference, prf  # noqa: E402

REPO_URL = "https://github.com/honojs/hono.git"
INDEXER = COOKBOOK / "sources" / "indexer" / "node_modules" / ".bin" / "scip-typescript"
CG = COOKBOOK / "client" / "cg"


def digest(*paths: Path) -> str:
    """A short hash of the code that produced a cached file, so a change to the
    converter or the reference builder is never served from a stale cache."""
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


CONVERTER = digest(COOKBOOK / "sources" / "build_seed.py", COOKBOOK / "sources" / "scip_index.py")
REFERENCE = digest(BENCH / "reference.mjs")


def sh(*args, cwd=None, env=None):
    p = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    if p.returncode:
        raise SystemExit(f"{' '.join(map(str, args))} failed:\n{p.stderr[-2000:]}")
    return p.stdout


def clone() -> Path:
    repo = WORK / "repo"
    if not (repo / ".git").exists():
        sh("git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", REPO_URL, str(repo))
    return repo


def sample(repo: Path, count: int, before: str) -> list[dict]:
    pinned = BENCH / "pr-sample.json"
    if pinned.exists():
        return json.loads(pinned.read_text())["pull_requests"]
    log = sh("git", "log", "--first-parent", "--no-merges", f"--before={before}", "--format=%H %P", "origin/main",
             "--", "src/*.ts", "src/**/*.ts", cwd=repo)
    picked = []
    for line in log.splitlines():
        sha, *parents = line.split()
        files = sh("git", "diff", "--name-only", parents[0], sha, "--", "src", cwd=repo).split()
        if any(f.endswith(".ts") and not f.endswith(".test.ts") and not f.endswith(".d.ts") for f in files):
            subject = sh("git", "log", "-1", "--format=%s", sha, cwd=repo).strip()
            picked.append({"head": sha, "base": parents[0], "subject": subject})
        if len(picked) == count:
            break
    pinned.write_text(json.dumps({"rule": f"the {count} most recent first-parent commits on main before {before} "
                                          "that change a non-test .ts file under src/",
                                  "repository": REPO_URL, "pull_requests": picked}, indent=2) + "\n")
    return picked


def revision(repo: Path, sha: str, node_env: dict) -> tuple[Path, Path]:
    """The cookbook file and the reference for one commit, cached."""
    cook = WORK / "cook" / f"{sha}-{CONVERTER}.jsonl"
    ref = WORK / "ref" / f"{sha}-{REFERENCE}.json"
    if cook.exists() and ref.exists():
        return cook, ref
    for d in ("checkouts", "index", "cook", "ref"):
        (WORK / d).mkdir(parents=True, exist_ok=True)
    checkout = WORK / "checkouts" / sha
    if not checkout.exists():
        sh("git", "worktree", "add", "--quiet", "--detach", str(checkout), sha, cwd=repo)
    index = WORK / "index" / f"{sha}.scip"
    if not index.exists():
        sh(str(INDEXER), "index", "tsconfig.build.json", "--no-progress-bar", "--output", str(index),
           cwd=checkout, env=node_env)
    if not cook.exists():
        sh(sys.executable, "-I", str(COOKBOOK / "sources" / "build_seed.py"), "--index", str(index), "--checkout",
           str(checkout), "--revision", sha, "--repository", REPO_URL, "--out", str(cook))
    if not ref.exists():
        sh("node", str(BENCH / "reference.mjs"), str(checkout), str(ref), env=node_env)
    return cook, ref


def branch_diff(pr: dict, cook_base: Path, cook_head: Path, omnigraph: str) -> dict:
    graph = WORK / "graphs" / f"{pr['head'][:12]}.omni"
    shutil.rmtree(graph, ignore_errors=True)
    graph.parent.mkdir(parents=True, exist_ok=True)
    sh(omnigraph, "init", "--schema", str(COOKBOOK / "schema.pg"), str(graph))
    env = {**os.environ, "CG_OMNIGRAPH": omnigraph, "CG_TARGET": str(graph)}
    sh(sys.executable, str(CG), "load", str(cook_base), "--branch", "main", env=env)
    sh(sys.executable, str(CG), "load", str(cook_head), "--branch", "pr", env=env)
    review = json.loads(sh(sys.executable, str(CG), "--json", "diff", "pr", env=env))
    shutil.rmtree(graph, ignore_errors=True)
    return review


def file_diff(base: Path, head: Path) -> dict:
    """The set difference of two converted files, keyed like the review."""
    def read(p):
        sym, refs = {}, {}
        for line in p.read_text().splitlines():
            r = json.loads(line)
            if r.get("type") == "Symbol":
                sym[r["data"]["symbol"]] = r["data"]
            elif r.get("edge") == "References":
                refs[(r["from"], r["to"])] = r["data"]
        return sym, refs
    (sb, rb), (sh_, rh) = read(base), read(head)
    return {
        "added": set(sh_) - set(sb), "removed": set(sb) - set(sh_),
        "changed": {k for k in set(sb) & set(sh_) if sb[k] != sh_[k]},
        "refs_added": set(rh) - set(rb), "refs_removed": set(rb) - set(rh),
        "refs_changed": {k for k in set(rb) & set(rh) if rb[k] != rh[k]},
    }


def review_sets(review: dict) -> dict:
    refs = review["references"]
    return {
        "added": {r["symbol"] for r in review["added"]}, "removed": {r["symbol"] for r in review["removed"]},
        "changed": {r["symbol"] for r in review["changed"]},
        "refs_added": {(r["from"], r["to"]) for r in refs["added"]},
        "refs_removed": {(r["from"], r["to"]) for r in refs["removed"]},
        "refs_changed": {(r["from"], r["to"]) for r in refs["changed"]},
    }


def score(truth: set, got: set) -> tuple[int, int, int]:
    return len(truth & got), len(got - truth), len(truth - got)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--before", default="2026-11-01")
    ap.add_argument("--omnigraph", default=os.environ.get("OMNIGRAPH_BIN") or shutil.which("omnigraph"))
    args = ap.parse_args()
    # Keep every omnigraph call away from the operator's own configuration.
    (WORK / "og-home").mkdir(parents=True, exist_ok=True)
    os.environ["OMNIGRAPH_HOME"] = str(WORK / "og-home")
    node_env = dict(os.environ)
    repo = clone()
    sh("git", "fetch", "--quiet", "origin", "main", cwd=repo)
    prs = sample(repo, args.count, args.before)
    from common import identity_from_key  # noqa: PLC0415

    cats = ("added", "removed", "changed", "refs_added", "refs_removed")
    mech = {c: [0, 0, 0] for c in cats + ("refs_changed",)}
    acc = {c: [0, 0, 0] for c in cats}
    exact_mech = exact_acc = 0
    per_pr = []
    for i, pr in enumerate(prs, 1):
        cb, rb = revision(repo, pr["base"], node_env)
        ch, rh = revision(repo, pr["head"], node_env)
        review = review_sets(branch_diff(pr, cb, ch, args.omnigraph))
        files = file_diff(cb, ch)
        ok_mech = True
        for c in mech:
            tp, fp, fn = score(files[c], review[c])
            mech[c] = [a + b for a, b in zip(mech[c], (tp, fp, fn))]
            ok_mech &= fp == fn == 0
        exact_mech += ok_mech

        # Accuracy over the definitions both sides model, in identity space.
        (rnb, reb), (rnh, reh) = load_reference(rb), load_reference(rh)
        (cnb, _), (cnh, _) = load_cookbook(cb), load_cookbook(ch)
        aligned = (set(rnb) & set(cnb)) | (set(rnh) & set(cnh))
        ident = lambda k: identity_from_key(k)  # noqa: E731
        idset = lambda keys: {ident(k) for k in keys if ident(k) in aligned}  # noqa: E731
        edgeset = lambda pairs: {(ident(a), ident(b)) for a, b in pairs  # noqa: E731
                                 if ident(a) in aligned and ident(b) in aligned}
        in_aligned = lambda edges: {e for e in edges if e[0] in aligned and e[1] in aligned}  # noqa: E731
        truth = {
            "added": (set(rnh) - set(rnb)) & aligned, "removed": (set(rnb) - set(rnh)) & aligned,
            "changed": {k for k in set(rnb) & set(rnh) & aligned
                        if rnb[k].get("digest") and rnb[k]["digest"] != rnh[k].get("digest")},
            "refs_added": in_aligned(set(reh) - set(reb)), "refs_removed": in_aligned(set(reb) - set(reh)),
        }
        ours = {
            "added": idset(review["added"]), "removed": idset(review["removed"]),
            "changed": idset(k for k in review["changed"]),
            "refs_added": edgeset(review["refs_added"]), "refs_removed": edgeset(review["refs_removed"]),
        }
        # A changed Symbol counts only when its code changed, not its kind or signature alone.
        ok_acc = True
        row = {"head": pr["head"][:12], "subject": pr["subject"][:70]}
        for c in cats:
            tp, fp, fn = score(truth[c], ours[c])
            acc[c] = [a + b for a, b in zip(acc[c], (tp, fp, fn))]
            ok_acc &= fp == fn == 0
            row[c] = [tp, fp, fn]
        exact_acc += ok_acc
        row["exact"] = ok_acc
        per_pr.append(row)
        print(f"[{i}/{len(prs)}] {pr['head'][:12]} mechanics {'exact' if ok_mech else 'DIFF'}, "
              f"accuracy {'exact' if ok_acc else 'differs'}: {pr['subject'][:60]}", flush=True)

    result = {
        "prs": len(prs), "mechanics_exact_prs": exact_mech, "accuracy_exact_prs": exact_acc,
        "mechanics": {c: prf(*v) for c, v in mech.items()},
        "accuracy": {c: prf(*v) for c, v in acc.items()},
        "per_pr": per_pr,
    }
    (BENCH / "results").mkdir(exist_ok=True)
    (BENCH / "results" / "pr_diff.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "per_pr"}, indent=2))


if __name__ == "__main__":
    main()
