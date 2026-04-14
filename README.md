# Omnigraph Starters

A collection of SPIKE-style graph starters built on [Omnigraph](https://github.com/ModernRelay/omnigraph). Each starter is a self-contained schema + seed + query set for a specific intelligence-mapping use case.

## The SPIKE Framework

**SPIKE** is an industry intelligence framework. It maps any complex, fast-moving domain into a graph of signals, patterns, insights, know-hows, and elements — so you can see what just moved, whether it matters, and how to act on it.

| Primitive | Question | Look for |
|-----------|----------|----------|
| **SIGNAL** | What just moved? | weak signal, data point, evidence |
| **PATTERN** | Is this movement persistent? | trends, shifts, contradictions |
| **INSIGHT** | How does this shift our perspective? | new paradigm, second-order effect |
| **KNOW-HOW** | How can we adopt it? | best practice, protocol |
| **ELEMENT** | What makes it possible? | product, framework, concept |

The framework stays the same. Only the seed data changes — which is why starters are a good fit.

## Starters

| Starter | Status | Description |
|---------|--------|-------------|
| [`industry-intel/`](./industry-intel) | ✅ ready | AI/ML industry intelligence — patterns, signals, elements, companies |
| `company-context/` | 🚧 planned | Company context graph — decisions, traces, actors, artifacts |
| `biomed-research/` | 🚧 planned | Biotech & medical research tracking — trials, therapeutics, mechanisms |
| `competitor-intel/` | 🚧 planned | Competitor intelligence — launches, pricing moves, positioning shifts |

Domains SPIKE works well for: AI, Biotech, Fintech, Crypto, Geopolitics, Macroeconomics — anywhere complex, fast-moving, and worth mapping.

## Repo Structure

```
omnigraph-starters/
├── README.md              ← you are here
├── CLAUDE.md              ← repo-wide agent guidance
├── industry-intel/        ← SPIKE starter (AI/ML)
│   ├── README.md
│   ├── CLAUDE.md
│   ├── schema.pg
│   ├── seed.md
│   ├── seed.jsonl
│   ├── omnigraph.yaml
│   ├── .env.omni          (gitignored)
│   └── queries/*.gq
└── <more starters>/
```

Each starter folder is fully self-contained — you `cd` into it to work with it.

## Getting Started

1. Pick a starter — see `industry-intel/README.md` as the reference example.
2. Make sure you have a running Omnigraph instance — see [Omnigraph docs](https://github.com/ModernRelay/omnigraph).
3. Follow the starter's own Quick Start section.

## Contributing a New Starter

1. Create a new folder (e.g. `biomed-research/`)
2. Add `schema.pg`, `README.md`, `CLAUDE.md`, `omnigraph.yaml`, and `queries/`
3. Seed data goes in `seed.md` (tabular, human-readable) + `seed.jsonl` (Omnigraph load format)
4. Reuse the SPIKE primitives where the domain fits; adapt the enums to match
5. Add the starter to the table above

The point of a starter is that it's opinionated and ready-to-run, not generic. Commit to a domain, seed it with real data, ship it.
