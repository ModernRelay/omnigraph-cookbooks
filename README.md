# Omnigraph Starters

Opinionated, ready-to-run graph starters built on [Omnigraph](https://github.com/ModernRelay/omnigraph). Each starter is a self-contained schema, seed, and query set for a specific use case.

## Starters

| Starter | Status | Description |
|---------|--------|-------------|
| [`industry-intel/`](./industry-intel) | ✅ ready | AI/ML industry intelligence graph |
| `company-context/` | 🚧 planned | Internal decisions, traces, actors, artifacts |
| `biomed-research/` | 🚧 planned | Biotech & medical research tracking |
| `competitor-intel/` | 🚧 planned | Competitor launches, pricing, positioning |

## Repo Structure

```
omnigraph-starters/
├── README.md
├── CLAUDE.md
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

## Contributing

Create a new folder, add a schema, seed, queries, and docs. Ship real seed data, not placeholders.
