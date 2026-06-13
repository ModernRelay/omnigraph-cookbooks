# Omnigraph Best Practices

Operational guide for working with Omnigraph: project layout, schema evolution, queries, data changes, branches, and agent automation.

For schema **design** principles (identity, types, edges, constraints) see [`omni-schema.md`](omni-schema.md). This doc is about how to **operate** an Omnigraph project day-to-day.

> **Cluster mode (omnigraph >= 0.7.0):** new projects should prefer the
> declarative cluster control plane — `cluster.yaml` + `omnigraph cluster
> plan/apply` + `omnigraph-server --cluster .` (or `--cluster s3://bucket/prefix`
> for config-free serving from object storage) — over hand-managed
> `omnigraph.yaml` deployments. Per-operator settings (identity, named servers,
> credentials, aliases) live in `~/.omnigraph/config.yaml` (RFC-007/008;
> `omnigraph.yaml` is the deprecated combined file). See the omnigraph repo's
> `docs/user/cluster.md` and the `omnigraph-best-practices` skill's
> `references/cluster.md`. Everything below remains valid for the classic
> single-graph path and for all data-plane operations.

## TL;DR

1. **Lint before commit** — `omnigraph lint --schema schema.pg --query queries/foo.gq`
2. **Plan before apply** — never `schema apply` without a successful `schema plan` first (cluster mode: `cluster plan` before `cluster apply`)
3. **Branches are for data; apply is for schema** — review bulk data loads on a branch, then merge; schema changes go straight to `main`
4. **Pick the right write command** — `mutate` for edits; `load` for bulk JSONL with a **required** `--mode` (`merge`/`append`/`overwrite`); `load --from <base>` forks a review branch
5. **Parameterize everything** — never string-interpolate into `.gq` bodies or `--params`
6. **Expose agent operations as aliases** — not raw CLI invocations

## Local Setup

### Storage: filesystem or S3

A graph's bytes live in one of two backends:

- **Local filesystem** — a path or `file://` URI. In cluster mode `storage:` defaults to the config directory, so local dev needs **no object store**; `cluster apply` creates the derived root `graphs/<id>.omni`.
- **S3-compatible object storage** — AWS, Railway, Tigris, or a local RustFS for dev (`s3://bucket/prefix`). Authenticate with the standard `AWS_*` environment contract.

`init` and `load` write storage directly (bypassing the server); `omnigraph-server` reads from it at startup.

### Local S3 dev with RustFS (optional)

For the classic single-graph S3 path, run a local RustFS (S3-compatible) in Docker:

```bash
docker version >/dev/null 2>&1 || { echo "Install Docker first: https://docs.docker.com/get-docker/"; exit 1; }
curl -fsSL https://raw.githubusercontent.com/ModernRelay/omnigraph/main/scripts/local-rustfs-bootstrap.sh | bash
```

Defaults: RustFS S3 on `127.0.0.1:9000`, console on `:9001`, `omnigraph-server` on `:8080`, bucket `omnigraph-local`. Put the matching creds in a git-ignored `.env.omni`:

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
set -a && source .env.omni && set +a
```

### Validate the setup

```bash
curl http://127.0.0.1:8080/healthz
omnigraph snapshot <graph-uri> --json
```

## Project Setup

### The two config surfaces (omnigraph >= 0.7.0)

Configuration has two single-owner homes (RFC-007/008):

- **`cluster.yaml`** (the team, in the repo) — the deployment: graphs, schemas, stored queries, policies, and an optional S3 `storage:` root. Read by `cluster` commands and `omnigraph-server --cluster`.
- **`~/.omnigraph/config.yaml`** (per operator) — identity (`operator.actor`), named `servers:`, output defaults, and personal aliases. Credentials go in `~/.omnigraph/credentials` via `omnigraph login <server>` (never in any config file).

```yaml
# ~/.omnigraph/config.yaml
operator:
  actor: act-andrew
