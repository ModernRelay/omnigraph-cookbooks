# RevOps — Code-first GTM Data Platform

A code-first GTM data platform built on [Omnigraph](https://github.com/ModernRelay/omnigraph). One versioned schema covering prospects, people, signals, decisions, measurements, opportunities, and provenance. Lint your queries, version your prompts, audit every classification, branch for safe iteration, export anywhere downstream.

For any team that prefers schemas to spreadsheets and named queries to ad-hoc SQL, at any scale up to roughly hundreds of thousands of accounts.

## What's in here

```
revops/
├── schema.pg              ← canonical core + extensible defaults
├── omnigraph.yaml         ← graphs, server, and 100+ named aliases
├── queries/
│   ├── accounts.gq        ← lookups, hierarchy, current people, signals on account
│   ├── people.gq          ← role history, champion tracking, job-change signals
│   ├── signals.gq         ← intent feed, funding feed, account heat
│   ├── decisions.gq       ← the audit trail — informed-by, screened-by, trace
│   ├── measurements.gq    ← time-series: predicted vs actual, ARR, headcount
│   ├── governance.gq      ← policy/prompt versioning, override rates
│   ├── opportunities.gq   ← pipeline, buying committee
│   ├── cohorts.gq         ← saved segments and segment aggregates
│   ├── engagements.gq     ← prospect touches + sales actions
│   ├── exports.gq         ← reverse-pipe queries (CRM-shaped, dashboard-shaped)
│   ├── search.gq          ← semantic + lexical retrieval over chunks
│   └── mutations.gq       ← the write surface (66 mutations)
├── seed.md                ← narrative description of the seed scenario
└── seed.jsonl             ← loadable seed data
```

## The shape

**The bet:** the loop is fixed, the taxonomy is yours. Canonical core (Person, Role, Account, Signal, Decision, Measurement, Policy, ...) is schema-fixed. Enums marked `[extension point]` in `schema.pg` (industry, segment, metric keys, signal kinds, stages) are where you extend per-domain.

**The discipline:** mutable *pointer* nodes (current state) vs append-only *claim* nodes (events, observations). Pointers get updated; claims never get overwritten — corrections become new Decisions with `Supersedes` edges.

```
                Signal ──onAccount──▶ Account ──matchesPolicy──▶ Policy (ICP)
                  │                     │                          ▲
                  │                     │                          │ refined by
                  │                  hasRole                       │
                  │                     ▼                          │
                  └─onPerson──▶ Person ◀─heldBy── Role          Outcome
                                  │                                ▲
                                  │ championedBy / blockerOnDeal   │
                                  ▼                                │
                              Opportunity ──atAccount──────────────┘
                                  ▲
                            Engagements (their touch) + Actions (our touch)
                                  ▲
                                  └── Decisions ── informedBy ──▶ Signal
                                          │
                                          ├── screenedBy ──▶ Policy
                                          ├── madeBy ──▶ Actor (human|agent)
                                          ├── resultedIn ──▶ Action
                                          └── producedBy ◀── Measurement
```

## Node types — 17 total

**Pointer nodes** (mutable): `Account`, `Person`, `Role`, `Lead`, `Opportunity`, `Cohort`, `Policy`, `Actor`, `Technology`, `Source`

**Claim / event nodes** (append-only): `Signal`, `Decision`, `Action`, `Measurement`, `Engagement`, `InformationArtifact`, `Chunk`

Key non-obvious choices:

- **`Role` is its own node**, not an edge. Time-bounded, with `startDate`/`endDate`/`current`. Champion tracking across job changes becomes one traversal.
- **`Lead` is distinct from `Person`** — Lead is raw inbound, Person is the canonical resolved entity. Multiple Leads can resolve to one Person over time.
- **`Decision` is append-only with full provenance** — every classification, advance, or disqualify carries edges to the Signals that informed it (`InformedBy {influence}`), the Policy that screened it (`ScreenedBy {outcome}`), and the Actor who made it (`MadeBy`).
- **`Measurement` is the time-series primitive** — every numeric observation (predicted spend, ARR, headcount, usage) carries `observedAt` + `metricKey` + `value` + provenance edges.
- **`Policy` versions chain via `Supersedes`** — ICPs, prompt versions, screening rules, compliance gates. One mechanism for all governance.
- **`Actor` has `actorType: enum(human, agent)`** — every Decision and Action knows whether a human or an LLM agent made it.
- **Embeddings only on `Chunk`** — narrative text (artifacts → chunks) is the only place vectors live.

## Quick Start

```bash
cd revops
set -a && source ./.env.omni && set +a

# Lint (no server needed)
omnigraph query lint --schema ./schema.pg --query ./queries/accounts.gq

# Init the repo (one-time, writes to RustFS storage)
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/revops

# Load the seed (one-time)
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/revops

# Start the server (keep running)
omnigraph-server --config ./omnigraph.yaml

# Everything else goes through aliases
omnigraph read --alias pipeline
omnigraph read --alias funding-feed 2026-01-01T00:00:00Z
omnigraph read --alias champion-tracking
omnigraph read --alias decision-trace dec-classify-zylon-2026-04
omnigraph read --alias predicted-vs-actual 2026-01-01T00:00:00Z
omnigraph read --alias policy-history icp.mid_market_ai_infra
omnigraph read --alias cohort-top-targets coh-q2-targets
```

## The killer queries

These are the queries that justify doing this in a graph rather than a table:

| Alias | What it answers |
|---|---|
| `champion-tracking` | People who championed a closed-won deal and now work somewhere else. The single highest-converting motion in B2B. |
| `recent-job-changes` | Signals of kind `job_change` in a window — high-signal, time-bounded. |
| `decision-trace` | For a given Decision: which Signals informed it, which Policy screened it, which Actor made it, what Action it produced. |
| `policy-history` | All versions of a policy key (ICP v1 → v2 → v3, or prompt v1 → v2). |
| `predicted-vs-actual` | Predicted spend (from an agent's Decision) vs actual spend (from billing telemetry). Drives prompt refinement. |
| `account-heat` | Recent signal count grouped by account. The "what's hot" feed. |
| `account-policy-matches` | Which ICPs does an account match. Returns the audit history of fit classifications. |
| `agent-decisions` | All Decisions made by a particular Actor (especially useful filtering on `actorType: agent`). |
| `cohort-top-targets` | Top accounts in a saved segment ranked by latest predicted spend. The "who do I call today" view. |
| `export-funding-trigger` | Recent funding signals shaped as flat JSON for CRM ingestion. |

## Aliases are the user-facing API

Every read and mutation is exposed as a named alias in `omnigraph.yaml`. Agents, scripts, dashboards, and CLI users invoke the alias by name — never raw queries. When the underlying `.gq` query evolves, the alias name stays. Default output is `table` for humans; pair with `--format jsonl` (or set on the alias) for scripts.

## Extension points

The schema marks `[extension point]` on enums you're expected to extend per-domain:

- `Account.industry` — add your verticals (`hospital_system`, `community_bank`, `law_firm_am200`)
- `Account.segment` — your sizing taxonomy
- `Measurement.metricKey` — your domain metrics (`gpu_hours_monthly`, `claims_processed_weekly`)
- `Signal.kind` — your trigger taxonomy (`fda_approval`, `case_filing`)
- `Policy.kind` — your governance categories
- `Opportunity.stage` — your funnel
- `Decision.intent` — left as `String` for free-form labeling

Extend via `omnigraph schema plan` → `schema apply`. Use `@rename_from(...)` when renaming.

## Operating playbooks

- **Continuous ingestion** — webhook-driven Monitor-style: each event writes to a staging branch, auto-merges to main if Cedar policy passes (e.g., no decision confidence drops below 0.5).
- **Prompt A/B** — branch from main, run new prompt version against all matching accounts, diff the resulting Decisions, merge or discard.
- **Point-in-time read** — `omnigraph commit list`, pick the commit, read against it. No SCD2 ceremony.
- **CRM sync** — `omnigraph read --alias export-accounts --format jsonl` piped into your CRM-of-choice's bulk import API. Same source of truth, no ETL.

See `../docs/best-practices.md` for the full operations guide.

## Ingest example: Parallel CLI → Omnigraph

`ingest/parallel_funding_ingest.py` is a worked example of the canonical Monitor-style enrichment pipeline. It reads a Parallel CLI enrichment CSV and emits the right `omnigraph change` mutations to:

1. Insert a funding `Signal` per account (the latest round)
2. Insert a `Measurement` of `funding_raised_usd` (total to date)
3. Insert a `Decision` with `intent: enrich_funding` recording the run
4. Link the Decision to its Actor (the agent that ran it), the Policy (the prompt version), and the Signal it surfaced

End-to-end:

```bash
# 1. Enrich via Parallel
parallel-cli enrich run \
    --data '[{"company":"Cognition Labs","domain":"cognition.ai"}, ...]' \
    --intent "Most recent funding round + total funding to date" \
    --processor core \
    --target /tmp/parallel-out.csv

# 2. Ingest into the graph
python ingest/parallel_funding_ingest.py /tmp/parallel-out.csv \
    --slug-map cognition.ai=acc-cognition,cursor.com=acc-cursor \
    --actor act-agent-classifier \
    --policy pol-prompt-classifier-v2 \
    --source src-parallel-task

# 3. Verify
omnigraph read --alias funding-feed 2025-08-01T00:00:00Z
omnigraph read --alias top-accounts-by-metric funding_raised_usd
omnigraph read --alias decision-trace dec-enrich-cognition-<id>
```

The pattern: every external enrichment becomes an append-only `Decision` + `Measurement` triple, with provenance back to the Source, Policy, and Actor that produced it. Replay, audit, and override are graph operations.

## Status

This cookbook is structural-complete: schema lints, all queries lint, seed loads, every alias is wired. Treat the seed scenario as illustrative — the account list mixes real (Moonshot AI, Zylon, Edra) and fictional (Atlas Data the seller, BigCorp) entities.
