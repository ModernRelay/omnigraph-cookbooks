"""Run beads (bd) and ob side by side on the same project.

    python3 tests/compare_bd.py --issues 2000 --agents 8 --seconds 20 \
        [--bd-snapshot DIR] [--bd-server]

Both tools import the same bd-format JSONL. The script then checks that they
agree on which issues are ready and which are blocked, times the same commands
on the same issue ids, and runs the same agent loop (ready --claim, then
close) against each in turn, counting double claims. bd's usage metrics are
disabled for every call. `--bd-snapshot` reuses an already imported bd
directory (copied, never modified) because bd imports slowly.
"""

from __future__ import annotations

import argparse
import json
import os
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
from bench_ob import synthetic_beads  # noqa: E402
from test_ob import OMNIGRAPH  # noqa: E402

OB = str(HERE / "ob")
BD = shutil.which("bd") or "bd"
QUIET_BD = {"BD_DISABLE_METRICS": "1", "DO_NOT_TRACK": "1", "NO_COLOR": "1"}


class Tool:
    name = ""

    def __init__(self, workdir: Path):
        self.workdir = workdir

    def run(self, args: list[str], actor: str = "bench", check: bool = True):
        raise NotImplementedError

    def timed(self, args: list[str], runs: int = 7):
        samples = []
        for _ in range(runs):
            start = time.perf_counter()
            self.run(args)
            samples.append(time.perf_counter() - start)
        return statistics.median(samples) * 1000


class Beads(Tool):
    name = "bd"

    def env(self, actor: str):
        return {**os.environ, **QUIET_BD, "BEADS_DIR": str(self.workdir / ".beads"), "BEADS_ACTOR": actor}

    def run(self, args, actor="bench", check=True):
        proc = subprocess.run([BD, *args, "--json"], capture_output=True, text=True, env=self.env(actor),
                              cwd=self.workdir)
        if check and proc.returncode != 0:
            raise RuntimeError(f"bd {' '.join(args)}: {proc.stderr.strip()[-300:]}")
        return proc


class Ob(Tool):
    name = "ob"

    def env(self, actor: str):
        env = {**os.environ, "OB_OMNIGRAPH": OMNIGRAPH, "OB_DIR": str(self.workdir / ".ob"), "OB_ACTOR": actor}
        for key in ("OB_STORE", "OB_SERVER"):
            env.pop(key, None)
        return env

    def run(self, args, actor="bench", check=True):
        proc = subprocess.run([OB, "--json", *args], capture_output=True, text=True, env=self.env(actor))
        if check and proc.returncode != 0:
            raise RuntimeError(f"ob {' '.join(args)}: {proc.stdout.strip()[-300:]}{proc.stderr.strip()[-300:]}")
        return proc


def ready_set_ob(tool: Ob) -> set[str]:
    source = (HERE.parent / "queries" / "issues.gq").read_text()
    start = source.index("query ready()")
    body = source[start:source.index("\n}\n", start) + 2]
    body = body.replace("limit 500", "limit 1000000")
    proc = subprocess.run([OMNIGRAPH, "query", "-e", body, "--store", str(tool.workdir / ".ob" / "graph.omni"),
                           "--json"], capture_output=True, text=True, check=True)
    return {r["i.slug"] for r in json.loads(proc.stdout)["rows"]}


