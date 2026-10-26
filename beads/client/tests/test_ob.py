"""End-to-end tests for ob against a real OmniGraph graph.

Run from beads/client:  python3 -m unittest discover -s tests -v
The omnigraph and omnigraph-server binaries come from $OB_OMNIGRAPH and
$OB_OMNIGRAPH_SERVER, else PATH (the cookbooks pin the 0.14.0 release). Most
tests use local graphs. ServedTests start a server for the cookbook behind the
repository's local HTTPS gateway and drive ob through server targets;
TransportTests put a scripted server behind the same gateway to see which
commands ob sends again. Both need python3 and openssl for the gateway.
"""

from __future__ import annotations

import concurrent.futures
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent   # beads/client
BUNDLE = HERE.parent                              # beads/: schema, queries, policies, cluster.yaml
OB = HERE / "ob"
REPO = BUNDLE.parent
GATEWAY = REPO / "scripts" / "local-tls-gateway.py"


def find_binary(name: str) -> str | None:
    env = os.environ.get("OB_OMNIGRAPH" if name == "omnigraph" else "OB_OMNIGRAPH_SERVER")
    if env:
        return env
    for build in ("release", "debug"):
        candidate = REPO / "target" / build / name
        if candidate.exists():
            return str(candidate)
    return shutil.which(name)


OMNIGRAPH = find_binary("omnigraph")
SERVER = find_binary("omnigraph-server")


