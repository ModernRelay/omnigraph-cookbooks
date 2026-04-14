---
name: omnigraph-intel-bootstrap
description: Bootstrap a new Omnigraph-based SPIKE industry intelligence graph from scratch. Use this skill whenever a user wants to set up a new SPIKE graph — either with the existing AI industry demo data or for a new domain (biotech, fintech, crypto, geopolitics, macroeconomics, SaaS, climate tech, etc.). The flow presents a demo-vs-custom decision, then for custom setups elicits domain scope + actors + cadence + sources via structured multi-select (AskUserQuestion), adapts schema and enums for the target domain, runs initial web research to generate real seed content, and executes init + load. Apply aggressively when the user says any of: "set up Omnigraph", "bootstrap a new graph", "create a new SPIKE starter", "I want to track X industry", "initialize intel for Y", "new graph for Z domain", "start a new context graph", or similar phrasing. This skill takes a user from zero to a populated, queryable graph.
---

# SPIKE Starter Bootstrap

This skill takes a user from zero to a populated, queryable SPIKE graph. Two paths:

- **Demo** — use the existing `industry-intel` starter (AI/ML signals as of early 2026). Good for demos, exploration, and understanding what SPIKE looks like populated.
- **Custom** — set up a new domain (biotech, crypto, fintech, geopolitics, etc.). Takes ~30–60 minutes including initial research and user review.

**Prerequisite:** a local Omnigraph must be running. If the user doesn't have one, direct them to the `omnigraph-best-practices` skill first for the RustFS bootstrap.

## Step 1: Ask the user which path

Use AskUserQuestion:

