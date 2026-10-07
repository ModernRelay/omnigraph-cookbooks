# Industry Intel — SPIKE Cookbook

Knowledge graph cookbook modeling AI/ML industry intelligence. Built on [Omnigraph](https://github.com/ModernRelay/omnigraph) using the [SPIKE framework](../README.md#spike-framework).

## Core Analytical Loop

Signals and Patterns form the analytical core. Insights interpret them. Elements and KnowHows map the domain around them.

```
  Signal ── FormsPattern ──────────▶ Pattern
    │                                  │
    ├── ContradictsPattern ──────────▶ │
    │                                  │
    │                                  ├── DrivesPattern ──────▶ Pattern
    │                                  └── ReliesOnPattern ────▶ Pattern
    │
    ├── OnElement ──▶ Element
    │                   │
    │                   ├── ExemplifiesPattern ──▶ Pattern
    │                   ├── EnablesPattern ──────▶ Pattern
    │                   │
    │                   ├── EnablesElement ──▶ Element
    │                   └── UsesElement ────▶ Element
    │
  Insight ── HighlightsPattern ──────▶ Pattern
    │
    └── ReliesOnElement ─────────────▶ Element

  KnowHow ── ReferencesElement ───────▶ Element
```

## Reference Seed: AI Industry, Early 2026

Five live patterns in the AI industry:

| Pattern | Kind | What it captures |
|---------|------|------------------|
| **Sovereign AI** | disruption | Enterprises moving AI off public cloud — driven by regulation (DORA, EU AI Act) and collapsing on-prem setup cost |
| **SaaSpocalypse** | disruption | Per-seat SaaS pricing breaking as agents replace workflows — $830B wiped from S&P software index in six days |
| **Context Graphs** | dynamic | Decision traces + ontology + temporal reasoning as a new infrastructure layer above databases |
| **New Cyber Threats** | challenge | AI models autonomously exploiting vulnerabilities + agentic attack surfaces inside enterprises |
| **Accelerated Research** | dynamic | AI agents running 100s of experiments autonomously — from Karpathy loops to AlphaEvolve to AI-proven math |

Each pattern is backed by ~3 real, dated signals with source URLs. Signals connect to the Elements (products, frameworks, concepts) they're about, which in turn connect to Companies that built them.

**Totals:** 109 nodes, 154 edges.

## Schema Essentials

**Nodes (10):** Signal, Pattern, Insight, KnowHow, Element + Company, SourceEntity, Expert, InformationArtifact, Chunk

**Enums that carry the analytical lens:**

| Enum | Values |
|------|--------|
| **PatternKind** | `challenge, disruption, dynamic` |
| **ElementKind** | `product, technology, framework, concept, ops` |
| **Domain** | `training, inference, infra, harness, robotics, security, data-eng, context` |

**Edges that carry the analytical logic** (everything else is provenance or classification):

| Edge | Route | Meaning |
|------|-------|---------|
| `FormsPattern` | Signal → Pattern | this movement supports that theme |
| `ContradictsPattern` | Signal → Pattern | this movement pushes back against that theme |
| `DrivesPattern` / `ReliesOnPattern` / `ContradictsToPattern` | Pattern → Pattern | causality and structure between themes |
| `HighlightsPattern` | Insight → Pattern | this observation illuminates a theme |
| `ReliesOnElement` | Insight → Element | this insight is grounded in a concrete thing |
| `ExemplifiesPattern` / `EnablesPattern` | Element → Pattern | concrete examples or enablers of a theme |
| `OnElement` | Signal → Element | which thing the signal is about |
| `EnablesElement` / `UsesElement` | Element → Element | capability and dependency relationships |
| `ReferencesElement` | KnowHow → Element | practice grounded in a specific tool/concept |

**Key design choices:**

- Flat node types with `kind` enums (no subtypes or interfaces)
- Domain is a property, not a node
- Edges follow `VerbTargetType` naming so direction is obvious
- `slug` is the external identity everywhere (`sig-`, `pat-`, `el-`, `ins-`, `how-to-`, `co-`, `exp-`, `ia-`, `source-`)
- Embeddings only on Chunk (`Vector(3072)`, supplied by the offline embedding pipeline using the same model as query-time search)

Full property tables and constraints in `schema.pg`.

## Files

- `schema.pg` — Executable Omnigraph schema (source of truth)
- `seed.md` / `seed.jsonl` — Seed dataset (human-readable / loadable)
- `queries/*.gq` — Read and mutation queries
- `omnigraph-config.example.yaml` — example operator config (aliases over the stored queries); merge into your per-user `~/.omnigraph/config.yaml`
- `.env.omni` — optional RustFS/S3 credentials (not committed)

## Quick Start

Follow the shared [0.13 local setup](../README.md#local-setup) with
`industry-intel` and graph ID `spike`. It creates the filesystem-backed cluster,
starts the authenticated server, and loads the seed through HTTP. Merge this
cookbook's `omnigraph-config.example.yaml` into your operator config for aliases.

```bash
omnigraph alias pattern-signals pat-sovereign-ai
omnigraph query recent_signals --server local --graph spike
```

Schema, query, policy and provider edits use the [live update workflow](../README.md#live-updates).

### Authorization

`cluster.yaml` binds `policies/intel.policy.yaml` to `spike` and
`policies/server.policy.yaml` to the cluster. The shared setup's `act-admin`
identity administers the deployment; `act-writer` can run stored mutations and
`act-reader` can read. Use distinct private credentials for these actors outside
the local demo. Stored mutations require both query invocation and write
permission.

For S3 hosting, use the [Railway deployment guide](../deploy/railway/README.md).

## The weekly review (operating loop)

The graph earns its keep through a recurring loop, supported by the
`queries/workflow.gq` set (aliases in parentheses):

1. **Triage** (`triage`) — `orphan_signals`: every signal not yet attached to
   a pattern, newest first. Work it to zero: attach with the `link_*`
   mutations, or drop the signal.
2. **Momentum** (`momentum`, takes `since`) — `pattern_momentum`: signals per
   pattern since the cutoff. Rising counts are where insights come from.
3. **Staleness** (`stale`, takes `since`) — `stale_patterns`: patterns with
   no new evidence since the cutoff. Prune, or push research at them.
4. **Tension** (`contested`) — `contested_patterns`: patterns accumulating
   contradicting signals. High counts deserve an Insight either way.
5. **Provenance** (`unsourced`) — `unsourced_signals`: claims with no
   artifact or source attached — an agent cannot verify them. Fix or drop.

```bash
omnigraph alias triage
omnigraph alias momentum 2026-05-01T00:00:00Z
```

## Enable embeddings (hybrid retrieval)

`queries/hybrid.gq` adds semantic and hybrid search over chunk embeddings
(`related_chunks`, `hybrid_chunks` — RRF of `nearest` + `bm25`). To enable it:

1. Make the provider secret available in the server environment. Declare the
   provider in `cluster.yaml`, bind it to `spike`, and use
   [live apply](../README.md#live-updates). A shell export cannot change an
   already running process; provision new secrets before starting that process.
2. Prepare raw `Chunk` JSONL and a matching embedding spec, then run the
   offline file pipeline:

   ```bash
   omnigraph embed --input chunks.raw.jsonl --output chunks.embedded.jsonl \
     --spec /path/to/embeddings.json --reembed-all
   ```

3. Load `chunks.embedded.jsonl` through the running server with `--mode append`
   for new chunks or `--mode merge` for updates. `omnigraph embed` never opens
   or mutates a graph; `--reembed-all` replaces selected vectors only in its
   output file. The offline and server providers must use the same model and
   vector dimension. See the engine's
   [embedding guide](https://github.com/ModernRelay/omnigraph/blob/v0.13.0/docs/user/search/embeddings.md#offline-file-pipeline)
   for the spec format.

See the [Omnigraph](https://github.com/ModernRelay/omnigraph) repo for full CLI reference.
