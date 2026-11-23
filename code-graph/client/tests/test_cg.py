"""Tests for cg that need no server: the diff review, display names, name
resolution and the omnigraph command lines cg builds.

The fixtures are real `omnigraph branch diff --json` output from OmniGraph
0.15.0: hono PR #5267 against its base, and the base loaded back over the PR.
Run with: python3 -m unittest discover -s code-graph/client/tests
"""

import argparse
import collections
import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import cg_cli  # noqa: E402

FIXTURES = HERE / "fixtures"
HELPER = "src/router/`utils.ts`/createNullObject."
MODULE = "src/router/`utils.ts`/"
CHANGED = {
    "src/router/reg-exp-router/`router.ts`/RegExpRouter#`#buildMatcher`().",
    "src/router/reg-exp-router/`router.ts`/RegExpRouter#`<constructor>`().",
    "src/router/reg-exp-router/`router.ts`/RegExpRouter#add().",
    "src/router/reg-exp-router/`router.ts`/RegExpRouter#buildAllMatchers().",
    "src/router/trie-router/`node.ts`/Node#`#pushHandlerSets`().",
}
BASE, HEAD = "a10592f3e1864cbe277619633db953450a6b1e4b", "4b44abe1b5c7755aac8555d7943611555183450b"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


class Summarize(unittest.TestCase):
    def test_pull_request(self):
        s = cg_cli.summarize(fixture("pr-5267.diff.json"))
        self.assertEqual((s["from_revision"], s["to_revision"]), (BASE, HEAD))
        self.assertEqual([r["symbol"] for r in s["added"]], [MODULE, HELPER])
        self.assertEqual(s["removed"], [])
        self.assertEqual({r["symbol"] for r in s["changed"]}, CHANGED)
        self.assertTrue(all(r["fields"] == ["digest"] for r in s["changed"]))
        # 58 definitions moved; the five that also changed count as changed.
        self.assertEqual(s["moved"], 53)
        refs = s["references"]
        self.assertEqual((len(refs["added"]), len(refs["removed"]), len(refs["changed"])), (18, 0, 0))
        self.assertEqual(collections.Counter(r["to"] for r in refs["added"]), {HELPER: 14, MODULE: 4})
        self.assertIn({"from": "src/router/reg-exp-router/`router.ts`/RegExpRouter#add().", "to": HELPER,
                       "call": True, "sites": 1}, refs["added"])
        self.assertEqual(s["members"]["added"], [{"from": HELPER, "to": MODULE}])
        self.assertEqual(s["implementations"], {"added": [], "removed": [], "changed": []})

    def test_revert_removes_what_the_pull_request_added(self):
        s = cg_cli.summarize(fixture("revert-5267.diff.json"))
        self.assertEqual((s["from_revision"], s["to_revision"]), (HEAD, BASE))
        self.assertEqual([r["symbol"] for r in s["removed"]], [MODULE, HELPER])
        self.assertEqual(s["added"], [])
        self.assertEqual({r["symbol"] for r in s["changed"]}, CHANGED)
        self.assertEqual(len(s["references"]["removed"]), 18)
        self.assertEqual(s["references"]["added"], [])
        self.assertEqual(s["members"]["removed"], [{"from": HELPER, "to": MODULE}])

    def test_edge_update_keeps_both_sides(self):
        diff = {"changes": [{"kind": "edge", "type": {"name": "References"}, "op": "update",
                             "before": {"properties": {"call": False, "sites": 1}, "endpoints": {"from": "a/`b.ts`/f().", "to": "a/`b.ts`/g()."}},
                             "after": {"properties": {"call": True, "sites": 2}, "endpoints": {"from": "a/`b.ts`/f().", "to": "a/`b.ts`/g()."}}}]}
        s = cg_cli.summarize(diff)
        self.assertEqual(s["references"]["changed"], [{"from": "a/`b.ts`/f().", "to": "a/`b.ts`/g().", "call": True,
                                                        "sites": 2, "before": {"call": False, "sites": 1}}])
        self.assertIn("call False to True, sites 1 to 2", cg_cli.render(s, "b", "main"))


