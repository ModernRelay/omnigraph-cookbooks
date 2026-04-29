# AGENTS.md — gtm-for-infra

Single source of agent context for the gtm-for-infra starter — usecase, onboarding flow, launch script, design rationale, editing conventions, and the moments where you should stop and ask the user.

Read this top to bottom on first contact with the folder. Then jump to the section the user's intent maps to.

## About

`gtm-for-infra` is an account intelligence graph for GTM teams at infrastructure companies. Built on [Omnigraph](https://github.com/ModernRelay/omnigraph) (a lakehouse-native graph engine with git-style workflows); enriched via the Parallel CLI for the live demo, with an SDK path available for full citation provenance. Designed to *feed* a CRM, not mirror one.

Every fact is a `Claim` with provenance back to the `ResearchRun` that produced it (carrying prompt + schema version). `Workload` — not headcount — is the canonical pivot from account → spend, because for accounts whose bill scales with what they run, workload predicts spend better than headcount. `Investor` is a first-class node, because shared cap tables are the strongest lookalike signal in the dataset.

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

## First-contact onboarding

If the user has just opened this folder or said something vague (*"what is this?"*, *"help me with this starter"*, *"can you set me up?"*), **ask before running anything destructive or that costs money**.

Three branches users typically want — pick the right one, ask if unclear:

1. **"Demo me the graph"** *(most common)* — Run **Prerequisites → Bootstrap → Headline**. Stop, show the result, narrate why it's interesting, then list **Follow-ups** and let them pick.
2. **"Set this up for my own GTM"** — Run **Prerequisites → Bootstrap** with the shipped seed first (so they see a working baseline), then walk them through the **Swap-seed** follow-up.
3. **"I'm just exploring"** — **Don't bootstrap.** Explain the shape (this section + the diagram above), point at `schema.pg` and `queries/`, stop. No server, no mutations.

If the user's intent is **editorial** (changing `schema.pg`, adding aliases, editing a `.gq` query), skip this section entirely and route to **When editing** further down — those tasks don't need the bootstrap flow.

If the user's intent is already clear (*"show me the demo"*, *"get me to the lookalikes query"*), skip the question and proceed. If unclear, ask once with the three options. If the answer is still vague, default to branch (1) — *Demo me the graph*.

## Prerequisites

```bash
omnigraph --version              # need >= 0.2.2
command -v omnigraph-server      # same package, separate binary — verify on PATH
```

If missing: `brew install modernrelay/tap/omnigraph`.

No API key needed for the headline — the seed ships with the repo.

## Bootstrap

Defaults: `REPO=/tmp/gtm-for-infra/repo`, `PORT=8090`. If the path or port is already in use, pick fresh values (e.g. `/tmp/gtm-for-infra-2/repo`, `8091`) and update the four `*FILE` variables to match.

```bash
REPO=/tmp/gtm-for-infra/repo
PORT=8090
PIDFILE=/tmp/gtm-for-infra-server.pid
LOGFILE=/tmp/gtm-for-infra-server.log

omnigraph init --schema ./schema.pg "$REPO"
omnigraph load --data ./seed.jsonl --mode overwrite "$REPO"
omnigraph-server --bind 127.0.0.1:$PORT "$REPO" >"$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
sleep 1   # let the server bind
```

`init` and `load` are storage-only — they touch `$REPO` on disk and never bind a port. Only the `omnigraph-server` line cares about `$PORT`. So if `$PORT` is already bound, you can either reuse the existing server (skip the `omnigraph-server` line and trust the prior `init`/`load` of the same `$REPO`) or pick a new `$PORT` and re-run just the server line.

The CLI's default URI in `omnigraph.yaml` is `http://127.0.0.1:8080`, but the bootstrap above binds the server on `$PORT` (default `8090`). The Headline and Follow-up commands therefore include `--uri http://127.0.0.1:$PORT` explicitly so they work on whatever port you picked. If you change `omnigraph.yaml`'s `local_server.uri` to match `$PORT`, you can drop the `--uri` flag.

## Headline

```bash
omnigraph read --uri "http://127.0.0.1:$PORT" --alias lookalikes
```

Expected: a ranked table of prospect accounts, each sharing both an investor and a workload category with an existing customer, ordered by the prospect's bottoms-up annual workload spend. Top row on the shipped seed: **Cognition (Devin)** — Founders Fund backs both Cognition and Cursor (an existing customer), and both run sandbox workloads. Cognition's estimated sandbox spend ($12M/yr) outranks the rest of the field.

Actual output:

```
4 rows from branch main via lookalikes_of_customers
pros.slug      | pros.name         | inv.name                    | cat.name  | est.annualUSD | cust.name
---------------+-------------------+-----------------------------+-----------+---------------+------------------
acct-cognition | Cognition (Devin) | Founders Fund               | sandbox   | 12000000      | Cursor
acct-pika      | Pika Labs         | Lightspeed Venture Partners | inference | 6500000       | Suno
acct-factory   | Factory           | Sequoia Capital             | sandbox   | 3000000       | Sourcegraph (Amp)
acct-krea      | Krea              | Matrix Partners             | inference | 2100000       | Suno
```

The "same workload" match is graph identity on a shared `WorkloadCategory`; the "same investor" match is graph identity on a shared `Investor`. One `match` block, no joins to write.

## Follow-ups

Pick any. Each is independent.

### See prompt-version provenance

```bash
omnigraph read --uri "http://127.0.0.1:$PORT" --alias claim-drift acct-cognition headcount
```

Returns old and new asserted values for `headcount` on Cognition, joined via the `Supersedes` edge, each side carrying its `ResearchRun.promptVersion` and `ranAt`. One prompt bump → `35 → 72` employees, with reasoning + source URL still attached on both sides. The bitemporal-by-default story: prompt iteration is auditable as native graph data, no separate history-table machinery.

### Live enrichment via Parallel CLI

**Ask before running.** This costs real money on the user's Parallel account and takes ~1–2 min per account. Confirm scope (which accounts, how many) before kicking off. Default demo scope: `acct-cognition acct-factory`.

Use the CLI path first. It supports OAuth login, so the user does not need to paste an API key into the shell.

```bash
command -v parallel-cli || curl -fsSL https://parallel.ai/install.sh | bash
parallel-cli auth || parallel-cli login
```

If the install script is unavailable, offer the pipx fallback:

```bash
pipx install "parallel-web-tools[cli]"
pipx ensurepath
parallel-cli login
```

Run the enrichment non-blocking, then show the returned monitoring URL to the user:

```bash
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/gtm-for-infra.XXXXXX")"
echo "$WORKDIR"

parallel-cli enrich run \
  --data '[{"account_slug":"acct-cognition","account_name":"Cognition (Devin)","domain":"cognition.ai"},{"account_slug":"acct-factory","account_name":"Factory","domain":"factory.ai"}]' \
  --target "$WORKDIR/parallel-enrichment.json" \
  --source-columns '[{"name":"account_slug","description":"Omnigraph account slug"},{"name":"account_name","description":"Company or product account name"},{"name":"domain","description":"Company domain"}]' \
  --enriched-columns '[{"name":"headcount","description":"Current employee headcount from LinkedIn or careers page"},{"name":"latest_funding_stage","description":"Most recent announced funding stage, e.g. series-b"},{"name":"latest_lead_investor","description":"Name of the lead investor on the most recent round"},{"name":"last_funding_amount_usd","description":"Amount raised in the most recent round in USD, numeric string without commas"},{"name":"primary_workload_kind","description":"One of: training, inference, sandbox, batch, eval, data-pipeline"},{"name":"estimated_annual_revenue_usd","description":"Best-available bottoms-up estimate of current annual revenue in USD"}]' \
  --processor core \
  --no-wait \
  --json
```

Poll the task group. Replace `tgrp_...` with the returned `taskgroup_id`:

```bash
TASKGROUP_ID=tgrp_...
parallel-cli enrich poll "$TASKGROUP_ID" --timeout 540 \
  --output "$WORKDIR/parallel-enrichment.json"
```

Use the launcher skill's reusable **external enrichment → graph patch** pattern for the Omnigraph-specific part. The launcher owns schema discovery, sample export, transient glue location, patch sanity checks, and merge mechanics.

Demo-specific transform intent:

- Input file: `$WORKDIR/parallel-enrichment.json`.
- Output patch: `$WORKDIR/claims-parallel-cli.jsonl`.
- Current ontology: each enriched output field becomes one `Claim`; all claims are asserted by one `ResearchRun`; each claim is linked back to its input `Account`.
- Current edge names: `AssertedClaim` from run to claim, and `AboutAccount` from claim to account.
- Suggested prompt/schema markers: `promptVersion = v5-cli`, `schemaVersion = v2`, `processor = core`.
- Suggested stable slugs: `run-<timestamp>` and `claim-<account>-<field>-v5-cli`.

For the current schema, the generated JSONL rows should look like this. Treat this as starter context, not as a substitute for launcher-led schema discovery:

```jsonl
{"type":"ResearchRun","data":{"id":"run-YYYYMMDD-HHMMSS","slug":"run-YYYYMMDD-HHMMSS","taskId":"tgrp_...","processor":"core","promptVersion":"v5-cli","schemaVersion":"v2","ranAt":"2026-04-28T11:04:24Z","createdAt":"2026-04-28T11:04:24Z"}}
{"type":"Claim","data":{"id":"claim-cognition-headcount-v5-cli","slug":"claim-cognition-headcount-v5-cli","predicate":"headcount","value":"49","confidence":"medium","reasoning":"Generated by Parallel CLI enrichment task group tgrp_...","assertedAt":"2026-04-28T11:04:24Z","createdAt":"2026-04-28T11:04:24Z"}}
{"edge":"AssertedClaim","from":"run-YYYYMMDD-HHMMSS","to":"claim-cognition-headcount-v5-cli","data":{}}
{"edge":"AboutAccount","from":"claim-cognition-headcount-v5-cli","to":"acct-cognition","data":{}}
```

Verification read after the launcher merges the generated patch:

```bash
omnigraph read --uri "http://127.0.0.1:$PORT" --alias claims-for acct-cognition
```

What just happened: each Parallel CLI output field became one `Claim` node, all wired to a single `ResearchRun` carrying `promptVersion` + `schemaVersion`, and each Claim linked back to its `Account`. The expected `claims-for` result should show new `v5-cli` claims alongside the seeded `v4` and `v3` history.

For full field-level citation provenance, use the SDK path in `demo/enrich.py` instead. It requires `PARALLEL_API_KEY`, reads `FieldBasis`, and emits `Source` plus `GroundedInSource` edges for citation URLs:

```bash
cd demo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PARALLEL_API_KEY=...
python enrich.py --accounts acct-cognition acct-factory
cd ..
omnigraph load --data demo/out/claims-run-*.jsonl --mode merge "$REPO"
```

### Swap in your own accounts

The 15 accounts in `seed.jsonl` are illustrative — `status` labels (`customer | opportunity | prospect | cold`) are chosen so the lookalike query returns a clean result, not to reflect real-world relationships. Two ways to bring your own:

- **Replace `seed.jsonl` and re-run `omnigraph load --mode overwrite`** — destructive. Confirm with the user before doing this against any non-`/tmp` repo.
- **Use the mutation aliases** (`add-account`, `add-product`, `link-builds`, `link-invests`, …) one row at a time. See `omnigraph.yaml` for the full list (~35 aliases).

Workload categories (`wlc-training`, `wlc-inference`, `wlc-sandbox`, …) are editable — change them to the user's wedge (`wlc-data-ingest`, `wlc-transform`, …) if they sell into a different stack. Same for the `Product.kind` enum.

## Teardown

```bash
kill "$(cat "$PIDFILE")" 2>/dev/null
rm -rf "$REPO" "$PIDFILE" "$LOGFILE"
```

## Domain model

**Core entities:** Account, Product, Workload, WorkloadCategory, SpendEstimate, Investor, FundingRound, TechSignal.
**Provenance layer:** ResearchRun, Claim, Source.

**Canonical traversal:** `Account → Product → Workload → SpendEstimate`. Every read about what an account is "worth" uses this path. Workload, not headcount, is the pivot.

**Claim lineage:** every Claim is asserted by exactly one ResearchRun (which carries `promptVersion` + `schemaVersion`). Claims are immutable; change is modeled as a new Claim plus a `Supersedes` edge to the old one.

## Design choices to preserve

- **Flat `kind` enum on Product** — no subtypes or interfaces.
- **Workload as a first-class node** — not a property on Account.
- **WorkloadCategory as a reference node**, not a `kind` enum on Workload — "same kind of workload" becomes a shared-node join in queries instead of a cross-variable comparison. Slug prefix: `wlc-`.
- **Investor as a first-class node** — not a string tag.
- **No CRM mirror** — no Opportunity, Stage, Activity, or Contact node types. The graph feeds CRMs; it doesn't replace them.
- **Edges follow `VerbTargetType` naming** — `BuildsProduct`, `InvestsIn`, `AssertedClaim`.
- **`slug` is external identity everywhere.** Prefixes: `acct-`, `prod-`, `wl-`, `wlc-`, `spend-`, `inv-`, `round-`, `tsig-`, `run-`, `claim-`, `src-`.
- **Source uses `url` as `@unique`** alongside `slug @key` — URLs are globally unique and the demo uses deterministic URL-derived source slugs to keep re-runs idempotent.

## When editing

- Keep `README.md` and this file in sync with `schema.pg` and the seed roster.
- If you add a new node type, make sure its `add-<name>` and link aliases exist in `omnigraph.yaml`, and that the live-enrichment transform guidance above or `demo/enrich.py` can write it if relevant.
- Don't add backwards-compat shims. Use `@rename_from(...)` for property/type renames.
- Prefer narrower types: enums over strings, Date over String, I64 over String for currency.
- Lint after every `.gq` or `schema.pg` edit:

  ```bash
  omnigraph query lint --schema ./schema.pg --query ./queries/lookalikes.gq
  ```

## Ask-the-user moments

Decision points where you should interrupt rather than guess. The first-contact branch above is one of these; here's the full list:

- **Intent ambiguous on first contact** — see "First-contact onboarding". Ask once; default to the demo branch if the answer is still vague.
- **Before live enrichment** — real $ on the user's Parallel account, minutes per account. Confirm scope (which accounts, how many).
- **Before `omnigraph load --mode overwrite` on any path that isn't `/tmp/...`** — overwrite wipes existing data. Confirm path is intended.
- **Before `omnigraph schema apply` without a successful prior `schema plan`** — destructive schema changes should not be applied unreviewed.
- **Before editing `seed.jsonl` when the user said "set this up for my own GTM"** — ask whether they want to *replace* the illustrative seed or *append* their accounts to it. The headline lookalike demo depends on the seeded `customer/prospect` labels.
- **Before any `--mode overwrite` of a graph the user has been mutating** — overwrite drops manual edits made via `change` mutations.

If you find yourself about to take one of these actions without an explicit user instruction, stop and ask.

## Repo-wide conventions

Repo-wide guidance lives in `../CLAUDE.md` — storage URI conventions, server lifecycle expectations, and the canonical workflow (lint → schema plan → schema apply → change/load). Read it when working on schema or operational questions.

## Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — Human-readable overview and ontology.
- `seed.md` / `seed.jsonl` — Illustrative roster (15 accounts, 31 investors, 2 research runs, 7 claims).
- `queries/*.gq` — Read and mutation queries.
- `omnigraph.yaml` — CLI config with ~35 aliases.
- `demo/README.md` — Parallel CLI live-enrichment walkthrough.
- `demo/enrich.py` — Parallel SDK enrichment with full FieldBasis citation provenance.
- `AGENTS.md` — This file (single source of agent context).
- `CLAUDE.md` — Pointer to this file.
