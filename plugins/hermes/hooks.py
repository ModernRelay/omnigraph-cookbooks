"""Lifecycle hooks — the plugin's whole runtime surface.

* ``on_session_start`` — resolve the omnigraph config once and cache it.
* ``pre_llm_call`` — inject the awareness/consult banner + (optionally) the autocapture
  save instruction. This is the plugin's entire "use the graph" mechanism: no tools,
  no schema knowledge. The model judges relevance and composes any write itself, from
  the live schema, using the ``omnigraph`` CLI via the terminal.

Hook signatures verified against Hermes source (`hermes_cli/plugins.py` / `hooks.py`):
  on_session_start(session_id, **kwargs)
  pre_llm_call(session_id, user_message, conversation_history, is_first_turn, model, platform, **kwargs)
    -> {"context": str} | str | None   (appended to the user message; cache-preserving)
"""

from __future__ import annotations

try:
    from . import discovery, settings
except ImportError:  # standalone dev tests
    import discovery, settings

_cache: dict = {"cfg": None}


def on_session_start(session_id=None, **kwargs):
    try:
        _cache["cfg"] = discovery.resolve_config()
    except Exception:
        _cache["cfg"] = None
    return None


def _cfg():
    if _cache["cfg"] is None:
        try:
            _cache["cfg"] = discovery.resolve_config()
        except Exception:
            pass
    return _cache["cfg"]


def build_banner() -> str | None:
    """The injected reminder. None when no config is discovered (stay quiet)."""
    cfg = _cfg()
    if not cfg or not cfg.path:
        return None

    graphs = ", ".join(cfg.graphs) if cfg.graphs else "(none defined)"
    dflt = settings.default_target() or cfg.cli_graph
    target_hint = f" (default target: {dflt})" if dflt else ""

    lines = [
        f"[omnigraph] Your Omnigraph graph is the source of truth for people, tasks, projects, "
        f"commitments, places and relationships. Graphs: {graphs}{target_hint}. Config: {cfg.path}.",
        f"Before answering factual questions about any of those, CONSULT the graph: run `omnigraph` "
        f"through the terminal — always pass `--config {cfg.path} --target <graph>` — and fetch the "
        f"schema first (`omnigraph schema show --config {cfg.path} --target <graph>`). If unsure how, "
        f'load skill_view("omnigraph-best-practices"). Use canonical verbs `query`/`mutate` (not '
        f"`read`/`change`); don't guess fields; don't `load --mode overwrite` a populated graph.",
    ]

    mode = settings.autocapture()
    if mode in ("branch", "main"):
        where = ("a NEW feature branch and suggest a merge (never write directly to main)"
                 if mode == "branch" else "the main branch")
        lines.append(
            f"If this turn contains durable info worth keeping (a task, person, note, decision, plan, "
            f"place, or something the user read/watched), SAVE it to the graph: write it to {where}. "
            f"Resolve a person via their existing ExternalID before creating a new one (avoid duplicates)."
        )
    return "\n".join(lines)


def pre_llm_call(session_id=None, user_message="", is_first_turn=False, **kwargs):
    try:
        if not is_first_turn and not settings.remind_every_turn():
            return None
        text = build_banner()
        return {"context": text} if text else None
    except Exception:
        return None