def clean_env(**extra: str) -> dict:
    """The caller's environment without any ob or OmniGraph setting, so that a
    shell configured for a real graph (OB_TARGET, OMNIGRAPH_HOME, ...) cannot
    leak in."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OB_", "OMNIGRAPH_", "OG_"))}
    env.update(extra)
    return env


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_until(check, what: str, timeout: float = 60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except OSError:
            pass
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {what}")


class Gateway:
    """scripts/local-tls-gateway.py in front of a plain-HTTP port, with its own
    CA in `certs`: the 0.14 CLI sends a target's token only over HTTPS."""

    def __init__(self, upstream: int, certs: Path):
        self.port = free_port()
        self.ca = certs / "ca.pem"
        self.proc = subprocess.Popen(
            [sys.executable, str(GATEWAY), "--listen", f"127.0.0.1:{self.port}",
             "--upstream", f"127.0.0.1:{upstream}", "--certs", str(certs)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def listening() -> bool:
            if self.proc.poll() is not None:
                raise AssertionError("the HTTPS gateway exited")
            with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                return True

        wait_until(listening, "the HTTPS gateway")

    def stop(self):
        self.proc.terminate()
        self.proc.wait(timeout=10)


def write_operator_config(path: Path, gateway: Gateway, targets: dict[str, str]) -> None:
    """One server target per name, each reading its token from the named
    environment variable and trusting the gateway's CA."""
    lines = ["version: 1", "targets:"]
    for name, token_env in targets.items():
        lines += [f"  {name}:", "    kind: server", f"    endpoint: https://localhost:{gateway.port}",
                  f"    auth: {{provider: token, source: {{env: {token_env}}}}}",
                  f"    transport: {{tls: {{ca: {{mode: append, file: {gateway.ca}}}}}}}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


class ObCase(unittest.TestCase):
    """A fresh project directory with an initialized local graph per test."""

    embed = False

    def setUp(self):
        if not OMNIGRAPH:
            self.skipTest("omnigraph binary not found")
        self.tmp = tempfile.mkdtemp(prefix="ob-test-")
        self.env = clean_env(OB_OMNIGRAPH=OMNIGRAPH, OB_DIR=f"{self.tmp}/.ob", OB_ACTOR="alice",
                             OMNIGRAPH_HOME=f"{self.tmp}/home")
        if self.embed:
            self.env["OMNIGRAPH_EMBEDDINGS_MOCK"] = "1"
        args = ["init"] + (["--embed"] if self.embed else [])
        self.ob(*args)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_ob(self, *args, actor: str | None = None, check: bool = True):
        env = dict(self.env)
        if actor:
            env["OB_ACTOR"] = actor
        proc = subprocess.run([str(OB), "--json", *args], capture_output=True, text=True, env=env, cwd=self.tmp)
        if check and proc.returncode != 0:
            self.fail(f"ob {' '.join(args)} failed ({proc.returncode}): {proc.stdout}{proc.stderr}")
        return proc

    def ob(self, *args, actor: str | None = None):
        out = self.run_ob(*args, actor=actor).stdout
        return json.loads(out) if out.strip() else None

    def ob_fails(self, *args, actor: str | None = None) -> str:
        proc = self.run_ob(*args, actor=actor, check=False)
        self.assertNotEqual(proc.returncode, 0, f"ob {' '.join(args)} unexpectedly succeeded: {proc.stdout}")
        return proc.stdout + proc.stderr

    def create(self, title: str, *args, actor: str | None = None) -> str:
        return self.ob("create", title, *args, actor=actor)["id"]

    def ready(self, *args) -> list[str]:
        return [r["slug"] for r in self.ob("ready", *args)]

    def import_beads(self, beads: list[dict]) -> dict:
        path = Path(self.tmp) / "import.jsonl"
        path.write_text("".join(json.dumps({"status": "open", "priority": 2, "created_at": "2026-01-01T00:00:00Z",
                                            **b}) + "\n" for b in beads))
        return self.ob("import", str(path))

    def commits(self) -> int:
        proc = subprocess.run([OMNIGRAPH, "commit", "list", "--target", f"{self.tmp}/.ob/graph.omni", "--json"],
                              capture_output=True, text=True, check=True, env=self.env)
        data = json.loads(proc.stdout)
        return len(data["commits"] if isinstance(data, dict) else data)


class ReadinessTests(ObCase):
    def test_ready_is_derived_from_blockers_ancestors_and_deferral(self):
        blocker = self.create("blocker", "-p", "3")
        waiting = self.create("waits on blocker", "--deps", blocker)
        epic = self.create("epic blocked by blocker", "-t", "epic", "--deps", blocker)
        child = self.create("child of blocked epic", "--parent", epic)
        grandchild = self.create("grandchild", "--parent", child)
        later = self.create("deferred into the future", "--defer", "2d")
        past = self.create("deferral already over", "--defer", "2020-01-01T00:00:00Z")
        free = self.create("free", "-p", "0")

        self.assertEqual(self.ready(), [free, past, blocker])
        blocked = {r["slug"]: r for r in self.ob("blocked")}
        self.assertEqual(set(blocked), {waiting, epic, child, grandchild})
        self.assertEqual(blocked[waiting]["blockers"], [blocker])
        self.assertEqual(blocked[grandchild]["via"], [f"{epic}<-{blocker}"])
        self.assertNotIn(later, self.ready())

        self.ob("close", blocker, "-r", "done")
        self.assertEqual(set(self.ready()), {free, past, waiting, epic, child, grandchild})
        self.assertEqual(self.ob("blocked"), [])

    def test_ancestors_pass_blocks_down_as_in_beads(self):
        # Found by running bd side by side (tests/compare_bd.py): an ancestor
        # passes a block down only while it is not closed, only through
        # unclosed ancestors, and only for a blocker outside its own subtree.
        outside = self.create("outside blocker")
        epic = self.create("epic", "-t", "epic", "--deps", outside)
        middle = self.create("middle", "--parent", epic)
        leaf = self.create("leaf", "--parent", middle)
        self.assertNotIn(leaf, self.ready())
        self.ob("close", middle, "--force")  # a closed issue between cuts the chain
        self.assertIn(leaf, self.ready())
        self.ob("reopen", middle)
        self.assertNotIn(leaf, self.ready())
        self.ob("close", epic, "--force")  # a closed ancestor passes nothing down
        self.assertIn(leaf, self.ready())

        parent = self.create("parent", "-t", "epic")
        first = self.create("first child", "--parent", parent)
        second = self.create("second child", "--parent", parent)
        # ob refuses a parent waiting on its own child, as bd does; data loaded
        # directly can still hold one, and must not block the children.
        self.assertIn("own descendant", self.ob_fails("dep", "add", parent, first))
        edge = Path(self.tmp) / "edge.jsonl"
        edge.write_text(json.dumps({"edge": "BlockedBy", "from": parent, "to": first}) + "\n")
        subprocess.run([OMNIGRAPH, "load", "--data", str(edge), "--mode", "merge", "--target",
                        f"{self.tmp}/.ob/graph.omni"], check=True, capture_output=True, env=self.env)
        ready = self.ready()
        self.assertNotIn(parent, ready)
        self.assertIn(first, ready)
        self.assertIn(second, ready)

    def test_deferred_status_and_undefer(self):
        a = self.create("a")
        self.ob("defer", a)
        self.assertEqual(self.ready(), [])
        self.ob("undefer", a)
        self.assertEqual(self.ready(), [a])

    def test_filters(self):
        bug = self.create("bug", "-t", "bug", "-l", "backend,urgent", "-p", "1")
        self.create("task", "-l", "frontend")
        self.assertEqual(self.ready("-l", "backend"), [bug])
        self.assertEqual(self.ready("-t", "bug"), [bug])
        self.assertEqual(len(self.ready("--exclude-type", "bug")), 1)
        self.assertEqual(self.ready("--priority-max", "1"), [bug])

    def test_filters_apply_before_the_ready_limit(self):
        tasks = [{"id": f"t-{i:04d}", "title": f"task {i}", "priority": 0} for i in range(520)]
        bugs = [{"id": "bug-1", "title": "a bug", "issue_type": "bug", "priority": 3, "labels": ["backend", "urgent"]},
                {"id": "bug-2", "title": "bob's bug", "issue_type": "bug", "priority": 3, "labels": ["backend"],
                 "assignee": "bob"}]
        self.import_beads(tasks + bugs)
        self.assertEqual(len(self.ob("ready", "-n", "1000")), 500)
        self.assertEqual(self.ready("-t", "bug"), ["bug-1", "bug-2"])
        self.assertEqual(self.ready("--exclude-type", "task"), ["bug-1", "bug-2"])
        self.assertEqual(self.ready("-t", "bug", "--priority-max", "2"), [])
        self.assertEqual(self.ready("-l", "backend", "-l", "urgent"), ["bug-1"])
        self.assertEqual(self.ready("-t", "bug", "-a", "none"), ["bug-1"])
        self.assertEqual(self.ready("-a", "bob"), ["bug-2"])
        self.assertEqual(self.ready("-a", "me"), [])
        self.assertEqual(self.ob("ready", "--claim", "-t", "bug", actor="carol")["claimed"], "bug-1")


class WriteTests(ObCase):
    def test_create_with_links_is_one_strict_commit(self):
        a = self.create("a")
        b = self.create("b")
        before = self.commits()
        c = self.create("c", "--deps", a, "--deps", f"related:{b}", "--parent", b, "--discovered-from", a,
                        "-l", "x,y")
        self.assertEqual(self.commits(), before + 1)
        shown = self.ob("show", c)
        links = sorted((l["link"], l["slug"]) for l in shown["links_out"])
        self.assertEqual(links, sorted([("BlockedBy", a), ("RelatesTo", b), ("ChildOf", b), ("DiscoveredFrom", a)]))
        self.assertEqual(shown["labels"], ["x", "y"])
        self.assertIn("already exists", self.ob_fails("create", "dup", "--id", c))

    def test_dependency_rules_are_enforced(self):
        a, b, c = self.create("a"), self.create("b"), self.create("c")
        self.ob("dep", "add", a, b)
        self.ob("dep", "add", b, c)
        self.assertIn("cycle", self.ob_fails("dep", "add", c, a))
        self.assertIn("itself", self.ob_fails("dep", "add", a, a))
        self.ob("dep", "add", a, b)  # keyed edges: adding twice is a no-op
        self.assertEqual([r["slug"] for r in self.ob("dep", "tree", a)["waits_on"]], sorted([b, c]))
        d = self.create("d")
        self.ob("dep", "add", a, c, "--type", "parent")
        self.assertIn("card", self.ob_fails("dep", "add", a, d, "--type", "parent"))
        self.assertIn("not found", self.ob_fails("dep", "add", a, "ob-missing"))
        self.ob("dep", "rm", a, b)
        self.assertEqual([r["slug"] for r in self.ob("dep", "tree", a)["waits_on"]], [])

    def test_beads_write_rules(self):
        epic = self.create("epic", "-t", "epic")
        child = self.create("child", "--parent", epic)
        grandchild = self.create("grandchild", "--parent", child)
        self.assertIn("own ancestor", self.ob_fails("dep", "add", grandchild, epic))
        self.assertIn("own ancestor", self.ob_fails("create", "x", "--deps", epic, "--parent", child))
        other = self.create("other")
        self.ob("dep", "add", other, epic)
        self.assertIn("own ancestor", self.ob_fails("dep", "add", other, epic, "--type", "parent"))
        self.assertIn("own descendant", self.ob_fails("dep", "add", epic, grandchild))
        self.assertIn("own descendant", self.ob_fails("dep", "add", epic, other, "--type", "parent"))

        self.assertIn("open child", self.ob_fails("close", epic))
        blocker = self.create("blocker")
        waiting = self.create("waiting", "--deps", blocker)
        self.assertIn("waits on open", self.ob_fails("close", waiting))
        self.assertEqual(self.ob("close", waiting, blocker)["closed"], 2)  # together is fine
        self.assertEqual(self.ob("close", epic, child, grandchild)["closed"], 3)
        stray = self.create("stray", "--deps", other)
        self.assertEqual(self.ob("close", stray, "--force")["closed"], 1)

    def test_parent_links_cannot_loop_or_trap_descendants(self):
        a = self.create("a", "-t", "epic")
        b = self.create("b", "--parent", a)
        self.assertIn("cycle", self.ob_fails("dep", "add", a, b, "--type", "parent"))
        # Moving x under p would leave x's child c waiting on its new ancestor.
        p = self.create("p", "-t", "epic")
        x = self.create("x", "-t", "epic")
        c = self.create("c", "--parent", x, "--deps", p)
        self.assertIn(f"{c} cannot wait on its own ancestor {p}", self.ob_fails("dep", "add", x, p, "--type", "parent"))
        # q waits on c, so x (and c with it) cannot move below q.
        q = self.create("q", "-t", "epic")
        self.ob("dep", "add", q, c)
        self.assertIn("own descendant", self.ob_fails("dep", "add", x, q, "--type", "parent"))
        # The rules hold however the parent is spelled.
        e = self.create("e", "-t", "epic")
        self.assertIn("own ancestor", self.ob_fails("create", "x2", "--deps", e, "--deps", f"parent-child:{e}"))
        self.assertIn("at most one parent", self.ob_fails("create", "x3", "--parent", e, "--deps", f"parent:{a}"))
        self.assertEqual(self.ob("close", a, b)["closed"], 2)

    def test_hierarchies_stay_within_eight_levels(self):
        chain = [self.create("level 0", "-t", "epic")]
        for depth in range(1, 9):
            chain.append(self.create(f"level {depth}", "--parent", chain[-1]))
        self.assertIn("8 levels", self.ob_fails("create", "level 9", "--parent", chain[-1]))
        loose = self.create("loose")
        self.assertIn("8 levels", self.ob_fails("dep", "add", loose, chain[-1], "--type", "parent"))
        top = self.create("new top", "-t", "epic")
        self.assertIn("8 levels", self.ob_fails("dep", "add", chain[0], top, "--type", "parent"))
        self.ob("dep", "add", loose, chain[-2], "--type", "parent")

    def test_close_and_reopen_batch(self):
        a, b = self.create("a"), self.create("b")
        self.assertEqual(self.ob("close", a, b, "-r", "shipped")["closed"], 2)
        self.assertEqual(self.ob("close", a, b)["closed"], 0)
        self.assertEqual(self.ob("show", a)["close_reason"], "shipped")
        self.assertEqual(self.ob("reopen", a)["reopened"], 1)
        self.assertEqual(self.ready(), [a])

    def test_update_is_a_per_issue_compare_and_swap(self):
        a = self.create("a")
        labels = [f"l{i}" for i in range(6)]
        with concurrent.futures.ThreadPoolExecutor(6) as pool:
            list(pool.map(lambda l: self.ob("label", "add", a, l), labels))
        self.assertEqual(sorted(self.ob("show", a)["labels"]), labels)
        self.ob("update", a, "--title", "renamed", "-p", "0", "--notes", "n", "--remove-label", "l0")
        shown = self.ob("show", a)
        self.assertEqual((shown["title"], shown["priority"], shown["notes"]), ("renamed", 0, "n"))
        self.assertNotIn("l0", shown["labels"])
        self.assertIn("invalid", self.ob_fails("update", a, "--metadata", "{not json"))


class ClaimTests(ObCase):
    def test_exactly_one_of_many_racing_claimers_wins(self):
        a = self.create("contended")
        agents = [f"agent-{i}" for i in range(8)]
        with concurrent.futures.ThreadPoolExecutor(len(agents)) as pool:
            results = list(pool.map(lambda who: self.run_ob("claim", a, actor=who, check=False), agents))
        winners = [who for who, proc in zip(agents, results) if proc.returncode == 0]
        self.assertEqual(len(winners), 1, [p.stdout + p.stderr for p in results])
        shown = self.ob("show", a)
        self.assertEqual((shown["status"], shown["assignee"]), ("in_progress", winners[0]))

    def test_parallel_ready_claim_hands_out_distinct_work(self):
        issues = {self.create(f"work {i}") for i in range(6)}
        agents = [f"agent-{i}" for i in range(6)]
        with concurrent.futures.ThreadPoolExecutor(len(agents)) as pool:
            claimed = list(pool.map(lambda who: self.ob("ready", "--claim", actor=who)["claimed"], agents))
        self.assertEqual(set(claimed), issues)
        self.assertEqual(self.ready(), [])

    def test_release_renew_and_lease_reclaim(self):
        a = self.create("a")
        self.ob("claim", a, "--lease", "1h", actor="bob")
        self.assertIn("held by bob", self.ob_fails("claim", a, actor="carol"))
        self.assertIn("not held", self.ob_fails("release", a, actor="carol"))
        self.ob("claim", a, actor="bob")  # re-claiming your own issue is idempotent
        self.assertEqual(self.ob("reclaim")["reclaimed"], 0)
        self.ob("renew", a, "--lease", "2020-01-01T00:00:00Z", actor="bob")  # an already-lapsed lease
        self.assertEqual(self.ob("reclaim")["reclaimed"], 1)
        self.assertEqual(self.ready(), [a])
        self.ob("claim", a, actor="carol")
        self.ob("renew", a, "--lease", "1h", actor="carol")
        self.ob("release", a, actor="carol")
        self.assertEqual(self.ob("show", a).get("assignee"), None)

    def test_claiming_again_with_a_lease_renews_it(self):
        a = self.create("a")
        self.ob("claim", a, "--lease", "1h", actor="bob")
        first = self.ob("show", a)["lease_expires_at"]
        self.ob("claim", a, "--lease", "4h", actor="bob")
        self.assertGreater(self.ob("show", a)["lease_expires_at"], first)

    def test_a_claim_ends_when_its_issue_leaves_in_progress(self):
        a = self.create("a")
        self.ob("claim", a, "--lease", "1h", actor="bob")
        self.ob("close", a, actor="bob")
        self.ob("reopen", a)
        self.assertEqual(self.ob("show", a).get("assignee"), None)
        self.ob("claim", a, "--lease", "1h", actor="carol")
        self.ob("defer", a)
        shown = self.ob("show", a)
        self.assertEqual((shown["status"], shown.get("assignee"), shown.get("lease_expires_at")),
                         ("deferred", None, None))
        self.ob("undefer", a)
        self.ob("claim", a, "--lease", "1h", actor="dave")
        self.ob("update", a, "--status", "open", actor="dave")
        shown = self.ob("show", a)
        self.assertEqual((shown["status"], shown.get("assignee"), shown.get("lease_expires_at")), ("open", None, None))
        self.assertEqual(self.ob("ready", "--claim", actor="erin")["claimed"], a)
        reserved = self.create("reserved for frank", "-a", "frank")
        self.ob("defer", reserved)
        self.ob("undefer", reserved)
        self.assertEqual(self.ob("show", reserved)["assignee"], "frank")  # a reservation is not a claim

    def test_update_claims_rather_than_leaving_work_ownerless(self):
        a = self.create("a")
        self.ob("update", a, "--status", "in_progress", "--claim", "--lease", "1h", actor="bob")
        shown = self.ob("show", a)
        self.assertEqual((shown["status"], shown["assignee"]), ("in_progress", "bob"))
        self.assertTrue(shown["lease_expires_at"])
        b = self.create("b")
        self.ob("update", b, "--status", "in_progress", "--notes", "started", actor="bob")
        shown = self.ob("show", b)
        self.assertEqual((shown["status"], shown["assignee"], shown["notes"]), ("in_progress", "bob", "started"))
        c = self.create("c")
        self.ob("claim", c, actor="carol")
        self.assertIn("held by carol", self.ob_fails("update", c, "--claim", "--notes", "x", actor="bob"))
        self.assertIsNone(self.ob("show", c).get("notes"))  # nothing landed
        self.assertIn("--claim assigns", self.ob_fails("update", a, "--claim", "--assignee", "zed", actor="bob"))
        self.assertIn("needs an assignee", self.ob_fails("update", a, "--assignee", "", actor="bob"))


class KnowledgeTests(ObCase):
    def test_comments_memories_and_prime(self):
        a = self.create("auth bug")
        self.ob("comment", a, "reproduced on staging")
        self.ob("remember", "Session tokens live in redis", "--key", "tokens", "--about", a)
        migrations = self.ob("remember", "Run migrations before tests")["key"]
        self.assertTrue(migrations.startswith("run-migrations-before-tests-"))
        shown = self.ob("show", a)
        self.assertEqual([c["body"] for c in shown["comments"]], ["reproduced on staging"])
        self.assertEqual([m["slug"] for m in shown["memories"]], ["tokens"])
        self.assertEqual([m["slug"] for m in self.ob("recall", "redis")], ["tokens"])
        prime = self.ob("prime")
        self.assertEqual(prime["ready_total"], 1)
        self.assertEqual(len(prime["memories"]), 2)
        self.ob("remember", "Session tokens live in valkey now", "--key", "tokens")
        self.assertEqual(self.ob("recall", "valkey")[0]["slug"], "tokens")
        self.ob("forget", "tokens")
        self.assertEqual([m["slug"] for m in self.ob("memories")], [migrations])

    def test_memories_that_start_alike_keep_separate_keys(self):
        first = self.ob("remember", "Do not push to main without review")["key"]
        second = self.ob("remember", "Do not push to main on Fridays")["key"]
        self.assertNotEqual(first, second)
        self.assertEqual(self.ob("remember", "Do not push to main on Fridays")["key"], second)
        self.assertEqual(len(self.ob("memories")), 2)

    def test_history_comes_from_commits_with_actors(self):
        a = self.create("a")
        b = self.create("b", actor="bob")
        self.ob("dep", "add", a, b, actor="bob")
        self.ob("claim", a, actor="carol")
        events = self.ob("history", a)
        self.assertEqual([(e["actor"], e["type"], e["op"]) for e in events],
                         [("alice", "Issue", "insert"), ("bob", "BlockedBy", "insert"), ("carol", "Issue", "update")])
        self.assertEqual(events[-1]["changed"]["status"], ["open", "in_progress"])

    def test_search_and_stats(self):
        self.create("timeout in login handler", "-d", "the session expires")
        self.create("unrelated work")
        self.assertEqual(len(self.ob("search", "login")), 1)
        stats = self.ob("stats")
        self.assertEqual((stats["by_status"], stats["ready"]), ({"open": 2}, 2))


class InterchangeTests(ObCase):
    def test_bd_import_export_round_trip(self):
        bd = Path(self.tmp) / "issues.jsonl"
        bd.write_text("\n".join(json.dumps(x) for x in [
            {"id": "bd-a1", "title": "epic", "issue_type": "epic", "status": "open", "priority": 1,
             "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
             "dependencies": [{"issue_id": "bd-a1", "depends_on_id": "bd-a1.1", "type": "blocks"}]},
            {"id": "bd-a1.1", "title": "child", "status": "blocked", "priority": 2, "labels": ["x"],
             "created_at": "2026-01-01T00:00:00Z",
             "dependencies": [{"issue_id": "bd-a1.1", "depends_on_id": "bd-a1", "type": "parent-child"},
                              {"issue_id": "bd-a1.1", "depends_on_id": "bd-b2", "type": "blocks"},
                              {"issue_id": "bd-a1.1", "depends_on_id": "external:gh-9", "type": "blocks"}]},
            {"id": "bd-b2", "title": "gate", "issue_type": "gate", "status": "hooked", "priority": 0,
             "created_at": "2026-01-01T00:00:00Z"},
            {"id": "bd-a1.2", "title": "waits on its own epic", "status": "open", "priority": 2,
             "created_at": "2026-01-01T00:00:00Z",
             "dependencies": [{"issue_id": "bd-a1.2", "depends_on_id": "bd-a1", "type": "parent-child"},
                              {"issue_id": "bd-a1.2", "depends_on_id": "bd-a1", "type": "blocks"}]},
        ]) + "\n")
        report = self.ob("import", str(bd))
        self.assertEqual((report["issues"], report["links"], report["skipped_links"]),
                         (4, 3, {"blocks": 1, "blocks-on-ancestor": 1, "blocks-on-descendant": 1}))
        self.assertEqual(self.ob("show", "bd-b2")["labels"], ["bd-type:gate"])
        self.assertEqual(self.ready(), ["bd-a1", "bd-a1.2"])
        out = Path(self.tmp) / "out.jsonl"
        self.run_ob("export", "-o", str(out))
        exported = {b["id"]: b for b in map(json.loads, out.read_text().splitlines())}
        self.assertTrue(all(b["created_at"].endswith("Z") for b in exported.values()))  # bd needs a zone
        self.assertEqual(sorted((d["depends_on_id"], d["type"]) for d in exported["bd-a1.1"]["dependencies"]),
                         [("bd-a1", "parent-child"), ("bd-b2", "blocks")])
        self.assertEqual(self.ob("import", str(bd))["issues"], 4)  # re-import converges

    def test_export_pages_past_query_limits(self):
        self.import_beads([{"id": f"e-{i:04d}", "title": f"issue {i}",
                            "dependencies": [{"depends_on_id": f"e-{i - 1:04d}", "type": "blocks"}] if i else []}
                           for i in range(1100)])
        out = Path(self.tmp) / "out.jsonl"
        self.run_ob("export", "-o", str(out))
        exported = {b["id"]: b for b in map(json.loads, out.read_text().splitlines())}
        self.assertEqual(len(exported), 1100)
        self.assertEqual(exported["e-1099"]["dependencies"], [{"issue_id": "e-1099", "depends_on_id": "e-1098",
                                                               "type": "blocks"}])

    def test_cycle_guard_and_tree_see_past_the_hop_bound(self):
        n = 70  # more than two frontier steps of 32 links
        self.import_beads([{"id": f"a-{i:02d}", "title": f"step {i}",
                            "dependencies": [{"depends_on_id": f"a-{i + 1:02d}", "type": "blocks"}] if i < n - 1 else []}
                           for i in range(n)])
        self.assertIn("cycle", self.ob_fails("dep", "add", f"a-{n - 1}", "a-00"))
        proc = self.run_ob("dep", "tree", "a-00")
        self.assertIn("stops 32 links", proc.stderr)
        self.assertEqual(len(json.loads(proc.stdout)["waits_on"]), 32)

    def test_plan_on_a_branch_then_merge(self):
        base = self.create("existing")
        self.ob("branch", "create", "plan")
        planned = self.ob("--branch", "plan", "create", "planned work", "--deps", base)["id"]
        self.assertEqual(self.ready(), [base])
        self.assertEqual(set(r["slug"] for r in self.ob("--branch", "plan", "list")), {base, planned})
        self.ob("branch", "merge", "plan")
        self.assertEqual(self.ob("show", planned)["links_out"][0]["slug"], base)


class EmbeddingTests(ObCase):
    embed = True

    def assert_exact_match(self, rows, slug):
        """The stored vector embeds the title as written, as the query embeds
        its text, so a query equal to the title lies at distance zero."""
        self.assertEqual(rows[0]["slug"], slug)
        self.assertLess(rows[0]["distance"], 1e-6)

    def test_similar_and_semantic_recall_use_stored_embeddings(self):
        a = self.create("Fix login timeout")
        self.create("Paint the bikeshed")
        self.assert_exact_match(self.ob("similar", "Fix login timeout"), a)
        self.assert_exact_match(self.ob("similar", a), a)
        self.ob("update", a, "--title", "Fix logout crash")
        self.assert_exact_match(self.ob("similar", "Fix logout crash"), a)
        self.ob("remember", "Deploys go through the staging gate", "--key", "deploys")
        self.assertEqual(self.ob("recall", "Deploys go through the staging gate", "--semantic")[0]["slug"], "deploys")


class CliTests(ObCase):
    def test_global_flags_work_after_the_subcommand(self):
        a = self.create("a")

        def raw(*args):
            return subprocess.run([str(OB), *args], capture_output=True, text=True, env=self.env, cwd=self.tmp,
                                  check=True).stdout

        self.assertEqual(json.loads(raw("ready", "--json"))[0]["slug"], a)
        raw("claim", a, "--as", "bob")
        self.assertEqual(self.ob("show", a)["assignee"], "bob")
        self.assertEqual(json.loads(raw("--json", "show", a))["assignee"], "bob")


class SeedTests(ObCase):
    """The seed must produce exactly the sets seed.md lists, whatever the date."""

    def test_seed_matches_seed_md(self):
        subprocess.run([OMNIGRAPH, "load", "--data", str(BUNDLE / "seed.jsonl"), "--mode", "append", "--target",
                        f"{self.tmp}/.ob/graph.omni"], check=True, capture_output=True, env=self.env)
        self.assertEqual(self.ready(), ["lk-sync", "lk-crash-empty", "lk-acl", "lk-release", "lk-import-md",
                                        "lk-changelog", "lk-search", "lk-version"])
        self.assertEqual(sorted(r["slug"] for r in self.ob("blocked")),
                         ["lk-conflict", "lk-share", "lk-share-api", "lk-share-ui", "lk-sync-docs"])
        self.assertIn("open child", self.ob_fails("close", "lk-release"))
        self.assertEqual([r["slug"] for r in self.ob("reclaim")["issues"]], ["lk-queue"])
        self.assertIn("lk-queue", self.ready())


API_HEADER = "Omnigraph-Http-Api"


def from_server(status: int, body: dict) -> tuple[int, dict, bool]:
    """A response the OmniGraph server sent: it carries the API header."""
    return status, body, True


def from_proxy(status: int) -> tuple[int, None, bool]:
    """A bare status from a proxy in front of the server, such as a 504."""
    return status, None, False


def refusal(status: int, code: str, action: str, **detail) -> tuple[int, dict, bool]:
    return from_server(status, {"error": code, "code": code,
                                "disposition": {"effects": "none", "action": action}, **detail})


def mutation(name: str, affected: int) -> tuple[int, dict, bool]:
    return from_server(200, {"branch": "main", "query_name": name, "affected_nodes": affected,
                             "affected_edges": 0, "actor_id": "alice", "commit": None})


def rows(name: str, found: list[dict]) -> tuple[int, dict, bool]:
    return from_server(200, {"query_name": name, "target": {"branch": "main", "snapshot": None},
                             "row_count": len(found), "columns": sorted(found[0]) if found else [],
                             "rows": found})


class TransportTests(unittest.TestCase):
    """ob through the real CLI against a scripted server behind the HTTPS
    gateway: which commands it sends again, decided by each failure's
    disposition."""

    @classmethod
    def setUpClass(cls):
        if not OMNIGRAPH:
            raise unittest.SkipTest("omnigraph binary not found")
        cls.tmp = Path(tempfile.mkdtemp(prefix="ob-transport-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def serve(self, script: dict[str, list[tuple[int, dict | None, bool]]]) -> list[str]:
        calls: list[str] = []

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_HEAD(self):  # the CLI's discovery probe
                self.send_response(200)
                self.send_header(API_HEADER, "0.14")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                name = self.path.rsplit("/", 1)[-1]
                calls.append(name)
                status, payload, api = script[name].pop(0)
                data = json.dumps(payload).encode() if payload is not None else b""
                self.send_response(status)
                if api:
                    self.send_header(API_HEADER, "0.14")
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        gateway = Gateway(server.server_address[1], self.tmp / "certs")
        self.addCleanup(gateway.stop)
        self.home = self.tmp / f"home-{gateway.port}"
        write_operator_config(self.home / "config.yaml", gateway, {"scripted": "OG_SCRIPTED_TOKEN"})
        return calls

    def run_ob(self, *args):
        env = clean_env(OB_OMNIGRAPH=OMNIGRAPH, OB_TARGET="scripted", OB_GRAPH="beads", OB_ACTOR="alice",
                        OMNIGRAPH_HOME=str(self.home), OG_SCRIPTED_TOKEN="scripted-token")
        return subprocess.run([str(OB), "--json", *args], capture_output=True, text=True, env=env)

    def test_a_write_without_an_answer_is_not_sent_again(self):
        calls = self.serve({"close": [from_proxy(504)]})
        proc = self.run_ob("close", "ob-1", "--force")
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["outcome"], "unknown")
        self.assertEqual(calls, ["close"])

    def test_a_write_refused_before_it_started_is_sent_again(self):
        calls = self.serve({"close": [refusal(429, "too_many_requests", "retry"), mutation("close", 1)]})
        proc = self.run_ob("close", "ob-1", "--force")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(calls, ["close", "close"])

    def test_a_write_that_lost_the_race_is_run_again(self):
        conflict = refusal(409, "conflict", "refresh", read_set_conflict={"member": "graph_head:main"})
        calls = self.serve({"close": [conflict, mutation("close", 1)]})
        proc = self.run_ob("close", "ob-1", "--force")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(calls, ["close", "close"])

    def test_a_refused_write_is_not_sent_again(self):
        calls = self.serve({"close": [refusal(403, "forbidden", "refresh")]})
        proc = self.run_ob("close", "ob-1", "--force")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertNotIn("outcome", json.loads(proc.stdout))
        self.assertEqual(calls, ["close"])

    def test_reads_are_sent_again(self):
        row = {"i.slug": "ob-1", "i.title": "t", "i.kind": "task", "i.priority": 2}
        calls = self.serve({"ready": [from_proxy(504), refusal(503, "service_unavailable", "retry"),
                                      rows("ready", [row])]})
        proc = self.run_ob("ready")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual([r["slug"] for r in json.loads(proc.stdout)], ["ob-1"])
        self.assertEqual(calls, ["ready", "ready", "ready"])

    def test_a_claim_reads_the_issue_before_claiming_again(self):
        calls = self.serve({
            "claim": [from_proxy(504), mutation("claim", 1)],
            "show": [rows("show", [{"i": {"slug": "ob-1", "status": "open"}}])],
        })
        proc = self.run_ob("claim", "ob-1")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(calls, ["claim", "show", "claim"])

    def test_a_claim_that_landed_is_not_sent_again(self):
        calls = self.serve({
            "claim": [from_proxy(504)],
            "show": [rows("show", [{"i": {"slug": "ob-1", "status": "in_progress", "assignee": "alice"}}])],
        })
        proc = self.run_ob("claim", "ob-1")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(calls, ["claim", "show"])


TOKENS = {"act-admin": "local-admin-token", "act-writer": "local-writer-token", "act-reader": "local-reader-token"}


class ServedTests(unittest.TestCase):
    """ob against the served cookbook: a real server and the HTTPS gateway,
    one server target per actor, addressed with OB_TARGET and OB_GRAPH."""

    @classmethod
    def setUpClass(cls):
        if not (OMNIGRAPH and SERVER):
            raise unittest.SkipTest("omnigraph and omnigraph-server binaries not found")
        cls.tmp = Path(tempfile.mkdtemp(prefix="ob-served-"))
        cls.processes: list = []
        try:
            cls.start()
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def start(cls):
        root = cls.tmp / "cluster"
        root.mkdir()
        for name in ("schema.pg", "cluster.yaml"):
            shutil.copy(BUNDLE / name, root / name)
        for name in ("queries", "policies"):
            shutil.copytree(BUNDLE / name, root / name)
        env = clean_env(OMNIGRAPH_HOME=str(cls.tmp / "home"))
        apply = subprocess.run([OMNIGRAPH, "cluster", "apply", "--target", ".", "--config", ".", "--as",
                                "act-admin", "--json"], cwd=root, env=env, capture_output=True, text=True)
        if apply.returncode != 0:
            raise AssertionError(f"cluster apply failed: {apply.stdout}{apply.stderr}")
        # The apply keeps its admission lock; nothing else uses this root.
        lock = re.search(r"Admission lock: (\S+?);", apply.stderr).group(1)
        subprocess.run([OMNIGRAPH, "cluster", "force-unlock", lock, "--target", "."], cwd=root, env=env,
                       check=True, capture_output=True)
        port = free_port()
        cls.log = open(cls.tmp / "server.log", "w")
        server = subprocess.Popen([SERVER, "--cluster", ".", "--bind", f"127.0.0.1:{port}"], cwd=root,
                                  stdout=cls.log, stderr=subprocess.STDOUT,
                                  env={**env, "OMNIGRAPH_SERVER_BEARER_TOKENS_JSON": json.dumps(TOKENS)})
        cls.processes.append(server)

        def ready() -> bool:
            if server.poll() is not None:
                raise AssertionError(f"omnigraph-server exited: {(cls.tmp / 'server.log').read_text()}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/readyz", timeout=2) as response:
                    return json.load(response).get("ready") is True
            except urllib.error.HTTPError as exc:  # 503 until the graph is served
                exc.close()
                return False

        wait_until(ready, "omnigraph-server")
        cls.gateway = Gateway(port, cls.tmp / "certs")
        cls.operator_config = cls.tmp / "home" / "config.yaml"
        write_operator_config(cls.operator_config, cls.gateway,
                              {actor: "OG_" + actor.upper().replace("-", "_") + "_TOKEN" for actor in TOKENS})
        cls.env = clean_env(OB_OMNIGRAPH=OMNIGRAPH, OB_GRAPH="beads", OMNIGRAPH_HOME=str(cls.tmp / "home"),
                            **{"OG_" + actor.upper().replace("-", "_") + "_TOKEN": token
                               for actor, token in TOKENS.items()})

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "gateway", None):
            cls.gateway.stop()
        for process in cls.processes:
            process.terminate()  # SIGTERM: the server releases its writer lock
            try:
                process.wait(timeout=35)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if getattr(cls, "log", None):
            cls.log.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_ob(self, actor: str, *args, **env):
        merged = {**self.env, "OB_TARGET": actor, "OB_ACTOR": actor, **env}
        return subprocess.run([str(OB), "--json", *args], capture_output=True, text=True, env=merged,
                              cwd=self.tmp, timeout=120)

    def ob(self, actor: str, *args, **env):
        proc = self.run_ob(actor, *args, **env)
        if proc.returncode != 0:
            self.fail(f"ob {' '.join(args)} as {actor} failed ({proc.returncode}): {proc.stdout}{proc.stderr}")
        return json.loads(proc.stdout)

    def ready(self, actor: str) -> list[str]:
        return [row["slug"] for row in self.ob(actor, "ready", "-n", "500")]

    def test_served_journey_records_each_tokens_actor(self):
        blocker = self.ob("act-admin", "create", "served blocker")["id"]
        work = self.ob("act-admin", "create", "served work", "--deps", blocker)["id"]
        ready = self.ready("act-writer")
        self.assertIn(blocker, ready)
        self.assertNotIn(work, ready)
        self.assertEqual(self.ob("act-reader", "show", work)["links_out"][0]["slug"], blocker)
        self.assertIn(work, {r["slug"] for r in self.ob("act-reader", "blocked")})
        self.assertEqual(self.ob("act-writer", "claim", blocker)["claimed"], blocker)
        self.assertEqual(self.ob("act-writer", "close", blocker)["closed"], 1)
        self.assertIn(work, self.ready("act-reader"))
        refused = self.run_ob("act-reader", "claim", work)
        self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)  # refused, not unknown
        self.assertEqual(json.loads(refused.stdout)["detail"]["disposition"]["effects"], "none")
        events = [(e["actor"], e["type"]) for e in self.ob("act-reader", "history", blocker)]
        self.assertEqual(events, [("act-admin", "Issue"), ("act-admin", "BlockedBy"), ("act-writer", "Issue"),
                                  ("act-writer", "Issue")])

    def test_racing_served_agents_get_distinct_work(self):
        # Concurrent CLI runs share the operator configuration, whose lock the
        # CLI does not wait for; ob sends a command refused by it again.
        label = f"race-{os.getpid()}"
        issues = {self.ob("act-writer", "create", f"race {i}", "-l", label)["id"] for i in range(6)}
        agents = [f"agent-{i}" for i in range(6)]
        with concurrent.futures.ThreadPoolExecutor(len(agents)) as pool:
            claimed = list(pool.map(lambda who: self.ob("act-writer", "ready", "--claim", "-l", label,
                                                         OB_ACTOR=who)["claimed"], agents))
        self.assertEqual(set(claimed), issues)
        holders = {self.ob("act-reader", "show", slug)["assignee"] for slug in claimed}
        self.assertEqual(holders, set(agents))

    def test_plan_on_a_served_branch_then_merge(self):
        base = self.ob("act-writer", "create", "served base")["id"]
        self.ob("act-writer", "branch", "create", "served-plan")
        planned = self.ob("act-writer", "--branch", "served-plan", "create", "planned", "--deps", base)["id"]
        self.assertNotIn(planned, self.ready("act-writer") + [r["slug"] for r in self.ob("act-writer", "blocked")])
        self.ob("act-admin", "branch", "merge", "served-plan")
        self.assertEqual(self.ob("act-writer", "show", planned)["links_out"][0]["slug"], base)
        self.ob("act-writer", "branch", "delete", "served-plan")
        self.assertNotIn("served-plan", json.dumps(self.ob("act-writer", "branch", "list")))

    def test_an_explicit_operator_config_file(self):
        empty_home = self.tmp / "empty-home"
        empty_home.mkdir(exist_ok=True)
        rows = self.ob("act-reader", "ready", "-n", "500", OMNIGRAPH_HOME=str(empty_home),
                       OB_OPERATOR_CONFIG=str(self.operator_config))
        self.assertIsInstance(rows, list)

    def test_the_old_server_settings_are_refused(self):
        proc = self.run_ob("act-writer", "ready", OB_SERVER="http://127.0.0.1:8080", OB_TOKEN="local-writer-token")
        self.assertEqual(proc.returncode, 1)
        message = json.loads(proc.stdout)["error"]
        self.assertIn("OB_SERVER is no longer read: use OB_TARGET", message)
        self.assertIn("OB_TOKEN is no longer read", message)


if __name__ == "__main__":
    unittest.main()
