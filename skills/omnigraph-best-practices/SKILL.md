---
name: omnigraph-best-practices
description: Operate a locally deployed Omnigraph graph database. Use this skill whenever you see Omnigraph CLI commands (omnigraph init/read/change/load/schema/embed/branch/commit/run), .pg schema files, .gq query files, RustFS S3 URIs (s3://omnigraph-local/...), or work inside a folder containing omnigraph.yaml. Covers local RustFS setup, project layout, schema authoring and evolution (plan before apply), query linting, data changes (change vs load --mode merge vs overwrite), branches for data review, embeddings, aliases for automation, HTTP server operation, Cedar policy, and common gotchas. Especially important BEFORE running schema apply (plan first), any load (pick --mode carefully), or any .gq/.pg edit (lint afterward). Apply this skill aggressively when the user mentions Omnigraph, graph migrations, or graph database local development.
---

# Operating Omnigraph Locally

This skill captures the operational rules for working with a locally deployed Omnigraph (RustFS-backed or remote S3). Follow them when authoring schema, writing queries, loading data, evolving schema, or automating graph operations.

## The Six Rules

1. **Lint before commit** — `omnigraph query lint --schema schema.pg --query queries/foo.gq` validates both sides against each other. No running repo required.
2. **Plan before apply** — never run `schema apply` without a successful `schema plan` first. Apply is destructive; plan is free.
3. **Branches are for data; apply is for schema** — review data ingests on a feature branch then merge. Schema changes go straight to `main`.
4. **Pick the right write command** — `change` for edits (typechecked, parameterized), `load --mode merge` for bulk upsert, `load --mode overwrite` only for clean slates.
5. **Parameterize everything** — never string-interpolate values into `.gq` bodies or `--params`. Declare `$var: Type` and pass via `--params`.
6. **Expose agent operations as aliases** — not raw CLI invocations. Aliases decouple the operation name from the query implementation.

## Local Setup

### Bootstrap a local RustFS + Omnigraph in one command

```bash
curl -fsSL https://raw.githubusercontent.com/ModernRelay/omnigraph/main/scripts/local-rustfs-bootstrap.sh | bash
```

Defaults: RustFS S3 on `127.0.0.1:9000`, console on `:9001`, `omnigraph-server` on `:8080`, bucket `omnigraph-local`. Override with `BUCKET=foo PREFIX=repos/bar BIND=127.0.0.1:8080 curl ...`.

### AWS env vars for direct S3 access

Direct `s3://...` URIs require AWS credentials pointed at RustFS. Keep them in `.env.omni` (git-ignored):

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

**Commit:** `schema.pg`, `queries/*.gq`, `omnigraph.yaml`, `seed.md`, `seed.jsonl`, per-starter `README.md` and `CLAUDE.md`.

**Ignore:** `.env.omni` (credentials), `.claude/` (local agent state), `*.omni/` (local repo artifacts), `.omnigraph-rustfs-demo/` (bootstrap state).

### Give agents a `CLAUDE.md`

A per-starter `CLAUDE.md` tells coding agents where files live and what conventions matter. Without it, agents re-discover the same things every session.

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
| [`references/data.md`](references/data.md) | Choosing between `change` and `load`, branch review workflow, destructive ops |
| [`references/search.md`](references/search.md) | Embeddings, `@embed`, vector/text ranking, scope-then-rank pattern |
| [`references/aliases.md`](references/aliases.md) | Defining aliases for agents, structured output, JSON args |
| [`references/server-policy.md`](references/server-policy.md) | Starting the HTTP server, routes, bearer auth, Cedar policy gating |
| [`references/commands.md`](references/commands.md) | `snapshot`, `export`, `run list/show/publish`, `commit list/show`, config resolution order |
