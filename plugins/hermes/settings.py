"""Plugin knobs, read from ``~/.hermes/config.yaml`` -> ``plugins.entries.omnigraph``.

Only behaviour lives here — never graph definitions (those stay in your omnigraph.yaml).
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

_DEFAULTS = {
    "config_path": None,          # explicit path to omnigraph.yaml (no folder hunting)
    "autocapture": "branch",      # off | branch | main
    "default_target": None,       # graph name to suggest by default
    "remind_every_turn": False,   # inject the reminder each turn, not just first turn
}


def _hermes_config() -> Path:
    """The active Hermes config — honors HERMES_HOME (profiles/sandboxes), not just ~/.hermes."""
    home = os.environ.get("HERMES_HOME") or "~/.hermes"
    return Path(os.path.expanduser(home)) / "config.yaml"


def _entry() -> dict:
    cfg = _hermes_config()
    if yaml is None or not cfg.is_file():
        return {}
    try:
        with open(cfg, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return ((data.get("plugins") or {}).get("entries") or {}).get("omnigraph") or {}
    except Exception:
        return {}


def get(key: str):
    return _entry().get(key, _DEFAULTS.get(key))


def config_path() -> str | None:
    return get("config_path")


def autocapture() -> str:
    v = str(get("autocapture") or "branch").strip().lower()
    return v if v in ("off", "branch", "main") else "branch"


def default_target() -> str | None:
    return get("default_target")


def remind_every_turn() -> bool:
    return bool(get("remind_every_turn"))