class Render(unittest.TestCase):
    def test_text(self):
        text = cg_cli.render(cg_cli.summarize(fixture("pr-5267.diff.json")), "pr-5267", "main")
        first = text.splitlines()[0]
        self.assertEqual(first, "pr-5267 against main, revision a10592f3..4b44abe1: 2 symbols added, 0 removed, "
                                "5 changed; 18 references added, 0 removed, 0 changed; 53 definitions only moved.")
        self.assertIn("  src/router/utils.ts:createNullObject (constant)", text)
        self.assertIn("  src/router/reg-exp-router/router.ts:RegExpRouter.add() (method): code changed", text)
        self.assertIn("  src/router/reg-exp-router/router.ts:RegExpRouter.add() now calls "
                      "src/router/utils.ts:createNullObject", text)
        self.assertNotIn("Removed:", text)

    def test_markdown(self):
        text = cg_cli.render(cg_cli.summarize(fixture("revert-5267.diff.json")), "revert-5267", "pr-5267",
                             markdown=True)
        self.assertTrue(text.startswith("### Code graph: revert-5267 against pr-5267"))
        self.assertIn("**Removed**", text)
        self.assertIn("- `src/router/utils.ts:createNullObject` (constant)", text)
        self.assertIn("`src/router/trie-router/node.ts:Node.#pushHandlerSets()` no longer calls "
                      "`src/router/utils.ts:createNullObject`", text)


class Display(unittest.TestCase):
    def test_forms(self):
        cases = {
            MODULE: "src/router/utils.ts",
            HELPER: "src/router/utils.ts:createNullObject",
            "src/`router.ts`/Router#add().": "src/router.ts:Router.add()",
            "src/`router.ts`/Router#": "src/router.ts:Router",
            "src/router/reg-exp-router/`router.ts`/RegExpRouter#`#buildMatcher`().":
                "src/router/reg-exp-router/router.ts:RegExpRouter.#buildMatcher()",
            "src/router/reg-exp-router/`router.ts`/RegExpRouter#`<constructor>`().":
                "src/router/reg-exp-router/router.ts:RegExpRouter.<constructor>()",
        }
        for key, shown in cases.items():
            self.assertEqual(cg_cli.display(key), shown, key)

    def test_unparseable_key_is_shown_as_is(self):
        self.assertEqual(cg_cli.display("not a descriptor ("), "not a descriptor (")


class FakeGraph:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def query(self, name, params=None, branch=None):
        self.calls.append((name, params, branch))
        return self.rows


ADD_ROWS = [
    {"s.symbol": "src/`router.ts`/Router#add().", "s.kind": "method", "s.path": "src/router.ts", "l.line": 42},
    {"s.symbol": "src/router/trie-router/`router.ts`/TrieRouter#add().", "s.kind": "method",
     "s.path": "src/router/trie-router/router.ts", "l.line": 9},
]


