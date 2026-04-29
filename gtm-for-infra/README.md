# gtm-for-infra

**gtm-for-infra** is an account intelligence graph: the accounts you might sell to, the products and workloads they ship, the capital behind them, and the research that asserts every fact about them.

The graph is shaped so that questions like *"which prospects share an investor and a workload category with an existing customer, ranked by their bottoms-up spend?"* are single graph reads.

Calibrated for GTM teams at infrastructure companies. The pivot is `Workload` — a per-account usage pattern — because when an account's bill scales with what they run, workload predicts spend better than headcount. For other domains the pivot is what you swap.

Built on [Omnigraph](https://github.com/ModernRelay/omnigraph), a lakehouse-native graph engine with git-style workflows. The live demo uses `parallel-cli` for OAuth-friendly enrichment, then converts the result into graph-native `ResearchRun` and `Claim` nodes. The Python SDK path is still available when you want per-field `FieldBasis` confidence, reasoning, and citation URLs preserved as `Source` graph data. Every fact in the graph carries its prompt version and provenance.

## The shape

```
      InvestsIn            ObservedTechSignal
   ┌───────────┐          ┌─────────────────┐
   │           ▼          ▼                 │
┌────────┐  ┌──────────┐BuildsProduct┌───────┐DrivesWorkload┌────────┐ OfKind ┌────────────────┐
│Investor│─▶│ Account  │────────────▶│Product│─────────────▶│Workload│───────▶│WorkloadCategory│
└────────┘  └──────────┘             └───────┘              └────────┘        └────────────────┘
    │         │                                               │
 LedRound     │ RaisedRound                             EstimatedBy
    ▼         ▼                                               ▼
 ┌──────────────┐                                    ┌──────────────┐
 │ FundingRound │                                    │ SpendEstimate│
 └──────────────┘                                    └──────────────┘

           ┌─────────────┐  TriggeredBy  ┌───────────┐
           │ ResearchRun │──────────────▶│ TechSignal│
           └─────────────┘               └───────────┘
                │ AssertedClaim
                ▼
             ┌──────┐  AboutAccount ─▶ Account
             │Claim │  AboutProduct ─▶ Product
             └──────┘  GroundedInSource ─▶ Source
                │ Supersedes ─▶ Claim
                ▼
```

- **Account** — a company you might sell to, with `status: customer | opportunity | prospect | cold`
- **Product** — what the account ships, typed by `kind` (`coding-agent`, `foundation-model`, `consumer-agent`, `vertical-saas`, `video-gen`, `image-gen`, `music-gen`, `infra`, `research-tool`, `robotics`, `other`)
- **Workload** — a per-account usage pattern (e.g. *"Cursor's autocomplete inference"*)
- **WorkloadCategory** — the shared kind of workload: `training | inference | sandbox | batch | eval | data-pipeline`
- **SpendEstimate** — bottoms-up annual USD attached to a workload
- **Investor** + **FundingRound** — the capital graph
- **TechSignal** — dated observables (funding, hiring, launch). Where Parallel Monitor API webhook events land.
- **ResearchRun** — one enrichment execution, carrying `promptVersion` and `schemaVersion`
- **Claim** — one asserted fact (`headcount = 72`), immutable
- **Source** — URL-level provenance for any Claim

## The pivot: what scales spend

Most account intelligence stacks model spend as a function of headcount. For accounts whose business scales with what they *use* — AI infra customers, developer tools customers, data platform customers, anything API-billed — that model is weak. A 30-person AI startup with one viral product can outspend a 300-person enterprise on inference by an order of magnitude.

The graph's pivot is `Workload`: a per-account compute or operational pattern. Cursor's autocomplete inference is one workload; its sandbox is another. One product produces many workloads with different spend profiles; one workload may belong to many accounts. The canonical traversal — the path every "what is this account worth" read takes — is `Account → Product → Workload → SpendEstimate`.

`WorkloadCategory` is then a separate reference node, not an enum on `Workload`. "Cognition and Cursor both run sandbox workloads" is a graph identity check — both their `Workload` nodes point to the same `WorkloadCategory` via `OfKind` — not a string compare across two `Workload.kind` values. It is what turns the lookalike query into a single traversal rather than a self-join.

For non-infra GTM domains the pivot is what you swap: a `Seat` for collaboration software where actively-engaged users predict spend better than total seats sold; a `Shipment` for logistics platforms; a `Document` for content tooling. The shared-category-node pattern carries over unchanged.

## Provenance

Every fact in the graph is a `Claim` node, asserted by exactly one `ResearchRun`.

`Account.headcount` is not a column. There is no `Account.lastRaisedStage`. Those facts live as `Claim` nodes with `predicate`, `value`, `confidence`, and `validFrom`, asserted via `AssertedClaim` from a `ResearchRun` that carries `promptVersion`, `schemaVersion`, and `ranAt`. Claims are immutable; revising a claim writes a new `Claim` and a `Supersedes` edge to the prior one.

Every fact then answers four questions without leaving the graph:

1. **Who says?** — `Claim → GroundedInSource → Source.url`
2. **How confident?** — `Claim.confidence`, sourced directly from Parallel's `FieldBasis`
3. **Which prompt version produced this?** — `Claim ← AssertedClaim ← ResearchRun.promptVersion`
4. **When did it change?** — `Supersedes` chain plus `ResearchRun.ranAt`

One read shows the full lineage for a single predicate:

```
$ omnigraph read --uri http://127.0.0.1:8090 --alias claim-drift acct-cognition headcount

1 rows from branch main via claim_drift
old.value | new.value | rOld.promptVersion | rNew.promptVersion | rOld.ranAt               | rNew.ranAt
----------+-----------+--------------------+--------------------+--------------------------+-------------------------
35        | 72        | v3                 | v4                 | 2026-02-15T09:00:00.000Z | 2026-04-15T09:00:00.000Z
```

The two `Claim` nodes are joined via `Supersedes`; each carries its asserting `ResearchRun`; the prompt version is one column away. The graph is bitemporal by construction — re-running enrichment with a bumped prompt version writes new Claims alongside the old ones, with a queryable lineage between them.

## Example reads

Each of these resolves to a single graph traversal:

- Prospects sharing both an investor and a workload category with an existing customer, ranked by their bottoms-up annual spend on that workload.
- The investors backing both an existing customer and a target account — the shortest warm-intro paths.
- For a given account: every product, workload, and spend estimate, with the source URLs grounding each spend figure.
- For a given predicate on an account: the lineage of asserted values across prompt versions.
- Claims revised in the wake of a tech signal, and the `ResearchRun` that revised them.

## Reads

The repo ships ~35 aliases in `omnigraph.yaml`. The canonical reads:

### `lookalikes`

Prospects that share both an investor and a workload category with an existing customer, ranked by the prospect's bottoms-up annual workload spend.

```
$ omnigraph read --uri http://127.0.0.1:8090 --alias lookalikes

4 rows from branch main via lookalikes_of_customers
pros.slug      | pros.name         | inv.name                    | cat.name  | est.annualUSD | cust.name
---------------+-------------------+-----------------------------+-----------+---------------+------------------
acct-cognition | Cognition (Devin) | Founders Fund               | sandbox   | 12000000      | Cursor
acct-pika      | Pika Labs         | Lightspeed Venture Partners | inference | 6500000       | Suno
acct-factory   | Factory           | Sequoia Capital             | sandbox   | 3000000       | Sourcegraph (Amp)
acct-krea      | Krea              | Matrix Partners             | inference | 2100000       | Suno
```

The "same workload" match is graph identity on a shared `WorkloadCategory`. The "same investor" match is graph identity on a shared `Investor`. One `match` block, zero joins.

### `lookalikes-for <customer>`

The same query scoped to one named customer.

### `account-workload <slug>`

What an account actually runs: products, workloads, categories, spend estimates. The canonical traversal made browsable.

### `top-spend <category>`

Top spenders in a given workload category (`wlc-sandbox`, `wlc-inference`, …). Useful for pricing model calibration and outbound prioritization within a wedge.

### `claim-drift <slug> <predicate>`

As shown above — change in a single predicate's asserted value across prompt versions.

### `claims-for <slug>` / `run-output <taskId>`

Every Claim about an account, or every Claim from one Parallel Task run. Both expose the asserting `ResearchRun` so prompt and schema versions are always one column away.

## Writes

Two paths populate the graph.

**The shipped seed.** 15 accounts (Cursor, Suno, Cognition, Pika, Factory, Krea, Mistral, Harvey, Character.AI, Liquid AI, Runway, Decagon, Perplexity, Sourcegraph, Poolside), 31 investors, 3 funding rounds, 3 tech signals, 2 research runs, 7 claims, 5 sources, 6 workload categories. Loaded via `omnigraph init` followed by `omnigraph load --mode overwrite ./seed.jsonl`. The accounts are real companies; their `customer / prospect / cold` labels are illustrative, picked so the lookalike query returns a clean result for the demo.

**Live enrichment via `parallel-cli`.** The default demo path guides the user through CLI install/auth, runs enrichment for two accounts, saves the result in a temporary work directory, discovers the accepted graph schema with the launcher skill's Omnigraph pattern, writes a transient transformer in that temp directory, and loads the generated JSONL with `omnigraph load --mode merge`.

The generated patch emits one `ResearchRun`, one `Claim` per returned field, and the `AssertedClaim` / `AboutAccount` edges needed to make the claims queryable from the account.

**Full-provenance SDK enrichment via [`demo/enrich.py`](./demo/enrich.py).** The Python SDK path requires `PARALLEL_API_KEY`, reads `output.basis`, and emits one `Source` per citation URL with deterministic `uuid5(url)` slugs plus `GroundedInSource` edges.

Re-running with a bumped prompt version plus `link-supersedes` reproduces the `claim-drift` story above against live data.

The `TechSignal` node type and `TriggeredBy: ResearchRun → TechSignal` edge exist so Parallel Monitor API webhook events can land as first-class nodes — every enrichment run can be linked to the signal that triggered it.

## Non-goals

This starter is not:

- **A CRM.** No `Opportunity`, `Stage`, `Activity`, or `Contact` node types. The graph feeds a CRM; the CRM stays the system of record for opportunities and people.
- **An ETL pipeline.** No row-to-object mapping layer, no warehouse-mirror tables. Writes are direct graph patches.
- **A general-purpose firmographics database.** The schema is opinionated toward "what does this account run, and what is that worth" — the kind of question a usage-aware GTM team asks.

## Quick start

Prerequisites: Omnigraph ≥ 0.2.2 (`brew install modernrelay/tap/omnigraph`).

```bash
cd gtm-for-infra

omnigraph query lint --schema ./schema.pg --query ./queries/lookalikes.gq

omnigraph init --schema ./schema.pg /tmp/gtm-for-infra/repo
omnigraph load --data ./seed.jsonl --mode overwrite /tmp/gtm-for-infra/repo
omnigraph-server --bind 127.0.0.1:8090 /tmp/gtm-for-infra/repo &

omnigraph read --uri http://127.0.0.1:8090 --alias lookalikes
```

Expected output:

```
4 rows from branch main via lookalikes_of_customers
pros.slug      | pros.name         | inv.name                    | cat.name  | est.annualUSD | cust.name
---------------+-------------------+-----------------------------+-----------+---------------+------------------
acct-cognition | Cognition (Devin) | Founders Fund               | sandbox   | 12000000      | Cursor
acct-pika      | Pika Labs         | Lightspeed Venture Partners | inference | 6500000       | Suno
acct-factory   | Factory           | Sequoia Capital             | sandbox   | 3000000       | Sourcegraph (Amp)
acct-krea      | Krea              | Matrix Partners             | inference | 2100000       | Suno
```

For the full onboarding flow — live enrichment, port handling, the moments where an agent should ask before acting — see [`AGENTS.md`](./AGENTS.md). For shared RustFS / S3 storage, replace the local path with `s3://…` and source credentials from `.env.omni`.

## Files

- `schema.pg` — Executable Omnigraph schema (source of truth)
- `seed.md` / `seed.jsonl` — Illustrative roster
- `queries/*.gq` — Reads and mutations
- `omnigraph.yaml` — CLI config; ~35 aliases
- `demo/README.md` — Live enrichment walkthrough
- `demo/enrich.py` — Parallel SDK enrichment with full FieldBasis citation provenance
- `AGENTS.md` — Agent onboarding and launch flow

## Reference

- [Omnigraph](https://github.com/ModernRelay/omnigraph) — schema, `.gq` query language, CLI, server
- [Parallel CLI](https://docs.parallel.ai/integrations/cli) — OAuth-friendly live enrichment path
- [Parallel Task API](https://docs.parallel.ai/task-api/task-quickstart)
- [Parallel Monitor API](https://docs.parallel.ai/monitor-api/monitor-quickstart)
