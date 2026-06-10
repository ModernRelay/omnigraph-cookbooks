"""Offline unit tests for the omnigraph Hermes plugin.

No network, no hermes, no omnigraph binary needed — these test pure logic:
build_argv flag ordering/format, the verify.py state machine (mocked runner),
the pre_tool_call guard matrix, capture.classify, and discovery resolution.

Run:  ~/.hermes/hermes-agent/venv/bin/python tests/test_plugin.py
(works under pytest too — functions are named test_*).
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

# --- load the plugin as a package (relative imports resolve) ---------------
_PKG_DIR = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "omniplug", _PKG_DIR / "__init__.py", submodule_search_locations=[str(_PKG_DIR)]
)
P = importlib.util.module_from_spec(spec)
sys.modules["omniplug"] = P
spec.loader.exec_module(P)

runner, verify, guards, capture, discovery = P.runner, P.verify, P.guards, P.capture, P.discovery
BIN = runner.OMNIGRAPH_BIN


# --- build_argv: ordering, format, params ----------------------------------

def test_build_argv_query_flags_after_subcommand_and_jsonl():
    argv = runner.build_argv("query", config="c.yaml", target="personal", alias="who-is", args=["alice"])
    assert argv[0] == BIN and argv[1] == "query"
    assert argv.index("query") < argv.index("--config")          # global flags AFTER subcommand
    assert "--format" in argv and argv[argv.index("--format") + 1] == "jsonl"
    assert argv[-1] == "alice"                                   # positional alias arg last
    assert "read" not in argv                                    # never deprecated verb


def test_build_argv_mutate_uses_json_not_format():
    argv = runner.build_argv("mutate", config="c.yaml", target="personal", alias="add-x")
    assert "--json" in argv and "--format" not in argv


def test_build_argv_schema_show_is_raw_pg():
    argv = runner.build_argv("schema show", config="c.yaml", target="personal")
    assert "--json" not in argv and "--format" not in argv       # raw .pg text


def test_build_argv_schema_plan_uses_json_and_schema():
    argv = runner.build_argv("schema plan", target="personal", schema_path="next.pg")
    assert "--json" in argv
    assert argv[argv.index("--schema") + 1] == "next.pg"


def test_build_argv_params_file():
    argv = runner.build_argv("query", config="c.yaml", params_file="/tmp/p.json")
    assert argv[argv.index("--params-file") + 1] == "/tmp/p.json"


# --- verify.py state machine (mocked runner) -------------------------------

class _FakeRunner:
    """Stateful fake: commit-list returns the current head; mutate behavior is set per test."""
    def __init__(self, head="A", mutate=None, advance_head_to=None):
        self.head = head
        self.mutate_kw = mutate or {}
        self.advance = advance_head_to
        self.calls = []

    def run(self, subcommand, **kw):
        self.calls.append(subcommand)
        if subcommand == "commit list":
            return runner.RunResult(argv=[], returncode=0, stdout="", stderr="", ok=True,
                                    parsed={"commits": [{"manifest_version": 1, "graph_commit_id": self.head}]})
        if subcommand == "mutate":
            if self.advance:                       # simulate a write that landed
                self.head = self.advance
            return runner.RunResult(argv=["omnigraph", "mutate"], returncode=self.mutate_kw.get("rc", 0),
                                    stdout="", stderr=self.mutate_kw.get("stderr", ""),
                                    ok=self.mutate_kw.get("ok", True), http=self.mutate_kw.get("http"))
        return runner.RunResult(argv=[], returncode=0, stdout="", stderr="", ok=True)


def _with_fake(fake, fn):
    orig = verify.runner.run
    verify.runner.run = fake.run
    try:
        return fn()
    finally:
        verify.runner.run = orig


def _mutate(is_remote, **kw):
    return verify.mutate_verified(config="c", target="personal", is_remote=is_remote,
                                  branch="hermes-personal", env_file=None, alias="add-x", **kw)


def test_verify_local_applied():
    r = _with_fake(_FakeRunner(mutate={"ok": True}), lambda: _mutate(False))
    assert r["status"] == "applied"


def test_verify_remote_landed_when_head_advances():
    r = _with_fake(_FakeRunner(head="A", advance_head_to="B", mutate={"ok": True}),
                   lambda: _mutate(True))
    assert r["status"] == "landed" and r["head_before"] == "A" and r["head_after"] == "B"


def test_verify_remote_504_did_not_land():
    r = _with_fake(_FakeRunner(head="A", mutate={"ok": False, "http": 504, "rc": 1}),
                   lambda: _mutate(True))
    assert r["status"] == "did_not_land"
    assert "append-only" in r["guidance"].lower()


def test_verify_remote_409_safe_retry():
    r = _with_fake(_FakeRunner(head="A", mutate={"ok": False, "http": 409}), lambda: _mutate(True))
    assert r["status"] == "safe_retry" and r["http"] == 409


def test_verify_remote_unchanged_clean_is_unknown():
    r = _with_fake(_FakeRunner(head="A", mutate={"ok": True}), lambda: _mutate(True))
    assert r["status"] == "unknown"


# --- guard matrix ----------------------------------------------------------

def test_guard_matrix():
    block = [
        "omnigraph read --alias who-is a",
        "omnigraph change --alias add-x",
        "omnigraph mutate --alias add-x",
        "omnigraph load --data x.jsonl --mode overwrite s3://b/r",
        "omnigraph schema apply --schema n.pg --target personal",
        "omnigraph --config ~/o.yaml query --alias who-is a",
        "echo hi && omnigraph mutate --alias add-x",
    ]
    allow = [
        "omnigraph query --target personal --alias who-is a",
        "omnigraph snapshot --target personal --json",
        "omnigraph commit list --target personal --json",
        "omnigraph schema show --target personal",
        "set -a && source .env.omni && omnigraph query --alias who-is a",
    ]
    for cmd in block:
        assert guards.inspect("terminal", {"command": cmd}), f"should block: {cmd}"
    for cmd in allow:
        assert guards.inspect("terminal", {"command": cmd}) is None, f"should allow: {cmd}"
    assert guards.inspect("omnigraph_query", {"x": 1}) is None     # non-terminal ignored
    assert guards.inspect("terminal", {"command": "ls -la"}) is None


# --- capture.classify ------------------------------------------------------

def test_capture_classify():
    assert "task" in capture.classify("remind me to email Bob")
    assert "person" in capture.classify("her email is jane@acme.com")
    assert set(capture.classify("Meeting with Sam tomorrow about the project")) >= {"commitment", "project"}
    assert capture.classify("what is 2 + 2?") == []               # nothing to capture
    assert capture.classify("") == []


# --- discovery resolution --------------------------------------------------

def test_discovery_explicit_and_walkup():
    assert discovery.resolve(explicit_config="/x/y.yaml").source == "explicit"
    with tempfile.TemporaryDirectory() as d:
        sub = Path(d) / "a" / "b"
        sub.mkdir(parents=True)
        (Path(d) / "omnigraph.yaml").write_text("graphs:\n  g: {uri: s3://x}\n")
        found = discovery.walk_up_config(str(sub))
        assert found and found.name == "omnigraph.yaml"


def test_discovery_env_var(monkeypatch=None):
    os.environ["OMNIGRAPH_CONFIG"] = "/tmp/env-omni.yaml"
    try:
        r = discovery.resolve()
        assert r.source == "env:OMNIGRAPH_CONFIG" and r.config_path.endswith("env-omni.yaml")
    finally:
        del os.environ["OMNIGRAPH_CONFIG"]


# --- runner http classification (precise, stderr-only) ---------------------

def test_http_classification_no_false_positive():
    # commit ids / version numbers must NOT trip the classifier
    assert runner._classify_http('{"graph_commit_id":"01KSX409...","manifest_version":429}') is None
    assert runner._classify_http("error: HTTP 504 gateway timeout") == 504
    assert runner._classify_http("manifest_conflict: stale") == 409
    assert runner._classify_http("429 Too Many Requests; Retry-After: 5") == 429


# --- runner -----------------------------------------------------------------

def _all_tests():
    g = globals()
    return [(n, f) for n, f in sorted(g.items()) if n.startswith("test_") and callable(f)]


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in _all_tests():
        try:
            fn()
            print(f"PASS {name}")
            passed += 1
        except Exception as e:
            print(f"FAIL {name}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
