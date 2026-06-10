"""Read the plugin's own knobs from ``~/.hermes/config.yaml`` -> ``plugins.entries.omnigraph``.

Only plugin *behaviour* lives here (capture mode, default target, guard level, search
alias, config-path hints). Graph *definitions* never live here — they stay in the
omnigraph config (``~/omnigraph.yaml`` etc.). See RFC §6.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

_HERMES_CONFIG = Path(os.path.expanduser("~/.hermes/config.yaml"))
_DEFAULTS = {
    "capture": {"mode": "suggest"},          # suggest | auto-branch | off
    "guard": {"level": "high"},
    "default_target": None,
    "config_paths": [],
    "search_aliases": {"personal": "semantic-transcripts"},
}


def _entry() -> dict[str, Any]:
    if yaml is None or not _HERMES_CONFIG.is_file():
        return {}
    try:
        with open(_HERMES_CONFIG, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return ((data.get("plugins") or {}).get("entries") or {}).get("omnigraph") or {}
    except Exception:
        return {}


def get(key: str, default=None):
    return _entry().get(key, _DEFAULTS.get(key, default))


def capture_mode() -> str:
    return (get("capture") or {}).get("mode", "suggest")


def guard_level() -> str:
    return (get("guard") or {}).get("level", "high")


def default_target() -> str | None:
    return get("default_target")


def config_paths() -> list[str]:
    return get("config_paths") or []


def search_alias(target: str | None) -> str | None:
    aliases = get("search_aliases") or {}
    return aliases.get(target or "") or aliases.get("personal")
