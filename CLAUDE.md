# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Repo-wide guidance. Each cookbook also has its own `CLAUDE.md` — read both when working inside one.

## What This Repo Is

A collection of Omnigraph graph cookbooks. Each cookbook is self-contained in its folder (schema, seed, queries, cluster config — no application code). Five cookbooks ship today: `industry-intel/` (AI/ML intel on the SPIKE framework — Signal, Pattern, Insight, KnowHow, Element), `pharma-intel/` (pharma competitive intelligence), `second-brain/` (personal-life automation graph), `vc-os/` (venture-capital operating system), and `dev-graph/` (software-development knowledge graph). See `README.md` for the full list and planned cookbooks.

## Architecture

- **Storage**: all five cookbooks are **filesystem-backed cluster** deployments — `cluster apply` creates the derived root `graphs/<id>.omni`; **no object store / RustFS needed**. (S3-compatible storage, `s3://bucket/prefix`, is supported for production; the SPIKE cookbooks document an optional S3 path.) `init` and direct-store `load` write storage directly — one-time setup ops that bypass the server.
- **Runtime**: `omnigraph-server` reads from storage at startup and exposes HTTP on `127.0.0.1:8080`. Day-to-day CLI calls (`query`, `mutate`) go through the server.
- **CLI config**: Per-operator settings (identity, named servers, defaults, **aliases**) live in `~/.omnigraph/config.yaml` (per-user, never committed). Each cookbook ships an `omnigraph-config.example.yaml` whose `aliases:` you merge in — short names binding to the graph's stored queries, invoked with `omnigraph alias <name> [args]` (e.g. `omnigraph alias pattern-signals pat-sovereign-ai`). Alias arg values are JSON-parsed first, then fall back to string — `29` is an integer, `"29"` is a string. Cookbooks ship no `omnigraph.yaml`; the engine does not read it.
- **Auth**: filesystem clusters need no credentials. For an optional S3 backend, `.env.omni` (git-ignored) holds the `AWS_*` creds; source it before CLI commands: `set -a && source .env.omni && set +a`.
- **Versioning**: these cookbooks target OmniGraph 0.11.0 (graph format v9). 0.11 cannot open a 0.10 (format v6) graph, and a cluster-managed root cannot be upgraded in place. A cookbook checkout is rebuilt from `seed.jsonl` by `cluster apply` + `load`, so upgrading one is delete `graphs/` and `__cluster/`, then apply and load again. A graph holding real data is exported with the old CLI and loaded into a freshly applied cluster under the new one — follow the engine upgrade guide, keep a verified whole-root backup, never run mixed old/new processes against one graph, and don't replace a real graph from seed unless the seed is intentionally its source of truth.

**Prerequisite**: just the `omnigraph`/`omnigraph-server` binaries — no object store. `lint` works with nothing running; once a server is up, verify with `curl http://127.0.0.1:8080/healthz`.

## Canonical Workflow

1. **Edit** `schema.pg` or `queries/*.gq`. Comments in both use `//` not `#`.
2. **Lint** — `omnigraph lint --schema schema.pg --query queries/<file>.gq` validates queries against the schema. Run after any edit. This is a pure file check: no server or storage needed.
3. **Schema changes** — plan before apply, always: edit the `.pg`, then `omnigraph cluster plan --config .` (shows real migration steps) and `omnigraph cluster apply --config . --as <you>`, then restart the `--cluster` server. Use `@rename_from(...)` for property/type renames.
4. **Data changes** — pick the right write command: `mutate` for served edits; `load` for bulk JSONL with a **required** `--mode` (`merge` upsert · `append` strict-insert · `overwrite` replaces the node/edge types present in the batch). `load --from main --branch <name>` forks a review branch in one shot. `load` works against local storage or a server. Review bulk loads on a branch, then merge.
5. **Never string-interpolate** into `.gq` bodies or `--params` — parameterize everything.

There are no repo-level build, test, or lint commands. Validation happens per-cookbook via `omnigraph lint`. CI is not configured in this repo.

## Setting a cookbook up, in order

Every cookbook is a **cluster directory**: `cluster.yaml` declares the deployment (graph id, `schema.pg`, every stored query under `queries/`); `cluster apply` converges it into `graphs/<id>.omni`; `omnigraph-server --cluster .` serves it. Per-operator settings (aliases, defaults, identity) live in `~/.omnigraph/config.yaml`, never committed — each cookbook ships an `omnigraph-config.example.yaml` to merge in, and a `--cluster` server never reads it. Never commit `graphs/` or `__cluster/` (gitignored, local derived state).

