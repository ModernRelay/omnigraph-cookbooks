"""Capture-by-default: classify shared info + scaffold its import into the graph.

Two parts:
  * ``classify(text)`` — a cheap heuristic the pre_llm_call banner uses to decide
    whether the user's message contains graph-worthy info (and nudge accordingly).
  * ``capture(args)`` — the ``omnigraph_capture`` tool. It does the deterministic,
    must-not-skip parts of the import procedure: fetch the schema, find candidate
    node types, and **resolve identity via ExternalID first** (so the model never
    creates a duplicate Person), then hands the model exact next steps to issue a
    parameterized ``omnigraph_mutate`` to a branch. Honors the capture policy
    (suggest | auto-branch | off).

Full NL->mutation automation via ``ctx.llm`` is a deliberate future enhancement; the
scaffolding design keeps the model in the loop and depends on no gated LLM access.
"""

from __future__ import annotations

import json
import os
import re
import tempfile

try:
    from . import discovery, runner, settings
except ImportError:        # standalone dev tests
    import discovery, runner, settings


_SIGNALS = {
    "task": [r"\bremind me\b", r"\bto-?do\b", r"\bneed to\b", r"\bdon'?t forget\b",
             r"\bdeadline\b", r"\bdue\b", r"\bfollow[- ]?up\b", r"\baction item\b"],
    "person": [r"\bmet\b", r"\bintroduced\b", r"\bworks at\b", r"\bnew (colleague|contact|friend)\b",
               r"\b(his|her|their) (email|number|phone|handle)\b"],
    "place": [r"\bmoved to\b", r"\bvisiting\b", r"\btravell?ing to\b", r"\brestaurant\b", r"\bcafe\b"],
    "project": [r"\bproject\b", r"\bworking on\b", r"\blaunching\b", r"\bbuilding\b", r"\bshipping\b"],
    "commitment": [r"\bmeeting\b", r"\bcall\b", r"\bappointment\b", r"\bscheduled\b", r"\btomorrow\b",
                   r"\bnext week\b", r"\bat \d{1,2}(:\d{2})?\s?(am|pm)\b",
                   r"\b(mon|tues?|wed(nes)?|thurs?|fri|sat(ur)?|sun)(day)?\b"],
    "note": [r"\bdecided\b", r"\bnote that\b", r"\bidea\b", r"\bremember that\b"],
    "media": [r"\bread\b", r"\bwatch(ed|ing)\b", r"\blistening to\b", r"\bbook\b", r"\bmovie\b",
              r"\bpodcast\b", r"\barticle\b"],
}
_COMPILED = {cat: [re.compile(p, re.I) for p in pats] for cat, pats in _SIGNALS.items()}

_TYPE_HINTS = {
    "task": ["Task", "ActionItem", "Todo"],
    "person": ["Person"],
    "place": ["Place", "Location"],
    "project": ["Project"],
    "commitment": ["Event", "Meeting", "Appointment", "Commitment"],
    "note": ["Note", "Decision"],
    "media": ["Media", "Book", "Article", "Content", "Consumption"],
}

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d[\d\-\s().]{6,}\d")
_HANDLE_RE = re.compile(r"(?<!\w)@[\w.]{2,}")


def classify(text: str | None) -> list[str]:
    """Return the graph-worthy categories detected in *text* (empty = nothing to capture)."""
    if not text:
        return []
    hits = [cat for cat, pats in _COMPILED.items() if any(p.search(text) for p in pats)]
    if (_EMAIL_RE.search(text) or _HANDLE_RE.search(text)) and "person" not in hits:
        hits.append("person")
    return sorted(hits)


def _extract_identifiers(text: str) -> dict[str, list[str]]:
    return {
        "emails": _EMAIL_RE.findall(text or ""),
        "phones": [p.strip() for p in _PHONE_RE.findall(text or "") if len(re.sub(r"\D", "", p)) >= 7],
        "handles": _HANDLE_RE.findall(text or ""),
    }


def _candidate_types(schema_text: str, categories: list[str]) -> list[str]:
    found: list[str] = []
    for cat in categories:
        for hint in _TYPE_HINTS.get(cat, []):
            if re.search(rf"\bnode\s+{re.escape(hint)}\b", schema_text):
                found.append(hint)
    return sorted(set(found))


def _write_schema(schema_text: str) -> str | None:
    if not schema_text:
        return None
    fd, path = tempfile.mkstemp(prefix="omni-schema-", suffix=".pg")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(schema_text)
    return path


def capture(args: dict, **kwargs) -> str:
    """omnigraph_capture handler. Returns a JSON string; never raises."""
    try:
        info_text = (args or {}).get("info_text") or ""
        if not info_text.strip():
            return json.dumps({"status": "error", "error": "info_text is required"})

        mode = (args or {}).get("mode") or settings.capture_mode()
        if mode == "off":
            return json.dumps({"status": "disabled", "reason": "capture.mode=off"})

        target = (args or {}).get("target") or settings.default_target()
        categories = (args or {}).get("categories") or classify(info_text)

        res = discovery.resolve(target=target)
        if not res.config_path:
            return json.dumps({"status": "error",
                               "error": "no omnigraph config found — run omnigraph_doctor"})
        cfg, tgt, info = res.config_path, res.target, res.info
        env_file = info.env_file if info else None
        aliases = (info.aliases if info else {}) or {}

        # 1) schema (so the model uses real type/property/enum names)
        s = runner.run("schema show", config=cfg, target=tgt, env_file=env_file)
        schema_text = s.stdout if s.ok else ""
        schema_file = s.stdout_file or _write_schema(schema_text)
        candidate_types = _candidate_types(schema_text, categories)

        # 2) identity resolution via ExternalID FIRST (never create a duplicate Person)
        ids = _extract_identifiers(info_text)
        identity_matches = []
        flat_ids = ids["emails"] + ids["phones"] + ids["handles"]
        if flat_ids and "who-is-ext" in aliases:
            for ext in flat_ids:
                q = runner.run("query", alias="who-is-ext", args=[ext],
                               config=cfg, target=tgt, env_file=env_file)
                rows = q.records[1:] if q.records else []
                identity_matches.append({"external_id": ext, "existing": rows})

        recommended_branch = f"capture-{tgt or 'graph'}" if mode == "auto-branch" else None

        next_steps = [
            f"Read the schema at {schema_file} for exact node/edge/property/enum names.",
            "If a person is involved, check identity_matches: reuse an existing Person's slug; "
            "only create a new Person (+ ExternalID) when there is no match.",
            "Build a PARAMETERIZED mutation (params, never inlined) for the candidate node type(s).",
        ]
        if mode == "auto-branch":
            next_steps.append(f"Call omnigraph_mutate(target='{tgt}', branch='{recommended_branch}', ...) "
                              "then report the landed/did_not_land verdict. Never write to main.")
        else:  # suggest
            next_steps.append("PROPOSE the mutation to the user; on confirmation call omnigraph_mutate "
                              "to a feature branch (never main).")

        return json.dumps({
            "status": "proposal",
            "mode": mode,
            "target": tgt,
            "config": cfg,
            "categories": categories,
            "schema_file": schema_file,
            "candidate_node_types": candidate_types,
            "identifiers_found": ids,
            "identity_matches": identity_matches,
            "recommended_branch": recommended_branch,
            "next_steps": next_steps,
        })
    except Exception as e:  # never raise out of a tool handler
        return json.dumps({"status": "error", "error": f"{type(e).__name__}: {e}"})
