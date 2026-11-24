"""What the VS Code graph answers by itself: for each scored question of the
scale benchmark, the one `cg` read that answers it, graded against the same key
and with the same rules as the agents' answers.

    python3 code-graph/bench/graph_answers.py     # after `scale.py build`

The reads are the ones the Omnigraph arm's CLAUDE.md lists. A family takes the
read named for it: callers for a uniquely named function, a shared method name
and a construction; transitive-callers for a chain of calls; the members that
implement the target, at every level, for dispatch; callers on both releases
for release changes. Test code is left out, as the answer format tells the
agents. Writes results/graph-answers.json.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))
import agent  # noqa: E402
import scale  # noqa: E402
from common import identity_from_key  # noqa: E402

CG = BENCH.parent / "client" / "cg"
ENV = {**os.environ, "OMNIGRAPH_HOME": str(scale.WORK / "og"), "CG_TARGET": str(scale.WORK / "graph.omni"),
       "CG_OMNIGRAPH": os.environ.get("OMNIGRAPH_BIN") or "omnigraph"}


def cg(*args: str) -> dict:
    out = subprocess.run([sys.executable, str(CG), *args, "--json"], capture_output=True, text=True, env=ENV)
    if out.returncode:
        raise SystemExit(f"cg {' '.join(args)}: {out.stderr or out.stdout}")
    return json.loads(out.stdout)


def key_of(target: str, branch: str | None = None) -> str | None:
    """The graph's key for a reference identity such as path:Class.member."""
    path, tail = target.split(":", 1)
    name = tail.split(".")[-1]
    extra = ["--branch", branch] if branch else []
    rows = cg("find", name, "--path", path, *extra)["rows"]
    keys = [r["symbol"] for r in rows if identity_from_key(r["symbol"]) == target]
    return keys[0] if keys else None


def column(rows: list[dict]) -> list[str]:
    """A read's definition column, whatever its title."""
    return [r[next(k for k in r if k not in ("kind", "sites"))] for r in rows]


def answer(family: str, target: str) -> list[str] | None:
    key = key_of(target)
    if key is None:
        return None
    if family in ("shared-name", "control", "construction"):
        return column(cg("callers", key)["rows"])
    if family == "transitive":
        return column(cg("transitive-callers", key)["rows"])
    if family == "dispatch":
        found, todo = set(), [key]
        while todo:
            for k in column(cg("implementers", todo.pop())["rows"]):
                if k not in found:
                    found.add(k)
                    todo.append(k)
        return sorted(found)
    previous = key_of(target, f"v{scale.PREVIOUS}")
    now = set(column(cg("callers", key)["rows"]))
    then = set(column(cg("callers", previous, "--branch", f"v{scale.PREVIOUS}")["rows"])) if previous else set()
    return sorted(now - then)


def main():
    agent.configure("vscode")
    cur = scale.Release(scale.CURRENT)
    questions = json.loads((BENCH / "scale-questions.json").read_text())["questions"]
    dropped = {q for q, c in scale.CORRECTIONS.items() if c.get("drop")}
    out = []
    for q in questions:
        if q["id"] in dropped:
            continue
        got = answer(q["family"], q["target"])
        # The answer format leaves out test code, as every agent was told.
        names = [n for n in (identity_from_key(k) or k for k in got or []) if not scale.is_test(n.split(":")[0])]
        grade = agent.grade(names, set(q["answer"]), cur.nodes, cur.lift, set(q.get("optional", [])))
        out.append({"question": q["id"], "family": q["family"], "rows": len(got or []),
                    "target_found": got is not None, **grade})
        print(f"{q['id']:<15} rows {len(got or []):>4}  F1 {grade['f1']:.2f}  {'exact' if grade['exact'] else ''}"
              f"  wrong {grade['wrong'][:2]} missed {grade['missed'][:2]}", flush=True)
    exact = sum(r["exact"] for r in out)
    print(f"{exact} of {len(out)} exact, mean F1 {sum(r['f1'] for r in out) / len(out):.3f}")
    version = subprocess.run([ENV["CG_OMNIGRAPH"], "--version"], capture_output=True, text=True).stdout.strip()
    (BENCH / "results" / "graph-answers.json").write_text(json.dumps(
        {"graph": str((scale.WORK / "graph.omni").relative_to(BENCH)), "omnigraph": version,
         "exact": exact, "questions": out}, indent=2) + "\n")


if __name__ == "__main__":
    main()
