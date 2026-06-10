"""pre_tool_call guard — block dangerous raw `omnigraph` calls.

Even when the model bypasses the typed tools and runs `omnigraph` through the
generic `terminal` tool, this hook intercepts the high-severity mistakes BEFORE
execution by returning ``{"action": "block", "message": ...}``. It is
allow-by-default: only an explicit danger set is blocked; every read-only call
passes untouched, so the guard can't become a nuisance.

Hook signature (verified against hermes source `_DEFAULT_PAYLOADS`):
    pre_tool_call(tool_name, args, session_id, task_id, tool_call_id, **kwargs)
Return ``{"action": "block", "message": str}`` to veto; ``None`` to allow.
"""

from __future__ import annotations

import shlex

# shell tokens that separate one command from the next
_OPERATORS = {"&&", "||", "|", ";", "&", "\n"}
# leading wrappers we skip to find the real `omnigraph ...` invocation
_PREFIX_CMDS = {"set", "source", ".", "env", "exec", "command", "sudo", "time", "nice"}
# read-only / safe subcommands — always allowed
_SAFE = {"query", "snapshot", "export", "commit", "lint", "version", "graphs",
         "optimize", "help"}


def _segments(command: str) -> list[list[str]]:
    """Return the token lists that follow each `omnigraph` invocation in *command*."""
    try:
        toks = shlex.split(command, comments=True)
    except Exception:
        toks = command.split()
    segs: list[list[str]] = []
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        is_omni = t == "omnigraph" or t.endswith("/omnigraph")
        if is_omni:
            j = i + 1
            seg: list[str] = []
            while j < n and toks[j] not in _OPERATORS:
                seg.append(toks[j])
                j += 1
            segs.append(seg)
            i = j
        else:
            i += 1
    return segs


def _first_word_and_sub(seg: list[str]) -> tuple[str | None, str | None, list[str]]:
    """Return (subcommand, sub-subcommand, flags-seen-before-subcommand)."""
    pre_flags: list[str] = []
    words: list[str] = []
    for tok in seg:
        if tok.startswith("-"):
            if not words:
                pre_flags.append(tok)        # a flag appeared before any subcommand word
            continue
        words.append(tok)
    sub = words[0] if words else None
    subsub = words[1] if len(words) > 1 else None
    return sub, subsub, pre_flags


def _verdict(seg: list[str]) -> str | None:
    """Return a block message for a dangerous segment, else None (allow)."""
    if not seg:
        return None
    sub, subsub, pre_flags = _first_word_and_sub(seg)

    # global flags placed BEFORE the subcommand (omnigraph rejects this)
    if pre_flags and any(f.split("=")[0] in ("--config", "--target", "--uri") for f in pre_flags):
        return ("Global flags must come AFTER the subcommand "
                "(e.g. `omnigraph query --config X`, not `omnigraph --config X query`). "
                "Prefer the omnigraph_* tools, which order flags correctly.")

    if sub in ("read", "change"):
        canonical = "query" if sub == "read" else "mutate"
        return (f"`omnigraph {sub}` is the deprecated alias for `{canonical}`. "
                f"Use the omnigraph_{canonical} tool (or `omnigraph {canonical}`).")

    if sub in ("mutate", "change"):
        return ("Don't run mutations through the terminal — use the omnigraph_mutate tool so the "
                "remote-write verification ritual runs (it compares the commit head before/after and "
                "never blind-retries after a 504). Writes also go to a branch, never main.")

    if sub == "load" and ("--mode" in seg and "overwrite" in seg):
        return ("`load --mode overwrite` truncates the whole branch — data-loss. Use a feature branch "
                "(`ingest`) or the omnigraph_mutate tool instead of overwriting in place.")

    if sub == "schema" and subsub == "apply":
        return ("Run a schema PLAN before applying — use omnigraph_schema_plan first and apply "
                "deliberately. `schema apply` is destructive and main-only.")

    return None


def inspect(tool_name: str | None = None, args: dict | None = None, **kwargs):
    """pre_tool_call hook. Block dangerous raw `omnigraph` terminal calls."""
    if tool_name != "terminal":
        return None
    command = ""
    if isinstance(args, dict):
        command = args.get("command") or args.get("cmd") or ""
    if "omnigraph" not in command:
        return None
    for seg in _segments(command):
        msg = _verdict(seg)
        if msg:
            return {"action": "block", "message": "[omnigraph guard] " + msg}
    return None
