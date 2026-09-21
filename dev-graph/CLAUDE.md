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

## Answering and writing (agents)

- **Answer from the graph, not the files.** Use the aliases / stored queries against the running server; never assemble an answer by reading `seed.jsonl` or `seed.md` — they are load inputs, not the live state.
- **Alias args bind by name to the query's `$params`** (`args: [slug]` fills `$slug`): `omnigraph alias issue iss-rate-limit` is `omnigraph query issue_lookup --graph dev --params '{"slug":"iss-rate-limit"}'`.
- **Mutations are not aliasable on 0.10** (`'add_x' is a mutation — use omnigraph mutate add_x`). Run them with `omnigraph mutate <name> --params '<json>'`, every non-optional property supplied; signatures live at the bottom of `queries/queries.gq`. Working example:

  ```bash
  omnigraph mutate create_issue --graph dev --params '{"slug":"iss-flaky-presence-test","title":"Presence integration test is flaky","status":"todo","issueType":"bug","actor":"act-admin","at":"2026-09-14"}'
  omnigraph mutate add_issue_to_epic --graph dev --params '{"issue":"iss-flaky-presence-test","epic":"epc-observability"}'
  ```

  With `defaults.server` / `default_graph` from the operator config, `--graph` can be omitted.

## Setup, in order (verified against 0.10)

`cluster import` comes **before** the first `apply` — without it `apply` exits 1
with `state_missing __cluster/state.json: apply requires an existing state.json`.

```bash
cd dev-graph
omnigraph cluster import --config .                # once: bootstraps __cluster/state.json
omnigraph cluster apply  --config . --as <you>     # creates graphs/dev.omni, applies schema + stored queries
omnigraph load --data seed.jsonl --mode overwrite graphs/dev.omni
omnigraph-server --cluster . --unauthenticated &   # 127.0.0.1:8080 — refuses to start without this flag or auth
curl -s http://127.0.0.1:8080/healthz              # {"status":"ok",…}; the path is /healthz, /health is 404
```

### `load` addressing

`--data` is the **seed file**; the **graph** is the positional URI. Both are
required, as is `--mode` (`overwrite` | `append` | `merge`).

| Target | Command |
|---|---|
| Local storage, no server | `omnigraph load --data seed.jsonl --mode overwrite graphs/dev.omni` |
| A running server | `omnigraph load --data seed.jsonl --mode overwrite --server http://127.0.0.1:8080 --graph dev --yes` |

One address per command. The engine's own refusals:

- `--graph` next to a positional URI or `--store` → *"--graph selects a graph
  within a server or cluster scope; a positional URI / --store is already a
  single graph"*. `--graph` pairs with `--server`, nothing else.
- `--cluster` on `load` → *"`load` is a data command; --cluster addresses a
  cluster-scoped command and does not apply."*
- `omnigraph load seed.jsonl …` — the positional slot is the **graph**, never the data file.
- `overwrite` through a server prompts, so non-interactive callers add `--yes`.

### Find the query instead of guessing it

- **`omnigraph queries list --cluster . --graph dev`** prints every stored query
  and mutation *with its parameter names*, offline, no server needed. Read the
  signature before writing `--params`: `query epic_issues($epic: String)` takes
  `{"epic":…}`, not `{"slug":…}`.
- `omnigraph query <name>` resolves a **stored query by name** and needs a
  server — passing query text there fails with *"by-name invocation needs a
  server (the stored-query catalog is server-owned)"*. Ad-hoc GQL goes through
  `-e`, in the same dialect as the `.gq` files:

  ```bash
  omnigraph query -e 'query q($slug: String) { match { $i: Issue { slug: $slug } } return { $i.slug, $i.title } }' \
    --params '{"slug":"iss-split-brain"}' --store file://$PWD/graphs/dev.omni
  ```

  Filters bind **inside the node's braces** (`$i: Issue { slug: $slug }`) — there
  is no `where`, no `filter { … }`, no `Issue[slug=="…"]`. The parameter list is
  required even when empty (`query q()`), and `limit N` / `order { … }` sit
  inside the outer braces after `return`, never trailing the string.

- `omnigraph alias <name> [args]` carries its own server and graph — adding
  `--graph`/`--server` errors with *"remove global scope flag(s)"*. **An alias
  name is not a query name:** `queries list` prints `epic_issues` and
  `issue_lookup`, whose aliases are `epic-issues` and `issue` — hyphenated, and
  often shorter than the query. They are the keys under `aliases:` in
  `omnigraph-config.example.yaml`; there is no `--list`.

## Cluster control plane (two-file model)

Filesystem-backed cluster — no object store, no S3 creds.

- `cluster.yaml` is the **deployment**: graph `dev`, `schema.pg`, and every stored
  query under `queries/`. Converge with `omnigraph cluster import|plan|apply
  --config .`. First run: `import` bootstraps `__cluster/state.json` before the
  first `apply`; `apply` creates the graph at `graphs/dev.omni`, applies the
  schema, and registers all stored queries. Re-run `apply` after editing any
  `.gq`/`.pg`, then restart the `--cluster` server.
- The **operator config** is per-operator only (aliases, defaults, identity) at
  `~/.omnigraph/config.yaml`. A `--cluster`-booted server never reads it.
- **Data** flows through `omnigraph load` (bulk) / `omnigraph mutate` (edits)
  against `graphs/dev.omni`. Invoke aliases with `omnigraph alias <name> [args]`.
- Never commit `__cluster/` or `graphs/` (gitignored — local derived state).

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
