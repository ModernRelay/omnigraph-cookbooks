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
- Embeddings only on Chunk (`Vector(3072)`, produced at ingest by the engine's configured model — default `gemini-embedding-2-preview`)

Full property tables and constraints in `schema.pg`.

## Files

- `schema.pg` — Executable Omnigraph schema (source of truth)
- `seed.md` / `seed.jsonl` — Seed dataset (human-readable / loadable)
- `queries/*.gq` — Read and mutation queries
- `omnigraph.yaml` — CLI config with aliases
- `.env.omni` — RustFS credentials (not committed)

## Quick Start

All commands run from `industry-intel/`:

The cookbook is a **cluster directory**: `cluster.yaml` declares the graph,
its schema, and all 66 stored queries; `omnigraph cluster apply` converges it
(creating the graph at `graphs/spike.omni`); the server serves the applied
state. No object store or credentials needed to get started.

```bash
cd industry-intel

# One-time: record the ledger, preview, converge (creates graphs/spike.omni,
# applies schema.pg, publishes all stored queries)
omnigraph cluster import --config .
omnigraph cluster plan   --config .
omnigraph cluster apply  --config . --as <you>

# Load the seed through the data plane (one-time)
omnigraph load --data seed.jsonl --mode overwrite graphs/spike.omni

# Serve the applied state (keep running — separate terminal or background)
omnigraph-server --cluster . --bind 127.0.0.1:8080 --unauthenticated   # local dev

# Query via CLI aliases (per-operator omnigraph.yaml sugar) …
omnigraph read --alias pattern-signals pat-sovereign-ai
# … or straight HTTP — every declared query is a served endpoint:
curl -s -X POST http://127.0.0.1:8080/graphs/spike/queries/recent_signals \
  -H 'content-type: application/json' -d '{"params":{}}'
```

Day-2 changes are declarative: edit `schema.pg` / a `.gq` file / `cluster.yaml`,
then `cluster plan` (schema edits show real migration steps) → `cluster apply`
→ restart the server. Deleting the graph requires an explicit
`omnigraph cluster approve graph.spike --as <you>` first.

<details>
<summary><strong>RustFS / S3 alternative (classic single-graph mode)</strong></summary>

To demo S3-compatible storage instead, skip the cluster flow and run the
classic path against RustFS (start it via the omnigraph repo's
`scripts/local-rustfs-bootstrap.sh`):

```bash
set -a && source .env.omni && set +a
omnigraph init --schema schema.pg s3://omnigraph-local/repos/spike-intel
omnigraph load --data seed.jsonl --mode overwrite s3://omnigraph-local/repos/spike-intel
omnigraph-server --config omnigraph.yaml --unauthenticated
```

Re-point `graphs.local_s3` in `omnigraph.yaml` (commented out by default) and
set `server.graph: local_s3`. The two boot sources are exclusive — a server
reads cluster state XOR omnigraph.yaml, never both.

</details>

See the [Omnigraph](https://github.com/ModernRelay/omnigraph) repo for full CLI reference.
