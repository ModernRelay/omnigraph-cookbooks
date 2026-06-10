"""Hermes ⇄ Omnigraph plugin — registration.

Wires guardrailed Omnigraph tools, lifecycle hooks (discovery banner, capture nudge,
the pre_tool_call guard, token redaction), the bundled skills, the `/omni` slash
command, and the `hermes omnigraph` CLI tree.

CLI-first: every tool shells the `omnigraph` binary via runner.py. No MCP.
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import schemas, tools, guards, cli

logger = logging.getLogger(__name__)

TOOLSET = "omnigraph"

# Read tools — never token-gated (discovery/doctor/reads must work without a write token).
_READ_TOOLS = [
    ("omnigraph_doctor", schemas.DOCTOR, tools.doctor),
    ("omnigraph_targets", schemas.TARGETS, tools.targets),
    ("omnigraph_schema", schemas.SCHEMA, tools.schema),
    ("omnigraph_query", schemas.QUERY, tools.query),
    ("omnigraph_search", schemas.SEARCH, tools.search),
    ("omnigraph_lint", schemas.LINT, tools.lint),
    ("omnigraph_schema_plan", schemas.PLAN, tools.schema_plan),
]

# Write tools — gated on a bearer token being present (hidden when absent).
_WRITE_TOOLS = [
    ("omnigraph_mutate", schemas.MUTATE, tools.mutate),
    ("omnigraph_capture", schemas.CAPTURE, tools.capture_tool),
]
_WRITE_REQUIRES_ENV = ["OMNIGRAPH_BEARER_TOKEN"]


def register(ctx) -> None:
    for name, schema, handler in _READ_TOOLS:
        ctx.register_tool(name=name, toolset=TOOLSET, schema=schema, handler=handler)
    for name, schema, handler in _WRITE_TOOLS:
        ctx.register_tool(name=name, toolset=TOOLSET, schema=schema, handler=handler,
                          requires_env=_WRITE_REQUIRES_ENV)

    # Lifecycle hooks
    ctx.register_hook("on_session_start", tools.on_session_start)   # discover configs -> registry
    ctx.register_hook("pre_llm_call", tools.banner)                 # consult-first + capture nudge
    ctx.register_hook("pre_tool_call", guards.inspect)              # block dangerous raw omnigraph calls
    ctx.register_hook("transform_tool_result", tools.harden_output) # redact leaked tokens

    # Bundled skills (namespaced omnigraph:<name>; not auto-indexed — banner names them)
    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            md = child / "SKILL.md"
            if child.is_dir() and md.exists():
                try:
                    ctx.register_skill(child.name, md)
                except Exception as exc:  # never abort registration over one skill
                    logger.warning("omnigraph: failed to register skill %s: %s", child.name, exc)

    # In-session slash command (CLI + gateways)
    ctx.register_command("omni", lambda raw: tools.slash(ctx, raw),
                         description="Omnigraph: doctor | targets | schema [target] | q <alias> [args]",
                         args_hint="doctor | targets | schema <t> | q <alias> ...")

    # Terminal subcommand tree (out-of-band setup/repair)
    ctx.register_cli_command(name="omnigraph",
                             help="Set up & operate Omnigraph for Hermes",
                             setup_fn=cli.setup_argparse, handler_fn=cli.dispatch)

    logger.info("omnigraph plugin registered: %d read + %d write tools, 4 hooks, 2 skills",
                len(_READ_TOOLS), len(_WRITE_TOOLS))
