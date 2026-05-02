# Omnigraph Best Practices

Operational guide for working with Omnigraph: project layout, schema evolution, queries, data changes, branches, and agent automation.

For schema **design** principles (identity, types, edges, constraints) see [`omni-schema.md`](./omni-schema.md). This doc is about how to **operate** an Omnigraph project day-to-day.

## TL;DR

1. **Lint before commit** — `omnigraph query lint --schema schema.pg --query queries/foo.gq`
2. **Plan before apply** — never `schema apply` without a successful `schema plan` first
3. **Branches are for data; apply is for schema** — review data ingests on a branch, then merge; schema changes go straight to `main`
4. **Pick the right write command** — `change` for edits, `load --mode merge` for bulk, `overwrite` only for clean slates
5. **Parameterize everything** — never string-interpolate into `.gq` bodies or `--params`
6. **Expose agent operations as aliases** — not raw CLI invocations

## Local Setup

### Bootstrap a local RustFS-backed Omnigraph

**Requires Docker.** RustFS runs in a container — install [Docker](https://docs.docker.com/get-docker/) and verify first:

```bash
docker version >/dev/null 2>&1 || { echo "Install Docker first: https://docs.docker.com/get-docker/"; exit 1; }
curl -fsSL https://raw.githubusercontent.com/ModernRelay/omnigraph/main/scripts/local-rustfs-bootstrap.sh | bash
```

Defaults: RustFS S3 on `127.0.0.1:9000`, console on `:9001`, `omnigraph-server` on `:8080`, bucket `omnigraph-local`. Override with `BUCKET=foo PREFIX=repos/bar BIND=127.0.0.1:8080 curl ...`.

### AWS env vars (for `init`, `load`, and the server)

`init` and `load` write directly to S3-backed storage, and `omnigraph-server` reads from it at startup. Both need AWS credentials pointed at RustFS. Put these in `.env.omni`:

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

Reference via `auth.env_file: .env.omni` in `omnigraph.yaml` if you want the CLI to load it automatically.

### Validate the setup

```bash
curl http://127.0.0.1:8080/healthz
omnigraph snapshot s3://omnigraph-local/repos/<your-repo> --json
```

## Project Setup

### `omnigraph.yaml` is the backbone

Every project has one at its root defining graphs, default branch, query roots, and aliases. Run CLI commands from the folder where it lives — relative paths (`queries/`, `schema.pg`, `.env.omni`) resolve from there.

```yaml
graphs:
  local:
    uri: s3://omnigraph-local/repos/spike-intel
cli:
  graph: local
  branch: main
  output_format: jsonl
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
```

The config field is `graphs:` (not `targets:` — that's the old schema) and `cli.graph:` / `server.graph:` (not `target:`).

### Commit these, not those

**Commit:** `schema.pg`, `queries/*.gq`, `omnigraph.yaml`, `seed.md`, `seed.jsonl`, per-cookbook `README.md` and `CLAUDE.md`.

**Ignore:** `.env.omni` (credentials), `.claude/` (local agent state), `*.omni/` (local repo artifacts), `.omnigraph-rustfs-demo/` (bootstrap state).

### Give agents a CLAUDE.md

A per-cookbook `CLAUDE.md` tells coding agents where files live, what conventions matter, and how to validate. Without it, agents re-discover the same things every session.

## Schema Authoring

### Use `//` for comments in `.pg`

Not `#`. The compiler rejects `#` with a cryptic parse error.

### Enums are inline, not standalone

The compiler does **not** accept top-level `enum Foo { ... }` blocks. Inline them on the property:

```pg
kind: enum(product, technology, framework) @index
```

If the same enum values appear on multiple nodes, duplicate the inline declaration — there's no shared enum type.

### Lists contain scalars only

`[String]` and `[I32]` are fine. `[Category]` (a list of enum) is not supported. Use `[String]` with query-level filtering, or a single-valued enum property.

### `@embed` takes a quoted string argument

`@embed("text")`, not `@embed(text)`.

### Edge constraints go inside a body block

`@unique(src, dst)` on an edge goes inside `{ }`, not after `@card(...)`:

```pg
edge PartOfArtifact: Chunk -> InformationArtifact @card(1..1) {
    @unique(src)
}
```

### Lint after every edit

```bash
omnigraph query lint --schema ./schema.pg --query ./queries/signals.gq
```

This validates **both** the schema and the queries against it — no running repo required. Wire it into a precommit hook.

## Schema Evolution

### Plan before apply, always

```bash
omnigraph schema plan --schema ./next.pg s3://bucket/repo --json
omnigraph schema apply --schema ./next.pg s3://bucket/repo
```

`schema plan` returns `"supported": true|false` with the full step list. If `supported: false`, fix the source before applying. Apply is destructive — there's no undo.

### Apply is main-only

`omnigraph schema apply` rejects any non-`main` branches. Delete or merge feature branches first. This is deliberate — schema changes don't go through review branches.

### Rename, don't replace

Use `@rename_from(...)` on renames so the planner emits a rename step, not a drop+add pair (which loses data):

```pg
node Account @rename_from("User") {
    full_name: String @rename_from("name")
}
```

### Required properties need a backfill plan

Adding a non-nullable property to an existing node is rejected as unsupported. Pattern: make it optional, backfill with a `change` mutation or `load --mode merge`, then tighten to required in a follow-up `apply`.

### Keep keys stable

Changing `@key` is effectively a replace. Treat identity changes as deliberate, multi-step migrations — not a casual field rename.

## Query Authoring

### Parameterize everything

```gq
query get_signal($slug: String) {
    match { $s: Signal { slug: $slug } }
    return { $s.slug, $s.name }
}
```

Never string-interpolate into query bodies. Pass values as typed parameters so the compiler can check them.

### Name queries `verb_object`

`get_signal`, `recent_signals`, `signal_patterns`, `pattern_elements`. Group related queries in a single `.gq` file (one per primary node type, plus `mutations.gq`). Keep each query focused on one projection.

### Mutations must provide every non-nullable field

If `Element.kind` is non-nullable, every `add_element` mutation must accept and insert `kind`. Lint catches this as error `T12: insert for 'Element' must provide non-nullable property 'kind'`.

### Ranking functions require `limit`

`nearest(...)`, `bm25(...)`, and `rrf(...)` are order operators, not filters. Every query using them must end with `limit N` — omitting `limit` is a compile error.

### Use negation where it reads naturally

```gq
query orphan_signals() {
    match {
        $s: Signal
        not { $s formsPattern $_ }
    }
    return { $s.slug }
}
```

### Edge traversal uses lowerCamelCase

Edge `FormsPattern` is traversed as `$s formsPattern $p` in query patterns (schema uses PascalCase, queries use lowerCamelCase).

## Safe Data Changes

### Choose the right write command

| Task | Command | Notes |
|------|---------|-------|
| Add/update a single entity | `change` with a named mutation | parameterized, typechecked, auditable |
| Bulk upsert by `@key` | `load --mode merge` | preserves rows not in the file |
| Additive-only bulk | `load --mode append` | fails on key collision |
| Clean-slate reseed | `load --mode overwrite` | destructive; wipes the branch |

### `merge` does not recompute embeddings

Changing seed rows that feed into `@embed(...)` via `load --mode merge` updates the source field but leaves the stale embedding. Either run `omnigraph embed --reembed_all` after, or use `load --mode overwrite` once.

### `overwrite` is destructive

`load --mode overwrite` truncates the entire branch's data for every node and edge type before loading. Safe on first load; risky afterward. Don't run it against `main` in production without a branch backup path.

### Destructive ops go through a feature branch

For ingestion that could disrupt downstream queries (overwriting a heavily-referenced node type, removing edges en masse), use `ingest --from main` to create a branch, load the data, verify, then merge.

## Branches & Review

### Branches are for data; `schema plan/apply` is for schema

Data changes go through feature branches. Schema changes go straight to `main` via `plan` + `apply`. Don't try to evolve schema through a branch — apply rejects non-main branches.

### The review loop

```bash
omnigraph branch create --uri $REPO --from main staging-2026-04-14
omnigraph ingest --data ./delta.jsonl --branch staging-2026-04-14 --mode merge --uri $REPO
# run read queries against --branch staging-2026-04-14 to verify
omnigraph branch merge --uri $REPO staging-2026-04-14 --into main
```

### Keep branches short-lived

Long-lived branches compound merge risk. Ingest → verify → merge within the same session when possible.

## Search & Embeddings

### Embeddings are schema-declared

```pg
node Chunk {
    text: String
    embedding: Vector(3072) @embed("text") @index
}
```

The schema says where embeddings live and what they come from. Queries read, they don't compute.

### Scope first, rank second

Filter with graph traversal before invoking vector or text ranking. Ranking over a narrow set is both cheaper and more relevant.

```gq
query related_chunks($slug: String, $q: Vector(3072)) {
    match {
        $a: InformationArtifact { slug: $slug }
        $c partOfArtifact $a
    }
    return { $c.text }
    order { nearest($c.embedding, $q) }
    limit 10
}
```

### Refresh after `@embed` changes

If you change the source field or mutate the text at scale:

```bash
omnigraph embed --seed ./embed-config.yaml --reembed_all
```

`--reembed_all` regenerates; the default is `fill_missing`.

## Aliases & Agent Automation

### Every agent operation should be an alias

Agents calling raw `omnigraph read --query ... --name ... --params ...` drift as queries evolve. Aliases decouple the operation name from the query implementation:

```yaml
aliases:
  signal:
    command: read
    query: signals.gq
    name: get_signal
    args: [slug]
    format: kv
```

Agents call `omnigraph read --alias signal sig-kimi-k25`. When the query changes, the alias stays.

### Default to structured output

For scripts and agents, use `--format jsonl` or `--format json`. `table` is for humans. Set `cli.output_format: jsonl` globally for an automation-first config.

### Alias args are JSON-first

Positional args are parsed as JSON, then fall back to string. `29` is an integer, `"29"` is a string, `true` is a boolean, `Alice` is a string. Explicit `--params` wins on key conflict.

### Secrets belong in `.env.omni`

Reference via `auth.env_file: .env.omni`. Aliases should only contain query names and parameter bindings — never tokens.

## Server Operation

### Start the server

The server is the canonical runtime entry point — point the CLI, aliases, and agents at it. Start it once per repo:

```bash
omnigraph-server --config ./omnigraph.yaml
```

Reads `server.graph` and `server.bind` from your config. Keep it running in a separate terminal or background process.

### HTTP routes

| Route | Purpose |
|-------|---------|
| `GET /healthz` | liveness probe |
| `GET /snapshot` | table state + row counts |
| `GET /export` | JSONL stream of a branch |
| `POST /read` | read query execution |
| `POST /change` | mutation execution |
| `POST /schema/apply` | schema migration |
| `GET /branches` | branch list |
| `GET /runs`, `GET /commits` | transactional history |

### Auth

Set `OMNIGRAPH_SERVER_BEARER_TOKEN` on the server process. On the client side, declare `bearer_token_env: OMNIGRAPH_BEARER_TOKEN` in `graphs.<name>` and export a matching token. Leave auth off for pure local dev.

### Setup operations (`init`, `load`) write directly to storage

`init` and `load` write the repo on disk or in S3 — they don't go through the server. Pass the repo URI directly:

```bash
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/<name>
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/<name>
```

Everything else — `read`, `change`, `snapshot`, `schema plan/apply`, `branch`, `run`, `commit` — goes through the running server via the CLI's default `cli.graph` target.

## Policy & Authorization

### Gate the dangerous actions

Cedar policies can gate `schema_apply`, `branch_merge`, `change`, `export`, etc. For any shared repo, gate at least `schema_apply` and `branch_merge`.

### Validate, test, explain

```bash
omnigraph policy validate --config ./omnigraph.yaml
omnigraph policy test --config ./omnigraph.yaml
omnigraph policy explain --actor act-alice --action schema_apply --branch main
```

`validate` checks Cedar syntax; `test` runs cases from `policy.tests.yaml`; `explain` debugs a single decision.

## Reference Commands

Commands you'll reach for but don't need best-practice rules around.

### Inspect state

```bash
omnigraph snapshot $REPO --branch main --json         # tables + row counts
omnigraph export $REPO --branch main > graph.jsonl    # stream JSONL dump
```

`export` is the right tool for large snapshots — don't try to page through the whole graph via read queries.

### Runs and commits

```bash
omnigraph run list $REPO                 # active/recent transactional runs
omnigraph run show $REPO <id>
omnigraph run publish $REPO <id>         # finalize
omnigraph run abort $REPO <id>

omnigraph commit list $REPO --branch main
omnigraph commit show $REPO <id>
```

### Init scaffolding

`omnigraph init --schema ./schema.pg $REPO` scaffolds an `omnigraph.yaml` if one doesn't exist. Review the template before committing — it has placeholder graphs and no aliases.

### Config resolution order

1. Explicit `--uri` or positional URI wins
2. `--target <name>` selects a named graph from `omnigraph.yaml`
3. Config default (`cli.graph`) wins last

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| `#` comments in `.pg` | `parse error: expected schema_file` | Use `//` |
| Standalone `enum Foo { ... }` block | `parse error: expected EOI or schema_decl` | Inline: `kind: enum(a, b)` |
| `[Category]` (list of enum) | compile error | Use `[String]` |
| `@embed(text)` without quotes | `unexpected constraint_name` | `@embed("text")` |
| `@unique(src)` on edge without body block | parse error | `@card(1..1) { @unique(src) }` |
| `load --mode merge` after `@embed` change | stale embeddings | `embed --reembed_all` or `load --mode overwrite` |
| `schema apply` with feature branches open | rejected | Merge or delete branches first |
| `nearest(...)` without `limit` | compile error | Add `limit N` |
| Adding required property without backfill | unsupported migration | Make optional first, backfill, then tighten |
| `targets:` in `omnigraph.yaml` | `graph 'X' not found in omnigraph.yaml` | Rename to `graphs:`, `target:` → `graph:` |
| `omnigraph init --json` | `unexpected argument --json` | `init` doesn't accept `--json` |
| Committing `.env.omni` | credential leak | Add `.env*` to `.gitignore` |
| Non-parameterized values in queries | typecheck surprise, injection risk | Declare `$param: Type` and pass via `--params` |
| Long-lived feature branches | merge conflicts, schema apply blocked | Merge promptly; delete when done |

## See Also

- [`omni-schema.md`](./omni-schema.md) — schema design principles
- [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph) — upstream repo
