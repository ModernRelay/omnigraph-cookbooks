# Seed: 2026 AI startup ecosystem

This seed exemplifies the focused GTM intelligence loop with **prominent real AI companies as recognizable accounts** — Anthropic, Harvey, Perplexity, Cognition (Devin), Cursor (Anysphere), Decagon, Sierra, Hippocratic AI, Suno, Together AI — plus Microsoft and GitHub as an enterprise parent/subsidiary pair, and Inflection AI's legacy commercial entity as the churned case. The seller is an unnamed AI infrastructure vendor selling into the AI-native ecosystem.

Real founders/CEOs appear with their actual names (Dario Amodei at Anthropic, Winston Weinberg at Harvey, Scott Wu at Cognition, etc.). Source artifacts, signals, VP/director roles, buying-committee assignments, opportunities, scores, and dollar amounts are **illustrative internal seed data** used to demonstrate graph shape.

## What the seed exercises

| Capability | How |
|---|---|
| **Account + technographic + hierarchy** | 13 accounts, mix of customer/prospect/churned/partner, Microsoft→GitHub parent-subsidiary, technographic edges |
| **Person + Role + career history** | 21 people across 23 roles (some current, some historical), including champions who moved from Anthropic→Cognition and Harvey→Sierra |
| **Lead resolution** | 4 leads, 3 resolved to existing People, 1 unresolved (rejected) |
| **Signals (multiple kinds)** | 12 signals: funding, hiring, job-change, leadership-change, churn, news — with provenance to artifacts |
| **Decisions (the audit spine)** | 10 decisions: classification, account scoring, qualification, advance-stage, disqualification — each with full provenance |
| **Policy versioning** | 2 ICP versions (v1 superseded by v2), a prompt-version chain (classifier v1 → v2), and a signal-priority scoring policy |
| **Actor (human + agent)** | 3 humans, 2 agents (a workload-classifier and a fit-scorer) |
| **Measurement (time-series)** | 19 measurements: intent score, predicted vs actual spend, ARR over time, headcount snapshots, funding |
| **Cohorts** | 3 cohorts: "Q2 target accounts", "AI-native mid-market watchlist", "expansion candidates" |
| **Opportunities + buying committee** | 7 opps across stages, with Champion/Buyer/Influencer assignments |
| **Engagement + Action** | A few of each, demonstrating direction asymmetry |
| **Artifacts** | 6 internal seed-note artifacts backing signals |

## The narrative threads

**Thread 1 — Workload-classifier agent at work.**
An agent (`act-agent-classifier`, running Claude Opus 4.7) runs against every new prospect account, emitting a `Decision` of `intent: classify_workload`. Each Decision is `InformedBy` recent Signals on the account, `ScreenedBy` the active classifier-prompt Policy, `MadeBy` the agent Actor, and `Targets` the Account. The Decision produces a `Measurement` of `estimated_annual_spend_usd` linked back to it via `ProducedByDecision`. Six months later, an actual usage Measurement lands from `src-internal-billing`. The graph naturally answers: *"how off were our spend predictions on accounts classified by prompt v1 vs prompt v2?"*

**Thread 2 — Champion follows the buyer.**
*Maya Chen* (a clearly fictional engineer for this seed) was the Champion on a closed-won deal at Anthropic, where she was Director of Platform Engineering. She left to take a VP Engineering role at Cognition Labs in April 2026 — exactly the kind of move that creates a warm path for the new opportunity at Cognition. Her old Role at Anthropic has `endDate: 2026-03-31` and `current: false`; her new Role at Cognition is `current: true`. The `champion-tracking` alias surfaces her immediately. A new Lead came in from Cognition (`lead-cognition-form`) and resolved to Maya's existing Person record.

*Nora Patel* is the second illustrative champion-movement example: she championed a closed-won Harvey deal, then joined Sierra as VP Customer Success. The `champion-job-change-queue` alias joins her job-change Signal, current Role, prior Opportunity, and Sierra's active ICP match into one outbound row.