> Do you want to:
> - **Demo** — set up the AI industry intel demo (5 patterns, 15 signals, ~110 nodes, ready to query in ~30 seconds)
> - **Custom** — set up a graph for a new domain (I'll elicit your domain + sources, adapt the schema, research real seed data, and wire it up)

Branch based on the answer.

## Path A: Demo Setup

Quick — just clone, init, load.

See [`references/demo-setup.md`](references/demo-setup.md) for the full command list. Summary:

```bash
cd industry-intel
set -a && source ./.env.omni && set +a
# first time only: aws --endpoint-url http://127.0.0.1:9000 s3 mb s3://omnigraph-local
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/spike-intel
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/spike-intel
omnigraph read --config ./omnigraph.yaml --alias patterns disruption
```

After this, point the user at the `omnigraph-best-practices` skill for day-to-day operations.

## Path B: Custom Domain Setup

Six phases, in order. Don't skip ahead — each phase's output feeds the next.

### Phase 1 — Domain identification

Ask the user which domain they want to track. Use AskUserQuestion with these examples as options:

- Biotech / therapeutics
- Fintech / financial services
- Crypto / web3
- Geopolitics / policy
- Macroeconomics
- SaaS / enterprise software
- Climate tech / energy transition
- Other (user specifies)

Then narrow:
- Scope: "all of X" or "only Y within X"?
- Global or regional?

Capture a **project slug** for the new starter: `bio-intel`, `crypto-intel`, `geo-intel`, etc. This becomes the folder name and the repo prefix (`s3://omnigraph-local/repos/<slug>`).

### Phase 2 — Key questions (multi-select)

Use AskUserQuestion for each. See [`references/custom-domain.md`](references/custom-domain.md) for full phrasing and option lists.

- **Actors to track** (multi-select): companies, labs, regulators, individuals, protocols, investors
- **Time horizon**: recent only (3mo), medium (12mo), or full historical
- **Update cadence**: daily, weekly, monthly, ad-hoc
- **Primary consumer**: human analysts, internal dashboard, AI agents, mixed

### Phase 3 — Sources (most important)

Sources are the lifeblood of a SPIKE graph. The quality of the output is bounded by the quality of the sources. Spend time here.

Ask in order (see [`references/custom-domain.md`](references/custom-domain.md) for exact wording):

1. **Primary reading list** — newsletters, blogs, publications the user already reads (free-form, 5–15 entries)
2. **Priority analysts / experts** — 3–10 people whose takes should be first-class entities
3. **Regulatory / authoritative sources** — governmental, self-regulatory (FDA, SEC, IMF, etc.)
4. **Academic / primary sources** — journals, preprint servers, research aggregators
5. **Social / community** — X accounts, podcasts, forums

### Phase 4 — Confirm summary

Before making changes, echo what you captured back to the user:

- Domain + scope + project slug
- Actor types to track
- Horizon + cadence + consumer
- Source list (grouped by category)

Write this to `<slug>/setup-notes.md` in the new starter folder. Confirming now is cheap; rework later isn't.

### Phase 5 — Adapt the schema

Copy `industry-intel/` as a template into `<slug>/`, then adapt:

```bash
cp -r industry-intel <slug>
# rename references in omnigraph.yaml, remove the old seed.jsonl
```

Update in `<slug>/schema.pg`:

- `Element.kind` enum — replace with domain-appropriate kinds
- `Signal.domain` / `Element.domain` enum — replace with domain slices
- `Company.type` enum — match the ecosystem
- `SourceEntity.type` enum — match how sources publish
- `ArtifactType` enum — include domain-relevant formats
- Kind-specific Element properties (biotech wants `phase`, `moa`; crypto wants `chain`, `token_symbol`; etc.)

Update in `<slug>/omnigraph.yaml`:

- `graphs.local_s3.uri` → `s3://omnigraph-local/repos/<slug>`
- `project.name` → domain-appropriate name
- Optionally adjust aliases if query names change

**Pattern.kind** (`challenge`, `disruption`, `dynamic`) is usually domain-agnostic. Don't change it unless the user has strong reasons.

See [`references/schema-adaptation.md`](references/schema-adaptation.md) for the full keep-vs-change rules. See [`references/domain-examples.md`](references/domain-examples.md) for worked examples across biotech, crypto, fintech, geopolitics.

After editing:

```bash
cd <slug>
omnigraph query lint --schema ./schema.pg --query ./queries/signals.gq
```

Fix any lint errors before moving on.

### Phase 6 — Research, seed, init, load

Use web research to build real seed content. **Do not fabricate signals or dates.** See [`references/research.md`](references/research.md) for the workflow. High-level:

1. For each source from Phase 3, pull recent items (WebFetch / WebSearch)
2. Extract candidate signals (dated, URL-backed, specific)
3. Cluster into 3–5 patterns (recurring themes)
4. For each pattern, identify the Elements, Companies, Experts mentioned
5. Write `<slug>/seed.md` (tabular, human-readable) — **present this to the user for review before generating JSONL**
6. Generate `<slug>/seed.jsonl` from the confirmed seed.md
7. Init and load:

```bash
set -a && source ./.env.omni && set +a
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/<slug>
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/<slug>
```

8. Verify with a sample query:

```bash
omnigraph read --config ./omnigraph.yaml --alias patterns <pattern-kind>
```

### Phase 7 — Hand-off

Tell the user:

- What got created (starter folder, schema, seed counts, repo URI)
- How to query (via aliases or raw read)
- To use the `omnigraph-best-practices` skill for day-to-day ops (adding signals, schema evolution, branches)

## Deep Dives

Load these only when you reach the relevant phase.

| Reference | When to load |
|-----------|--------------|
| [`references/demo-setup.md`](references/demo-setup.md) | User picked Demo path |
| [`references/custom-domain.md`](references/custom-domain.md) | Phases 1–4: elicitation question bank and source patterns |
| [`references/schema-adaptation.md`](references/schema-adaptation.md) | Phase 5: what stays vs changes in the schema |
| [`references/domain-examples.md`](references/domain-examples.md) | Phase 5: ready-made enum sets for biotech, crypto, fintech, geopolitics |
| [`references/research.md`](references/research.md) | Phase 6: web research → seed.md → seed.jsonl workflow |
