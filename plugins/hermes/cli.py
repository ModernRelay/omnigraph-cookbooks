"""`hermes omnigraph <subcommand>` — out-of-band setup/repair from a terminal.

Subcommands: setup, doctor, migrate-config, targets, schema. These share the same
handlers as the model-facing tools (tools.py). NOTE: this subcommand tree only
exists once the plugin is enabled (`hermes plugins enable omnigraph`) — a plugin
cannot enable itself, so `setup` does *post-enable* config only.
"""

from __future__ import annotations

import json
import re
import shutil

try:
    from . import tools, discovery, settings
except ImportError:        # standalone dev tests
    import tools, discovery, settings


def setup_argparse(subparser) -> None:
    subs = subparser.add_subparsers(dest="omni_cmd")
    subs.add_parser("doctor", help="Preflight: binary, configs, tokens, reachability")
    subs.add_parser("targets", help="List discovered graphs + aliases")
    sc = subs.add_parser("schema", help="Dump a graph's schema to a file")
    sc.add_argument("target", nargs="?", help="Graph name (default: config's cli.graph)")
    mc = subs.add_parser("migrate-config", help="Fix omnigraph.yaml rot (read->query, table->jsonl)")
    mc.add_argument("--config", help="Path to omnigraph.yaml (default: resolved)")
    mc.add_argument("--write", action="store_true", help="Apply changes (default: dry-run)")
    subs.add_parser("setup", help="Post-enable wizard (doctor + migrate-config suggestions)")
    subparser.set_defaults(func=dispatch)


# ---- migrate-config --------------------------------------------------------

_RULES = [
    (re.compile(r"(^\s*command:\s*)read\b"), r"\1query"),
    (re.compile(r"(^\s*command:\s*)change\b"), r"\1mutate"),
    (re.compile(r"(^\s*output_format:\s*)table\b"), r"\1jsonl"),
    (re.compile(r"^targets:(\s*)$"), r"graphs:\1"),
]


def _transform(lines: list[str]) -> tuple[list[str], list[tuple[int, str, str]]]:
    out, changes = [], []
    for i, line in enumerate(lines, 1):
        new = line
        for pat, repl in _RULES:
            new2 = pat.sub(repl, new)
            if new2 != new:
                new = new2
        if new != line:
            changes.append((i, line.rstrip("\n"), new.rstrip("\n")))
        out.append(new)
    return out, changes


def _migrate_config(args) -> None:
    path = getattr(args, "config", None) or (discovery.resolve().config_path)
    if not path:
        print("No omnigraph config found. Pass --config or run `hermes omnigraph doctor`.")
        return
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    new_lines, changes = _transform(lines)
    if not changes:
        print(f"✓ {path}: nothing to migrate (no deprecated read/change, table output, or targets:).")
        return
    print(f"{path}: {len(changes)} change(s){' (DRY-RUN)' if not args.write else ''}:")
    for ln, old, new in changes:
        print(f"  line {ln}:")
        print(f"    - {old.strip()}")
        print(f"    + {new.strip()}")
    if args.write:
        shutil.copy2(path, path + ".bak")
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(new_lines)
        print(f"✓ written (backup at {path}.bak). Graph definitions untouched.")
    else:
        print("Re-run with --write to apply (a .bak backup is made).")


# ---- dispatch --------------------------------------------------------------

def _pp(json_str: str) -> None:
    try:
        print(json.dumps(json.loads(json_str), indent=2))
    except Exception:
        print(json_str)


def dispatch(args) -> None:
    cmd = getattr(args, "omni_cmd", None)
    if cmd == "doctor":
        _pp(tools.doctor({}))
    elif cmd == "targets":
        _pp(tools.targets({}))
    elif cmd == "schema":
        _pp(tools.schema({"target": getattr(args, "target", None)}))
    elif cmd == "migrate-config":
        _migrate_config(args)
    elif cmd == "setup":
        print("=== omnigraph plugin setup (post-enable) ===\n")
        print("1) Doctor:")
        _pp(tools.doctor({}))
        print("\n2) Config migration suggestions (dry-run):")
        _migrate_config(type("A", (), {"config": None, "write": False})())
        print("\n3) Capture policy:", settings.capture_mode(),
              "| default target:", settings.default_target())
        print("\nNext: set knobs under plugins.entries.omnigraph in ~/.hermes/config.yaml "
              "(capture.mode, default_target, search_aliases). Load skill_view(\"omnigraph:best-practices\").")
    else:
        print("Usage: hermes omnigraph <doctor|targets|schema [target]|migrate-config [--write]|setup>")
