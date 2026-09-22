# CLAUDE.md — dev-graph

Scoped guidance for the `dev-graph/` cookbook. Repo-wide conventions live in
`../CLAUDE.md`. For general Omnigraph ops — schema authoring, queries, loading,
branches, cluster commands, the CLI — use the **omnigraph** skill rather than
re-deriving them here; this file covers only what's specific to dev-graph.

## What This Is

An Omnigraph schema + seed + query set modeling **software-development work** as
one typed graph — planning, code, release, operations, and a governance/substrate
layer — as a **tracker replacement** (Issue/Epic/Decision/SpecFile are native;
the VCS host stays authoritative for code via `githubRef`). Schema, seed, and
queries only — no application code.

The reference seed is a **fictional real-time-collaboration product ("Meridian")**.
All names are fabricated; the seed exists to shape the demo queries.

## Key Files

- `schema.pg` — executable schema. Source of truth. **22 node classes** (17
  pointer, 5 append-only), 92 edge types. Comments are `//`, never `#`.
- `README.md` — design rationale, the ontology, killer queries, quick start.
- `seed.jsonl` / `seed.md` — reference seed (loadable / human-readable). Keep in sync.
- `queries/queries.gq` — derived reads (ready/blocked/stale, incident root-cause,
  governance), `search_*` semantic queries, and stored mutations.
- `queries/issues-dashboard.gq` — per-issue / per-epic triage reads.
- `cluster.yaml` — deployment (graph `dev`, schema, stored queries). Filesystem-backed.
- `omnigraph-config.example.yaml` — example operator aliases; merge into
  `~/.omnigraph/config.yaml` (per-user, never committed).

## Setup

The rules — `import` before the first `apply`, `load` addressing, `/healthz`, how aliases and
stored queries behave — are in `../CLAUDE.md`. This is that sequence with dev-graph's names filled in:

```bash
cd dev-graph
omnigraph cluster import --config .
omnigraph cluster plan   --config .
omnigraph cluster apply  --config . --as <you>     # creates graphs/dev.omni
omnigraph load --data seed.jsonl --mode overwrite graphs/dev.omni
omnigraph-server --cluster . --bind 127.0.0.1:8080 --unauthenticated &
curl -s http://127.0.0.1:8080/healthz
```

Graph id `dev`. Stored queries and their parameters: `omnigraph queries list --cluster . --graph dev`.
Alias args bind by name to `$params`: `omnigraph alias issue iss-rate-limit` is `omnigraph query issue_lookup --graph dev --params '{"slug":"iss-rate-limit"}'`.

## Writing

Aliases are read-only; mutations run as `omnigraph mutate <name> --params '<json>'` with every
non-optional property supplied. Signatures live at the bottom of `queries/queries.gq`. Working example:

```bash
omnigraph mutate create_issue --graph dev --params '{"slug":"iss-flaky-presence-test","title":"Presence integration test is flaky","status":"todo","issueType":"bug","actor":"act-admin","at":"2026-09-14"}'
omnigraph mutate add_issue_to_epic --graph dev --params '{"issue":"iss-flaky-presence-test","epic":"epc-observability"}'
```

With `defaults.server` / `default_graph` from the operator config, `--graph` can be omitted.

## The mutability model (do not bend it)

The single most load-bearing rule. Enforced by node class:

- **Pointer nodes** (Epic, SpecFile, Component, Repo, PR, Release, Incident,
  Issue, Actor, Gate, Label, Invariant, Principle, Gap, ExternalBlocker,
  Assumption, Capability) **update in place** — `update … where slug`. They carry
  `createdAt`/`createdBy` **and** `updatedAt`/`updatedBy`; stamp `updatedAt`/
  `updatedBy` on every write.
- **Append-only nodes** (Decision, Commit, Deployment, Learning, Comment) are
  **never overwritten** — insert only. They carry `createdAt`/`createdBy` **and
  have no `updatedAt`/`updatedBy` columns** (do not emit those). Corrections are a
  *new* node linked by a `Supersedes` edge (`DecisionSupersedes`, `SpecSupersedes`,
  `ReleaseSupersedes`).
- There are intentionally **no `delete` mutations**: removal is a status
  transition (`canceled`/`abandoned`/`superseded`/`retired`).
- **State is derived, not stored.** Never add a `ready`/`blocked`/`stale` property
  — those are queries over the edges. Ownership/authorship/targets are **edges**,
  not fields.

## Loading gotchas (verified against this engine build)

- **Seed load uses `--mode overwrite`** (clean slate). `--mode merge`/`append`
  currently fail on this schema: the camelCase `versionTag @unique` column trips a
  case-sensitivity check in the loader's uniqueness lookup
  (`No field named versiontag`). For incremental data use `mutate`, not bulk
  `load`.
- **Dates are `Date` (day-granularity), passed as ISO strings** (`"2026-07-09"`).
  `load` accepts ISO for `Date` columns. There is **no `DateTime`** in this
  schema, so mutations take `$at: Date` — `now()` (a DateTime) can't be assigned;
  the caller supplies the date.
- **Every non-nullable property must be supplied** on insert or lint/load fails
  (e.g. `PR.githubRef`, `Release.versionTag`, `Incident.startedAt`,
  `Commit.sha`/`authoredAt`, `Deployment.env`/`outcome`/`startedAt`).
- `@unique` columns to keep distinct across a load batch: `Component.name`,
  `Repo.name`, `Actor.name`, `Label.name`, `Capability.name`, `Release.versionTag`,
  `Commit.sha`.

## Query authoring notes

- **Anchor every match with a node binding.** A match block that *opens* with a
  bare edge traversal between two unbound variables (`$b issueBlocksIssue $i`) and
  then filters/projects their properties can lint clean but **fail at runtime**
  (`column '…' not found in wide batch`). Bind the endpoints first (`$i: Issue`,
  `$b: Issue`) — see the `blocked` query. Projecting an *unbound* endpoint is fine
  as long as another bound node anchors the match (e.g. `blocked_on_upstream`).
- **Edge verb = the schema edge name, first letter lowercased**
  (`EpicContainsIssue` → `epicContainsIssue`).
- **`nearest()`/`bm25()`/`rrf()` need a trailing `limit N`.** The `search_*`
  queries have it; keep it on any new ranked query.
- **Lint after every edit:** `omnigraph lint --schema schema.pg --query
  queries/<file>.gq` (no server needed). Warnings like "X exists in schema but no
  update query sets it" are informational.

## Schema notes / known drift

- **A `Learning`'s author is its `createdBy` column** — there is **no
  `LearningAuthoredBy` edge** in `schema.pg`. (The upstream ontology prose lists
  one; the schema omits it.) Don't emit that edge; it will dangle.
- `Component` has **no `repo` field** — repo membership is the `RepoHasComponent`
  edge. `Release.artifactsChecklist` is a **JSON string**, not a native list.

## Regenerating the seed

`seed.jsonl` is generated by `.context/gen_seed.py` (gitignored scratch), which
holds the data model in readable form and validates referential integrity
(unique keys, no dangling edge endpoints, append-only nodes without `updatedAt`)
before emitting. Edit the generator, re-run `python3 .context/gen_seed.py
dev-graph/seed.jsonl`, then update `seed.md` totals to match. If you hand-edit
`seed.jsonl` instead, keep every `@key` unique within the file and every edge
endpoint pointing at a real slug.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).
