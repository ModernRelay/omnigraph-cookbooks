# Omnigraph Starters

Opinionated, ready-to-run graph starters built on [Omnigraph](https://github.com/ModernRelay/omnigraph). Each starter is a self-contained schema, seed, and query set for a specific use case.

## Starters

| Starter | Status | Description |
|---------|--------|-------------|
| [`industry-intel/`](./industry-intel) | ✅ ready | AI/ML industry intelligence graph |
| `company-context/` | 🚧 planned | Internal decisions, traces, actors, artifacts |
| `biomed-research/` | 🚧 planned | Biotech & medical research tracking |
| `competitor-intel/` | 🚧 planned | Competitor launches, pricing, positioning |

## Agent Skills

Packaged agent skills live under [`skills/`](./skills) and can be installed with the `npx skills` CLI:

| Skill | Description |
|-------|-------------|
| [`omnigraph-local`](./skills/omnigraph-local) | Operate a locally deployed Omnigraph — schema authoring and evolution, query linting, data changes, branches, embeddings, aliases, server, policy, and common gotchas |

Install:

```bash
npx skills add ModernRelay/omnigraph-starters@omnigraph-local
```

See [`docs/best-practices.md`](./docs/best-practices.md) for the human-readable version of the same content.

## Repo Structure

```
omnigraph-starters/
├── README.md
├── CLAUDE.md
├── docs/
│   ├── best-practices.md      ← human-readable operational guide
│   └── omni-schema.md         ← schema design principles
├── skills/
│   └── omnigraph-local/       ← agent skill (SKILL.md + references/)
└── <starter>/
    ├── README.md
    ├── CLAUDE.md
    ├── schema.pg
    ├── seed.md
    ├── seed.jsonl
    ├── omnigraph.yaml
    └── queries/*.gq
```

Each starter is fully self-contained — `cd` in and follow its README.

## Getting Started

1. Pick a starter.
2. Make sure you have a running Omnigraph instance — see the [Omnigraph repo](https://github.com/ModernRelay/omnigraph).
3. Follow the starter's Quick Start.

## SPIKE Framework

The `industry-intel/` starter uses SPIKE, an opinionated graph modeling lens:

- `Signal`: a dated external fact, movement, or observation
- `Pattern`: a recurring theme formed, contradicted, or driven by signals
- `Insight`: a synthesized interpretation explaining why a pattern matters
- `KnowHow`: an actionable practice or playbook grounded in the graph
- `Element`: a concrete product, framework, company, or concept the signals are about

SPIKE is a starter-level convention, not a requirement for every graph in this repo.

## Contributing

Create a new folder, add a schema, seed, queries, and docs. Ship real seed data, not placeholders.