def agent_loop(tool: Tool, agents: int, seconds: float):
    claims: dict[str, list[str]] = {}
    errors: list[str] = []
    lock = threading.Lock()
    stop = time.time() + seconds

    def agent(name: str):
        while time.time() < stop:
            try:
                if tool.name == "bd":
                    rows = json.loads(tool.run(["ready", "--claim"], actor=name).stdout or "[]")
                    got = rows[0]["id"] if rows else None
                else:
                    got = json.loads(tool.run(["ready", "--claim"], actor=name).stdout)["claimed"]
                if not got:
                    return
                with lock:
                    claims.setdefault(got, []).append(name)
                tool.run(["close", got, "--force"], actor=name)
            except (RuntimeError, json.JSONDecodeError, KeyError, IndexError) as exc:
                with lock:
                    errors.append(str(exc)[:200])
                return

    threads = [threading.Thread(target=agent, args=(f"agent-{i}",)) for i in range(agents)]
    start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start
    doubles = sum(1 for v in claims.values() if len(v) > 1)
    return len(claims), elapsed, doubles, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", type=int, default=2000)
    parser.add_argument("--agents", type=int, default=8)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--bd-snapshot", help="an imported bd directory for the same --issues and --seed")
    parser.add_argument("--bd-server", action="store_true", help="bd in Dolt server mode (bd init --server)")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    root = Path(tempfile.mkdtemp(prefix="ob-vs-bd-"))
    data = root / "beads.jsonl"
    beads = synthetic_beads(args.issues, args.seed)
    data.write_text("\n".join(json.dumps(b) for b in beads) + "\n")
    links = sum(len(b["dependencies"]) for b in beads)
    bd, ob = Beads(root / "bd"), Ob(root / "ob")
    table: list[tuple[str, str, str, str]] = []
    try:
        # -- import ----------------------------------------------------------
        if args.bd_snapshot:
            shutil.copytree(args.bd_snapshot, bd.workdir)
            bd_import = "(snapshot)"
        else:
            bd.workdir.mkdir()
            init = ["init", "--stealth", "--prefix", "bench", "--non-interactive", "--skip-agents", "-q"]
            if args.bd_server:
                init.append("--server")
            subprocess.run([BD, *init], cwd=bd.workdir, env=bd.env("bench"), check=True, capture_output=True)
            start = time.perf_counter()
            bd.run(["import", str(data)])
            bd_import = f"{time.perf_counter() - start:.1f} s"
        # A bulk import leaves Dolt's journal at hundreds of MB, and every bd
        # command reads its index on open. bd's own maintenance compacts it;
        # ob's import likewise ends with `omnigraph optimize`.
        start = time.perf_counter()
        bd.run(["gc", "--skip-decay", "--force"])
        bd_gc = f"{time.perf_counter() - start:.1f} s"
        ob.workdir.mkdir()
        ob.run(["init", "--prefix", "bench"])
        start = time.perf_counter()
        ob.run(["import", str(data)])
        ob_import = f"{time.perf_counter() - start:.1f} s"
        table.append((f"import {args.issues} issues, {links} links", bd_import, ob_import,
                      f"then bd gc --skip-decay: {bd_gc}; ob import includes optimize"))

        # -- semantics ---------------------------------------------------------
        bd_ready = {r["id"] for r in json.loads(bd.run(["ready", "--limit", "0"]).stdout)}
        ob_ready = ready_set_ob(ob)
        bd_blocked = {r["id"] for r in json.loads(bd.run(["blocked"]).stdout)}
        ob_blocked = {r["slug"] for r in json.loads(ob.run(["blocked"]).stdout)}
        same_ready, same_blocked = bd_ready == ob_ready, bd_blocked == ob_blocked
        table.append(("ready set", str(len(bd_ready)), str(len(ob_ready)), "identical" if same_ready else
                      f"differ: {len(bd_ready - ob_ready)} only bd, {len(ob_ready - bd_ready)} only ob"))
        table.append(("blocked set", str(len(bd_blocked)), str(len(ob_blocked)), "identical" if same_blocked else
                      f"differ: {len(bd_blocked - ob_blocked)} only bd, {len(ob_blocked - bd_blocked)} only ob"))

        # -- single commands, same ids --------------------------------------------
        common = sorted(bd_ready & ob_ready)
        sample = common[len(common) // 2]
        claim_ids = common[:7]
        close_ids = common[7:14]
        edit_id = common[14]
        commands = [
            ("ready (500 rows)", ["ready", "--limit", "500"], ["ready", "-n", "500"]),
            ("blocked", ["blocked"], ["blocked"]),
            ("show", ["show", sample], ["show", sample]),
            ("search", ["search", "login token"], ["search", "login token"]),
            ("stats", ["stats"], ["stats"]),
        ]
        for label, bd_args, ob_args in commands:
            table.append((label, f"{bd.timed(bd_args):.0f} ms", f"{ob.timed(ob_args):.0f} ms", ""))
        table.append(("create with a dependency", f"{bd.timed(['create', 'bench issue', '--deps', sample]):.0f} ms",
                      f"{ob.timed(['create', 'bench issue', '--deps', sample]):.0f} ms", ""))
        table.append(("update a title", f"{bd.timed(['update', edit_id, '--title', 'renamed']):.0f} ms",
                      f"{ob.timed(['update', edit_id, '--title', 'renamed']):.0f} ms", ""))

        def per_id(tool: Tool, verb: list[str], ids: list[str]) -> float:
            samples = []
            for slug in ids:
                start = time.perf_counter()
                tool.run([*verb[:1], slug, *verb[1:]] if verb[0] != "update" else ["update", slug, "--claim"])
                samples.append(time.perf_counter() - start)
            return statistics.median(samples) * 1000

        table.append(("claim one issue", f"{per_id(bd, ['update'], claim_ids):.0f} ms",
                      f"{per_id(ob, ['claim'], claim_ids):.0f} ms", "bd update --claim / ob claim"))
        table.append(("close one issue", f"{per_id(bd, ['close', '--force'], close_ids):.0f} ms",
                      f"{per_id(ob, ['close', '--force'], close_ids):.0f} ms", ""))

        # -- concurrent agents, one tool at a time ---------------------------------
        for tool in (bd, ob):
            done, elapsed, doubles, errors = agent_loop(tool, args.agents, args.seconds)
            row = f"{done / elapsed:.2f} issues/s"
            note = f"{done} done in {elapsed:.0f} s, {doubles} double claims, {len(errors)} errors"
            if errors:
                note += f" (first: {errors[0][:120]})"
            if tool is bd:
                bd_row, bd_note = row, note
            else:
                table.append((f"{args.agents} agents: ready --claim + close", bd_row, row,
                              f"bd: {bd_note}; ob: {note}"))

        mode = "Dolt server" if args.bd_server else "embedded Dolt"
        bd_version = subprocess.run([BD, "version"], capture_output=True, text=True,
                                    env={**os.environ, **QUIET_BD}).stdout.strip().splitlines()[0]
        og_version = subprocess.run([OMNIGRAPH, "version"], capture_output=True, text=True).stdout.splitlines()[0]
        print(f"\n{bd_version} ({mode}) vs ob on {og_version} (local store); "
              f"{args.issues} issues, {links} links, seed {args.seed}\n")
        print("| | bd | ob | note |")
        print("|---|---:|---:|---|")
        for row in table:
            print("| " + " | ".join(row) + " |")
        return 0 if same_ready and same_blocked else 1
    finally:
        if args.bd_server and (bd.workdir / ".beads").exists():
            subprocess.run([BD, "dolt", "stop"], cwd=bd.workdir, env=bd.env("bench"), capture_output=True)
        if args.keep:
            print(f"\nkept {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
