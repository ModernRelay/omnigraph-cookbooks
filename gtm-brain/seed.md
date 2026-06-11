# Seed Data — GTM Brain

`seed.jsonl` ships one realistic week of the loop, across three accounts in three different states, so every query in `queries/` returns something meaningful on first load.

## The story

| Account | Status | What happened |
|---|---|---|
| `northwind-robotics.com` | `engaged` | The hot path, end to end: funding signal + job signal clustered in one run → action verdict (score 86, `first_touch`, weighs both signals) → email touch to the VP RevOps → `replied`. |
| `lumenpay.io` | `qualified` | The patient path: one lone social signal → fit verdict (score 72, `nurture`). Qualified, not touched. The judge saying "not yet". |
| `harborline-logistics.com` | `prospect` | The pool: imported from CSV, enriched once, never judged. This is what `rank-prospects` ranks. |

Two people (`maya-chen-…` valid email, `daniel-okafor-…` unverified), three signals across three buckets, two enrichment records with `fields_updated` provenance, two verdicts (one `fit`, one `action`), one touch with an outcome.

## Loading

```bash
set -a && source ./.env.omni && set +a
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/gtm-brain
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/gtm-brain
```

`load` populates `@embed` fields (`Account.profile_embedding`, `Signal.embedding`) at ingest — set `GEMINI_API_KEY`, or `OMNIGRAPH_EMBEDDINGS_MOCK=1` to run offline without one.

## Format notes

- Node lines: `{"type":"X","data":{...}}` with `id` equal to `slug`.
- Edge lines: `{"edge":"E","from":"<src slug>","to":"<dst slug>","data":{...}}`.
- All timestamps are `DateTime` ISO strings. The schema's only `Date` fields (`WorksAt.since/until`) are intentionally omitted here — in JSONL a `Date` must be an **integer days-since-epoch**, not an ISO string (the classic silent type error; see the best-practices skill).

## What good looks like after load

```bash
omnigraph query --alias account-signals northwind-robotics.com   # 2 signals, funding + job
omnigraph query --alias account-touches northwind-robotics.com   # 1 touch, outcome=replied
omnigraph query --alias rank-prospects "B2B SaaS, outbound sales team, RevOps owner, EU"
omnigraph query --alias bucket-outcomes                          # funding/job → replied
```
