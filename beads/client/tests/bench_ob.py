"""Measure ob on a synthetic project: command latency and parallel agents.

    python3 tests/bench_ob.py --issues 2000 --agents 8 --seconds 20
    OB_TOKEN=... python3 tests/bench_ob.py --server http://127.0.0.1:8080

Builds a random dependency DAG (with epics and parent links) in bd's JSONL
format, imports it through `ob import`, then times each command and runs
parallel agents that loop `ready --claim` / `close`. Every claim is checked:
no issue may be claimed by two agents.

By default it uses a scratch local graph. `--server` measures a running
beads server instead (see ../README.md#local-setup) with a writer token in
OB_TOKEN; everything happens on a scratch branch, deleted afterwards, so the
graph's main branch is untouched. The benchmark never starts or bootstraps a
server itself.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tests"))
from test_ob import OMNIGRAPH, clean_env  # noqa: E402

OB = str(HERE / "ob")


def synthetic_beads(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    beads = []
    epics = []
    for i in range(n):
        slug = f"bench-{i:06d}"
        kind = "epic" if i % 50 == 0 else rng.choice(["task", "task", "bug", "feature", "chore"])
        deps = []
        if i > 0 and rng.random() < 0.6:
            for target in rng.sample(range(max(0, i - 200), i), k=min(i, rng.choice([1, 1, 2, 3]))):
                deps.append({"issue_id": slug, "depends_on_id": f"bench-{target:06d}", "type": "blocks"})
        if kind != "epic" and epics and rng.random() < 0.5:
            deps.append({"issue_id": slug, "depends_on_id": rng.choice(epics[-5:]), "type": "parent-child"})
        status = "closed" if rng.random() < 0.3 else "open"
        beads.append({"id": slug, "title": f"{kind} {i}: " + " ".join(rng.sample(WORDS, 4)),
                      "description": " ".join(rng.sample(WORDS, 12)), "issue_type": kind, "status": status,
                      "priority": rng.randrange(5), "labels": rng.sample(LABELS, rng.randrange(3)),
                      "created_at": "2026-09-01T00:00:00Z", "dependencies": deps})
        if kind == "epic":
            epics.append(slug)
    return beads


WORDS = ("login session token cache index query planner merge branch commit retry lease agent "
         "schema export import search vector graph edge node timeout crash memory disk network "
         "deploy staging review docs test flaky metric alert queue worker parser").split()
LABELS = ["backend", "frontend", "infra", "docs", "urgent", "agent"]


class Runner:
    def __init__(self, workdir: str, server_url: str | None = None, token: str | None = None,
                 branch: str | None = None):
        if server_url:
            self.env = clean_env(OB_OMNIGRAPH=OMNIGRAPH, OB_SERVER=server_url, OB_GRAPH="beads", OB_TOKEN=token,
                                 OB_ACTOR="bench")
        else:
            self.env = clean_env(OB_OMNIGRAPH=OMNIGRAPH, OB_DIR=f"{workdir}/.ob", OB_ACTOR="bench")
        self.branch = ["--branch", branch] if branch else []

    def ob(self, *args, actor: str | None = None, check: bool = True, on_branch: bool = True):
        env = dict(self.env)
        if actor:
            env["OB_ACTOR"] = actor  # one token for all agents: the claims still carry each name
        branch = self.branch if on_branch else []
        proc = subprocess.run([OB, "--json", *branch, *args], capture_output=True, text=True, env=env)
        if check and proc.returncode != 0:
            raise RuntimeError(f"ob {' '.join(args)}: {proc.stdout}{proc.stderr}")
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def timed(self, *args, runs: int = 7) -> tuple[float, object]:
        samples, result = [], None
        for _ in range(runs):
            start = time.perf_counter()
            result = self.ob(*args)
            samples.append(time.perf_counter() - start)
        return statistics.median(samples) * 1000, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", type=int, default=2000)
    parser.add_argument("--agents", type=int, default=8)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--keep", action="store_true", help="keep the scratch graph")
    parser.add_argument("--server", help="URL of a running beads server; needs a writer token in OB_TOKEN")
    args = parser.parse_args()

    workdir = tempfile.mkdtemp(prefix="ob-bench-")
    branch = None
    rows = []
    try:
        if args.server:
            if not os.environ.get("OB_TOKEN"):
                parser.error("--server needs a writer token in OB_TOKEN")
            name = f"bench-{os.getpid()}"
            run = Runner(workdir, args.server, os.environ["OB_TOKEN"], name)
            run.ob("branch", "create", name, on_branch=False)
            branch = name  # delete it afterwards
        else:
            run = Runner(workdir)
            run.ob("init", "--prefix", "bench")
        beads = synthetic_beads(args.issues, args.seed)
        data = Path(workdir) / "beads.jsonl"
        data.write_text("\n".join(json.dumps(b) for b in beads) + "\n")
        links = sum(len(b["dependencies"]) for b in beads)

        start = time.perf_counter()
        report = run.ob("import", str(data))
        rows.append(("import (bd JSONL)", (time.perf_counter() - start) * 1000,
                     f"{report['issues']} issues, {report['links']} links, {report['commits']} commits"))

        floor = []
        for _ in range(7):
            start = time.perf_counter()
            subprocess.run([OMNIGRAPH, "version"], capture_output=True, check=True)
            floor.append(time.perf_counter() - start)
        rows.append(("omnigraph process floor", statistics.median(floor) * 1000, "`omnigraph version`"))

        ms, ready = run.timed("ready", "-n", "1000")
        rows.append(("ready", ms, f"{len(ready)} ready issues"))
        ms, blocked = run.timed("blocked")
        rows.append(("blocked", ms, f"{len(blocked)} blocked issues"))
        sample = ready[len(ready) // 2]["slug"]
        ms, _ = run.timed("show", sample)
        rows.append(("show (6 reads in parallel)", ms, sample))
        ms, _ = run.timed("search", "login token")
        rows.append(("search (BM25, RRF of two fields)", ms, ""))
        ms, stats = run.timed("stats")
        rows.append(("stats", ms, json.dumps(stats["by_status"])))
        ms, _ = run.timed("create", "bench issue", "--deps", sample, "-l", "bench")
        rows.append(("create with a link (1 commit)", ms, ""))
        ms, _ = run.timed("update", sample, "--notes", "touched")
        rows.append(("update (read + CAS edit)", ms, ""))
        targets = [r["slug"] for r in ready[:7]]
        samples = []
        for slug in targets:
            start = time.perf_counter()
            run.ob("claim", slug)
            samples.append(time.perf_counter() - start)
        rows.append(("claim (1 conditional update)", statistics.median(samples) * 1000, ""))
        samples = []
        for slug in targets:
            start = time.perf_counter()
            run.ob("close", slug, "--force")
            samples.append(time.perf_counter() - start)
        rows.append(("close", statistics.median(samples) * 1000, ""))

        # Parallel agents: each loops ready --claim, then close.
        claims: dict[str, list[str]] = {}
        lock = threading.Lock()
        stop = time.time() + args.seconds
        errors: list[str] = []

        def agent(name: str):
            while time.time() < stop:
                try:
                    got = run.ob("ready", "--claim", actor=name)["claimed"]
                    if not got:
                        return
                    with lock:
                        claims.setdefault(got, []).append(name)
                    run.ob("close", got, "--force", "-r", f"done by {name}", actor=name)
                except RuntimeError as exc:
                    errors.append(str(exc)[:300])
                    return

        threads = [threading.Thread(target=agent, args=(f"agent-{i}",)) for i in range(args.agents)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - start
        doubles = {k: v for k, v in claims.items() if len(v) > 1}
        rows.append((f"{args.agents} agents claim+close loop", elapsed * 1000,
                     f"{len(claims)} issues done, {len(claims) / elapsed:.1f}/s, "
                     f"{len(doubles)} double claims, {len(errors)} errors"))

        mode = f"served over HTTP, branch {branch}" if args.server else "local store"
        print(f"\nob on OmniGraph, {mode}: {args.issues} issues, {links} links "
              f"({subprocess.run([OMNIGRAPH, 'version'], capture_output=True, text=True).stdout.splitlines()[0]})\n")
        print("| operation | median ms | detail |")
        print("|---|---:|---|")
        for name, ms, detail in rows:
            print(f"| {name} | {ms:.0f} | {detail} |")
        if errors:
            print("\nerrors:", *errors[:3], sep="\n  ")
        return 1 if doubles or errors else 0
    finally:
        if branch and not args.keep:
            run.ob("branch", "delete", branch, on_branch=False, check=False)
        if args.keep:
            print(f"\ngraph kept in {branch or workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
