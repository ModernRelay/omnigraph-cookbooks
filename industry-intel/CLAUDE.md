# CLAUDE.md — industry-intel

Scoped guidance for the `industry-intel/` SPIKE cookbook. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

An Omnigraph schema + seed modeling AI/ML industry intelligence using the SPIKE framework. Schema, seed data, and queries only — no application code.

SPIKE is Signal (observed fact), Pattern (recurring theme), Insight
(interpretation), KnowHow (practice) and Element (concrete subject). It is a
modelling convention of this cookbook and pharma-intel, not something the
engine requires.

[`skill/`](skill/) is a skill that guides choosing a domain, researching it
and preparing a seed. Install it with
`npx skills add https://github.com/ModernRelay/omnigraph-cookbooks/tree/main/industry-intel/skill`.

## Key Files

`schema.pg` is the source of truth. `README.md` is the landing page and follows
the template in `../AGENTS.md`; this file holds everything it has no place for.
`omnigraph-config.example.yaml` has read aliases over the stored queries; merge
its `aliases:` into the operator config from the
[local setup](../docs/local-setup.md). `seed.md` describes the seed and
`seed.jsonl` loads it.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

## Setup

Use the shared [local setup](../docs/local-setup.md) with cookbook
`industry-intel` and graph `spike`. It owns authentication, the bootstrap writer-lock
handoff, readiness, and served seed loading. Apply later configuration edits with
the [live update workflow](../docs/local-setup.md#live-updates).

Graph id `spike`. Stored queries and their parameters: `omnigraph queries list --target local --graph spike`.
Aliases pass parameters by name: `omnigraph alias pattern-signals --params '{"slug":"pat-sovereign-ai"}'` is `omnigraph query pattern_signals --target local-reader --graph spike --params '{"slug":"pat-sovereign-ai"}'`.

## Writing

Aliases are read-only; mutations run as `omnigraph mutate <name> --target local-writer --graph spike --params '<json>'`
with every non-optional property supplied. Signatures live in `queries/mutations.gq`. Working example:

```bash
# local-writer is the writer target from the shared setup.
omnigraph mutate add_signal --target local-writer --graph spike --params '{"slug":"sig-eu-sovereign-cloud","name":"EU mandates sovereign cloud for public-sector AI","brief":"Public-sector AI workloads must run on EU-controlled infrastructure.","stagingTimestamp":"2026-09-14T00:00:00Z","createdAt":"2026-09-14T00:00:00Z","updatedAt":"2026-09-14T00:00:00Z"}'
omnigraph mutate link_signal_forms_pattern --target local-writer --graph spike --params '{"signal":"sig-eu-sovereign-cloud","pattern":"pat-sovereign-ai"}'
```

`--graph` can be omitted only for a target with `default_graph`; the shared setup's targets have none.

## Questions: the command for each

Run these against the loaded seed; the README's Sample data section gives what
they return. An alias can replace `--target local-reader --graph spike`.

```bash
omnigraph query contested_patterns --target local-reader --graph spike
omnigraph query pattern_momentum --target local-reader --graph spike --params '{"since":"2026-05-01T00:00:00Z"}'
omnigraph query recent_signals --target local-reader --graph spike
omnigraph query pattern_signals --target local-reader --graph spike --params '{"slug":"pat-saaspocalypse"}'
```

## Review and roles

The roles are `act-admin`, `act-writer` and `act-reader`. `act-writer` can
change `main` and merge into it, and there is no agent role kept to branches,
so review of an agent's work is a practice here and the policy does not
enforce it. Give an agent the writer token only for work on its own branch, and
have an analyst merge. Do not add or change a role without task authorization.

```bash
omnigraph branch create intake-2026-w47 --target local-writer --graph spike
omnigraph mutate add_signal --target local-writer --graph spike --branch intake-2026-w47 --params '{...}'
omnigraph query orphan_signals --target local-writer --graph spike --branch intake-2026-w47
omnigraph branch merge intake-2026-w47 --into main --dry-run --target local-writer --graph spike
omnigraph branch merge intake-2026-w47 --into main --target local-writer --graph spike
```

`omnigraph branch diff intake-2026-w47 --target local-writer --graph spike`
shows what the branch changed. Rows written on a branch are not covered by the
graph's indexes, so a read over them scans.

## Workflows, step by step

Each workflow reads through stored queries, writes only on a branch, and ends
with a person reviewing the branch or acting on a report. `since` is an RFC
3339 timestamp. Mutation parameters are in `queries/mutations.gq`; every
non-optional property must be supplied.

**Signal intake (capture).** Starts with a new article, filing or post.
1. Search first, so the signal is not filed twice:
   `omnigraph query search_signals --target local-reader --graph spike --params '{"q":"..."}'`.
2. On a branch run `add_artifact` (give `artifactType`), `add_source` for a
   publisher not yet in the record, then `add_signal`. `add_artifact` takes no
   URL, so the stored writes leave the artifact without its address; a merge
   load of the artifact on the branch can carry it.
3. Attach with `link_signal_spotted_in` and `link_signal_sourced_from`.
4. An analyst merges. `add_signal` takes only slug, name, brief and three
   timestamps; no stored write sets `description` or `domain`.

**Evidence filing (capture).** Starts with a signal in the triage list.
Read the candidates with `patterns_by_kind` or `search_patterns`, decide
whether the signal supports or contradicts, and run
`link_signal_forms_pattern` or `link_signal_contradicts_pattern`, plus
`link_signal_on_element` for each product it concerns. The agent proposes the
direction; the analyst confirms it in review, because it is a judgment.

**Landscape mapping (capture).** `search_elements` first, then `add_element`,
`add_company`, `link_element_developed_by` and `link_signal_relevant_company`.
`add_element` and `add_pattern` take only slug, name, kind and timestamps.

**Triage (maintain).** `omnigraph alias triage`. Work the list to zero by
filing evidence. No stored write removes a signal.

**Provenance audit (maintain).** `omnigraph alias unsourced`, then find the
original source and run `link_signal_spotted_in`.

**Staleness review (maintain).** `omnigraph alias stale --params
'{"since":"..."}'`. A pattern that drew a contradiction is not stale. Read
`pattern_signals` for each pattern, then decide to research it or retire it.
No stored write retires a pattern.

**Insight drafting (maintain).** Read `pattern_momentum` and
`contested_patterns`; where either is high, run `add_insight`,
`link_insight_highlights_pattern` and `link_insight_relies_on_element` on a
branch. A person reads and merges it.

**Pattern linking (maintain).** Read `pattern_drives` and `pattern_relies_on`,
then propose `link_pattern_drives`, `link_pattern_relies_on` or
`link_pattern_contradicts` where signals and products shared by two patterns
suggest it. Always on a branch.

**Weekly brief, contradiction alert (act).** Read `recent_signals`,
`pattern_momentum` and `contested_patterns`; for an alert, `signal_contradictions`
and `signal_sources`. Draft the message and have a person approve it. The agent
sends it with its own tools; the cookbook has no integration, and the record
cannot note that a message was sent. To avoid a repeat, the agent keeps its own
list of what it has announced.

**Source search (act).** `hybrid_chunks` or `related_chunks`; needs the
embeddings below.

### The review loop

The weekly review runs the five reads in `queries/workflow.gq`. Aliases are in
parentheses.

1. **Triage** (`triage`): `orphan_signals`, every signal attached to no pattern.
2. **Momentum** (`momentum`, takes `since`): `pattern_momentum`, evidence per
   pattern since the cutoff, supporting and contradicting together.
3. **Staleness** (`stale`, takes `since`): `stale_patterns`.
4. **Tension** (`contested`): `contested_patterns`.
5. **Provenance** (`unsourced`): `unsourced_signals`, claims with no artifact
   or publisher.

```bash
omnigraph alias triage
omnigraph alias momentum --params '{"since":"2026-05-01T00:00:00Z"}'
```

## Authorization

`cluster.yaml` binds `policies/intel.policy.yaml` to `spike` and
`policies/server.policy.yaml` to the cluster. In the shared setup the `local`
target (`act-admin`) administers the deployment, `local-writer` (`act-writer`)
runs stored mutations and `local-reader` (`act-reader`) reads. Use distinct
private credentials outside the local demo. A stored mutation needs both query
invocation and write permission. `omnigraph access --target local-reader
--graph spike` lists what the reader may do. Schema, query, policy and provider
edits use the [live update workflow](../docs/local-setup.md#live-updates).

## Enable embeddings (hybrid retrieval)

`queries/hybrid.gq` adds semantic and hybrid search over chunk embeddings
(`related_chunks`, and `hybrid_chunks`, which fuses `nearest` and `bm25` by
RRF). The seed has no `Chunk` rows, so both return nothing until you add some,
and they fail without a provider. To enable them:

1. Make the provider secret available in the server environment. Declare the
   provider in `cluster.yaml`, bind it to `spike`, and use
   [live apply](../docs/local-setup.md#live-updates). A shell export cannot change an
   already running process; provision new secrets before starting it.
2. Prepare raw `Chunk` JSONL and a matching embedding spec, then run the
   offline file pipeline:

   ```bash
   omnigraph embed --input chunks.raw.jsonl --output chunks.embedded.jsonl \
     --spec /path/to/embeddings.json --reembed-all
   ```

3. Load `chunks.embedded.jsonl` through the running server with `--mode append`
   for new chunks or `--mode merge` for updates. `omnigraph embed` never opens
   or mutates a graph. The offline and server providers must use the same model
   and vector dimension. See the engine's
   [embedding guide](https://github.com/ModernRelay/omnigraph/blob/v0.15.0/docs/user/search/embeddings.md#offline-file-pipeline)
   for the spec format.

A ranked read answers a `ranking` object beside its rows, naming the search
(`bm25`, `nearest` or `rrf`), whether a higher or lower score is better, and
whether it was `exhaustive`. On a vector search, `exhaustive: false` means the
`ann_nprobes` cap left partitions unsearched, so an empty or short answer is not
evidence that the graph holds nothing closer. Project a score by repeating the
leading order key, for example `nearest($c.embedding, $q) as distance`.

## What the cookbook does not do

No connectors, no scheduler and no enforced review. There is no stored write
to update or remove a signal, pattern or insight, to set a signal's `domain` or
`description`, or to add a `Chunk`. The record has no place to note that an
outside action (a brief, an alert) was taken.

## Domain Model

**SPIKE Nodes:** Signal, Element, Pattern, Insight, KnowHow
**Supportive:** Company, SourceEntity, Expert, InformationArtifact, Chunk

**Edges that carry the analytical logic** (the rest is provenance or classification):

| Edge | Route | Meaning |
|---|---|---|
| `FormsPattern` / `ContradictsPattern` | Signal → Pattern | the signal supports / pushes back against the pattern |
| `DrivesPattern` / `ReliesOnPattern` / `ContradictsToPattern` | Pattern → Pattern | causality and structure between patterns |
| `HighlightsPattern` | Insight → Pattern | the insight illuminates the pattern |
| `ReliesOnElement` | Insight → Element | the insight is grounded in a concrete thing |
| `ExemplifiesPattern` / `EnablesPattern` | Element → Pattern | examples or enablers of the pattern |
| `OnElement` | Signal → Element | what the signal is about |
| `EnablesElement` / `UsesElement` | Element → Element | capability and dependency |
| `ReferencesElement` | KnowHow → Element | practice grounded in a tool or concept |

Domain enum: `training, inference, infra, harness, robotics, security,
data-eng, context`. `slug` is the identity, with prefixes `sig-`, `pat-`, `el-`,
`ins-`, `how-to-`, `co-`, `exp-`, `ia-`, `source-`.

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
- Keep README.md and this file in sync with schema.pg and the stored queries
- Prefer semantic edge names over generic ones (`Enables` not `RelatedTo`)
- Use the narrowest type that fits (enums over strings, Date over String)
- Required vs optional is deliberate — don't add `?` without reason
