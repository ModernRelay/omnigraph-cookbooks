# RevOps — GTM Intelligence Backplane

Knowledge graph cookbook for AI-native GTM engineering. Built on [Omnigraph](https://github.com/ModernRelay/omnigraph), it models account signals, buyer context, champion movement, AI enrichment, prompt governance, measurements, and decision provenance in one versioned graph.

## Core GTM Loop

Signals and roles form the prospecting core. Decisions interpret them. Measurements rank accounts. Policies govern the AI and ICP logic. Exports turn the graph into downstream GTM work queues.

```
  Signal ── onAccount ─────────────▶ Account ── matchesPolicy ──▶ Policy
    │                                  │                              ▲
    │                                  │                              │
    ├── onPerson ──▶ Person ◀─ heldBy ─┤ Role                         │
    │                 │                │                              │
    │                 └── championedBy ▼                              │
    │                              Opportunity ── atAccount ──────────┘
    │
    └── informedBy ◀── Decision ── screenedBy ──▶ Policy
                        │   │
                        │   ├── madeBy ─────────▶ Actor (human|agent)
                        │   ├── producedBy ◀──── Measurement
                        │   └── resultedIn ─────▶ Action
```

The operating loop is concrete:

| Workflow | What it answers | Primary aliases |
|---|---|---|
| Signal-based account prioritization | Which accounts should a seller or agent work today, and why? | `daily-priority-accounts`, `account-priority-detail` |
| Champion job-change outbound | Which known champions moved into in-ICP accounts? | `champion-job-change-queue`, `champion-context` |
| AI enrichment audit | Which agent, prompt, source, and signal produced this score or recommendation? | `decision-trace`, `prompt-governance`, `enrichment-audit` |
| Prompt and ICP governance | Which policy version screened each decision, and what changed over time? | `policy-history`, `decision-lineage` |
| Reverse-pipe exports | What rows should CRM, sales engagement, Slack, or dashboards consume? | `export-priority-accounts`, `export-champion-job-changes` |

## Reference Seed: AI GTM, Early 2026

The seed uses recognizable AI companies as accounts: Anthropic, Harvey, Perplexity, Cognition Labs, Anysphere/Cursor, Decagon, Sierra, Hippocratic AI, Suno, Together AI, Microsoft, GitHub, and Inflection AI.

It exercises five GTM patterns:

| Pattern | What it captures |
|---|---|
| **Daily account priority** | In-ICP prospects ranked by recent signals, intent score, and predicted spend |
| **Warm-path outbound** | Prior champions who changed jobs into target accounts |
| **AI enrichment provenance** | Funding and workload enrichment linked to source, prompt policy, actor, and measurement |
| **Prompt and ICP versioning** | ICP v1 → v2, classifier prompt v1 → v2, and a signal-priority scoring policy |
| **Revenue feedback loop** | Predicted spend vs actual spend for prompt and scoring refinement |

**Totals:** 147 nodes, 260 edges, 177 named queries exposed through aliases.

## What's in here

```
revops/
├── schema.pg              ← canonical core + extensible defaults
├── omnigraph.yaml         ← graphs, server, and 100+ named aliases
├── queries/
│   ├── accounts.gq        ← lookups, hierarchy, current people, signals on account
│   ├── people.gq          ← role history, champion tracking, job-change signals
│   ├── signals.gq         ← intent feed, funding feed, account heat
│   ├── prioritization.gq  ← daily account queue + champion job-change queue
│   ├── decisions.gq       ← the audit trail — informed-by, screened-by, trace
│   ├── measurements.gq    ← time-series: predicted vs actual, ARR, headcount
│   ├── governance.gq      ← policy/prompt versioning, override rates
│   ├── opportunities.gq   ← pipeline, buying committee
│   ├── cohorts.gq         ← saved segments and segment aggregates
│   ├── engagements.gq     ← prospect touches + sales actions
│   ├── exports.gq         ← reverse-pipe queries (CRM-shaped, dashboard-shaped)
│   ├── search.gq          ← semantic + lexical retrieval over chunks
│   └── mutations.gq       ← the write surface (69 mutations)
├── seed.md                ← narrative description of the seed scenario
└── seed.jsonl             ← loadable seed data
```

## Schema Essentials

**The bet:** the loop is fixed, the taxonomy is yours. Canonical core (Person, Role, Account, Signal, Decision, Measurement, Policy, ...) is schema-fixed. Enums marked `[extension point]` in `schema.pg` (industry, segment, metric keys, signal kinds, stages) are where you extend per-domain.

**The discipline:** mutable *pointer* nodes (current state) vs append-only *claim* nodes (events, observations). Pointers get updated; claims never get overwritten — corrections become new Decisions with `SupersedesDecision` edges. Policy versions use `Supersedes`.

## Node types — 17 total

**Pointer nodes** (mutable): `Account`, `Person`, `Role`, `Lead`, `Opportunity`, `Cohort`, `Policy`, `Actor`, `Technology`, `Source`

**Claim / event nodes** (append-only): `Signal`, `Decision`, `Action`, `Measurement`, `Engagement`, `InformationArtifact`, `Chunk`

**Enums that carry the GTM lens:**

| Enum-backed field | Values |
|---|---|
| `Account.kind` | `prospect, customer, churned, partner` |
| `Signal.kind` | `funding, hiring, job_change, leadership_change, usage, churn, news, intent` |
| `Decision.status` | `pending, approved, rejected, superseded, overridden` |
| `Opportunity.stage` | `identified, qualified, evaluation, business_case, procurement, closed_won, closed_lost` |
| `Policy.kind` | `icp, prompt_version, routing_rule, do_not_sell, compliance, scoring_rule` |
| `Actor.actorType` | `human, agent` |

**Edges that carry the GTM logic:**

| Edge | Route | Meaning |
|---|---|---|
| `OnAccount` / `OnPerson` | Signal -> Account / Person | what the signal is about |
| `HasRole` / `HeldByPerson` | Account -> Role -> Person | current and historical employment, title, function, seniority |
| `MatchesPolicy` | Account -> Policy | active ICP, screening, and account-fit logic |
| `ChampionedBy` / `BuyerOnDeal` / `InfluencerOnDeal` / `BlockerOnDeal` | Opportunity -> Person | buying committee and champion graph |
| `InformedBy` / `ScreenedBy` / `MadeBy` | Decision -> Signal / Policy / Actor | audit trail for AI or human decisions |
| `TargetsAccount` / `TargetsOpportunity` / `TargetsPerson` | Decision -> Account / Opportunity / Person | what the decision affected |
| `ProducedByDecision` | Measurement -> Decision | numeric output from a prompt, scorer, or enrichment run |
| `SupersedesDecision` / `Supersedes` | Decision -> Decision / Policy -> Policy | correction lineage and policy versioning |

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
omnigraph read --alias daily-priority-accounts 2026-01-01T00:00:00Z pol-icp-v2
omnigraph read --alias account-priority-detail acc-cognition 2026-01-01T00:00:00Z
omnigraph read --alias funding-feed 2026-01-01T00:00:00Z
omnigraph read --alias champion-job-change-queue 2026-01-01T00:00:00Z pol-icp-v2
omnigraph read --alias decision-trace dec-classify-cognition-2026-04
omnigraph read --alias decision-lineage dec-classify-cognition-2026-04
omnigraph read --alias prompt-governance pol-signal-score-v1
omnigraph read --alias enrichment-audit 2026-01-01T00:00:00Z
omnigraph read --alias predicted-vs-actual 2026-01-01T00:00:00Z
omnigraph read --alias policy-history icp.ai_native_mid_market
omnigraph read --alias cohort-top-targets coh-q2-targets
```

## Walkthrough — signal to seller action

The seed uses real AI companies as recognizable accounts, while the seller, source artifacts, signals, relationships, roles below C-level, opportunity amounts, and predictions are illustrative. The goal is to demonstrate the graph shape for a GTM team.

Below is the core workflow when your job is to *find and qualify accounts to reach out to today*.

### 1. Start with the daily priority queue

```text
$ omnigraph read --alias daily-priority-accounts 2026-01-01T00:00:00Z pol-icp-v2
a.slug         | a.legalName    | intent_score | predicted_spend
---------------+----------------+--------------+----------------
acc-cognition  | Cognition Labs | 0.92         | 220000.0
acc-github     | GitHub         | 0.88         | 850000.0
acc-sierra     | Sierra         | 0.84         | 260000.0
acc-cursor     | Anysphere      | 0.76         | 180000.0
```

`daily-priority-accounts` is the seller queue: in-ICP prospects with recent signal evidence, an `intent_score`, and a predicted spend Measurement. Each score is a Measurement produced by a `Decision { intent: "score_account" }` screened by `pol-signal-score-v1`.

Drill into why an account made the list:

```text
$ omnigraph read --alias account-priority-detail acc-cognition 2026-01-01T00:00:00Z
signalName: Cognition: $300M Series D at $5B valuation
signalKind: funding
decision: dec-score-cognition-2026-04
intent: score_account
policyKey: score.signal_priority
actorName: icp-fit-scorer
```

### 2. Start with intent: who lit up recently?

```text
$ omnigraph read --alias account-heat 2026-01-01T00:00:00Z
9 rows from branch main via account_heat
a.slug          | a.legalName            | signal_count
----------------+------------------------+-------------
acc-cognition   | Cognition Labs         | 2
acc-github      | GitHub                 | 2
acc-anthropic   | Anthropic              | 1
acc-cursor      | Anysphere              | 1
acc-perplexity  | Perplexity             | 1
...
```

`account-heat` ranks accounts by recent signal volume. Cognition and GitHub are the hottest. Drilling into Cognition:

```text
$ omnigraph read --alias funding-feed 2026-01-01T00:00:00Z
1 rows from branch main via funding_feed
s.slug                 | s.name                                     | s.capturedAt | s.strength | a.legalName
-----------------------+--------------------------------------------+--------------+------------+----------------
sig-cognition-series-d | Cognition: $300M Series D at $5B valuation | 2026-03-18   | strong     | Cognition Labs
```

A live trigger from Q1: Cognition raised $300M at $5B. Funding is the canonical outbound-prospecting trigger — budget just opened, vendor evaluations are likely.

### 3. Filter to active ICP — separate the qualified from the curious

```text
$ omnigraph read --alias policy-accounts pol-icp-v2
7 rows from branch main via policy_matched_accounts
a.slug         | a.legalName    | a.kind   | a.segment  | a.industry    | a.tier
---------------+----------------+----------+------------+---------------+-------
acc-anthropic  | Anthropic      | customer | enterprise | ai_infra      | tier_1
acc-harvey     | Harvey         | customer | mid_market | vertical_saas | tier_1
acc-perplexity | Perplexity     | customer | mid_market | ai_infra      | tier_1
acc-cognition  | Cognition Labs | prospect | startup    | devtools      | tier_1
acc-cursor     | Anysphere      | prospect | startup    | devtools      | tier_1
acc-sierra     | Sierra         | prospect | mid_market | saas          | tier_1
acc-github     | GitHub         | prospect | enterprise | devtools      | tier_1
```

Seven accounts match the active ICP version. Three are already customers; four are prospects (Cognition, Cursor, Sierra, GitHub). Compared against `account-heat`, both heat leaders fall inside the ICP — the funding-trigger workflow above produced a qualified target list of one (Cognition is hot AND in-ICP AND a prospect).

ICP itself is versioned. v1 ("post Series A") was archived in March after closed-lost analysis showed pre-revenue startups don't convert; v2 ("post Series B") is what these matches use. Every classification against v1 still references the v1 Policy node — `Supersedes` chains the history without rewriting it.

### 4. Cohort + spend predicted = priority order

```text
$ omnigraph read --alias cohort-top-targets coh-q2-targets
2 rows from branch main via cohort_top_targets
a.slug        | a.legalName    | a.industry | a.tier | predicted_spend
--------------+----------------+------------+--------+----------------
acc-github    | GitHub         | devtools   | tier_1 | 850000.0
acc-cognition | Cognition Labs | devtools   | tier_1 | 220000.0
```

The Q2 target cohort already holds the curated short-list, sorted by predicted spend. GitHub leads at $850k; Cognition is #2 at $220k. Each number is a `Measurement` produced by a specific `Decision` made by the classifier agent.

### 5. Technographic adjacency — adjacent prospects without explicit signals

```text
$ omnigraph read --alias accounts-using-tech tech-modal
2 rows from branch main via accounts_using_tech
a.slug        | a.legalName    | a.kind   | a.segment | a.industry
--------------+----------------+----------+-----------+-----------
acc-cognition | Cognition Labs | prospect | startup   | devtools
acc-cursor    | Anysphere      | prospect | startup   | devtools
```

Both Cognition and Cursor run Modal for their compute — a buying signal *adjacent to* explicit intent signals. Useful when two prospects show similar technographic profiles; sell motion can lean on each other.

### 6. Who do we talk to? Current people at the top target

```text
$ omnigraph read --alias account-people acc-cognition
2 rows from branch main via account_current_people
p.slug        | p.fullName | r.title          | r.level | r.department | r.startDate
--------------+------------+------------------+---------+--------------+------------
per-maya-chen | Maya Chen  | VP Engineering   | vp      | engineering  | 2026-04-01
per-scott-wu  | Scott Wu   | CEO & Co-founder | c_level | ceo_office   | 2023-11-01
```

Two current Roles to consider for outreach. To find similar function-leaders across the whole prospect cohort:

```text
$ omnigraph read --alias people-by-segment-function startup engineering
2 rows from branch main via people_by_segment_function
p.slug          | p.fullName  | r.title                      | account       | a.legalName
----------------+-------------+------------------------------+---------------+---------------
per-aman-sanger | Aman Sanger | Co-founder & Chief Architect | acc-cursor    | Anysphere
per-maya-chen   | Maya Chen   | VP Engineering               | acc-cognition | Cognition Labs
```

### 7. Champion job-change outbound — already know someone at a prospect?

```text
$ omnigraph read --alias champion-job-change-queue 2026-01-01T00:00:00Z pol-icp-v2
person          | fullName   | fromName  | toName         | currentTitle        | priorStage
----------------+------------+-----------+----------------+---------------------+-----------
per-nora-patel  | Nora Patel | Harvey    | Sierra         | VP Customer Success | closed_won
per-maya-chen   | Maya Chen  | Anthropic | Cognition Labs | VP Engineering      | closed_won
```

`champion-job-change-queue` rolls through prior champions, current roles, recent job-change signals, and ICP fit. Maya championed the Anthropic deal and is now at Cognition; Nora championed a Harvey deal and is now at Sierra. The value is relationship history joined to current account fit.

### 8. Show the agent's work before the rep picks up the phone

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

Every fact behind the $220k prediction is one traversal away: which Signals informed it, which prompt version screened it, which Actor produced it. Reps don't trust black-box scores; they trust evidence chains. This *is* the evidence chain.

Decision corrections are explicit too:

```text
$ omnigraph read --alias decision-lineage dec-classify-cognition-2026-04
decision: dec-classify-cognition-2026-04
supersedes: dec-classify-cognition-2026-02
policyKey: prompt.workload_classifier
actorName: workload-classifier
```

### 9. Fresh data on a borderline candidate

For Sierra (ICP match, no recent strong signals), pull current fundraising context with the Parallel CLI:

```bash
$ parallel-cli enrich run \
    --data '[{"company":"Sierra","domain":"sierra.ai"}]' \
    --intent "Most recent funding round + total funding raised" \
    --processor core --target /tmp/sierra.csv

$ python ingest/parallel_funding_ingest.py /tmp/sierra.csv \
    --slug-map sierra.ai=acc-sierra \
    --actor act-agent-classifier --policy pol-prompt-classifier-v2 \
    --source src-parallel-task
```

12 atomic mutations land: a new funding `Signal`, a source link for the Signal, a `Measurement` of total funding, a `Decision` with rationale + `MadeBy` agent + `InformedBy` Signal + `ScreenedBy` prompt-v2. Sierra now has the same audit-grade context as Cognition. Whether it stays in the cohort or graduates to a higher tier is the next prompt's call — and that prompt's decisions will reference *its* Policy version, so the upgrade trail is preserved automatically.

### Today's outbound list

The five-call list assembles from a handful of named aliases:

| Priority | Account | Predicted spend | Trigger | Who to reach | Warm path? |
|---|---|---|---|---|---|
| 1 | GitHub | $850k | Microsoft AI-Everywhere mandate + 8 ML hires | Priya Iyer (VP Eng) | — |
| 2 | Cognition Labs | $220k | Series D $300M + Maya hire | Scott Wu, Maya Chen | **Yes — Maya, Anthropic champion** |
| 3 | Cursor | TBD | $100M ARR milestone | Aman Sanger | — |
| 4 | Harvey | (customer, expansion) | Allen & Overy win | Winston Weinberg | (existing) |
| 5 | Sierra | (newly enriched) | fresh Parallel fundraising data | Bret Taylor | — |

Each row in that table came from a separate alias. The aliases are the user-facing API; the underlying queries can evolve without breaking the rep's workflow.

### What prospecting in flat tables looks like

The same workflow on a warehouse: union the Monitor events table to the news feed for the trigger surface; join `accounts × icp_snapshots × icp_versions` with a date filter to get the active ICP membership; SCD2 the `champion_assignments` table to know who championed what; window-function the `predictions` table to get latest predicted spend per account; left-join to `roles × persons × employments` for current contacts. Five queries, three ETL jobs, one daily refresh, two staleness windows. Above, each step is one named alias against a single live source — and every output carries its own provenance graph the rep can drill into.

## The killer queries

These are the queries that justify doing this in a graph rather than a table:

| Alias | What it answers |
|---|---|
| `daily-priority-accounts` | The seller queue: in-ICP prospects ranked by recent signals, intent score, and predicted spend. |
| `account-priority-detail` | Why an account is in the queue: signals, decisions, policies, and actor. |
| `champion-job-change-queue` | Prior champions who moved into in-ICP accounts. |
| `decision-lineage` | Which Decision replaced a previous Decision, plus signal/policy/actor provenance. |
| `prompt-governance` | Decisions and measurements produced under a prompt/scoring Policy. |
| `enrichment-audit` | Recent agent-produced enrichment/scoring decisions and their measurements. |
| `champion-tracking` | People who championed a closed-won deal and now work somewhere else. The single highest-converting motion in B2B. |
| `recent-job-changes` | Signals of kind `job_change` in a window — high-signal, time-bounded. |
| `decision-trace` | For a given Decision: which Signals informed it, which Policy screened it, which Actor made it, what Action it produced. |
| `policy-history` | All versions of a policy key (ICP v1 → v2 → v3, or prompt v1 → v2). |
| `predicted-vs-actual` | Predicted spend (from an agent's Decision) vs actual spend (from billing telemetry). Drives prompt refinement. |
| `account-heat` | Recent signal count grouped by account. The "what's hot" feed. |
| `account-policy-matches` | Which ICPs does an account match. Returns the audit history of fit classifications. |
| `agent-decisions` | All Decisions made by a particular Actor (especially useful filtering on `actorType: agent`). |
| `cohort-top-targets` | Top accounts in a saved segment ranked by latest predicted spend. |
| `export-funding-trigger` | Recent funding signals shaped as flat JSON for CRM ingestion. |
| `export-priority-accounts` | Seller queue shaped as flat JSON for CRM or sales-engagement ingestion. |
| `export-champion-job-changes` | Champion movement rows shaped for CRM, sequencing, or Slack alerts. |

## Aliases are the user-facing API

Every read and mutation query is exposed as a named alias in `omnigraph.yaml`, enforced by `ingest/check_alias_coverage.py`. Agents, scripts, dashboards, and CLI users invoke the alias by name — never raw queries. When the underlying `.gq` query evolves, the alias name stays. Default output is `table` for humans; pair with `--format jsonl` (or set on the alias) for scripts.

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

This cookbook is structural-complete: schema lints, all queries lint, seed loads, every query is exposed through an alias, and `ingest/test_all_aliases.sh` covers 107 read aliases against the loaded seed. Treat the seed scenario as illustrative — the seller is unnamed, the accounts are recognizable real companies, and source artifacts, signals, roles below the C-level, buying committees, opportunity dollar amounts, predicted spend, and relationships are invented for demonstration.
