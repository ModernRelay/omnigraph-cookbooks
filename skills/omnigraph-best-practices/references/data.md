# Data Changes & Branches

How to modify data safely in Omnigraph.

## Choose the Right Write Command

| Task | Command | Why |
|------|---------|-----|
| Add/update a single entity | `change` with a named mutation | typechecked, parameterized, auditable |
| Bulk upsert by `@key` (local repo) | `load --mode merge` | preserves rows not in the file |
| Bulk upsert (remote repo) | `ingest --mode merge` | server-orchestrated; `load` is rejected on remote URIs |
| Additive-only bulk | `load` / `ingest --mode append` | fails on key collision |
| Clean-slate reseed | `load` / `ingest --mode overwrite` | **destructive** — wipes the branch |

> **Local vs remote**: `load` only works against local repo URIs (`load is only supported against local repo URIs in this milestone`). For remote graphs (HTTP server endpoints, CloudFront-fronted production) use `ingest` — same JSONL format, but the server orchestrates the write and leaves a reviewable branch. See [`references/remote-ops.md`](remote-ops.md) for remote-specific operational concerns including 504 handling and write-verification ritual.

## `change` — Single Edits

Goes through the running server via `cli.graph` (or an alias):

```bash
omnigraph change \
  --query mutations.gq \
  --name add_signal \
  --params '{"slug":"sig-foo","name":"Foo","brief":"...","stagingTimestamp":"2026-04-14T00:00:00Z","createdAt":"2026-04-14T00:00:00Z","updatedAt":"2026-04-14T00:00:00Z"}'
```

Or via an alias:

```bash
omnigraph change --alias add-signal sig-foo "Foo" "..." 2026-04-14T00:00:00Z 2026-04-14T00:00:00Z 2026-04-14T00:00:00Z
```

Prefer `change` for interactive edits, mutations called from agents, and anything you want typechecked at call time.

## `load` — Bulk JSONL

JSONL format:

```jsonl
{"type":"Signal","data":{"id":"sig-foo","slug":"sig-foo","name":"Foo","brief":"...","stagingTimestamp":"2026-04-14T00:00:00Z","createdAt":"2026-04-14T00:00:00Z","updatedAt":"2026-04-14T00:00:00Z"}}
{"edge":"FormsPattern","from":"sig-foo","to":"pat-bar","data":{}}
```

- Nodes: `{"type":"<NodeType>","data":{...props...}}` — `id` equals `slug`
- Edges: `{"edge":"<EdgeType>","from":"<src_slug>","to":"<dst_slug>","data":{...edge_props...}}`

Load command:

```bash
omnigraph load --data ./seed.jsonl --mode merge s3://omnigraph-local/repos/spike-intel
```

### `--mode` semantics

- **`overwrite`** (destructive) — truncates every node/edge table on the branch, then loads the file. Safe on a **first** load; risky afterward. Don't run it against `main` in production without a branch backup path.
- **`merge`** (upsert) — for each row, insert if `@key` is new, update if it exists. Rows not in the file are preserved. The safe default for incremental bulk updates.
- **`append`** (strict insert) — fails on key collision. Use when you're certain every row is new.

### `merge` does NOT recompute embeddings

If you change seed rows that feed into `@embed("source")` via `load --mode merge`, the source field updates but the embedding stays stale.

**Fix:** run `omnigraph embed --reembed_all` after, or use `load --mode overwrite` once (which re-triggers embedding on load).

### `overwrite` is destructive

Wipes the entire branch's data for every node and edge type. Use only for:
- First-time seed
- Intentional full reseed on a feature branch
- Recovery scenarios

Never on `main` without a branch backup.

## Branches: Review Before Merge

Branches exist for **data review**, not schema changes. Schema goes straight to `main` via `plan` + `apply`.

### The review loop

```bash
REPO=s3://omnigraph-local/repos/spike-intel

# 1. Create feature branch from main
omnigraph branch create --uri $REPO --from main staging-2026-04-14

# 2. Load delta onto the branch (merge mode is typical for review)
omnigraph ingest --data ./delta.jsonl --branch staging-2026-04-14 --mode merge --uri $REPO

# 3. Verify on the branch (reads can target --branch or --snapshot)
omnigraph read --alias recent-signals --branch staging-2026-04-14

# 4. Merge to main when happy
omnigraph branch merge --uri $REPO staging-2026-04-14 --into main

# 5. Optionally delete the branch
omnigraph branch delete --uri $REPO staging-2026-04-14
```

### `ingest` vs `load`

- `load` operates on an existing branch (default `main`)
- `ingest` can create a named branch from `--from main` in one shot, load data onto it, and leave it for review

Use `ingest` for anything you want reviewed before touching `main`.

### Keep branches short-lived

Long-lived branches compound merge risk. The usual flow is: create → ingest → verify → merge → delete, all in the same session. A week-old feature branch is a yellow flag.

### Schema apply blocks non-main branches

`omnigraph schema apply` rejects the request if any non-main branches exist. Merge or delete them first. This is enforced — it's not just a guideline.

## Destructive Ops Go Through a Branch

For any ingestion that could disrupt downstream queries (overwriting a heavily-referenced node type, removing edges en masse, reseeding a core table), use a feature branch:

```bash
omnigraph ingest --data ./risky.jsonl --branch recovery-2026-04-14 \
  --from main --mode overwrite --uri $REPO
# inspect, diff, verify reads
omnigraph branch merge --uri $REPO recovery-2026-04-14 --into main
```

## Branch Commands (quick reference)

```bash
omnigraph branch create --uri $REPO --from main <branch-name>
omnigraph branch list --uri $REPO
omnigraph branch merge --uri $REPO <branch-name> --into main
omnigraph branch delete --uri $REPO <branch-name>
```

All support `--json` for automation-friendly output.

## Inspecting State After Changes

```bash
omnigraph snapshot $REPO --branch main --json           # tables + row counts
omnigraph export $REPO --branch main > graph.jsonl      # full JSONL dump
omnigraph commit list $REPO --branch main --json        # history
```

`export` is the right tool for large-snapshot inspection — don't try to page through the whole graph with read queries.