servers:
  intel-dev: { url: https://graph.example.com }
defaults:
  output: jsonl
aliases:
  triage: { server: intel-dev, graph: spike, query: weekly_triage, args: [since] }
```

> **Legacy `omnigraph.yaml` (deprecated, RFC-008).** The old combined file still works through the deprecation window but prints a per-key notice on load (silence with `OMNIGRAPH_SUPPRESS_YAML_DEPRECATION=1`; `OMNIGRAPH_NO_LEGACY_CONFIG=1` hard-errors). `omnigraph config migrate [--write]` splits it into `cluster.yaml` + `~/.omnigraph/config.yaml`; `omnigraph init` no longer scaffolds it. Run data-plane CLI commands from a graph's project folder so relative `queries/`, `schema.pg`, `.env.omni` paths resolve. Field naming in the legacy file: `graphs:` (not `targets:`), `cli.graph`/`server.graph` (not `cli.target`/`server.target`).

### Commit these, not those

**Commit:** `schema.pg`, `queries/*.gq`, `cluster.yaml`, the per-operator `omnigraph.yaml` (legacy, still shipped by the cookbooks), `seed.md`, `seed.jsonl`, per-cookbook `README.md` and `CLAUDE.md`.

**Ignore:** `.env.omni` (credentials), `.claude/` (local agent state), `*.omni/` (local graph artifacts), `__cluster/` and `graphs/` (cluster state + derived roots).

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

`@unique(src, dst)` on an edge goes inside a `{ }` body block, after `@card(...)`:

```pg
edge PartOfArtifact: Chunk -> InformationArtifact @card(1..1) {
    @unique(src)
}
```

### Lint after every edit

```bash
omnigraph lint --schema schema.pg --query queries/signals.gq
```

This validates **both** the schema and the queries against it — no running repo required. Wire it into a precommit hook.

## Schema Evolution

### Plan before apply, always

```bash
omnigraph schema plan --schema next.pg s3://bucket/repo --json
omnigraph schema apply --schema next.pg s3://bucket/repo
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

Adding a non-nullable property to an existing node is rejected as unsupported. Pattern: make it optional, backfill with a `mutate` or `load --mode merge`, then tighten to required in a follow-up `apply`.

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

`load` is the one bulk-JSONL command — local **or** remote, with a **required** `--mode` (no default). `load --from <base>` forks a missing `--branch` from `<base>` and loads onto it in one shot. (`ingest` is a deprecated alias of `load --from main --mode merge`.)

| Task | Command | Notes |
|------|---------|-------|
| Add/update a single entity | `mutate` with a named mutation | parameterized, typechecked, auditable |
| Bulk upsert by `@key` | `load --mode merge` | preserves rows not in the file |
| Additive-only bulk | `load --mode append` | fails on key collision |
| Clean-slate reseed | `load --mode overwrite` | destructive; wipes the branch |
| Bulk load onto a review branch | `load --from main --mode merge --branch <name>` | forks `<name>` from `main`, leaves it for review |

### `merge` does not recompute embeddings

Changing seed rows that feed into `@embed(...)` via `load --mode merge` updates the source field but leaves the stale embedding. Either run `omnigraph embed --reembed_all` after, or use `load --mode overwrite` once.

### `overwrite` is destructive

`load --mode overwrite` truncates the entire branch's data for every node and edge type before loading. Safe on first load; risky afterward. Don't run it against `main` in production without a branch backup path.

### Destructive ops go through a feature branch

For a bulk load that could disrupt downstream queries (overwriting a heavily-referenced node type, removing edges en masse), use `load --from main --branch <name>` to fork a branch, load the data, verify, then merge.

## Branches & Review

### Branches are for data; `schema plan/apply` is for schema

Data changes go through feature branches. Schema changes go straight to `main` via `plan` + `apply`. Don't try to evolve schema through a branch — apply rejects non-main branches.

### The review loop

```bash
omnigraph branch create --uri $REPO --from main staging-2026-04-14
omnigraph load --data delta.jsonl --branch staging-2026-04-14 --mode merge --uri $REPO
# run read queries against --branch staging-2026-04-14 to verify
omnigraph branch merge --uri $REPO staging-2026-04-14 --into main
```

### Keep branches short-lived

Long-lived branches compound merge risk. Load → verify → merge within the same session when possible.

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
omnigraph embed --seed embed-config.yaml --reembed_all
```

`--reembed_all` regenerates; the default is `fill_missing`.

### Two embedding clients

Omnigraph runs two distinct embedding clients: the **engine/ingest** client (default `gemini-embedding-2-preview`, 3072-dim — this is what `@embed` uses at load time, configured via `GEMINI_API_KEY` / `OMNIGRAPH_GEMINI_BASE_URL`) and the **compiler/query-time** client (default `text-embedding-3-small`, OpenAI-style, configured via `OPENAI_*` / `NANOGRAPH_EMBED_MODEL`) that auto-embeds a query string passed to a ranking op. `Vector(N)` must match the **ingest** model's dimension; keep the query-time model on the same dimension or similarity search breaks.

## Aliases & Agent Automation

### Every agent operation should be an alias

Agents calling raw `omnigraph query --query ... --name ... --params ...` drift as queries evolve. Aliases decouple the operation name from the query implementation:

```yaml
aliases:
  signal:
    command: query
    query: signals.gq
    name: get_signal
    args: [slug]
    format: kv
```

Agents call `omnigraph query --alias signal sig-kimi-k25`. When the query changes, the alias stays. (Operator aliases in `~/.omnigraph/config.yaml` are pure bindings to a server's stored queries — `{ server, graph, query }` — carrying no `.gq` content.)

### Default to structured output

For scripts and agents, use `--format jsonl` or `--format json`. `table` is for humans. Set `cli.output_format: jsonl` globally for an automation-first config.

### Alias args are JSON-first

Positional args are parsed as JSON, then fall back to string. `29` is an integer, `"29"` is a string, `true` is a boolean, `Alice` is a string. Explicit `--params` wins on key conflict.

### Secrets stay out of config

Remote bearer tokens go in `~/.omnigraph/credentials` via `omnigraph login <server>`; S3 storage creds go in a git-ignored `.env.omni`. Aliases should only contain query names and parameter bindings — never tokens.

## Server Operation

### Start the server

The server is the canonical runtime entry point — point the CLI, aliases, and agents at it. Start it once per deployment from one of the mutually-exclusive boot sources:

```bash
omnigraph-server --cluster . --unauthenticated               # cluster mode (or --cluster s3://bucket/prefix for config-free serving)
omnigraph-server s3://my-bucket/repos/<name> --unauthenticated   # a single bare graph URI
omnigraph-server --config omnigraph.yaml --unauthenticated   # legacy combined file (deprecated)
```

`--unauthenticated` is required for local dev: since v0.6.0 the server refuses to start without bearer tokens or a policy file. Drop the flag once you've configured auth (see below). `--config` reads `server.graph`/`server.bind`; `--cluster` reads the applied ledger. Keep the server running in a separate terminal or background process.

### HTTP routes

| Route | Purpose |
|-------|---------|
| `GET /healthz` | liveness probe |
| `GET /snapshot` | table state + row counts |
| `GET /export` | JSONL stream of a branch |
| `POST /query` | read query execution |
| `POST /mutate` | mutation execution |
| `GET /queries`, `POST /queries/{name}` | stored-query catalog + invocation (v0.6.1) |
| `POST /schema/apply` | schema migration |
| `GET /branches` | branch list |
| `GET /commits` | write/audit history |

> There is **no `/runs` endpoint** — the transactional Run state machine was removed in v0.4.0. Use `GET /commits` for write history; a request to `/runs` returns 404.

### Auth

Set bearer tokens on the server process — `OMNIGRAPH_SERVER_BEARER_TOKENS_JSON='{"act-reader":"…"}'` (actor-keyed) or the single-token `OMNIGRAPH_SERVER_BEARER_TOKEN`. On the client side (0.7.0), register the server once with `omnigraph login <server>` (token → `~/.omnigraph/credentials`, `0600`) and target it with `--server <server>`; the token resolves via `OMNIGRAPH_TOKEN_<NAME>` → the credentials file → the legacy `bearer_token_env` chain. **Since v0.6.0 the server refuses to start** with neither bearer tokens nor a policy file — for pure local dev pass `--unauthenticated` (or `OMNIGRAPH_UNAUTHENTICATED=1`) deliberately.

### Setup operations (`init`, `load`) write directly to storage

`init` and `load` write the repo on disk or in S3 — they don't go through the server. Pass the repo URI directly:

```bash
omnigraph init --schema schema.pg s3://my-bucket/repos/<name>
omnigraph load --data seed.jsonl --mode overwrite s3://my-bucket/repos/<name>
```

Everything else — `query`, `mutate`, `snapshot`, `schema plan/apply`, `branch`, `commit` — goes through the running server via the CLI's default graph target.

## Policy & Authorization

### Gate the dangerous actions

Cedar policies can gate `schema_apply`, `branch_merge`, `change`, `export`, `invoke_query`, etc. For any shared repo, gate at least `schema_apply` and `branch_merge`. (`invoke_query`, v0.6.1, gates the stored-query surface — stored mutations are double-gated with `change`.)

### Config follows identity (v0.6.1)

A top-level `policy:` (and `queries:`) block applies **only** to an anonymous bare-URI single-graph server. A graph served **by name** (`server.graph` / `--target`) must nest them under `graphs.<name>.policy` / `graphs.<name>.queries`. Leaving them at the top level with a named graph makes the server **refuse to boot** with migration guidance.

### Validate, test, explain

```bash
omnigraph policy validate --config omnigraph.yaml
omnigraph policy test --config omnigraph.yaml
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

### Maintenance & stored queries (v0.6.1)

```bash
omnigraph optimize $REPO --json                      # non-destructive Lance compaction (skips Blob-column tables; see --json "skipped")
omnigraph cleanup  $REPO --keep 5 --older-than 7d --confirm   # destructive version GC
omnigraph queries validate                           # type-check the stored-query registry vs live schema (offline)
omnigraph queries list                               # list registry queries, MCP exposure, typed params
```

### Commits

```bash
omnigraph commit list $REPO --branch main
omnigraph commit show $REPO <id>
```

### Init

`omnigraph init --schema schema.pg $REPO` creates a graph at `$REPO`. **It no longer scaffolds a config file** (RFC-008) — start a `cluster.yaml` from the omnigraph repo's `docs/user/cluster.md`, or run `omnigraph config migrate` against an existing legacy `omnigraph.yaml`. `init` does not accept `--json`.

### Config resolution order

1. Explicit `--uri` or positional URI wins
2. `--server <name>` (with optional `--graph <id>`) selects an operator-defined endpoint from `~/.omnigraph/config.yaml` — the modern remote path
3. `--target <name>` selects a named graph from a legacy `omnigraph.yaml`
4. Config default (`cli.graph`) wins last

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
| `omnigraph load` without `--mode` | `--mode` is required | Pass `--mode merge\|append\|overwrite` (no default; overwrite is destructive) |
| `omnigraph init` writes no config file | expected (RFC-008) — `init` stopped scaffolding it | Start a `cluster.yaml`, or `config migrate` a legacy `omnigraph.yaml` |
| `@unique` on a `[List]`/`Blob` column | `load` errors loudly (was silently un-enforced) | `@unique` needs a scalar (or composite-scalar) key |
| `omnigraph init --json` | `unexpected argument --json` | `init` doesn't accept `--json` |
| Committing `.env.omni` | credential leak | Add `.env*` to `.gitignore` |
| Non-parameterized values in queries | typecheck surprise, injection risk | Declare `$param: Type` and pass via `--params` |
| Long-lived feature branches | merge conflicts, schema apply blocked | Merge promptly; delete when done |
| Top-level `policy:`/`queries:` with a named graph (v0.6.1) | server refuses to boot | Nest under `graphs.<name>.policy` / `.queries` |
| `omnigraph optimize` "skipping" a Blob table | not an error — Lance blob-v2 limitation | Expected; non-blob tables still compact |

## See Also

- [`omni-schema.md`](omni-schema.md) — schema design principles
- [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph) — upstream repo
