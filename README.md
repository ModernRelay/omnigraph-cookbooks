# Omnigraph Cookbooks

Opinionated, ready-to-run graph cookbooks built on [Omnigraph](https://github.com/ModernRelay/omnigraph). Each cookbook is a self-contained schema, seed, and query set for a specific use case.

## Cookbooks

| Cookbook | Status | Description |
|----------|--------|-------------|
| [`industry-intel/`](./industry-intel) | ✅ ready | AI/ML industry intelligence graph |
| [`pharma-intel/`](./pharma-intel) | ✅ ready | Pharma competitive intelligence with external pipeline + SPIKE + internal context (Viking Therapeutics GLP-1 reference seed) |
| [`second-brain/`](./second-brain) | ✅ ready | Personal life ontology — people, places, notes, tasks, projects, habits, media (13 node types, fictional "Alex Chen" reference seed) |
| `company-context/` | 🚧 planned | Internal decisions, traces, actors, artifacts |
| `biomed-research/` | 🚧 planned | Biotech & medical research tracking |
| `competitor-intel/` | 🚧 planned | Competitor launches, pricing, positioning |

## Agent Skills

Packaged agent skills live under [`skills/`](./skills) and can be installed with the `npx skills` CLI:

| Skill | Description |
|-------|-------------|
| [`omnigraph-intel-bootstrap`](./skills/omnigraph-intel-bootstrap) | Bootstrap a new SPIKE graph from scratch — choose demo or custom, elicit domain + sources, adapt schema, research seed content, init + load |
| [`omnigraph-best-practices`](./skills/omnigraph-best-practices) | Operate a locally deployed Omnigraph — schema authoring and evolution, query linting, data changes, branches, embeddings, aliases, server, policy, and common gotchas |

Install:

```bash
npx skills add ModernRelay/omnigraph-cookbooks@omnigraph-intel-bootstrap
npx skills add ModernRelay/omnigraph-cookbooks@omnigraph-best-practices
```

Typical flow: use `omnigraph-intel-bootstrap` once to set up a new graph, then `omnigraph-best-practices` for day-to-day operations.

See [`docs/best-practices.md`](./docs/best-practices.md) for the human-readable version of the ops content.

## Repo Structure

```
omnigraph-cookbooks/
├── README.md
├── CLAUDE.md
├── docs/
│   ├── best-practices.md      ← human-readable operational guide
│   └── omni-schema.md         ← schema design principles
├── skills/
│   ├── omnigraph-intel-bootstrap/   ← bootstrap a new SPIKE graph (elicitation + research)
│   └── omnigraph-best-practices/    ← day-to-day ops (SKILL.md + references/)
└── <cookbook>/
    ├── README.md
    ├── CLAUDE.md
    ├── schema.pg
    ├── seed.md
    ├── seed.jsonl
    ├── omnigraph.yaml
    └── queries/*.gq
```

Each cookbook is fully self-contained — `cd` in and follow its README.

## Getting Started

1. Pick a cookbook.
2. Make sure you have a running Omnigraph instance — see the [Omnigraph repo](https://github.com/ModernRelay/omnigraph).
3. Follow the cookbook's Quick Start.

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
