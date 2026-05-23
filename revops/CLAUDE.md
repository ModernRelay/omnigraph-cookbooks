# CLAUDE.md — revops

Scoped guidance for the `revops/` cookbook. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

A code-first GTM intelligence backplane on Omnigraph. One graph holds the prospect universe, signal-based account prioritization, champion job-change context, the enrichment trail, every decision, every measurement, and all provenance. Schema, queries, and seed data only — no application code.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth. 17 nodes, typed edges.
- `omnigraph.yaml` — CLI config + named aliases (the user-facing API).
- `queries/*.gq` — Read and mutation queries grouped by primary lens.
- `seed.md` / `seed.jsonl` — Illustrative scenario (fictional seller, real-ish accounts).
- `README.md` — Overview, killer queries, extension points.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

## Schema Language (`.pg`)

- `node` defines entity types; `edge` defines typed relationships (`edge Name: Source -> Target`)
- `@key` marks external identity (always `slug` here)
- `@index`, `@unique`, `@card(min..max)`, `@embed("prop")`, `@rename_from(...)`
- `?` = optional, `[Type]` = list of scalars, `enum(...)` = inline closed set
- Comments use `//` not `#`

## Domain Model

**Pointer (mutable):** Account, Person, Role, Lead, Opportunity, Cohort, Policy, Actor, Technology, Source
**Claim (append-only):** Signal, Decision, Action, Measurement, Engagement, InformationArtifact, Chunk

**Core loop:** Signals attach to Accounts and People → scoring/classification Decisions are informed-by Signals, screened-by Policies, made-by Actors, target Accounts/Opps → Decisions produce Measurements (`intent_score`, predicted spend, actual spend) and Actions → prioritized accounts and champion job-change queues feed downstream CRM/outreach tools → outcomes refine Policies (ICP and prompt versioning).

**Design choices to preserve:**

- Mutable pointer vs append-only claim split — never overwrite a Signal, Decision, Action, Measurement, or Engagement. Decision corrections use `SupersedesDecision`; policy versions use `Supersedes`.
- `Role` is its own node, time-bounded. Champion tracking and job-change signals depend on this.
- `Lead` is distinct from `Person`. Resolution via `ResolvesToPerson`.
- `Policy` carries `policyKey` (stable across versions) + `Supersedes` chain.
- `Actor.actorType: enum(human, agent)` — every Decision and Action knows what produced it.
- `Measurement` is the time-series primitive. Numeric observations live here, not as Account properties (except trivial latest-pointer values).
- Edges follow `VerbTargetType` naming (`OnAccount`, `MadeBy`, `InformedBy`, `MeasuresAccount`, ...).
- Edge properties carry audit semantics — `InformedBy.influence`, `ScreenedBy.outcome`, `MatchesPolicy.score`.
- Embeddings only on `Chunk`: `Vector(3072) @embed("text")`.

**Extension points** (enums explicitly meant to grow per-domain): `Account.industry`, `Account.segment`, `Measurement.metricKey`, `Signal.kind`, `Policy.kind`, `Opportunity.stage`. `Decision.intent` is `String` for free-form labeling.

## Validation

```bash
omnigraph query lint --schema ./schema.pg --query ./queries/accounts.gq
```

Lint after every schema or query edit. No server, no env required.

## When Editing

- Use `@rename_from(...)` for property/type renames.
- Keep `README.md` in sync with `schema.pg`.
- Prefer narrowest type (enum > string, Date > String).
- Mutations on pointer nodes — `change` with named mutations. Bulk ingest — `load --mode merge`.
- Discipline rule, unenforceable in schema: when updating a pointer property that has analytical meaning (e.g., `Account.tier`), always insert a matching `Decision` so the audit trail stays intact.
- Aliases are the user-facing API. Every `.gq` query must be exposed in `omnigraph.yaml`; `ingest/check_alias_coverage.py` enforces this. Agents should never invoke raw `--query`/`--name` against this cookbook.

## When Adding a Mutation

- Parameterize everything — never string-interpolate into the query body.
- Mutations on append-only nodes are `insert` only — never `update` or `delete`.
- Wire it into `omnigraph.yaml` as a named alias.
- Lint with `omnigraph query lint --schema ./schema.pg --query ./queries/mutations.gq`.