class Resolve(unittest.TestCase):
    def test_a_key_is_used_as_given(self):
        g = FakeGraph([])
        self.assertEqual(cg_cli.resolve(g, HELPER), HELPER)
        self.assertEqual(g.calls, [])

    def test_a_unique_name(self):
        g = FakeGraph(ADD_ROWS[:1])
        self.assertEqual(cg_cli.resolve(g, "add", branch="pr-1"), "src/`router.ts`/Router#add().")
        self.assertEqual(g.calls, [("symbols_named", {"name": "add"}, "pr-1")])

    def test_an_ambiguous_name_lists_the_candidates(self):
        with self.assertRaises(cg_cli.CgError) as caught:
            cg_cli.resolve(FakeGraph(ADD_ROWS), "add")
        self.assertEqual(caught.exception.status, cg_cli.EXIT_USAGE)
        self.assertIn("2 symbols are named 'add'", str(caught.exception))
        self.assertIn("src/router/trie-router/`router.ts`/TrieRouter#add().", str(caught.exception))

    def test_path_narrows_a_name(self):
        g = FakeGraph(ADD_ROWS)
        self.assertEqual(cg_cli.resolve(g, "add", path="src/router/trie-router/"),
                         "src/router/trie-router/`router.ts`/TrieRouter#add().")
        # The path filters in the query, so a name with more definitions than
        # the read's limit is still found in its directory.
        self.assertEqual(g.calls, [("symbols_named_in", {"name": "add", "path": "src/router/trie-router"}, None)])
        self.assertEqual(cg_cli.resolve(FakeGraph(ADD_ROWS), "add", path="src/router.ts"),
                         "src/`router.ts`/Router#add().")

    def test_no_match(self):
        with self.assertRaises(cg_cli.CgError) as caught:
            cg_cli.resolve(FakeGraph([]), "nothing")
        self.assertEqual(caught.exception.status, cg_cli.EXIT_USAGE)


class Limits(unittest.TestCase):
    def test_the_limits_match_the_query_file(self):
        text = cg_cli.QUERIES.read_text()
        limits = {}
        for block in re.split(r"(?m)^(?=query )", text):
            name, limit = re.match(r"query (\w+)", block), re.search(r"(?m)^\s*limit (\d+)\s*$", block)
            if name and limit:
                limits[name.group(1)] = int(limit.group(1))
        # most_referenced is a top-20 list by design, not a cut list.
        limits.pop("most_referenced")
        self.assertEqual(limits, cg_cli.LIMITS)

    def test_a_read_that_returns_its_limit_says_it_may_be_cut(self):
        limit = cg_cli.LIMITS["callers"]
        self.assertEqual(cg_cli.cut_note("callers", [{}] * (limit - 1)), "")
        self.assertIn(f"stops at {limit}", cg_cli.cut_note("callers", [{}] * limit))
        self.assertEqual(cg_cli.cut_note("implementers", [{}] * 10_000), "")