`cluster import` comes **before** the first `apply`: without it `apply` exits 1 with
`state_missing __cluster/state.json: apply requires an existing state.json`.

```bash
cd <cookbook>                                       # configs and paths are relative to the cookbook
omnigraph cluster validate --config .
omnigraph cluster import   --config .               # once: bootstraps __cluster/state.json
omnigraph cluster plan     --config .               # preview — read it before apply
omnigraph cluster apply    --config . --as <you>    # creates graphs/<id>.omni, applies schema + stored queries
omnigraph load --data seed.jsonl --mode overwrite graphs/<id>.omni
omnigraph-server --cluster . --bind 127.0.0.1:8080 --unauthenticated &   # refuses to start without this flag or auth
curl -s http://127.0.0.1:8080/healthz               # {"status":"ok",…}; the path is /healthz — /health is 404
```

`industry-intel` ships a Cedar policy, so its server takes **tokens** instead of `--unauthenticated`: `export OMNIGRAPH_SERVER_BEARER_TOKENS_JSON='{"act-admin":"local-admin-token","act-writer":"local-writer-token","act-reader":"local-reader-token"}'`, then `omnigraph-server --cluster . --bind 127.0.0.1:8080 &`, then `printf '%s' 'local-reader-token' | omnigraph login local` (the writer token for mutations). Each cookbook's `CLAUDE.md` carries this block with its graph id filled in. Leave the server running in a separate terminal or background process.

### `load` addressing

`--data` is the **seed file**; the **graph** is the positional URI. Both are required, as is `--mode`.

| Target | Command |
|---|---|
| Local storage, no server | `omnigraph load --data seed.jsonl --mode overwrite graphs/<id>.omni` |
| A running server | `omnigraph load --data seed.jsonl --mode overwrite --server http://127.0.0.1:8080 --graph <id> --yes` |

One address per command. The engine's own refusals:

- `--graph` next to a positional URI or `--store` → *"--graph selects a graph within a server or cluster scope; a positional URI / --store is already a single graph"*. `--graph` selects **within** a `--server` or `--cluster` scope; a positional URI or `--store` already names one graph.
- `--cluster` on `load` → *"`load` is a data command; --cluster addresses a cluster-scoped command and does not apply."*
- `omnigraph load seed.jsonl …` — the positional slot is the **graph**, never the data file.
- `overwrite` through a server prompts, so non-interactive callers add `--yes`.

## Answering and writing (agents)

- **Answer from the graph, not the files.** Use the aliases / stored queries against the running server; never assemble an answer by reading `seed.jsonl` or `seed.md` — they are load inputs, not the live state.
- **Find the query instead of guessing it.** `omnigraph queries list --cluster . --graph <id>` prints every stored query and mutation *with its parameter names*, offline, no server needed. Read the signature before writing `--params`: `query search_signals($q: String)` takes `{"q":…}`, not `{"term":…}`.
- **Alias args bind by name to the query's `$params`** (`args: [slug]` fills `$slug`): `omnigraph alias pattern-signals pat-sovereign-ai` is `omnigraph query pattern_signals --graph spike --params '{"slug":"pat-sovereign-ai"}'`. Arg values are JSON-parsed first, then string — `29` is an integer, `"29"` a string.
- **An alias carries its own server and graph** — adding `--graph`/`--server` to `omnigraph alias` errors with *"remove global scope flag(s)"*. There is no `--list`; alias names are the keys under `aliases:` in `omnigraph-config.example.yaml`. **An alias name is not a query name**: `queries list` prints `epic_issues` and `get_person`, whose aliases are `epic-issues` and `person` — hyphenated, often shorter.
- **Aliases are read-only.** A stored mutation bound to an alias is refused; run mutations with `omnigraph mutate <name> --graph <id> --params '<json>'`, every non-optional property supplied. Signatures come from `queries list`; each cookbook's `CLAUDE.md` has a worked example. With `defaults.server` / `default_graph` in the operator config, `--graph` can be omitted.
- **`omnigraph query <name>` is a stored query by name and needs a server** — passing query text there fails with *"by-name invocation needs a server (the stored-query catalog is server-owned)"*. Ad-hoc GQL goes through `-e`, in the dialect of the `.gq` files:

  ```bash
  omnigraph query -e 'query q($slug: String) { match { $p: Pattern { slug: $slug } $s formsPattern $p } return { $s.slug, $s.name } }' \
    --params '{"slug":"pat-sovereign-ai"}' --server http://127.0.0.1:8080 --graph spike
  ```

  Against a server, `--graph <id>` is required — without it the server answers `404 Not Found`.
  With no server, address the storage instead: `--store file://$PWD/graphs/<id>.omni` (no
  `--graph`). The parameter list is required even when empty (`query q()`). Property filters bind inside the node's braces (`$p: Pattern { slug: $slug }`) or as predicate lines in `match` (`$p.age > 30`); an edge is traversed as its name in lowerCamelCase between two bound variables (`$s formsPattern $p` for `FormsPattern`); `limit N` and `order { … }` sit inside the query block after `return`. The full dialect — traversal, search, aggregation, mutations — is in the vendored **omnigraph** skill (`.claude/skills/omnigraph/references/queries.md`).
