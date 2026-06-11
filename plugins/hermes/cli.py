"""`hermes omnigraph doctor | setup` — human-facing diagnostics & onboarding.

`doctor` is awareness/diagnostics (no model-facing tool, by design). `setup` installs
the best-practices skill from the GitHub tap (the repo is already a valid tap).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

try:
    from . import discovery, settings
except ImportError:  # standalone dev tests
    import discovery, settings

OMNIGRAPH = shutil.which("omnigraph") or "/opt/homebrew/bin/omnigraph"
TAP_REPO = "ModernRelay/omnigraph-cookbooks"
SKILL = "omnigraph-best-practices"


def setup_argparse(subparser) -> None:
    subs = subparser.add_subparsers(dest="omni_cmd")
    subs.add_parser("doctor", help="Check binary, config, graphs, tokens")
    subs.add_parser("setup", help="Install the omnigraph-best-practices skill (tap) + config tips")
    subparser.set_defaults(func=dispatch)


def _run(argv, timeout=20):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:  # pragma: no cover
        return 127, "", str(e)


def _token_env(path, graph):
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return ((data.get("graphs") or {}).get(graph) or {}).get("bearer_token_env")
    except Exception:
        return None


def doctor() -> dict:
    rc, out, err = _run([OMNIGRAPH, "version"])
    cfg = discovery.resolve_config()
    report = {
        "binary": OMNIGRAPH,
        "version": (out or err).strip().splitlines()[0] if (out or err) else None,
        "binary_ok": rc == 0,
        "config": cfg.path,
        "config_source": cfg.source,
        "autocapture": settings.autocapture(),
        "graphs": {},
    }
    issues = []
    if not cfg.path:
        issues.append("no omnigraph config found — set plugins.entries.omnigraph.config_path")
    for g in (cfg.graphs or []):
        tenv = _token_env(cfg.path, g) if cfg.path else None
        tset = bool(os.environ.get(tenv)) if tenv else None
        report["graphs"][g] = {"token_env": tenv, "token_set": tset}
        if tenv and not tset:
            issues.append(f"{g}: token env {tenv} not set")
    report["ok"] = report["binary_ok"] and bool(cfg.path) and not issues
    report["issues"] = issues
    return report


def setup() -> None:
    hermes = shutil.which("hermes") or "hermes"
    print("=== omnigraph plugin setup ===\n")
    print(f"Installing the '{SKILL}' skill from the GitHub tap ({TAP_REPO}):")
    for cmd in (["skills", "tap", "add", TAP_REPO],
                ["skills", "install", f"{TAP_REPO}/{SKILL}"]):
        print(f"  $ hermes {' '.join(cmd)}")
        rc, out, err = _run([hermes, *cmd], timeout=120)
        msg = (out or err).strip()
        if msg:
            print("    " + msg.splitlines()[-1][:200])
    print("\nConfig — add to ~/.hermes/config.yaml under plugins.entries.omnigraph:")
    print("  config_path: ~/omnigraph.yaml   # point at your omnigraph.yaml")
    print("  autocapture: branch             # off | branch | main")
    print("  default_target: personal")
    print("\nRuntime: tool/CLI use needs the chat_completions harness "
          "(model.openai_runtime: auto), not codex_app_server.\n")
    print("Doctor:")
    print(json.dumps(doctor(), indent=2))


def dispatch(args) -> None:
    cmd = getattr(args, "omni_cmd", None)
    if cmd == "doctor":
        print(json.dumps(doctor(), indent=2))
    elif cmd == "setup":
        setup()
    else:
        print("Usage: hermes omnigraph <doctor|setup>")
