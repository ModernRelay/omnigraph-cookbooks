# CLAUDE.md — industry-intel

Scoped guidance for the `industry-intel/` SPIKE cookbook. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

An Omnigraph schema + seed modeling AI/ML industry intelligence using the SPIKE framework. Schema, seed data, and queries only — no application code.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — Reference seed description, schema essentials, quick start.
- `seed.md` / `seed.jsonl` — Seed dataset (human-readable / loadable).
- `queries/*.gq` — Read and mutation queries.
- `omnigraph.yaml` — CLI config with aliases.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

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
- Embeddings only on Chunk: `Vector(3072) @embed("text")` — produced at ingest by the engine's configured embedding model (default `gemini-embedding-2-preview`, 3072-dim)
- Chunk is immutable (no `updatedAt`)

## Validation

```bash
omnigraph lint --schema ./schema.pg --query ./queries/signals.gq
```

The `lint` command validates both queries and schema against each other — use it after any schema or query edit. (`query lint` still works as a deprecated alias.)

## When Editing

- Consult [Omnigraph schema principles](https://github.com/ModernRelay/omnigraph) for design guidance
- Use `@rename_from(...)` on property/type renames for migration support
- Keep README.md in sync with schema.pg
- Prefer semantic edge names over generic ones (`Enables` not `RelatedTo`)
- Use the narrowest type that fits (enums over strings, Date over String)
- Required vs optional is deliberate — don't add `?` without reason
