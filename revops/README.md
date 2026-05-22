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
omnigraph read --alias decision-trace dec-classify-cognition-2026-04
omnigraph read --alias predicted-vs-actual 2026-01-01T00:00:00Z
omnigraph read --alias policy-history icp.ai_native_mid_market
omnigraph read --alias cohort-top-targets coh-q2-targets
```

## Walkthrough — a Monday morning lead becomes a prioritized deal

The seed (`seed.jsonl`, `seed.md`) populates a realistic snapshot built around prominent 2026 AI startups (Anthropic, Harvey, Perplexity, Cognition Labs, Anysphere/Cursor, Decagon, Sierra, Hippocratic AI, Suno, Together AI) with a Microsoft → GitHub parent/subsidiary and Inflection AI as the churned case. Here's what five minutes of working the graph looks like.

**Setup:** a new inbound form submission landed Friday at 14:23. The overnight resolution job linked it to an existing Person.

### 1. Resolve the lead — and discover an existing relationship

```text
$ omnigraph read --alias lead-resolution lead-cognition-form
1 rows from branch main via lead_resolution
p.slug         | p.fullName | p.primaryEmail    | p.seniority | p.function
---------------+------------+-------------------+-------------+------------
per-maya-chen  | Maya Chen  | maya@cognition.ai | vp          | engineering
```

She's not a new contact. Run the killer query:

```text
$ omnigraph read --alias champion-tracking
1 rows from branch main via champion_movement
p.slug         | p.fullName | fromAccount   | fromName  | toAccount     | toName         | rNew.title     | rNew.startDate
---------------+------------+---------------+-----------+---------------+----------------+----------------+---------------
per-maya-chen  | Maya Chen  | acc-anthropic | Anthropic | acc-cognition | Cognition Labs | VP Engineering | 2026-04-01
```

Maya *championed* the closed-won Anthropic deal a year ago, left in March, and started as VP Eng at Cognition on April 1. The inbound form caught her three weeks into the new role. This is the highest-converting motion in B2B and the graph surfaced it from one named traversal.

### 2. Confirm via the career timeline

```text
$ omnigraph read --alias person-history per-maya-chen
2 rows from branch main via person_role_history
a.slug         | a.legalName    | r.title                          | r.startDate | r.endDate  | r.current
---------------+----------------+----------------------------------+-------------+------------+----------
acc-cognition  | Cognition Labs | VP Engineering                   | 2026-04-01  | null       | true
acc-anthropic  | Anthropic      | Director of Platform Engineering | 2023-04-01  | 2026-03-31 | false
```

`Role` as a time-bounded node — not a property on `Person` — is what makes this work. There's no SCD2 modeling and no historical denormalization.

### 3. Why now? Signals on the new employer

```text
$ omnigraph read --alias account-signals acc-cognition
2 rows from branch main via account_signals
s.slug                 | s.name                                      | s.kind     | s.strength | s.capturedAt
-----------------------+---------------------------------------------+------------+------------+-------------------------
sig-maya-job-change    | Maya Chen joins Cognition as VP Engineering | job_change | strong     | 2026-04-01T00:00:00.000Z
sig-cognition-series-d | Cognition: $300M Series D at $5B valuation  | funding    | strong     | 2026-03-18T00:00:00.000Z
```

A funding round and a leadership change inside 14 days. The job-change is also a `Signal` on Maya herself, so the same event reaches the account both through `OnAccount` and through `OnPerson` traversals.

### 4. The classifier already weighed in — show its work

```text
$ omnigraph read --alias decision-trace dec-classify-cognition-2026-04
d.intent: classify_workload
d.rationale: Series D ($300M) + VP Eng hire from Anthropic + Devin scaling.
             Workload: agentic inference. Predicted annual spend: $220k.
