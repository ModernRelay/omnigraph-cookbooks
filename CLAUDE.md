# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Repo-wide guidance. Each cookbook also has its own `CLAUDE.md` — read both when working inside one. For deeper operational guidance, the packaged skills under `skills/` mirror the human-readable docs in `docs/`.

## What This Repo Is

A collection of Omnigraph graph cookbooks plus packaged agent skills. Each cookbook is self-contained in its folder; skills live under `skills/` and are installable via `npx skills add`. Four cookbooks ship today: `industry-intel/` (AI/ML intel on the SPIKE framework — Signal, Pattern, Insight, KnowHow, Element), `pharma-intel/` (pharma competitive intelligence), `second-brain/` (personal-life automation graph), and `vc-os/` (venture-capital operating system). See `README.md` for the full list and planned cookbooks.

## Architecture

- **Storage**: two backends in play. Cluster-mode cookbooks (industry-intel, pharma-intel) are **filesystem-backed** — `cluster apply` creates the derived root `graphs/<id>.omni`, no object store needed. The classic single-graph cookbooks (second-brain, vc-os) use an **S3-compatible store** at `s3://<bucket>/repos/<name>` (RustFS for local dev, or any S3). `init` and `load` write storage directly — one-time setup ops that bypass the server.
- **Runtime**: `omnigraph-server` reads from storage at startup and exposes HTTP on `127.0.0.1:8080`. Day-to-day CLI calls (`query`, `mutate`) go through the server.
- **CLI config**: Per-cookbook `omnigraph.yaml` is the per-operator file (graph targets, server bind, CLI defaults, `cli.actor`, and a library of `aliases` — short names mapping to named queries/mutations in `queries/*.gq`). Agents should invoke aliases (e.g. `omnigraph query --alias pattern-signals pat-sovereign-ai`), not raw query files. Alias arg values are JSON-parsed first, then fall back to string — `29` is an integer, `"29"` is a string. (0.7.0 begins moving the per-operator surface to `~/.omnigraph/config.yaml`; the cookbooks still ship `omnigraph.yaml`.)
- **Auth**: `.env.omni` holds the S3 creds for the S3-backed path (RustFS locally, or your cloud store; not committed) — only needed for S3-backed cookbooks. Source before CLI commands: `set -a && source .env.omni && set +a`.

**Prerequisite**: cluster-mode cookbooks (industry-intel, pharma-intel) are filesystem-backed and need no object store — just the `omnigraph`/`omnigraph-server` binaries. The S3-backed cookbooks (second-brain, vc-os) need a running S3-compatible store (RustFS for local dev, bootstrapped via the script in `docs/best-practices.md` → *Local Setup*; verify with `curl http://127.0.0.1:9000`). In both, `lint` works with nothing running; once a server is up, verify with `curl http://127.0.0.1:8080/healthz`.

## Canonical Workflow

1. **Edit** `schema.pg` or `queries/*.gq`. Comments in both use `//` not `#`.
2. **Lint** — `omnigraph lint --schema schema.pg --query queries/<file>.gq` validates queries against the schema. Run after any edit. This is a pure file check: no server, no storage, no `.env.omni` needed — use it as the tight inner loop while editing. Everything below requires the server running (and, for S3-backed cookbooks, env vars sourced).
3. **Schema changes** — plan before apply, always. Cluster-mode cookbooks (industry-intel, pharma-intel — they ship a `cluster.yaml`): edit the `.pg`, then `omnigraph cluster plan --config .` (shows real migration steps) and `omnigraph cluster apply --config . --as <you>`, then restart the `--cluster` server. Classic single-graph: `omnigraph schema plan` before `schema apply`. Use `@rename_from(...)` for property/type renames in both.
4. **Data changes** — pick the right write command: `mutate` for edits; `load` for bulk JSONL with a **required** `--mode` (`merge` upsert · `append` strict-insert · `overwrite` clean-slate, destructive). `load --from main --branch <name>` forks a review branch in one shot. `load` works local **and** remote. Review bulk loads on a branch, then merge.
5. **Never string-interpolate** into `.gq` bodies or `--params` — parameterize everything.

**Two deployment models.** Cookbooks with a `cluster.yaml` are cluster
directories: that file declares the deployment (graph, schema, stored
queries); `omnigraph cluster apply` converges it (creating the graph at
`graphs/<id>.omni`) and `omnigraph-server --cluster .` serves it.
`omnigraph.yaml` is per-operator only (aliases, CLI defaults, `cli.actor`).
Never commit `graphs/` or `__cluster/` (gitignored). second-brain and vc-os
instead use the classic single-graph S3 path (RustFS for local dev, or any
S3-compatible store); each README documents it.

There are no repo-level build, test, or lint commands. Validation happens per-cookbook via `omnigraph lint`. CI is not configured in this repo.

## Working in a Cookbook

Always `cd` into the cookbook folder first — configs and paths are relative:

```bash
cd industry-intel
set -a && source .env.omni && set +a
omnigraph lint --schema schema.pg --query queries/signals.gq
```

Start the server once per session from inside the cookbook folder — `query`, `mutate`, and `snapshot` all go through it:

```bash
omnigraph-server --cluster . --unauthenticated               # cluster cookbooks (industry-intel, pharma-intel)
omnigraph-server --config omnigraph.yaml --unauthenticated   # classic single-graph cookbooks (second-brain, vc-os)
# binds 127.0.0.1:8080; local dev — v0.6.0+ refuses to start without auth/policy or this flag
```

Leave it running in a separate terminal or background process.

## Skills and Docs

- `skills/omnigraph-intel-bootstrap/` — bootstrap a new SPIKE graph (elicitation + research + init/load)
- `skills/omnigraph-best-practices/` — day-to-day ops; mirrors `docs/best-practices.md`
- `docs/best-practices.md` — operational guide (human-readable)
- `docs/omni-schema.md` — schema design principles

When working on schema or ops questions, consult `docs/` directly rather than duplicating guidance here.

## When Adding a New Cookbook

- Create the folder with `README.md`, `CLAUDE.md`, `schema.pg`, `cluster.yaml` (recommended — cluster mode) plus a per-operator `omnigraph.yaml`, `queries/`, and seed data (`seed.md` + `seed.jsonl`)
- Ship real seed data, not placeholders
- Keep the cookbook's README and CLAUDE in sync with its schema
- Expose agent-facing operations as aliases in `omnigraph.yaml`, not raw CLI invocations

Omnigraph reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).
