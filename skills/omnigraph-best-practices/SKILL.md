---
name: omnigraph-best-practices
description: Operate a locally or remotely deployed Omnigraph graph database. Use this skill whenever you see Omnigraph CLI commands (omnigraph init/read/change/load/ingest/schema/embed/branch/commit), .pg schema files, .gq query files, RustFS S3 URIs (s3://omnigraph-local/...), remote bearer-authed graph endpoints, 504 errors against a graph, or work inside a folder containing omnigraph.yaml. Covers local RustFS setup, project layout, schema authoring and evolution (plan before apply), query linting, data changes (change vs load vs ingest, --mode merge vs overwrite), branches for data review, embeddings, aliases for automation, HTTP server operation, Cedar policy, remote graph operations (504 verification ritual, ingest vs load tradeoffs, version drift), and common gotchas. Especially important BEFORE running schema apply (plan first), any load (pick --mode carefully), any .gq/.pg edit (lint afterward), or any write to a remote graph (verify via commit list afterward). Apply this skill aggressively when the user mentions Omnigraph, graph migrations, remote graph deploys, 504 errors, or graph database development.
license: MIT (see LICENSE at repo root)
compatibility: Requires omnigraph CLI >= 0.3.1 and Docker (for local RustFS).
metadata:
  author: ModernRelay
  version: "0.2.0"
  repository: https://github.com/ModernRelay/omnigraph-cookbooks
---

# Operating Omnigraph Locally

This skill captures the operational rules for working with a locally deployed Omnigraph (RustFS-backed or remote S3). Follow them when authoring schema, writing queries, loading data, evolving schema, or automating graph operations.

## The Seven Rules

1. **Lint before commit** — `omnigraph query lint --schema schema.pg --query queries/foo.gq` validates both sides against each other. No running repo required.
2. **Plan before apply** — never run `schema apply` without a successful `schema plan` first. Apply is destructive; plan is free.
3. **Branches are for data; apply is for schema** — review data ingests on a feature branch then merge. Schema changes go straight to `main`.
4. **Pick the right write command** — `change` for edits (typechecked, parameterized), `load --mode merge` for bulk upsert on local repos, `ingest` for remote, `load --mode overwrite` only for clean slates.
5. **Parameterize everything** — never string-interpolate values into `.gq` bodies or `--params`. Declare `$var: Type` and pass via `--params`.
6. **Expose agent operations as aliases** — not raw CLI invocations. Aliases decouple the operation name from the query implementation.
7. **Verify after every remote write** — compare `commit list --branch main` head before and after. The CLI's exit code is not authoritative on remote graphs; proxies can drop the response while the write commits server-side. See `references/remote-ops.md` for the verification ritual and how to recover from 504s.

## Local Setup

### Bootstrap a local RustFS + Omnigraph in one command

**Requires Docker.** RustFS runs in a container — install [Docker](https://docs.docker.com/get-docker/) and verify before running the bootstrap:

```bash
docker version >/dev/null 2>&1 || { echo "Install Docker first: https://docs.docker.com/get-docker/"; exit 1; }
curl -fsSL https://raw.githubusercontent.com/ModernRelay/omnigraph/main/scripts/local-rustfs-bootstrap.sh | bash
```

Defaults: RustFS S3 on `127.0.0.1:9000`, console on `:9001`, `omnigraph-server` on `:8080`, bucket `omnigraph-local`. Override with `BUCKET=foo PREFIX=repos/bar BIND=127.0.0.1:8080 curl ...`.

**Heads up — port :8080 is in use after bootstrap.** The bootstrap auto-starts an `omnigraph-server` against its own demo repo. If you start a second server (e.g. for a different cookbook) without stopping the first, you'll get a silent port collision. Either stop the bootstrap server or start yours with `--bind 127.0.0.1:8090`.

Bootstrap also installs `omnigraph` and `omnigraph-server` binaries under `<workdir>/.omnigraph-rustfs-demo/bin/` — **not on PATH by default**. Add it or invoke binaries by absolute path.

### AWS env vars (for `init`, `load`, and the server)

`init` and `load` write S3-backed storage directly, and `omnigraph-server` reads from it. Both need AWS credentials pointed at RustFS. Keep them in `.env.omni` (git-ignored):

```bash
AWS_ACCESS_KEY_ID=rustfsadmin
AWS_SECRET_ACCESS_KEY=rustfsadmin
AWS_REGION=us-east-1
AWS_ENDPOINT_URL=http://127.0.0.1:9000
AWS_ENDPOINT_URL_S3=http://127.0.0.1:9000
AWS_ALLOW_HTTP=true
AWS_S3_FORCE_PATH_STYLE=true
```

Source before running CLI commands:

```bash
set -a && source ./.env.omni && set +a
```

Or reference `auth.env_file: .env.omni` in `omnigraph.yaml` for automatic loading.

### Validate the setup

```bash
curl http://127.0.0.1:8080/healthz
omnigraph snapshot s3://omnigraph-local/repos/<your-repo> --json
```

## Project Layout

### `omnigraph.yaml` is the operational backbone

Run CLI commands from the folder containing `omnigraph.yaml` — relative paths for `queries/`, `schema.pg`, and `.env.omni` resolve from there.

```yaml
graphs:
  local_s3:
    uri: s3://omnigraph-local/repos/spike-intel
  local_server:
    uri: http://127.0.0.1:8080
    bearer_token_env: OMNIGRAPH_BEARER_TOKEN

server:
  graph: local_s3
  bind: 127.0.0.1:8080

cli:
  graph: local_s3
  branch: main
  output_format: jsonl      # use `table` for human reading; `jsonl` for automation

auth:
  env_file: .env.omni

query:
  roots: [queries, .]

aliases:
  signal:
    command: read
    query: signals.gq
    name: get_signal
    args: [slug]
    format: kv
```

Key naming: the config field is `graphs:` (not `targets:` — that's the old schema). `cli.graph` and `server.graph` replaced `cli.target` / `server.target`. The CLI flag is still `--target <name>` though.

### What to commit

**Commit:** `schema.pg`, `queries/*.gq`, `omnigraph.yaml`, `seed.md`, `seed.jsonl`, per-cookbook `README.md` and `CLAUDE.md`.

**Ignore:** `.env.omni` (credentials), `.claude/` (local agent state), `*.omni/` (local repo artifacts), `.omnigraph-rustfs-demo/` (bootstrap state).

### Give agents a `CLAUDE.md`

A per-cookbook `CLAUDE.md` tells coding agents where files live and what conventions matter. Without it, agents re-discover the same things every session.

## Common Gotchas

These are the traps most likely to bite. Scan this table before debugging any parse or runtime error.

| Trap | Symptom | Fix |
|------|---------|-----|
| `#` comments in `.pg` | `parse error: expected schema_file` | Use `//` |
| Standalone `enum Foo { ... }` block | `parse error: expected EOI or schema_decl` | Inline: `kind: enum(a, b)` |
| `[Category]` (list of enum) | compile error | Use `[String]`; lists must contain scalars |
| `@embed(text)` without quotes | `unexpected constraint_name` | `@embed("text")` |
| `@unique(src)` on edge without body block | parse error | `@card(1..1) { @unique(src) }` |
| `load --mode merge` after `@embed` source change | stale embeddings | `omnigraph embed --reembed_all` or `load --mode overwrite` |
| `schema apply` with feature branches open | rejected | Merge or delete branches first |
| `nearest(...)` / `bm25(...)` / `rrf(...)` without `limit` | compile error | Add `limit N` |
| Adding non-nullable property without backfill | unsupported migration | Make optional → backfill → tighten in follow-up apply |
| Config uses `targets:` / `target:` | `graph 'X' not found in omnigraph.yaml` | Rename to `graphs:` / `graph:` |
| `omnigraph init --json` | `unexpected argument --json` | `init` doesn't support `--json`; drop the flag |
| Committing `.env.omni` | credential leak | Add `.env*` to `.gitignore` |
| Non-parameterized query values | typecheck surprise, injection risk | Declare `$param: Type` and pass via `--params` |
| Missing required field in `insert` | `T12: insert for 'X' must provide non-nullable property 'Y'` | Accept the param in the mutation signature |
| Long-lived feature branches | merge conflicts, schema apply blocked | Merge promptly; delete when done |
| `mutation { ... }` wrapper in `.gq` | `parse error: expected query_file` at line 1 | Use `query <name>(...) { insert T { ... } }`; there is no top-level `mutation` keyword |
| `--config` placed before subcommand | `unexpected argument --config` | Put `--config` **after** the subcommand (e.g. `omnigraph schema show --config X`) |
| Reading a large schema via stdout-capped tool | Truncated, garbled, or duplicated output | `omnigraph schema show > /tmp/schema.pg` first; then read the file with offset/limit |
| `omnigraph load` against a remote URI | `load is only supported against local repo URIs in this milestone` | Use `ingest` for remote graphs |
| Blind retry after 504 | Duplicate Signal/Decision/Claim (append-only types lack `@key` dedup) | `commit list --branch main --json` first; head advanced means it landed; only retry if unchanged |
| `sync_branch()` mentioned in version-drift error | Searching for nonexistent CLI command | Server-internal directive in error text; retry once, fall back to `ingest` if persistent |
| Stale `ingest/<name>` branches at `main`'s head | 504-orphaned empty branches; eventually block writes | List branches, find ones at `main`'s `graph_commit_id`, `omnigraph branch delete --config X <name>` |

## Edge Traversal Casing

Schema declares edges in **PascalCase** (`FormsPattern`), but queries traverse them in **lowerCamelCase**:

```gq
match {
    $s: Signal
    $s formsPattern $p       // edge FormsPattern: Signal -> Pattern
}
```

## Deep Dives

For anything beyond the basics, load the relevant reference file. Each is self-contained — load only what you need.

| Reference | When to load |
|-----------|--------------|
| [`references/schema.md`](references/schema.md) | Editing `.pg` files, running `schema plan`/`apply`, renaming types, backfilling required fields |
| [`references/queries.md`](references/queries.md) | Writing or linting `.gq` files, search functions, aggregations, multi-hop patterns |
| [`references/data.md`](references/data.md) | Choosing between `change`, `load`, and `ingest`; branch review workflow; destructive ops |
| [`references/remote-ops.md`](references/remote-ops.md) | Operating against a remote/CloudFront-fronted graph: 504 verification ritual, version drift, ingest fingerprints, append-only retry safety |
| [`references/search.md`](references/search.md) | Embeddings, `@embed`, vector/text ranking, scope-then-rank pattern |
| [`references/aliases.md`](references/aliases.md) | Defining aliases for agents, structured output, JSON args |
| [`references/server-policy.md`](references/server-policy.md) | Starting the HTTP server, routes, bearer auth, Cedar policy gating |
| [`references/commands.md`](references/commands.md) | `snapshot`, `export`, `commit list/show`, config resolution order |
