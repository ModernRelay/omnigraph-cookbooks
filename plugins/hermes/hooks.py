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

import logging

try:
    from . import discovery, settings
except ImportError:  # standalone dev tests
    import discovery, settings

logger = logging.getLogger(__name__)
_cache: dict = {"cfg": None}


def on_session_start(session_id=None, **kwargs):
    try:
        _cache["cfg"] = discovery.resolve_config()
        cfg = _cache["cfg"]
        logger.info("[omnigraph hook] on_session_start: config=%s graphs=%s",
                    cfg.path if cfg else None, cfg.graphs if cfg else None)
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
        f"[omnigraph] Your Omnigraph graph is the source of truth for the entities and facts it models. "
        f"Graphs: {graphs}{target_hint}. Config: {cfg.path}.",
        f"Before answering a factual question the graph could answer, CONSULT it: run `omnigraph` "
        f"through the terminal — always pass `--config {cfg.path} --target <graph>` — and read the "
        f"schema first (`omnigraph schema show --config {cfg.path} --target <graph>`) so you use its real "
        f'types. If unsure how, load skill_view("omnigraph-best-practices"). Use canonical verbs '
        f"`query`/`mutate` (not `read`/`change`); don't guess fields; don't `load --mode overwrite` a "
        f"populated graph.",
    ]

    mode = settings.autocapture()
    if mode in ("branch", "main"):
        where = ("a NEW feature branch and suggest a merge (never write directly to main)"
                 if mode == "branch" else "the main branch")
        lines.append(
            f"If this turn contains durable information the graph should hold, SAVE it: write it to {where}. "
            f"Read the schema first to use the right types, and avoid duplicates by checking for an existing "
            f"matching record before creating one."
        )
    return "\n".join(lines)


def pre_llm_call(session_id=None, user_message="", is_first_turn=False, **kwargs):
    try:
        if not is_first_turn and not settings.remind_every_turn():
            return None
        text = build_banner()
        if text:
            logger.info("[omnigraph hook] pre_llm_call: injected banner (autocapture=%s, first_turn=%s, %d chars)",
                        settings.autocapture(), is_first_turn, len(text))
            return {"context": text}
        return None
    except Exception:
        return None
