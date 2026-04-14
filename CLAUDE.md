# CLAUDE.md

Repo-wide guidance for Claude Code. Each starter also has its own `CLAUDE.md` — read both when working inside one.

## What This Repo Is

A collection of Omnigraph graph starters plus packaged agent skills. Each starter is self-contained in its folder; skills live under `skills/` and are installable via `npx skills add`. See `README.md` for the full list.

## Tooling

- `omnigraph` CLI works against a live repo (S3 URI or server).
- `omnigraph query lint --schema ./schema.pg --query ./queries/<file>.gq` validates queries against the schema — run after any edit.
- Comments in `.pg` files use `//` not `#`.
- Reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

## Working in a Starter

Always `cd` into the starter folder first — configs and paths are relative:

```bash
cd industry-intel
set -a && source ./.env.omni && set +a
omnigraph query lint --schema ./schema.pg --query ./queries/signals.gq
```

## When Adding a New Starter

- Create the folder with `README.md`, `CLAUDE.md`, `schema.pg`, `omnigraph.yaml`, `queries/`, and seed data
- Ship real seed data, not placeholders
- Keep the starter's README and CLAUDE in sync with its schema
