# CLAUDE.md — industry-intel

Scoped guidance for the `industry-intel/` SPIKE cookbook. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

An Omnigraph schema + seed modeling AI/ML industry intelligence using the SPIKE framework. Schema, seed data, and queries only — no application code.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — the landing page, from the template in the root `AGENTS.md`. Commands go here, not there.
- `site.json` — the copy omnigraph.dev shows; its questions name stored reads.
- `seed.md` / `seed.jsonl` — Seed dataset (human-readable / loadable).
- `queries/*.gq` — Read and mutation queries.
- `omnigraph-config.example.yaml` — read aliases over the stored queries; merge its `aliases:` into the operator config from the [local setup](../README.md#local-setup).

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

## Setup

Use the shared [local setup](../README.md#local-setup) with cookbook
`industry-intel` and graph `spike`. It owns authentication, the bootstrap writer-lock
handoff, readiness, and served seed loading. Apply later configuration edits with
the [live update workflow](../README.md#live-updates).

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

## Questions

Each question in `site.json`, as its alias (`omnigraph alias <name>`; see `omnigraph-config.example.yaml`) or the stored read behind it:

```bash
omnigraph alias momentum --params '{"since":"2026-03-01T00:00:00Z"}'      # pattern_momentum
omnigraph alias signals                                                   # recent_signals
omnigraph alias pattern-signals --params '{"slug":"pat-context-graphs"}'  # pattern_signals
omnigraph alias unsourced                                                 # unsourced_signals
```

On the seed: Context Graphs 3 and New Cyber Threats 2 since 1 March 2026; newest signal `sig-mythos-181-exploits`; three signals form `pat-context-graphs`; `sig-gartner-50pct-context-graphs` has no source. `contested_patterns` and `orphan_signals` return no rows on the seed, which has no contradicting signal and no unattached one.

## Workflows

Run every write on its own branch, never on `main`: `omnigraph branch create --target local-writer --graph spike <branch>` (see `omnigraph branch --help`), pass `--branch <branch>` to `mutate`, and leave the merge to a person. The sample `act-writer` role can merge into `main`, so the branch rule is a convention, not a policy. Aliases read `main`; to read a branch, use `omnigraph query <name> --branch <branch> --target local-reader --graph spike`.

**Signal intake** (capture). Starts with a new item in a source.
1. Check it is new: `search_signals` with a phrase from it.
2. `add_source`, `add_artifact`, then `link_artifact_published_by` (and `add_expert`, `link_artifact_contributed_by` for an author).
3. `add_signal`, then `link_signal_spotted_in`, `link_signal_sourced_from`, `link_signal_on_element`, `link_signal_relevant_company`. Add a missing element or company first (`add_element`, `add_company`, `link_element_developed_by`).
4. Hand the branch to an analyst.

**Triage** (maintain). Run `orphan_signals`. For each signal, run `search_patterns` or `patterns_by_kind`, then `link_signal_forms_pattern` or `link_signal_contradicts_pattern`. If no pattern fits, say so on the branch; a new pattern is `add_pattern` and an analyst's call.

**Evidence lookup** (maintain). `hybrid_chunks` and `related_chunks` need the embeddings set up below; without them `search_signals`, `search_patterns` and `search_insights` still work, as keyword reads.

**Tension review** (maintain). Run `contested_patterns`. For each pattern, read `signal_contradictions` and `pattern_signals`. Propose `add_insight` and `link_insight_highlights_pattern` (and `link_insight_relies_on_element`) on a branch. Note that `add_insight` takes only slug and name; set the text through a merge load.

**Momentum and staleness** (maintain). Run `pattern_momentum` and `stale_patterns` with the same `since`, and read `pattern_signals` for the movers. Nothing is stored. The cookbook has no stored mutation that changes or deletes a pattern.

**Provenance audit** (maintain). Run `unsourced_signals`; attach with `link_signal_spotted_in` or `link_signal_sourced_from`, or flag the signal for an analyst.

**Weekly briefing** and **research requests** (act). Compose from `recent_signals`, `pattern_momentum`, `contested_patterns` and `stale_patterns`. The record has no field for "briefing sent" or for who follows a pattern; the agent tracks what it sent and asks whoever the team names. Send nothing without a person's approval.

## What this cookbook does not do

- No connectors to sources; a sync is your script or agent.
- No stored mutation changes or deletes a node or edge, and no agent role limits writes to branches.
- No embeddings in the seed, so semantic search returns nothing until you load chunks.
- No record that a message was sent, and no owner on a pattern.

## Authorization

`cluster.yaml` binds `policies/intel.policy.yaml` to `spike` and `policies/server.policy.yaml` to the cluster. In the shared setup, `local` (`act-admin`) administers the deployment, `local-writer` (`act-writer`) runs stored mutations and `local-reader` (`act-reader`) reads. Use distinct private credentials outside the local demo. Stored mutations need both query invocation and write permission. `omnigraph access --target local-reader --graph spike` lists what the reader may do.

## Enable embeddings (hybrid retrieval)

`queries/hybrid.gq` adds search over chunk embeddings (`related_chunks`, `hybrid_chunks`: RRF of `nearest` and `bm25`).

1. Make the provider secret available in the server environment. Declare the provider in `cluster.yaml`, bind it to `spike`, and use [live apply](../README.md#live-updates). A shell export cannot change a running process.
2. Prepare raw `Chunk` JSONL and an embedding spec, then run the offline pipeline:

   ```bash
   omnigraph embed --input chunks.raw.jsonl --output chunks.embedded.jsonl \
     --spec /path/to/embeddings.json --reembed-all
   ```

3. Load `chunks.embedded.jsonl` through the running server with `--mode append` for new chunks or `--mode merge` for updates. The offline and server providers must use the same model and dimension. See the engine's [embedding guide](https://github.com/ModernRelay/omnigraph/blob/v0.15.0/docs/user/search/embeddings.md#offline-file-pipeline).

A ranked read answers a `ranking` object beside its rows. On a vector search, `exhaustive: false` means unsearched partitions remain, so an empty or short answer is not proof nothing is closer.

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
