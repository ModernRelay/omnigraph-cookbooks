#!/usr/bin/env python3
"""Check out the pinned hono revisions and index each one with the locked SCIP indexer.

source.json pins the repository, every revision by full commit SHA, and the
indexer; indexer/package-lock.json pins the indexer and the TypeScript compiler
it runs to exact versions. The script refuses a checkout whose HEAD is not the
pinned commit and an indexer whose installed version is not the pinned one.

    python3 code-graph/sources/fetch.py                # into code-graph/sources/work/
    python3 code-graph/sources/fetch.py --into DIR

Needs git, and Node.js 22.23.4 or later with npm for the indexer. Everything it
writes is under the work directory, which git ignores; build_seed.py reads it.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(*args, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"{' '.join(args)} failed in {cwd or os.getcwd()}:\n{result.stderr.strip()}")
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--into", default=os.path.join(HERE, "work"), help="work directory (default: sources/work)")
    args = parser.parse_args()
    with open(os.path.join(HERE, "source.json")) as f:
        source = json.load(f)
    for tool in ("git", "node", "npm"):
        if not shutil.which(tool):
            sys.exit(f"{tool} is needed; see the comment at the top of this script")
    node = tuple(int(part) for part in run("node", "--version").lstrip("v").split(".")[:3])
    if node < (22, 23, 4):
        sys.exit(f"the indexer needs Node.js 22.23.4 or later, not {'.'.join(map(str, node))}")
    work = os.path.abspath(args.into)
    os.makedirs(work, exist_ok=True)

    # The indexer, from the lockfile only.
    indexer = os.path.join(HERE, "indexer")
    binary = os.path.join(indexer, "node_modules", ".bin", "scip-typescript")
    if not os.path.exists(binary):
        print("installing the locked indexer with npm ci", flush=True)
        run("npm", "ci", "--no-audit", "--no-fund", "--ignore-scripts", cwd=indexer)
    with open(os.path.join(indexer, "node_modules", source["indexer"]["package"], "package.json")) as f:
        installed = json.load(f)["version"]
    if installed != source["indexer"]["version"]:
        sys.exit(f"installed {source['indexer']['package']} is {installed}, not the pinned "
                 f"{source['indexer']['version']}: delete sources/indexer/node_modules and run again")

    # One blobless clone, one detached worktree per pinned revision.
    clone = os.path.join(work, "repo")
    if not os.path.isdir(os.path.join(clone, ".git")):
        print(f"cloning {source['repository']}", flush=True)
        run("git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", source["repository"], clone)
    for rev in source["revisions"]:
        checkout = os.path.join(work, rev["sha"])
        if not os.path.isdir(checkout):
            run("git", "fetch", "--quiet", "origin", rev["sha"], cwd=clone)
            run("git", "worktree", "add", "--quiet", "--detach", checkout, rev["sha"], cwd=clone)
        head = run("git", "rev-parse", "HEAD", cwd=checkout)
        if head != rev["sha"]:
            sys.exit(f"{checkout} is at {head}, not the pinned {rev['sha']}")
        if run("git", "status", "--porcelain", cwd=checkout):
            sys.exit(f"{checkout} has local changes; remove it and run again")
        index = os.path.join(work, f"{rev['sha']}.scip")
        print(f"indexing {rev['name']} ({rev['sha'][:12]})", flush=True)
        run(binary, "index", source["project"], "--no-progress-bar", "--output", index, cwd=checkout)
    print(f"done: {len(source['revisions'])} revisions indexed under {work}")


if __name__ == "__main__":
    main()
