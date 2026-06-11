# GTM Brain

An Omnigraph ontology for an autonomous go-to-market loop: **sense** market signals, **remember** every account and person, **judge** who is worth a message and why now, **act** on the trigger, **learn** from what comes back — with prospecting and enrichment as first-class citizens, not afterthoughts.

Inspired by the "AI GTM Brain" pattern (signals → memory → judge → act → learn), redesigned as a graph: evidence is separated from interpretation, people exist (not just accounts), and every judgment is an auditable, queryable claim.

## The ontology (6 nodes, 7 edges)

| Layer | Node | Role |
|---|---|---|
| Universe | `Account` | keyed by domain; `status` lifecycle enum; `profile_summary` + embedding for semantic prospecting |
| Universe | `Person` | contacts with `email_status` hygiene (`unverified/valid/risky/invalid`) |
| Evidence | `Signal` | append-only market movement, `bucket: job/social/company/funding`, keyed by `source:source_ref` (idempotent re-ingest), embedded |
| Evidence | `Enrichment` | append-only "who asserted what, when" — provenance for every firmographic refresh |
| Judgment | `Verdict` | the model's claim: `kind: fit/action`, score 0–100, `play`, `why_now` quoting the trigger |
| Action | `Touch` | what was sent; `variant` records copy attribution; `outcome` folds the result in |

Edges: `WorksAt` (titled, temporal — enables champion tracking), `SignalAbout`, `EnrichmentOf`, `VerdictOn`, `Weighed` (verdict → evidence it considered), `Executes` (touch → authorizing verdict), `TouchTargets`.

**Design rules baked in:**

- **Evidence ≠ interpretation.** Signals and enrichments are immutable observations; verdicts are claims *about* them. "Why did we email them" is the traversal `Touch → Verdict → Weighed → Signal`.
- **Attribution is written from touch #1.** Variant assignment and verdict-evidence links cannot be backfilled later — they're on the write path now.
- **`Account.status` is a projection** of the latest verdict, written only by `add-verdict`. Never hand-edit it.
- **Deferred reifications as strings:** `source`, `variant`, `icp_version`, `discovered_via` are slug-disciplined strings today; promote to nodes when they grow properties (see `CLAUDE.md`).

## Quickstart

```bash
cd gtm-brain
set -a && source ./.env.omni && set +a          # RustFS creds (see repo root CLAUDE.md)
omnigraph lint --schema ./schema.pg --query ./queries/queries.gq
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/gtm-brain
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/gtm-brain
omnigraph-server --config ./omnigraph.yaml --unauthenticated   # separate terminal
```

## The loop, as aliases

| Step | Alias | What it does |
|---|---|---|
| Sense | `add-signal` | record a signal + its account link |
| Remember | `add-account`, `add-person`, `add-enrichment` | grow the universe; enrichment writes evidence + current-best values atomically |
| Judge (read) | `account-signals`, `account-touches` | the judge's full payload in two calls |
| Judge (write) | `add-verdict`, `link-weighed` | record the claim + project status; attach the evidence it weighed |
| Act | `add-touch` | record the send, bound to its verdict, target, and copy variant |
| Learn | `set-outcome`, `set-email-status`, `bucket-outcomes` | feed results back; bounced → email invalid; win rates by bucket |
| Prospect | `rank-prospects` | semantic queue: pass ICP prose, or a won account's profile for lookalike search |

```bash
omnigraph query --alias rank-prospects "B2B SaaS, outbound team, RevOps owner, EU"
omnigraph query --alias account-signals northwind-robotics.com
omnigraph mutate --alias set-outcome t:northwind-robotics.com:2026-06-05 replied 2026-06-06T10:12:00Z
```

## What the lean v1 deliberately defers

`Technology`/`Uses` edges (displacement plays), `Source` nodes (vendor trust weights), `Identifier` nodes (multi-channel identity), `MessageVariant` nodes, `ICP` nodes, an `Outcome` event node. Each has a promotion trigger documented in `CLAUDE.md`; none loses historical data by waiting — the attribution survives as string properties.
