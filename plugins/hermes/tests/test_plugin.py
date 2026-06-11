"""Offline unit tests for the slim omnigraph Hermes plugin.

No network, no hermes, no omnigraph binary needed.
Run: ~/.hermes/hermes-agent/venv/bin/python plugins/hermes/tests/test_plugin.py
"""

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

_PKG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "omniplug", _PKG / "__init__.py", submodule_search_locations=[str(_PKG)]
)
P = importlib.util.module_from_spec(spec)
sys.modules["omniplug"] = P
spec.loader.exec_module(P)

discovery, settings, hooks, cli = P.discovery, P.settings, P.hooks, P.cli


# --- discovery: explicit-path resolution, no folder hunting ---------------

def test_config_path_setting_wins():
    # an existing config_path wins over the ~/omnigraph.yaml fallback
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "my-omni.yaml"
        p.write_text("graphs:\n  g: {uri: 's3://x'}\n")
        settings.config_path = lambda: str(p)
        try:
            r = discovery.resolve_config()
            assert r.source == "config_path" and r.path == str(p) and r.graphs == ["g"]
        finally:
            settings.config_path = lambda: None


def test_env_then_graph_parse():
    settings.config_path = lambda: None
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "omnigraph.yaml"
        p.write_text("graphs:\n  alpha: {uri: 's3://x'}\n  beta: {uri: 'https://y'}\ncli:\n  graph: alpha\n")
        os.environ["OMNIGRAPH_CONFIG"] = str(p)
        try:
            r = discovery.resolve_config()
            assert r.source == "env:OMNIGRAPH_CONFIG" and r.path == str(p)
            assert r.graphs == ["alpha", "beta"] and r.cli_graph == "alpha"
        finally:
            del os.environ["OMNIGRAPH_CONFIG"]


def test_unresolved_when_nothing_found():
    settings.config_path = lambda: None
    os.environ.pop("OMNIGRAPH_CONFIG", None)
    with tempfile.TemporaryDirectory() as d:
        r = discovery.resolve_config(cwd=d)
        # may resolve ~/omnigraph.yaml on this machine (source 'home'); never crashes
        assert r.source in ("home", "unresolved")


# --- settings: autocapture normalization ----------------------------------

def test_autocapture_default_and_normalization():
    settings._entry = lambda: {}
    assert settings.autocapture() == "branch"          # default
    settings._entry = lambda: {"autocapture": "MAIN"}
    assert settings.autocapture() == "main"            # case-insensitive
    settings._entry = lambda: {"autocapture": "weird"}
    assert settings.autocapture() == "branch"          # invalid -> default
    settings._entry = lambda: {"autocapture": "off"}
    assert settings.autocapture() == "off"
    settings._entry = lambda: {}                        # reset


# --- hooks: banner content per autocapture --------------------------------

def _fake_cfg():
    hooks._cache["cfg"] = discovery.Config(
        path="/tmp/omnigraph.yaml", graphs=["personal", "modernrelay"],
        cli_graph="personal", source="test")


def test_banner_branch_main_off():
    _fake_cfg()
    settings.default_target = lambda: None
    for mode, expect_save in [("off", False), ("branch", True), ("main", True)]:
        settings.autocapture = lambda m=mode: m
        b = hooks.build_banner()
        assert ("SAVE it" in b) == expect_save, mode
        assert "--config /tmp/omnigraph.yaml" in b      # surfaces the path
        assert "omnigraph-best-practices" in b          # points at the skill
        assert "personal, modernrelay" in b             # lists graphs
    settings.autocapture = lambda: "branch"
    assert "feature branch" in hooks.build_banner()
    settings.autocapture = lambda: "main"
    assert "main branch" in hooks.build_banner()


def test_banner_none_when_no_config():
    hooks._cache["cfg"] = discovery.Config(path=None, source="unresolved")
    assert hooks.build_banner() is None


def test_pre_llm_call_first_turn_only():
    _fake_cfg()
    settings.autocapture = lambda: "branch"
    settings.remind_every_turn = lambda: False
    assert hooks.pre_llm_call(is_first_turn=True) is not None
    assert hooks.pre_llm_call(is_first_turn=False) is None      # not every turn
    settings.remind_every_turn = lambda: True
    assert hooks.pre_llm_call(is_first_turn=False) is not None  # every turn


# --- registration: zero tools ---------------------------------------------

def test_register_zero_tools():
    class Ctx:
        def __init__(s): s.hooks = []; s.clis = []; s.tools = []
        def register_hook(s, n, cb): s.hooks.append(n)
        def register_cli_command(s, **k): s.clis.append(k.get("name"))
        def register_tool(s, **k): s.tools.append(k.get("name"))
    c = Ctx(); P.register(c)
    assert c.tools == []
    assert c.hooks == ["on_session_start", "pre_llm_call"]
    assert c.clis == ["omnigraph"]


# --- no schema coupling: the v1 hardcoded constructs must NOT return -------

def test_no_hardcoded_schema_bits():
    src = "\n".join((_PKG / f).read_text() for f in
                    ("discovery.py", "settings.py", "hooks.py", "cli.py", "__init__.py"))
    for banned in ("APPEND_ONLY", "_TYPE_HINTS", "candidate_node_types", "_SIGNALS", "def classify"):
        assert banned not in src, f"reintroduced schema coupling: {banned}"


def _all_tests():
    return [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in _all_tests():
        try:
            fn(); print(f"PASS {name}"); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {type(e).__name__}: {e}"); failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
