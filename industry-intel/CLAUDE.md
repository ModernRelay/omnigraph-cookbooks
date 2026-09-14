# CLAUDE.md — industry-intel

Scoped guidance for the `industry-intel/` SPIKE cookbook. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

An Omnigraph schema + seed modeling AI/ML industry intelligence using the SPIKE framework. Schema, seed data, and queries only — no application code.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — Reference seed description, schema essentials, quick start.
- `seed.md` / `seed.jsonl` — Seed dataset (human-readable / loadable).
- `queries/*.gq` — Read and mutation queries.
- `omnigraph-config.example.yaml` — example operator config (aliases over the stored queries); merge into your per-user `~/.omnigraph/config.yaml`.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

## Answering and writing (agents)

- **Answer from the graph, not the files.** Use the aliases / stored queries against the running server; never assemble an answer by reading `seed.jsonl` or `seed.md` — they are load inputs, not the live state.
- **Alias args bind by name to the query's `$params`** (`args: [slug]` fills `$slug`): `omnigraph alias pattern-signals pat-sovereign-ai` is `omnigraph query pattern_signals --graph spike --params '{"slug":"pat-sovereign-ai"}'`.
- **Mutations are not aliasable on 0.10** (`'add_x' is a mutation — use omnigraph mutate add_x`). Run them with `omnigraph mutate <name> --params '<json>'`, every non-optional property supplied; signatures live in `queries/mutations.gq`. Working example:

  ```bash
  printf '%s' 'local-writer-token' | omnigraph login local   # mutations need the writer token, not the reader one
  omnigraph mutate add_signal --graph spike --params '{"slug":"sig-eu-sovereign-cloud","name":"EU mandates sovereign cloud for public-sector AI","brief":"Public-sector AI workloads must run on EU-controlled infrastructure.","stagingTimestamp":"2026-09-14T00:00:00Z","createdAt":"2026-09-14T00:00:00Z","updatedAt":"2026-09-14T00:00:00Z"}'
  omnigraph mutate link_signal_forms_pattern --graph spike --params '{"signal":"sig-eu-sovereign-cloud","pattern":"pat-sovereign-ai"}'
  ```

  With `defaults.server` / `default_graph` from the operator config, `--graph` can be omitted.
- **Full-text `search()` is case-sensitive** (the `search_*` queries, invoked via `omnigraph query search_signals --graph spike --params '{"q":"Zylon"}'`): the term must match the stored casing — `Zylon` matches, `zylon` returns 0 rows with no error.

## Schema Language (`.pg`)

- `node` defines entity types; `edge` defines typed relationships (`edge Name: Source -> Target`)
- `@key` marks external identity (always `slug` here)
- `@index`, `@unique`, `@card(min..max)`, `@range(lo..hi)`, `@embed("prop")`
- `?` = optional, `[Type]` = list, `enum(...)` = inline closed set
- Comments use `//` not `#`

## Domain Model

**SPIKE Nodes:** Signal, Element, Pattern, Insight, KnowHow
**Supportive:** Company, SourceEntity, Expert, InformationArtifact, Chunk

**Core analytical loop:** Signals form or contradict Patterns. Patterns drive or rely on other Patterns. Everything else supports this loop or maps the domain.

**Design choices to preserve:**
- Flat `kind` enums on Element and Pattern — no interfaces or subtypes
- ElementKind: `product, technology, framework, concept, ops`
- PatternKind: `challenge, disruption, dynamic`
- Domain is an enum property on Signal/Element, not a node
- Edges follow `VerbTargetType` naming (e.g. `FormsPattern`, `DevelopedByCompany`)
- Embeddings only on Chunk: `Vector(3072) @embed("text")`. OmniGraph 0.10 does not populate `@embed` fields during load; prepare vectors with the offline JSONL-to-JSONL `omnigraph embed` pipeline, then load that output. The query-time provider must use the same model and dimension.
- Chunk is immutable (no `updatedAt`)

## Validation

```bash
omnigraph lint --schema schema.pg --query queries/signals.gq
```

The `lint` command validates both queries and schema against each other — use it after any schema or query edit.

## When Editing

- Consult [Omnigraph schema principles](https://github.com/ModernRelay/omnigraph) for design guidance
- Use `@rename_from(...)` on property/type renames for migration support
- Keep README.md in sync with schema.pg
- Prefer semantic edge names over generic ones (`Enables` not `RelatedTo`)
- Use the narrowest type that fits (enums over strings, Date over String)
- Required vs optional is deliberate — don't add `?` without reason

## Cluster control plane (two-file model)

`cluster.yaml` is the deployment: graph `spike`, `schema.pg`, and every
stored query, converged with `omnigraph cluster import|plan|apply --config .`
(apply creates `graphs/spike.omni`; schema edits show migration previews in
plan; graph deletion is approval-gated). Operator settings (aliases, CLI
defaults, actor for `--as` attribution) live in the per-user
`~/.omnigraph/config.yaml` — never committed; the cookbook ships
`omnigraph-config.example.yaml` to merge in. Aliases bind to the stored
queries declared in `cluster.yaml` and invoke them through a running server
(`omnigraph alias <name> [args]`). Serve with `omnigraph-server --cluster .`
(reads cluster state only, never the operator config). Data still flows
through `omnigraph load/mutate` against `graphs/spike.omni`. Never commit
`__cluster/` or `graphs/` (gitignored — local state).
