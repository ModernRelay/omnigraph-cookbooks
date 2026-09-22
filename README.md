# Omnigraph Cookbooks

Opinionated, ready-to-run graph cookbooks built on [Omnigraph](https://github.com/ModernRelay/omnigraph). Each cookbook is a self-contained schema, seed, and query set for a specific use case.

## Cookbooks

| Cookbook | Status | Description |
|----------|--------|-------------|
| [`industry-intel/`](industry-intel) | ✅ ready | AI/ML industry intelligence graph |
| [`pharma-intel/`](pharma-intel) | ✅ ready | Pharma competitive intelligence |
| [`second-brain/`](second-brain) | ✅ ready | Personal life automation graph |
| [`vc-os/`](vc-os) | ✅ ready | Venture-capital operating system |
| [`dev-graph/`](dev-graph) | ✅ ready | Software-development work: planning, code, release, ops + governance |
| `company-context/` | 🚧 planned | Internal decisions, traces, actors, artifacts |
| `biomed-research/` | 🚧 planned | Biotech & medical research tracking |
| `competitor-intel/` | 🚧 planned | Competitor launches, pricing, positioning |

## Agent Skills

The bootstrap skill ships with the `industry-intel` cookbook it builds from, and installs with the `npx skills` CLI:

| Skill | Description |
|-------|-------------|
| [`industry-intel/skill`](industry-intel/skill) | Bootstrap a new SPIKE graph from scratch — choose demo or custom, elicit domain + sources, adapt schema, research seed content, apply + load |

Install (direct-path form):

```bash
npx skills add https://github.com/ModernRelay/omnigraph-cookbooks/tree/main/industry-intel/skill
```

> **Day-to-day operations** are covered by the **`omnigraph` skill** from the engine repo ([ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph/tree/main/skills/omnigraph)). It is **vendored here** at `.claude/skills/omnigraph/` (Claude Code) and `.agents/skills/omnigraph` (Codex), pinned to the engine release in `deploy/railway/Dockerfile`, so both clients pick it up in a checkout with no install step; `scripts/sync-skill.sh` refreshes it after a pin bump. Other clients: `npx skills add ModernRelay/omnigraph@omnigraph`. The operating guide and schema-design docs live in that repo and on the docs site.

Typical flow: use the bootstrap skill once to set up a new graph, then the `omnigraph` skill for day-to-day operations.

## Repo Structure

```
omnigraph-cookbooks/
├── README.md  CLAUDE.md  LICENSE
├── railway.toml  deploy/railway/   ← container deploy (Dockerfile, config)
└── <cookbook>/                     ← industry-intel, pharma-intel, second-brain, vc-os, dev-graph
    ├── README.md
    ├── CLAUDE.md
    ├── schema.pg
    ├── cluster.yaml
    ├── seed.md
    ├── seed.jsonl
    ├── omnigraph-config.example.yaml
    └── queries/*.gq
```

The `industry-intel` cookbook additionally ships the bootstrap skill at
[`industry-intel/skill/`](industry-intel/skill). Each cookbook is fully
self-contained — `cd` in and follow its README.

## Getting Started

1. Pick a cookbook.
2. Install the OmniGraph v0.11.0 CLI and server — see the [OmniGraph repo](https://github.com/ModernRelay/omnigraph). No server or object store is needed for the initial cluster apply and seed load.
3. Follow the cookbook's Quick Start. Every cookbook is a **cluster
   directory** (aligned to OmniGraph 0.11.0): `omnigraph cluster apply`
   creates the graph and publishes the stored queries;
   `omnigraph-server --cluster .` serves them — no object store needed to
   get started.

OmniGraph 0.11 writes graph format v9 and cannot open a v0.10 (format v6)
graph. A cookbook checkout carries no data of its own — `cluster apply` plus
the seed load rebuild it — so upgrading one is: install 0.11, delete the
cookbook's `graphs/` and `__cluster/`, run its Quick Start again. A graph that
holds real data is different: cluster-managed roots cannot be upgraded in
place, so export it with the 0.10 CLI, apply the cluster fresh with 0.11 and
load the export, following the engine's
[v0.11 upgrade guide](https://github.com/ModernRelay/omnigraph/blob/v0.11.0/docs/user/operations/upgrade.md).
Stop traffic and keep a verified whole-root backup first; never run mixed
old/new processes against one graph.

## SPIKE Framework

The `industry-intel/` cookbook uses SPIKE, an opinionated graph modeling lens:

- `Signal`: a dated external fact, movement, or observation
- `Pattern`: a recurring theme formed, contradicted, or driven by signals
- `Insight`: a synthesized interpretation explaining why a pattern matters
- `KnowHow`: an actionable practice or playbook grounded in the graph
- `Element`: a concrete product, framework, company, or concept the signals are about

SPIKE is a cookbook-level convention, not a requirement for every graph in this repo.

## Contributing

Create a new folder, add a schema, seed, queries, and docs. Ship real seed data, not placeholders.
