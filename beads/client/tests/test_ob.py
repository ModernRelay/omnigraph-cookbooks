"""End-to-end tests for ob against a real OmniGraph graph.

Run from beads/client:  python3 -m unittest discover -s tests -v
The omnigraph binary comes from $OB_OMNIGRAPH, else PATH (the cookbooks pin
the 0.13.0 release). Served-mode tests also need omnigraph-server and skip
without it.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent   # beads/client
BUNDLE = HERE.parent                              # beads/: schema, queries, policies, cluster.yaml
OB = HERE / "ob"
REPO = BUNDLE.parent


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


class ObCase(unittest.TestCase):
    """A fresh project directory with an initialized local graph per test."""

    embed = False

    def setUp(self):
        if not OMNIGRAPH:
            self.skipTest("omnigraph binary not found")
        self.tmp = tempfile.mkdtemp(prefix="ob-test-")
        self.env = {**os.environ, "OB_OMNIGRAPH": OMNIGRAPH, "OB_DIR": f"{self.tmp}/.ob", "OB_ACTOR": "alice"}
        for key in ("OB_STORE", "OB_SERVER", "OB_GRAPH"):
            self.env.pop(key, None)
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

    def commits(self) -> int:
        proc = subprocess.run([OMNIGRAPH, "commit", "list", "--store", f"{self.tmp}/.ob/graph.omni", "--json"],
                              capture_output=True, text=True, check=True)
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
        subprocess.run([OMNIGRAPH, "load", "--data", str(edge), "--mode", "merge", "--store",
                        f"{self.tmp}/.ob/graph.omni", "--quiet"], check=True, capture_output=True)
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


class KnowledgeTests(ObCase):
    def test_comments_memories_and_prime(self):
        a = self.create("auth bug")
        self.ob("comment", a, "reproduced on staging")
        self.ob("remember", "Session tokens live in redis", "--key", "tokens", "--about", a)
        self.ob("remember", "Run migrations before tests")
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
        self.assertEqual([m["slug"] for m in self.ob("memories")], ["run-migrations-before-tests"])

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


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(OMNIGRAPH and SERVER, "omnigraph-server binary not found")
class ServedModeTests(unittest.TestCase):
    """The cluster in this directory, served, with stored queries and policy."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ob-served-")
        cluster = Path(cls.tmp) / "cluster"
        cluster.mkdir()
        for name in ("cluster.yaml", "schema.pg"):
            shutil.copy(BUNDLE / name, cluster / name)
        for directory in ("queries", "policies"):
            shutil.copytree(BUNDLE / directory, cluster / directory)
        env = {**os.environ, "OMNIGRAPH_HOME": cls.tmp}
        apply = subprocess.run([OMNIGRAPH, "cluster", "apply", "--config", str(cluster), "--as", "act-admin", "--json"],
                               capture_output=True, text=True, env=env)
        if apply.returncode != 0:
            raise RuntimeError(f"cluster apply failed: {apply.stdout}{apply.stderr}")
        lock = _lock_id(apply.stderr + apply.stdout)
        if lock:
            subprocess.run([OMNIGRAPH, "cluster", "force-unlock", lock, "--config", str(cluster)],
                           capture_output=True, text=True, env=env)
        cls.port = free_port()
        cls.tokens = {"act-admin": "admin-secret", "act-writer": "writer-secret", "act-reader": "reader-secret"}
        server_env = {**env, "OMNIGRAPH_SERVER_BEARER_TOKENS_JSON": json.dumps(cls.tokens)}
        cls.server = subprocess.Popen([SERVER, "--cluster", str(cluster), "--bind", f"127.0.0.1:{cls.port}"],
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=server_env)
        deadline = time.time() + 60
        while time.time() < deadline:
            probe = subprocess.run(["curl", "-sf", f"http://127.0.0.1:{cls.port}/readyz"], capture_output=True)
            if probe.returncode == 0:
                break
            time.sleep(0.2)
        else:
            cls.server.kill()
            raise RuntimeError("server did not become ready: " + cls.server.stdout.read().decode()[-2000:])

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(timeout=30)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_ob(self, actor: str, *args):
        env = {**os.environ, "OB_OMNIGRAPH": OMNIGRAPH, "OB_SERVER": f"http://127.0.0.1:{self.port}",
               "OB_GRAPH": "beads", "OB_ACTOR": actor, "OMNIGRAPH_HOME": self.tmp,
               "OMNIGRAPH_BEARER_TOKEN": self.tokens[actor]}
        env.pop("OB_DIR", None)
        env.pop("OB_STORE", None)
        return subprocess.run([str(OB), "--json", *args], capture_output=True, text=True, env=env)

    def ob(self, actor: str, *args):
        proc = self.run_ob(actor, *args)
        if proc.returncode != 0:
            self.fail(f"ob {' '.join(args)} as {actor} failed: {proc.stdout}{proc.stderr}")
        return json.loads(proc.stdout)

    def test_served_workflow_records_token_actor_and_enforces_policy(self):
        a = self.ob("act-admin", "create", "served blocker")["id"]
        b = self.ob("act-admin", "create", "served work", "--deps", a)["id"]
        self.assertIn(a, [r["slug"] for r in self.ob("act-writer", "ready")])
        self.assertNotIn(b, [r["slug"] for r in self.ob("act-writer", "ready")])
        self.ob("act-writer", "claim", a)
        self.ob("act-writer", "close", a)
        self.assertIn(b, [r["slug"] for r in self.ob("act-reader", "ready")])
        denied = self.run_ob("act-reader", "claim", b)
        self.assertNotEqual(denied.returncode, 0)
        events = self.ob("act-reader", "history", a)
        self.assertEqual([(e["actor"], e["type"]) for e in events],
                         [("act-admin", "Issue"), ("act-admin", "BlockedBy"), ("act-writer", "Issue"),
                          ("act-writer", "Issue")])


def _lock_id(text: str) -> str | None:
    import re
    match = re.search(r"Admission lock: ([0-9A-Z]+)", text)
    return match.group(1) if match else None


if __name__ == "__main__":
    unittest.main()