**Thread 3 — ICP refinement loop.**
ICP v1 (`pol-icp-v1`) defined the ideal customer as "AI-native, 50–500 employees, post Series A." Closed-lost analysis showed funded-but-pre-revenue startups don't convert. ICP v2 (`pol-icp-v2`) tightened to "post Series B." Both Policy nodes exist; v2 `Supersedes` v1. `MatchesPolicy` edges connect each Account to whichever ICP version they fit. Decagon matches v1 only (Series A, doesn't qualify under v2 — visible via the `dec-qualify-decagon-2026-04` Decision with `ScreenedBy.outcome: failed`).

**Thread 4 — Funding signal triggers a full chain.**
Cognition's $300M Series D announcement becomes a `Signal { kind: funding, strength: strong }` linked to its source artifact (`ia-bloomberg-cognition`) and to Cognition's Account. The classifier agent runs, emits a `Decision`, which emits a `Measurement` of predicted spend ($220k, confidence 0.84). The agent also fires an `Action { operation: enrich, success: true }` that updates the Account's `tier` and adds it to the `coh-q2-targets` Cohort.

**Thread 4b — Daily priority scoring.**
The scoring agent (`act-agent-fit-scorer`) screens prospect accounts through `pol-signal-score-v1`, emits `Decision { intent: "score_account" }`, and writes `Measurement { metricKey: "intent_score" }`. `daily-priority-accounts` combines ICP fit, recent Signals, intent score, and predicted spend into the seller queue.

**Thread 5 — Predicted-vs-actual feedback loop.**
Anthropic was predicted to spend $440k annually (Measurement from January, agent-produced, confidence 0.83). End-of-Q1 actual spend from billing telemetry was $495k. The 12.5% under-prediction is now queryable via the `predicted-vs-actual` alias — exactly the kind of feedback that drives prompt-version refinement.

**Thread 6 — Enterprise via parent + subsidiary.**
Microsoft's CEO publicly committed to "AI Everywhere" on the Q2 FY26 earnings call (`sig-microsoft-ai-everywhere`). The Signal attaches to both Microsoft (parent) and GitHub (subsidiary via `ParentAccount` edge). The GitHub opportunity (`opp-github-2026`) has Priya Iyer (fictional VP Eng) as Champion, Amy Hood (Microsoft CFO, real) as Buyer because the deal needs parent-level financial approval, and Thomas Dohmke (GitHub CEO, real) as Influencer.

## Files

- `seed.jsonl` — Loadable JSONL with all nodes and edges
- This document — human-readable narrative

## Loading

```bash
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/revops
```

## After loading

```bash
omnigraph read --alias pipeline
omnigraph read --alias daily-priority-accounts 2026-01-01T00:00:00Z pol-icp-v2
omnigraph read --alias account-priority-detail acc-cognition 2026-01-01T00:00:00Z
omnigraph read --alias funding-feed 2026-01-01T00:00:00Z
omnigraph read --alias champion-job-change-queue 2026-01-01T00:00:00Z pol-icp-v2
omnigraph read --alias decision-trace dec-classify-cognition-2026-04
omnigraph read --alias decision-lineage dec-classify-cognition-2026-04
omnigraph read --alias prompt-governance pol-signal-score-v1
omnigraph read --alias predicted-vs-actual 2026-01-01T00:00:00Z
omnigraph read --alias policy-history icp.ai_native_mid_market
omnigraph read --alias cohort-top-targets coh-q2-targets
```

## Note on real-vs-illustrative

CEO/founder names and company names are used for verisimilitude. Internal source artifacts, signals, roles below the CEO level (VPs, Directors), buying-committee assignments (champion, blocker, etc.), and the dollar amounts of opportunities, scores, and predicted spend are illustrative examples of what the schema can express.
