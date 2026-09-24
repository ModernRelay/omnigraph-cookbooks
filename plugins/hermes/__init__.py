"""Hermes ⇄ Omnigraph plugin (slim) — registration.

Three jobs, nothing else: make Hermes **aware** of Omnigraph, point at the **skill**
(installed via tap), and **remind** the model to consult/save. No tools, no guard —
every operation is the `omnigraph` CLI, run by the model through the terminal, so the
plugin doesn't drift as the CLI evolves.
"""

from __future__ import annotations

import logging

from . import hooks, cli

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    ctx.register_hook("on_session_start", hooks.on_session_start)
    ctx.register_hook("pre_llm_call", hooks.pre_llm_call)
    ctx.register_cli_command(
        name="omnigraph",
        help="Omnigraph awareness for Hermes (doctor, setup)",
        setup_fn=cli.setup_argparse,
        handler_fn=cli.dispatch,
    )
    logger.info("omnigraph (slim) registered: 0 tools, 2 hooks, 1 CLI command")
