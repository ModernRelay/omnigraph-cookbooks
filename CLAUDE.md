# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Repo-wide guidance. Each cookbook also has its own `CLAUDE.md` — read both when working inside one. For deeper operational guidance, the packaged skills under `skills/` mirror the human-readable docs in `docs/`.

## What This Repo Is

A collection of Omnigraph graph cookbooks plus packaged agent skills. Each cookbook is self-contained in its folder; skills live under `skills/` and are installable via `npx skills add`. Currently only `industry-intel/` is shipped (AI/ML intel on the SPIKE framework — Signal, Pattern, Insight, KnowHow, Element). See `README.md` for the full list and planned cookbooks.

## Architecture

- **Storage**: RustFS (S3-compatible) at `s3://omnigraph-local/repos/<name>`. `init` and `load` write directly to storage — they are one-time setup ops and bypass the server.
- **Runtime**: `omnigraph-server` reads from storage at startup and exposes HTTP on `127.0.0.1:8080`. Day-to-day CLI calls (`read`, `change`) go through the server.
- **CLI config**: Per-cookbook `omnigraph.yaml` defines storage URI, server bind, and a library of `aliases` — short names that map to named queries/mutations in `queries/*.gq`. Agents should invoke aliases (e.g. `omnigraph read --alias pattern-signals pat-sovereign-ai`), not raw query files. Alias arg values are JSON-parsed first, then fall back to string — `29` is an integer, `"29"` is a string.
- **Auth**: `.env.omni` holds RustFS AWS creds (not committed). Source before CLI commands: `set -a && source ./.env.omni && set +a`.

**Prerequisite**: RustFS must be running locally (Docker-based) before anything beyond `query lint` will work. Bootstrap once via the script in `docs/best-practices.md` → *Local Setup*. Verify with `curl http://127.0.0.1:9000` (RustFS) and, once the server is up, `curl http://127.0.0.1:8080/healthz`.

## Canonical Workflow

1. **Edit** `schema.pg` or `queries/*.gq`. Comments in both use `//` not `#`.
2. **Lint** — `omnigraph query lint --schema ./schema.pg --query ./queries/<file>.gq` validates queries against the schema. Run after any edit. This is a pure file check: no server, no RustFS, no `.env.omni` needed — use it as the tight inner loop while editing. Everything below requires the server running and env vars sourced.
3. **Schema changes** — `omnigraph schema plan` before `schema apply`. Never apply without a successful plan. Use `@rename_from(...)` for property/type renames.
4. **Data changes** — pick the right write command: `change` for edits, `load --mode merge` for bulk, `load --mode overwrite` only for clean slates. Review bulk ingests on a branch, then merge.
5. **Never string-interpolate** into `.gq` bodies or `--params` — parameterize everything.

There are no repo-level build, test, or lint commands. Validation happens per-cookbook via `omnigraph query lint`. CI is not configured in this repo.

## Working in a Cookbook

Always `cd` into the cookbook folder first — configs and paths are relative:

```bash
cd industry-intel
set -a && source ./.env.omni && set +a
omnigraph query lint --schema ./schema.pg --query ./queries/signals.gq
```

Start the server once per session from inside the cookbook folder — `read`, `change`, and `snapshot` all go through it:

```bash
omnigraph-server --config ./omnigraph.yaml   # binds 127.0.0.1:8080
```

Leave it running in a separate terminal or background process.

## Skills and Docs

- `skills/omnigraph-intel-bootstrap/` — bootstrap a new SPIKE graph (elicitation + research + init/load)
- `skills/omnigraph-best-practices/` — day-to-day ops; mirrors `docs/best-practices.md`
- `docs/best-practices.md` — operational guide (human-readable)
- `docs/omni-schema.md` — schema design principles

When working on schema or ops questions, consult `docs/` directly rather than duplicating guidance here.

## When Adding a New Cookbook

- Create the folder with `README.md`, `CLAUDE.md`, `schema.pg`, `omnigraph.yaml`, `queries/`, and seed data (`seed.md` + `seed.jsonl`)
- Ship real seed data, not placeholders
- Keep the cookbook's README and CLAUDE in sync with its schema
- Expose agent-facing operations as aliases in `omnigraph.yaml`, not raw CLI invocations

Omnigraph reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).