class Commands(unittest.TestCase):
    """The omnigraph command lines cg sends, with the CLI replaced."""

    def fake_cli(self, branches=("main",), fail=None):
        calls = []

        def run(argv, capture_output, text):
            calls.append(argv)
            verb = argv[1]
            if fail and verb == fail[0]:
                return subprocess.CompletedProcess(argv, 1, json.dumps(fail[1]), "")
            if verb == "branch":
                return subprocess.CompletedProcess(argv, 0, json.dumps({"branches": list(branches)}), "")
            if verb == "load":
                return subprocess.CompletedProcess(argv, 0, json.dumps({"commit": {"graph_commit_id": "c1"}}), "")
            return subprocess.CompletedProcess(argv, 0, json.dumps({"rows": []}), "")

        return calls, mock.patch.object(cg_cli.subprocess, "run", side_effect=run)

    def test_a_server_target_runs_stored_queries(self):
        calls, patch = self.fake_cli()
        with patch:
            cg_cli.Graph("ck-reader", "code").query("callers", {"symbol": HELPER}, "pr-1")
        argv = calls[0]
        self.assertEqual(argv[1:3], ["query", "callers"])
        self.assertEqual(argv[-5:], ["--target", "ck-reader", "--graph", "code", "--json"])
        self.assertIn("--branch", argv)

    def test_impact_lifts_the_traversal_work_cap(self):
        calls, patch = self.fake_cli()
        with patch:
            cg_cli.Graph("./code.omni", "code").query("impact", {"symbol": HELPER})
            cg_cli.Graph("./code.omni", "code").query("callers", {"symbol": HELPER})
        self.assertIn("traversal_work_limit=1000000000000", calls[0])
        self.assertNotIn("--set", calls[1])
        # A server's stored query takes no session settings.
        calls, patch = self.fake_cli()
        with patch:
            cg_cli.Graph("ck-reader", "code").query("impact", {"symbol": HELPER})
        self.assertNotIn("--set", calls[0])

    def test_a_local_target_runs_the_cookbook_query_file(self):
        calls, patch = self.fake_cli()
        with patch:
            cg_cli.Graph("./code.omni", "code").query("revision")
        argv = calls[0]
        self.assertEqual(argv[1:5], ["query", "--query", str(cg_cli.QUERIES), "revision"])
        self.assertNotIn("--graph", argv)

    def test_load_creates_a_missing_branch_from_its_base(self):
        calls, patch = self.fake_cli(branches=("main",))
        with patch:
            cg_cli.Graph("ck-agent", "code").load(Path("r.jsonl"), "pr-1", "main")
        load = calls[-1]
        self.assertEqual(load[1:8], ["load", "--data", "r.jsonl", "--mode", "overwrite", "--yes", "--branch"])
        self.assertEqual(load[8:11], ["pr-1", "--from", "main"])

    def test_load_onto_an_existing_branch_or_main_forks_nothing(self):
        for branch, branches in (("pr-1", ("main", "pr-1")), ("main", ("main",))):
            calls, patch = self.fake_cli(branches=branches)
            with patch:
                cg_cli.Graph("ck-writer", "code").load(Path("r.jsonl"), branch, "main")
            self.assertNotIn("--from", calls[-1], branch)

    def test_a_large_local_load_raises_the_write_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            big = Path(tmp) / "big.jsonl"
            with open(big, "wb") as f:
                f.truncate(cg_cli.WRITE_MAX_BYTES + 1)
            calls, patch = self.fake_cli()
            with patch:
                cg_cli.Graph("./code.omni", "code").load(big, "main", "main")
            self.assertIn(f"write_max_bytes={cg_cli.WRITE_MAX_BYTES + 1}", calls[-1])
            # A server load request is capped and takes no settings: refused before any call.
            calls, patch = self.fake_cli()
            with patch, self.assertRaises(cg_cli.CgError) as caught:
                cg_cli.Graph("ck-agent", "code").load(big, "main", "main")
            self.assertEqual(caught.exception.status, cg_cli.EXIT_USAGE)
            self.assertEqual(calls, [])
            # A small file loads with the default.
            small = Path(tmp) / "small.jsonl"
            small.write_text("{}\n")
            calls, patch = self.fake_cli()
            with patch:
                cg_cli.Graph("./code.omni", "code").load(small, "main", "main")
            self.assertNotIn("--set", calls[-1])

    def test_a_local_load_onto_main_builds_its_indexes(self):
        build_seed = cg_cli._converter()
        with tempfile.TemporaryDirectory() as tmp:
            revision = Path(tmp) / "r.jsonl"
            revision.write_text("".join(json.dumps({"type": t, "data": {}}) + "\n" for t in build_seed.TYPES)
                                + "".join(json.dumps({"edge": e, "from": "a", "to": "b"}) + "\n"
                                          for e in build_seed.EDGES))
            # optimize reaches main only, and only a local graph.
            for target, branch, optimized in (("./code.omni", "main", True), ("./code.omni", "pr-1", None),
                                              ("ck-agent", "main", None)):
                calls, patch = self.fake_cli(branches=("main", "pr-1"))
                args = argparse.Namespace(branch=branch, base="main", allow_missing=False, json=True)
                out = io.StringIO()
                with patch, contextlib.redirect_stdout(out):
                    cg_cli._load(args, cg_cli.Graph(target, "code"), revision)
                self.assertEqual([a[1] for a in calls].count("optimize"), int(bool(optimized)), (target, branch))
                self.assertEqual(json.loads(out.getvalue()).get("optimized"), optimized, (target, branch))
            # A failed optimize leaves the committed load reported, and says so.
            _, patch = self.fake_cli(fail=("optimize", {"error": "busy"}))
            args = argparse.Namespace(branch="main", base="main", allow_missing=False, json=True)
            out, err = io.StringIO(), io.StringIO()
            with patch, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                cg_cli._load(args, cg_cli.Graph("./code.omni", "code"), revision)
            self.assertEqual(json.loads(out.getvalue())["commit"], "c1")
            self.assertFalse(json.loads(out.getvalue())["optimized"])
            self.assertIn("the load committed, but optimize failed", err.getvalue())

    def test_a_failed_load_reports_whether_anything_changed(self):
        for effects, status in (("none", cg_cli.EXIT_FAILED), ("unknown", cg_cli.EXIT_UNKNOWN),
                                ("partial", cg_cli.EXIT_UNKNOWN), (None, cg_cli.EXIT_UNKNOWN)):
            payload = {"error": "refused", "disposition": {"effects": effects} if effects else {}}
            _, patch = self.fake_cli(branches=("main", "pr-1"), fail=("load", payload))
            with patch, self.assertRaises(cg_cli.CgError) as caught:
                cg_cli.Graph("ck-agent", "code").load(Path("r.jsonl"), "pr-1", "main")
            self.assertEqual(caught.exception.status, status, effects)

    def test_index_refuses_a_checkout_that_differs_from_its_commit(self):
        # The fixture repository ignores the user's git configuration.
        env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "PATH": "/usr/bin:/bin"}
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            sh = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *a],  # noqa: E731
                                           cwd=repo, env=env, check=True, capture_output=True)
            sh("init", "-q")
            (repo / "a.ts").write_text("export const a = 1\n")
            sh("add", "a.ts")
            sh("commit", "-q", "-m", "a")
            # status.showUntrackedFiles=no must not hide an untracked source file.
            sh("config", "status.showUntrackedFiles", "no")
            args = argparse.Namespace(checkout=str(repo), allow_dirty=False)
            for name, text in (("b.ts", "export const b = 2\n"), ("a.ts", "export const a = 3\n")):
                (repo / name).write_text(text)
                with mock.patch.dict(cg_cli.os.environ, env), \
                        mock.patch.object(cg_cli, "indexer_binary", side_effect=AssertionError("indexer ran")), \
                        self.assertRaises(cg_cli.CgError) as caught:
                    cg_cli.cmd_index(args, cg_cli.Graph("./code.omni", "code"))
                self.assertEqual(caught.exception.status, cg_cli.EXIT_USAGE, name)

    def test_a_failed_read_changes_nothing(self):
        _, patch = self.fake_cli(fail=("query", {"error": "forbidden", "code": "forbidden"}))
        with patch, self.assertRaises(cg_cli.CgError) as caught:
            cg_cli.Graph("ck-reader", "code").query("revision")
        self.assertEqual(caught.exception.status, cg_cli.EXIT_FAILED)