d.confidence: 0.84
actorName: workload-classifier      actor.actorType: agent
signalName: Cognition: $300M Series D at $5B valuation     signalKind: funding
signalName: Maya Chen joins Cognition as VP Engineering    signalKind: job_change
policyKey: prompt.workload_classifier    policyKind: prompt_version
```

Every fact the classification used (`InformedBy` Signal), the prompt version it was screened by (`ScreenedBy` Policy), the agent that ran it (`MadeBy` Actor) — visible as one traversal. The graph *is* the audit trail; there is no separate log to grep.

### 5. Layer in fresh data with one Parallel CLI call

```bash
$ parallel-cli enrich run \
    --data '[{"company":"Cognition Labs","domain":"cognition.ai"}]' \
    --intent "Most recent funding round + total funding raised" \
    --processor core --target /tmp/cog.csv

$ python ingest/parallel_funding_ingest.py /tmp/cog.csv \
    --slug-map cognition.ai=acc-cognition \
    --actor act-agent-classifier --policy pol-prompt-classifier-v2 \
    --source src-parallel-task
```

The ingest emits 11 atomic mutations: a new `Signal` (latest round), a new `Measurement` (total funding to date), a new `Decision` with full provenance back to the agent, the Policy version, and the Source. The Action of running the enrich is itself append-only. Every cell of new information is now queryable with the same aliases you'd use for hand-curated data.

### 6. The ICP refinement loop closes

```text
$ omnigraph read --alias account-policy-matches acc-cognition
pol-icp-v2 | icp.ai_native_mid_market | ICP — AI-native mid-market v2 | icp | active

$ omnigraph read --alias policy-history icp.ai_native_mid_market
pol-icp-v2 | ICP — AI-native mid-market v2 | active   | 2026-04-01 effective
pol-icp-v1 | ICP — AI-native mid-market v1 | archived | 2026-01-01 → 2026-03-31
```

ICPs themselves live as versioned `Policy` nodes chained by `Supersedes`. Closed-lost analysis on the previous version led to v2 ("post Series B"); Cognition matches v2. Every Decision that screened against v1 still references the v1 policy node — no rewriting history.

### 7. Where does she land on the priority list?

```text
$ omnigraph read --alias cohort-top-targets coh-q2-targets
a.slug         | a.legalName     | a.industry | a.tier | predicted_spend
---------------+-----------------+------------+--------+----------------
acc-github     | GitHub          | devtools   | tier_1 | 850000.0
acc-cognition  | Cognition Labs  | devtools   | tier_1 | 220000.0
```

Cognition is the #2 predicted-spend account in the Q2 cohort — hand to the rep with a one-pager assembled from a handful of named aliases:

- **The warm path:** `champion-tracking` → Maya at Anthropic → Cognition
- **The trigger:** `account-signals acc-cognition` → 2 strong signals in 14 days
- **The number:** `latest-metric acc-cognition estimated_annual_spend_usd` → $220k
- **The audit:** `decision-trace dec-classify-cognition-2026-04` → exactly which prompt produced which prediction from which evidence

### What this would have taken without a graph

The same workflow over flat tables: three joins to dedup the lead, four to walk Maya's role history (`employments × accounts × deals × deal_roles`), an SCD2 table for the historical ICP definition, a `signals × decisions × policies × actors` star to reconstruct provenance, a daily-refreshed materialized view for the cohort ranking. Each link with its own ETL lag and its own staleness window. Above, every step runs against the same live source, every result carries its own provenance, and the same aliases the seller calls are the ones an agent or a downstream dashboard calls.

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

This cookbook is structural-complete: schema lints, all queries lint, seed loads, every alias is wired, and `ingest/test_all_aliases.sh` runs 83 read aliases green against the loaded seed. Treat the seed scenario as illustrative — the seller is unnamed, the accounts (Anthropic, Harvey, Perplexity, Cognition, Cursor, Decagon, Sierra, Hippocratic, Suno, Together, Microsoft, GitHub, Inflection) are real, and roles below the C-level along with all opportunity dollar amounts are invented for demonstration.
