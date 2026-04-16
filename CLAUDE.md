# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Repo-wide guidance. Each starter also has its own `CLAUDE.md` — read both when working inside one. For deeper operational guidance, the packaged skills under `skills/` mirror the human-readable docs in `docs/`.

## What This Repo Is

A collection of Omnigraph graph starters plus packaged agent skills. Each starter is self-contained in its folder; skills live under `skills/` and are installable via `npx skills add`. Currently only `industry-intel/` is shipped (AI/ML intel on the SPIKE framework — Signal, Pattern, Insight, KnowHow, Element). See `README.md` for the full list and planned starters.

## Architecture

- **Storage**: RustFS (S3-compatible) at `s3://omnigraph-local/repos/<name>`. `init` and `load` write directly to storage — they are one-time setup ops and bypass the server.
- **Runtime**: `omnigraph-server` reads from storage at startup and exposes HTTP on `127.0.0.1:8080`. Day-to-day CLI calls (`read`, `change`, `query lint`) go through the server.
- **CLI config**: Per-starter `omnigraph.yaml` defines storage URI, server bind, and a library of `aliases` — short names that map to named queries/mutations in `queries/*.gq`. Agents should invoke aliases (e.g. `omnigraph read --alias pattern-signals pat-sovereign-ai`), not raw query files.
- **Auth**: `.env.omni` holds RustFS AWS creds (not committed). Source before CLI commands: `set -a && source ./.env.omni && set +a`.

## Canonical Workflow

1. **Edit** `schema.pg` or `queries/*.gq`. Comments in both use `//` not `#`.
2. **Lint** — `omnigraph query lint --schema ./schema.pg --query ./queries/<file>.gq` validates queries against the schema. Run after any edit.
3. **Schema changes** — `omnigraph schema plan` before `schema apply`. Never apply without a successful plan. Use `@rename_from(...)` for property/type renames.
4. **Data changes** — pick the right write command: `change` for edits, `load --mode merge` for bulk, `load --mode overwrite` only for clean slates. Review bulk ingests on a branch, then merge.
5. **Never string-interpolate** into `.gq` bodies or `--params` — parameterize everything.

## Working in a Starter

Always `cd` into the starter folder first — configs and paths are relative:

```bash
cd industry-intel
set -a && source ./.env.omni && set +a
omnigraph query lint --schema ./schema.pg --query ./queries/signals.gq
```

## Skills and Docs

- `skills/omnigraph-intel-bootstrap/` — bootstrap a new SPIKE graph (elicitation + research + init/load)
- `skills/omnigraph-best-practices/` — day-to-day ops; mirrors `docs/best-practices.md`
- `docs/best-practices.md` — operational guide (human-readable)
- `docs/omni-schema.md` — schema design principles

When working on schema or ops questions, consult `docs/` directly rather than duplicating guidance here.

## When Adding a New Starter

- Create the folder with `README.md`, `CLAUDE.md`, `schema.pg`, `omnigraph.yaml`, `queries/`, and seed data (`seed.md` + `seed.jsonl`)
- Ship real seed data, not placeholders
- Keep the starter's README and CLAUDE in sync with its schema
- Expose agent-facing operations as aliases in `omnigraph.yaml`, not raw CLI invocations

Omnigraph reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).
