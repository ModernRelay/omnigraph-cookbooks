"""Find the omnigraph config and list its graphs — for awareness only.

There are no standard config folders here (no XDG, no ~/.config/omnigraph). So the
plugin does NOT hunt folders; you point at the file via ``config_path`` (settings),
with a small fallback chain. The resolved path is surfaced in the reminder so the
model passes ``--config <path>`` to ``omnigraph`` (deterministic, cwd-independent).

Resolution (first match wins):
  config_path setting → $OMNIGRAPH_CONFIG → ~/omnigraph.yaml → ./omnigraph.yaml
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

try:
    from . import settings
except ImportError:  # standalone dev tests
    import settings


def _expand(p) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(str(p))))


@dataclass
class Config:
    path: str | None = None
    graphs: list[str] = field(default_factory=list)
    cli_graph: str | None = None
    source: str = "unresolved"


def _candidates(cwd=None) -> list[tuple[Path, str]]:
    cands: list[tuple[Path, str]] = []
    cp = settings.config_path()
    if cp:
        cands.append((_expand(cp), "config_path"))
    env = os.environ.get("OMNIGRAPH_CONFIG")
    if env:
        cands.append((_expand(env.split(os.pathsep)[0]), "env:OMNIGRAPH_CONFIG"))
    cands.append((_expand("~/omnigraph.yaml"), "home"))
    cands.append((Path(cwd or os.getcwd()) / "omnigraph.yaml", "cwd"))
    return cands


def _parse(path: Path) -> tuple[list[str], str | None]:
    if yaml is None:
        return [], None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception:
        return [], None
    graphs = sorted((data.get("graphs") or {}).keys())
    cli_graph = (data.get("cli") or {}).get("graph")
    return graphs, cli_graph


def resolve_config(cwd=None) -> Config:
    for path, source in _candidates(cwd):
        if path.is_file():
            graphs, cli_graph = _parse(path)
            return Config(path=str(path), graphs=graphs, cli_graph=cli_graph, source=source)
    return Config(path=None, source="unresolved")