class Completeness(unittest.TestCase):
    def test_every_type_is_required_for_an_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.jsonl"
            path.write_text('{"type":"Revision","data":{}}\n{"type":"Symbol","data":{}}\n')
            counts = cg_cli.revision_types(path)
        with self.assertRaises(cg_cli.CgError) as caught:
            cg_cli.check_complete(counts, allow_missing=False)
        self.assertEqual(caught.exception.status, cg_cli.EXIT_USAGE)
        self.assertIn("Location", str(caught.exception))
        cg_cli.check_complete(counts, allow_missing=True)

    def test_the_cookbook_files_are_complete(self):
        bundle = HERE.parents[1]
        for name in ("seed.jsonl", "examples/pr-5267.jsonl"):
            cg_cli.check_complete(cg_cli.revision_types(bundle / name), allow_missing=False)


class Arguments(unittest.TestCase):
    def test_json_is_accepted_after_the_command(self):
        args = cg_cli.build_parser().parse_args(["diff", "pr-1", "--json"])
        self.assertTrue(args.json)
        args = cg_cli.build_parser().parse_args(["--json", "diff", "pr-1"])
        self.assertTrue(args.json)
        self.assertFalse(cg_cli.build_parser().parse_args(["diff", "pr-1"]).json)


if __name__ == "__main__":
    unittest.main()
