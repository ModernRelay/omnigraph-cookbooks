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

All commands run from `industry-intel/`:

The cookbook is a **cluster directory**: `cluster.yaml` declares the graph,
its schema, and all 73 stored queries; `omnigraph cluster apply` converges it
(creating the graph at `graphs/spike.omni`); the server serves the applied
state. No object store or credentials needed to get started.

First merge the `servers`, `defaults`, and `aliases` from
`omnigraph-config.example.yaml` into `~/.omnigraph/config.yaml`; the token is
stored separately by `omnigraph login` below.

```bash
cd industry-intel

# One-time: record the ledger, preview, converge (creates graphs/spike.omni,
# applies schema.pg, publishes all stored queries)
omnigraph cluster import --config .
omnigraph cluster plan   --config .
omnigraph cluster apply  --config . --as <you>   # any id — recorded in the cluster ledger as who applied; set operator.actor in ~/.omnigraph/config.yaml to make it the default

# Load the seed through the data plane (one-time)
omnigraph load --data seed.jsonl --mode overwrite graphs/spike.omni

# Serve with the cookbook policy and three local-only development tokens
export OMNIGRAPH_SERVER_BEARER_TOKENS_JSON='{"act-admin":"local-admin-token","act-writer":"local-writer-token","act-reader":"local-reader-token"}'
omnigraph-server --cluster . --bind 127.0.0.1:8080 &

# Query via CLI aliases (operator-config sugar) …
printf '%s' 'local-reader-token' | omnigraph login local
omnigraph alias pattern-signals pat-sovereign-ai
# … or straight HTTP — every declared query is a served endpoint:
curl -s -X POST http://127.0.0.1:8080/graphs/spike/queries/recent_signals \
  -H 'authorization: Bearer local-reader-token' \
  -H 'content-type: application/json' -d '{"params":{}}'
```

> Or invoke a stored query directly:
> `omnigraph query <name> --graph spike [--params …]`.

Day-2 changes are declarative: edit `schema.pg` / a `.gq` file / `cluster.yaml`,
then `cluster plan` (schema edits show real migration steps) → `cluster apply`
→ restart the server. Deleting the graph requires an explicit
`omnigraph cluster approve graph.spike --as <you>` first.

### Authorization

The cookbook declares two Cedar bundles in `cluster.yaml`: `policies/intel.policy.yaml`
(graph-bound — `readers` invoke stored read queries, `writers` can also run
the stored mutations) and `policies/server.policy.yaml` (cluster-bound — only
`admins` may enumerate graphs). Production uses the same actor ids as Railway:

```bash
OMNIGRAPH_SERVER_BEARER_TOKENS_JSON='{"act-reader":"<reader-token>","act-writer":"<writer-token>","act-admin":"<admin-token>"}' \
  omnigraph-server --cluster . --bind 127.0.0.1:8080
```

What the gates do (verified): `GET /graphs` → admin 200 / reader 403 /
anonymous 401; stored reads → reader 200; stored mutations (`add_signal`,
…) → reader 403, writer 200 — stored mutations are double-gated
(`invoke_query` at the boundary, `change` inside the engine).

`act-analyst` remains accepted as a backwards-compatible writer identity, but
new deployments should use `act-writer`.

<details>
<summary><strong>RustFS / S3 alternative (cluster on object storage)</strong></summary>

To demo S3-compatible storage, start a local RustFS (see the omnigraph repo's
`docs/user/deployment.md` → *Testing against S3 locally*), root the cluster on
S3 with `storage: s3://omnigraph-local/clusters/spike` in `cluster.yaml`, then
serve config-free from the bucket:

```bash
set -a && source .env.omni && set +a
omnigraph cluster import --config .                 # fresh S3 root only
omnigraph cluster apply --config . --as <you>
omnigraph load --data seed.jsonl --mode overwrite s3://omnigraph-local/clusters/spike/graphs/spike.omni
OMNIGRAPH_SERVER_BEARER_TOKENS_JSON='{"act-reader":"<reader-token>","act-writer":"<writer-token>","act-admin":"<admin-token>"}' \
  omnigraph-server --cluster s3://omnigraph-local/clusters/spike
```

The cluster's ledger, catalog, and graph data all live under the S3 root.

</details>

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

1. Declare a named embedding provider in `cluster.yaml`, bind it to `spike`,
   apply the cluster, and run the server with that provider's secret.
2. Prepare raw `Chunk` JSONL and a matching embedding spec, then run the
   offline file pipeline:

   ```bash
   omnigraph embed --input chunks.raw.jsonl --output chunks.embedded.jsonl \
     --spec /path/to/embeddings.json --reembed-all
   ```

3. Load `chunks.embedded.jsonl` into the graph. `omnigraph embed` never opens
   or mutates a graph; `--reembed-all` replaces selected vectors only in its
   output file. The offline and server providers must use the same model and
   vector dimension. See the engine's
   [embedding guide](https://github.com/ModernRelay/omnigraph/blob/v0.10.0/docs/user/search/embeddings.md#offline-file-pipeline)
   for the spec format.

See the [Omnigraph](https://github.com/ModernRelay/omnigraph) repo for full CLI reference.
