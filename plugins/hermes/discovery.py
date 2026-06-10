"""Omnigraph config discovery + a tool-neutral project registry.

The plugin never hardcodes ``~/omnigraph.yaml``. It resolves which config to use
via a documented precedence ladder (first match wins — NO cross-file merge, per
cluster-config axiom 15) and *always* passes ``--config <path>`` to the CLI so
behaviour is deterministic regardless of cwd. A small registry maps graph/target
names -> config path so an agent can resolve **by name** rather than by cwd accident.

Resolution order (highest precedence first):
  1. explicit config path (caller-supplied)
  2. ``OMNIGRAPH_CONFIG`` env var
  3. registry lookup by ``target`` name (the config that defines that graph)
  4. nearest ``omnigraph.yaml`` walking up from cwd (git/cargo style)
  5. user-global search list (XDG, ~/.config, ~/.omnigraph, ~/omnigraph.yaml, ~/.hermes)

This is the *removable bridge* for what should ultimately live in the `omnigraph`
binary itself (see the RFC Appendix B / config-discovery proposal).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - yaml ships with hermes
    yaml = None


# ---- locations -------------------------------------------------------------

def _expand(p: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(p)))


def _xdg(var: str, default: str) -> Path:
    return _expand(os.environ.get(var) or default)


def global_config_candidates() -> list[Path]:
    """User-global config search list, in precedence order (first existing wins)."""
    return [
        _xdg("XDG_CONFIG_HOME", "~/.config") / "omnigraph" / "config.yaml",
        _expand("~/.config/omnigraph/config.yaml"),
        _expand("~/.omnigraph/config.yaml"),
        _expand("~/omnigraph.yaml"),
        _expand("~/.hermes/omnigraph/config.yaml"),
    ]


def registry_path() -> Path:
    """Tool-neutral state file (NOT under ~/.hermes) so other tools can read it too."""
    return _xdg("XDG_STATE_HOME", "~/.local/state") / "omnigraph" / "registry.yaml"


# ---- config model ----------------------------------------------------------

@dataclass
class ConfigInfo:
    path: str
    kind: str = "operator"                 # "operator" (omnigraph.yaml) | "cluster" (cluster.yaml dir)
    graphs: list[str] = field(default_factory=list)
    graph_uris: dict[str, str] = field(default_factory=dict)   # name -> uri
    aliases: dict[str, Any] = field(default_factory=dict)
    cli_graph: str | None = None
    env_file: str | None = None            # absolute path, resolved relative to the config dir

    def is_remote(self, target: str | None) -> bool:
        uri = self.graph_uris.get(target or self.cli_graph or "", "")
        return uri.startswith("http://") or uri.startswith("https://")


def _safe_load(path: Path) -> dict:
    if yaml is None or not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_config(path: str | Path) -> ConfigInfo | None:
    """Parse an omnigraph.yaml (operator config). Returns None if unreadable."""
    p = Path(path)
    data = _safe_load(p)
    if not data:
        return None
    graphs = data.get("graphs") or {}
    graph_uris = {
        name: (g or {}).get("uri", "")
        for name, g in graphs.items()
        if isinstance(g, dict)
    }
    cli = data.get("cli") or {}
    auth = data.get("auth") or {}
    env_file = auth.get("env_file")
    if env_file:
        env_file = str((p.parent / os.path.expanduser(env_file)).resolve())
    return ConfigInfo(
        path=str(p.resolve()),
        kind="operator",
        graphs=sorted(graphs.keys()),
        graph_uris=graph_uris,
        aliases=data.get("aliases") or {},
        cli_graph=cli.get("graph"),
        env_file=env_file,
    )


# ---- discovery -------------------------------------------------------------

def walk_up_config(start: str | Path | None = None) -> Path | None:
    """Nearest ``omnigraph.yaml`` walking up from *start* (default cwd)."""
    cur = Path(start or os.getcwd()).resolve()
    for d in [cur, *cur.parents]:
        cand = d / "omnigraph.yaml"
        if cand.is_file():
            return cand
    return None


def scan(cwd: str | Path | None = None, extra_roots: list[str] | None = None) -> list[ConfigInfo]:
    """Discover operator configs on this machine and (re)write the registry.

    Scans: $OMNIGRAPH_CONFIG, cwd walk-up, the global candidate list, plus any
    extra roots (e.g. common project dirs). Deduped by resolved path.
    """
    seen: dict[str, ConfigInfo] = {}

    def add(path: Path | None):
        if not path or not Path(path).is_file():
            return
        info = load_config(path)
        if info and info.path not in seen:
            seen[info.path] = info

    env_cfg = os.environ.get("OMNIGRAPH_CONFIG")
    if env_cfg:
        for chunk in env_cfg.split(os.pathsep):       # KUBECONFIG-style list tolerated
            add(_expand(chunk))
    add(walk_up_config(cwd))
    for cand in global_config_candidates():
        add(cand)
    for root in (extra_roots or []):
        add(_expand(root) / "omnigraph.yaml")

    infos = list(seen.values())
    write_registry(infos)
    return infos


# ---- registry --------------------------------------------------------------

def read_registry() -> list[ConfigInfo]:
    data = _safe_load(registry_path())
    out: list[ConfigInfo] = []
    for entry in (data.get("configs") or []):
        if not isinstance(entry, dict) or not entry.get("path"):
            continue
        out.append(ConfigInfo(
            path=entry["path"],
            kind=entry.get("kind", "operator"),
            graphs=entry.get("graphs", []) or [],
            graph_uris=entry.get("graph_uris", {}) or {},
            aliases=entry.get("aliases", {}) or {},
            cli_graph=entry.get("cli_graph"),
            env_file=entry.get("env_file"),
        ))
    return out


def write_registry(infos: list[ConfigInfo]) -> None:
    if yaml is None:
        return
    rp = registry_path()
    try:
        rp.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "configs": [
                {
                    "path": i.path,
                    "kind": i.kind,
                    "graphs": i.graphs,
                    "graph_uris": i.graph_uris,
                    "cli_graph": i.cli_graph,
                    "env_file": i.env_file,
                }
                for i in infos
            ],
        }
        with open(rp, "w", encoding="utf-8") as fh:
            yaml.safe_dump(payload, fh, sort_keys=False)
    except Exception:
        pass  # registry is a convenience; never fatal


# ---- resolution ------------------------------------------------------------

@dataclass
class Resolution:
    config_path: str | None
    target: str | None
    info: ConfigInfo | None
    source: str                       # which ladder rung resolved it (for doctor/--show-origin)


def _registry_or_scan(cwd=None) -> list[ConfigInfo]:
    infos = read_registry()
    if not infos:
        infos = scan(cwd=cwd)
    return infos


def resolve(target: str | None = None,
            explicit_config: str | None = None,
            cwd: str | Path | None = None) -> Resolution:
    """Resolve (config_path, target) deterministically. First match wins; no merge."""
    # 1. explicit config
    if explicit_config:
        p = _expand(explicit_config)
        return Resolution(str(p), target, load_config(p), "explicit")

    # 2. env var (first entry of a possible list)
    env_cfg = os.environ.get("OMNIGRAPH_CONFIG")
    if env_cfg:
        p = _expand(env_cfg.split(os.pathsep)[0])
        return Resolution(str(p), target, load_config(p), "env:OMNIGRAPH_CONFIG")

    # 3. by target name via registry (cwd-independent)
    if target:
        for info in _registry_or_scan(cwd):
            if target in info.graphs:
                # reload fresh so aliases/env_file/uris are complete (registry is a sparse index)
                return Resolution(info.path, target, load_config(info.path) or info, "registry:by-target")

    # 4. project walk-up
    proj = walk_up_config(cwd)
    if proj:
        return Resolution(str(proj), target, load_config(proj), "project:walk-up")

    # 5. user-global search list
    for cand in global_config_candidates():
        if cand.is_file():
            return Resolution(str(cand), target, load_config(cand), "global")

    return Resolution(None, target, None, "unresolved")
