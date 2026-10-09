"""Measure ob on a synthetic project: command latency and parallel agents.

    python3 tests/bench_ob.py --issues 2000 --agents 8 --seconds 20

Builds a random dependency DAG (with epics and parent links) in bd's JSONL
format, imports it through `ob import`, then times each command and runs
parallel agents that loop `ready --claim` / `close`. Every claim is checked:
no issue may be claimed by two agents.
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
from test_ob import OMNIGRAPH, SERVER, free_port, _lock_id  # noqa: E402

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
    def __init__(self, workdir: str, server_url: str | None = None, token: str | None = None):
        self.env = {**os.environ, "OB_OMNIGRAPH": OMNIGRAPH, "OB_DIR": f"{workdir}/.ob", "OB_ACTOR": "bench"}
        for key in ("OB_STORE", "OB_SERVER"):
            self.env.pop(key, None)
        if server_url:
            self.env.update({"OB_SERVER": server_url, "OB_GRAPH": "beads", "OB_TOKEN": token})
            self.env.pop("OB_DIR")

    served = False

    def ob(self, *args, actor: str | None = None, check: bool = True):
        env = dict(self.env)
        if actor:
            env["OB_ACTOR"] = actor
            if self.served:
                env["OB_TOKEN"] = f"{actor}-secret"
        proc = subprocess.run([OB, "--json", *args], capture_output=True, text=True, env=env)
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


def start_server(workdir: str):
    """Apply this directory's cluster into the scratch dir and serve it."""
    cluster = Path(workdir) / "cluster"
    cluster.mkdir()
    bundle = HERE.parent
    for name in ("cluster.yaml", "schema.pg"):
        shutil.copy(bundle / name, cluster / name)
    for directory in ("queries", "policies"):
        shutil.copytree(bundle / directory, cluster / directory)
    actors = ["bench"] + [f"agent-{i}" for i in range(64)]
    listed = ", ".join(actors)
    policy = cluster / "policies" / "graph.policy.yaml"
    policy.write_text(policy.read_text()
                      .replace("readers: [act-admin, act-writer, act-reader]", f"readers: [{listed}]")
                      .replace("writers: [act-admin, act-writer]", f"writers: [{listed}]")
                      .replace("admins: [act-admin]", "admins: [bench]"))
    env = {**os.environ, "OMNIGRAPH_HOME": workdir}
    applied = subprocess.run([OMNIGRAPH, "cluster", "apply", "--config", str(cluster), "--as", "bench", "--json"],
                             capture_output=True, text=True, env=env, check=True)
    subprocess.run([OMNIGRAPH, "cluster", "force-unlock", _lock_id(applied.stderr), "--config", str(cluster)],
                   capture_output=True, env=env, check=True)
    port = free_port()
    tokens = {actor: f"{actor}-secret" for actor in actors}  # the server maps each token to its actor
    server = subprocess.Popen([SERVER, "--cluster", str(cluster), "--bind", f"127.0.0.1:{port}"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              env={**env, "OMNIGRAPH_SERVER_BEARER_TOKENS_JSON": json.dumps(tokens)})
    for _ in range(300):
        if subprocess.run(["curl", "-sf", f"http://127.0.0.1:{port}/readyz"], capture_output=True).returncode == 0:
            return server, f"http://127.0.0.1:{port}"
        time.sleep(0.2)
    server.kill()
    raise RuntimeError("server did not become ready")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", type=int, default=2000)
    parser.add_argument("--agents", type=int, default=8)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--keep", action="store_true", help="keep the scratch graph")
    parser.add_argument("--served", action="store_true", help="serve the cluster and use ob's HTTP transport")
    args = parser.parse_args()

    workdir = tempfile.mkdtemp(prefix="ob-bench-")
    server = None
    rows = []
    try:
        if args.served:
            server, url = start_server(workdir)
            run = Runner(workdir, url, "bench-secret")
            run.served = True
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

        mode = "served over HTTP" if args.served else "local store"
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
        if server:
            server.terminate()
            server.wait(timeout=30)
        if args.keep:
            print(f"\ngraph kept in {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
