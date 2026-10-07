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

## Setup

Use the shared [0.13 local setup](../README.md#local-setup) with cookbook
`industry-intel` and graph `spike`. It owns authentication, the bootstrap writer-lock
handoff, readiness, and served seed loading. Apply later configuration edits with
the [live update workflow](../README.md#live-updates).

Graph id `spike`. Stored queries and their parameters: `omnigraph queries list --cluster . --graph spike`.
Alias args bind by name to `$params`: `omnigraph alias pattern-signals pat-sovereign-ai` is `omnigraph query pattern_signals --graph spike --params '{"slug":"pat-sovereign-ai"}'`.

## Writing

Aliases are read-only; mutations run as `omnigraph mutate <name> --params '<json>'` with every
non-optional property supplied. Signatures live in `queries/mutations.gq`. Working example:

```bash
# Use the admin or writer identity from the shared setup.
omnigraph mutate add_signal --graph spike --params '{"slug":"sig-eu-sovereign-cloud","name":"EU mandates sovereign cloud for public-sector AI","brief":"Public-sector AI workloads must run on EU-controlled infrastructure.","stagingTimestamp":"2026-09-14T00:00:00Z","createdAt":"2026-09-14T00:00:00Z","updatedAt":"2026-09-14T00:00:00Z"}'
omnigraph mutate link_signal_forms_pattern --graph spike --params '{"signal":"sig-eu-sovereign-cloud","pattern":"pat-sovereign-ai"}'
```

With `defaults.server` / `default_graph` from the operator config, `--graph` can be omitted.

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
- Embeddings only on Chunk: `Vector(3072) @embed("text")`. OmniGraph does not populate `@embed` fields during load; prepare vectors with the offline JSONL-to-JSONL `omnigraph embed` pipeline, then load that output. The query-time provider must use the same model and dimension.
- Chunk is immutable (no `updatedAt`)

## When Editing

- Consult [Omnigraph schema principles](https://github.com/ModernRelay/omnigraph) for design guidance
- Use `@rename_from(...)` on property/type renames for migration support
- Keep README.md in sync with schema.pg
- Prefer semantic edge names over generic ones (`Enables` not `RelatedTo`)
- Use the narrowest type that fits (enums over strings, Date over String)
- Required vs optional is deliberate — don't add `?` without reason