- **Full-text `search()` is case-sensitive**: the term must match the stored casing — `Zylon` matches, `zylon` returns 0 rows with no error.

## Skills and Docs

- **`omnigraph` skill** (day-to-day ops: CLI, `.pg`/`.gq` dialect, cluster, loading, branches) is **vendored** at `.claude/skills/omnigraph/` (Claude Code) and `.agents/skills/omnigraph` (Codex — a symlink to the same directory), pinned to the engine release in `deploy/railway/Dockerfile`; both clients discover it in this repo with no install step. Other clients: `npx skills add ModernRelay/omnigraph@omnigraph`. After bumping `OMNIGRAPH_REF`, run `scripts/sync-skill.sh` so the skill matches the engine.
- `industry-intel/skill/` — bootstrap a new SPIKE graph (elicitation + research + apply/load); install with `npx skills add https://github.com/ModernRelay/omnigraph-cookbooks/tree/main/industry-intel/skill`
- Every `AGENTS.md` is a symlink to the `CLAUDE.md` beside it, so Codex reads the same guidance.

When working on schema or ops questions, consult the skill and the engine repo's docs rather than duplicating guidance here.

## Railway Deploy

`railway.toml` (repo root — Railway requires it there) + `deploy/railway/` deploy any cookbook as a managed cloud service backed by a Railway Bucket (S3-compatible). Key facts, all detailed in `deploy/railway/README.md`:

- **Schema-only, cluster-mode (OmniGraph 0.11.0)**: the cookbook cluster configs are bundled in the image; `init.sh` selects one via `OMNIGRAPH_COOKBOOK`, points its `storage:` at the Bucket, and converges it with `cluster validate` → `import` (fresh Bucket only) → `apply`. Seed data is not auto-loaded. Idempotent across re-deploys; the server boots config-free via `--cluster $OMNIGRAPH_CLUSTER_URI`.
- The Dockerfile pins the engine via `ARG OMNIGRAPH_REF` — bump it on engine releases; a format-changing release requires the export/rebuild recipe in the deploy README. Cookbook config changes ship with the image (Railway rebuilds on every repo deploy).
- Sharp edges documented there: service region **must** match the Bucket region (cross-region makes writes unusable), keep a **single replica** (single-writer store — replicas corrupt the graph), and direct `load` to the Bucket requires a version-matched CLI run in-region (or go through the server).
- Auth is `act-admin`/`act-writer`/`act-reader` bearer tokens via `OMNIGRAPH_SERVER_BEARER_TOKENS_JSON`; policy is applied **cluster state**. Template bundles at `deploy/railway/config/*.railway.yaml` are injected for cookbooks without their own `policies:`; industry-intel's own policy accepts the same generated actors.

## When Adding a New Cookbook

- Create the folder with `README.md`, `CLAUDE.md`, `schema.pg`, `cluster.yaml` (the deployment), `omnigraph-config.example.yaml` (example operator aliases), `queries/`, and seed data (`seed.md` + `seed.jsonl`)
- Ship real seed data, not placeholders
- A `@key` value (`slug` by convention) must appear only once per `seed.jsonl` — since 0.8.0 a key repeated within one load batch fails the whole load. Same for duplicate edge rows on `@unique(src)`/`@unique(src,dst)` edges.
- Keep the cookbook's README and CLAUDE in sync with its schema
- Expose agent-facing operations as aliases in the operator config (ship them in `omnigraph-config.example.yaml`), not raw CLI invocations

Omnigraph reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).
