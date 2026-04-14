# Industry Intel — SPIKE Starter

Knowledge graph starter modeling AI/ML industry intelligence. Built on [Omnigraph](https://github.com/ModernRelay/omnigraph) using the [SPIKE framework](../README.md#spike-framework).

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

**Totals:** 111 nodes, 148 edges.

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
| `ExemplifiesPattern` / `EnablesPattern` | Element → Pattern | concrete examples or enablers of a theme |
| `OnElement` | Signal → Element | which thing the signal is about |
| `EnablesElement` / `UsesElement` | Element → Element | capability and dependency relationships |
| `ReferencesElement` | KnowHow → Element | practice grounded in a specific tool/concept |

**Key design choices:**

- Flat node types with `kind` enums (no subtypes or interfaces)
- Domain is a property, not a node
- Edges follow `VerbTargetType` naming so direction is obvious
- `slug` is the external identity everywhere (`sig-`, `pat-`, `el-`, `ins-`, `how-to-`, `co-`, `exp-`, `ia-`, `source-`)
- Embeddings only on Chunk (`Vector(3072)`, text-embedding-3-large)

Full property tables and constraints in `schema.pg`.

## Files

- `schema.pg` — Executable Omnigraph schema (source of truth)
- `seed.md` / `seed.jsonl` — Seed dataset (human-readable / loadable)
- `queries/*.gq` — Read and mutation queries
- `omnigraph.yaml` — CLI config with aliases
- `.env.omni` — RustFS credentials (not committed)

## Quick Start

All commands run from `industry-intel/`:

```bash
cd industry-intel

# Source RustFS credentials
set -a && source ./.env.omni && set +a

# Lint the schema and queries
omnigraph query lint --schema ./schema.pg --query ./queries/signals.gq

# Init the repo
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/spike-intel

# Load the seed
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/spike-intel

# Query signals forming a pattern
# `omnigraph.yaml` defaults the CLI to the local S3 graph, so aliases work
# immediately after init/load.
omnigraph read --alias pattern-signals pat-sovereign-ai

# Optional: start the starter's local HTTP server in another terminal
omnigraph-server --config ./omnigraph.yaml

# Then point the alias at the HTTP graph explicitly
omnigraph read --target local_server --alias pattern-signals pat-sovereign-ai
```

See the [Omnigraph](https://github.com/ModernRelay/omnigraph) repo for full CLI reference.
