# VC OS - A venture-capital operating system as a knowledge graph

Opinionated Omnigraph cookbook for venture-capital firms. Built on [Omnigraph](https://github.com/ModernRelay/omnigraph), shaped from a first-principles teardown of how a token-maxxing VC should work. Covers pipeline, diligence, decisions, portfolio, network, audit, and learning - all in one typed graph.

## Why a graph, not another tool

A modern VC's stack typically contains 8–12 systems: a CRM (Affinity / Airtable ), a wiki (Notion), chat (Slack), a call-recording tool (Granola), spreadsheets and drives (Drive / Excel), portfolio modeling (Tactyc), an outbound platform (Lemlist), and per-firm bespoke hacks - a sightings / prospect databases enriched via Spectre/Harmonic, a third-party vector store for semantic search, local notes for firm memory, a cross-session memory daemon, a homegrown audit log.

Each store solved one problem at one moment. None of them talk to each other natively. Agents end up plumbing the gaps: brittle point-to-point integrations, slow queries and high token usage, scattered audit trail, no shared definitions. Adding automations makes the system more fragile rather than compouding.

With Omnigraph's native capabilities - typed schema + typed mutations, native blobs, hybrid search (vector + BM25 + RRF + FTS) in one runtime, git-style branches/commits, snapshot-pinned reads, policy-as-code - most of that per-firm bespoke storage collapses inward.

## From first principles

A firm is in the business of maintaining a **structured, dated, contradictable set of beliefs** about organizations, founders, and markets - and acting on them.

Every action either:
- **generates** a belief (scout finding, founder call, research brief)
- **updates** a belief (a new signal supports or contradicts an assumption)
- **acts on** a belief (decision, intro, board flag, follow-on)
- **records** the act (memo, log, comment)

The seven jobs a VC does - **Find, Evaluate, Decide, Win, Help, Monitor, Learn** - all collapse into one analytical loop over beliefs. The ontology is shaped to make that loop a 2-hop graph traversal.

## The schema - 7 core + 10 growth-ring

The core is the entities the team can hold in their head, stable for years even as the analytical layer above them compounds. The schema is organized accordingly.

### Core entities (7)

| Node | Purpose |
|---|---|
| **`Organization`** | Any real-world business entity |
| **`Person`** | An individual human. Roles live on edges, not on the node - `WorksAt org-quito` (team), `FounderOf co-x` (founder), `RoleInDeal {role: expert}` (expert). |
| **`Deal`** | A funding event involving an Organization. |
| **`Fund`** | The firm's funds. |
| **`Market`** | Sector/vertical hub. Sector-specialist Theses, Patterns, and Lessons cluster around it. |
| **`Artifact`** | Raw content with native `Blob` - Granola transcripts, pitch decks, emails, screenshots, chat messages, markdown wiki pages.  |
| **`Meeting`** | A scheduled (or ad-hoc) event with attendees, subject, and outputs. The transcript is an `Artifact`; the Meeting binds attendees + agenda + outcomes (Decisions, Commitments) around it. Covers IC, board, founder calls, partner offsites, pipeline reviews, expert calls. |

### Analytical layer

Built on top of the core. These can be added to or refined without touching the core.

| Layer | Nodes | Purpose |
|---|---|---|
| Belief | `Thesis` · `Assumption` · `Question` | The value layer (investing DNA). `Question` is the home for open uncertainties - not `Insight{kind=hypothesis}`. |
| Evidence | `Signal` · `Insight` · `Chunk` | What moves beliefs. `Chunk` is implementation detail for hybrid search. |
| Action | `Decision` · `Commitment` | What we do. `Decision` is one-shot (`decided_at`); `Commitment` is deferred-action with a deadline. Intros, follow-ups, *schedule-another-meeting*, and *flag-at-next-board* are `Commitment`s, not `Decision`s. |
| Reflexive | `Pattern` · `Lesson` | What we learn. `Pattern` aggregates across many subjects; `Insight` interprets one. `Lesson` is operational (changes future behavior); `Insight` is descriptive. |

**17 node types total** (`Chunk` should be populated via `omnigraph embed --reembed_all`). Source-provenance entities (TechCrunch, PitchBook, Tegus, anon blog) live as `Organization` rows with `kind` in `(publisher, database, expert-network)` and a `reliability` rating - no separate `SourceEntity` node.

Slug prefixes: `org- per- mkt- deal- fund- art- mtg- thesis- asmp- q- sig- ins- chk- dec- cmt- pat- lsn-`.

### The ontology at a glance

Every node type appears exactly once. Each row lists a node and where its outgoing edges go (with the edge verb in parens). Layers stacked from operational rules at the top to the engagement substrate at the bottom; flow between layers labelled on the connectors.

```
   ┌─── REFLEXIVE (what we learn) ─────────────────────────────────────────────┐
   │  Pattern  → Decision (acrossDecision), Signal (acrossSignal),             │
   │            Organization (acrossOrganization)                              │
   │  Lesson   → Pattern (distilledFromPattern), Market (appliesToMarket)      │
   └───────────────────────────────────────────────────────────────────────────┘
              ▲ patternAcrossDecision  (Pattern aggregates Decisions, Signals, Orgs)
              │ distilledFromPattern  (Lesson refines Pattern)
   ┌─── ACTION (what we do) ───────────────────────────────────────────────────┐
   │  Decision   → Deal/Thesis (regarding), Assumption (basedOn),              │
   │              Question (needsAnswer), Person (byPerson), Meeting (from)    │
   │  Commitment → Person (forPerson, assignedTo), Deal (regarding),           │
   │              Artifact (from), Meeting (from)                              │
   └───────────────────────────────────────────────────────────────────────────┘
              ▲ decisionBasedOnAssumption / decisionRegardingThesis
              │ decisionNeedsAnswer  (Decisions rest on the belief state)
   ┌─── BELIEF (investing DNA) ────────────────────────────────────────────────┐
   │  Thesis     → Assumption (reliesOnAssumption), Market (aboutMarket),      │
   │              Organization (aboutOrganization)                             │
   │  Assumption [leaf - receives reliesOn, supports/contradicts, basedOn]     │
   │  Question   → Deal (questionAboutDeal)                                    │
   └───────────────────────────────────────────────────────────────────────────┘
              ▲ supportsThesis | contradictsThesis  (Signals move beliefs)
              │ supportsAssumption | contradictsAssumption | informsQuestion
   ┌─── EVIDENCE (what moves beliefs) ─────────────────────────────────────────┐
   │  Signal   → Thesis (supports/contradicts), Assumption (supports/contra),  │
   │             Question (informs), Org/Person/Market/Deal (signalAbout*),    │
   │             Artifact (sourcedFromArtifact)                                │
   │  Insight  → Signal (reliesOnSignal), Pattern (highlightsPattern),         │
   │             Deal/Org/Person (insightAbout*)                               │
   │  Chunk    → Artifact (chunkOf)                [zero rows in v1 seed]      │
   └───────────────────────────────────────────────────────────────────────────┘
              ▲ signalAboutOrganization | signalAboutPerson | signalAboutDeal
              │ artifactAboutDeal | publishedByOrganization | documentsThesis
   ┌─── CORE (engagement, the CRM grain) ──────────────────────────────────────┐
   │  Fund         [leaf - receives FromFund + LpInFund]                       │
   │  Deal         → Fund (fromFund), Organization (forOrganization,           │
   │                 leadInvestor, participantInvestor), Person (ledByPerson), │
   │                 Thesis (relevantThesis), Market (relevantMarket)          │
   │  Organization → Market (organizationInMarket), Organization (wouldAcquire │
   │                 - self), Fund (lpInFund, when kind=lp-institution|        │
   │                 family-office)                                            │
   │  Person       → Deal (roleInDeal), Organization (worksAt, founderOf,      │
   │                 boardMemberAt, decisionMakerAt), Person (knows - self,    │
   │                 bidirectional)                                            │
   │  Market       [leaf]                                                      │
   │  Artifact     → Organization (publishedByOrganization,                    │
   │                 artifactAboutOrganization), Deal (artifactAboutDeal),     │
   │                 Person (fromPerson, mentionsPerson), Artifact             │
   │                 (derivedFrom - self), Thesis/Lesson/Pattern (documents),  │
   │                 Meeting (fromMeeting)                                     │
   │  Meeting      → Deal/Organization/Thesis/Market (meetingAbout*),          │
   │                 Person (attendedBy {role})                                │
   └───────────────────────────────────────────────────────────────────────────┘
```

17 node types · 67 edge types declared · 65 populated in the v1 seed. The five query loops (Engagement / Belief+Evidence / Decision / Reflexive / Operational) are the five layers above.

### Key enums (the lens)

| Enum | Values |
|---|---|
| `Organization.kind` | `startup, lp-institution, vc-firm, acquirer, customer, bank, regulator, association, accelerator, university, family-office, publisher, database, expert-network, other` |
| `Organization.status` | `cold, watching, pipeline, evaluating, portfolio, exited, passed, observed` - nullable for non-startup kinds |
| `Organization.reliability` | `low, medium, high` - meaningful for `kind` in (publisher, database, expert-network); null elsewhere |
| `Deal.stage` | `sourced, qualified, in-diligence, ic-ready, decided, closed, dead` |
| `Deal.outcome` | `open, invested, passed, lost, withdrawn, observed` (`observed` = external round we tracked but didn't engage with) |
| `Decision.kind` | `invest, pass, follow-on, double-down, write-off, exit-plan, no-decision` (intros, follow-ups, schedule-another-meeting, flag-at-next-board are `Commitment`s) |
| `Assumption.level` | `market, founder, product, competitive, financial, strategic` |
| `Question.status` | `open, partial, resolved` |
| `Signal.kind` | `discovery, launch, fundraise, exit, founder-event, market-move, competitive, customer, regulatory, team-change, portfolio-update, board-decision` |
| `Insight.kind` | `memo, brief, observation, recap` - open uncertainties live on `Question`, not here |
| `Insight.stance` | `bull, bear, neutral` |
| `Artifact.kind` | `email, ticket, chat-msg, meeting-note, transcript, deck, web-page, screenshot, doc, audio, image, summary, markdown` |
| `Artifact.source` | `email, chat, meeting-tool, web, doc-tool, crm, outbound, manual, derived, repo, other` - coarse category, vendor name in `source_app` |
| `Pattern.kind` | `gtm, pricing, founder-archetype, market-timing, exit, failure-mode, tech-adoption, capital-structure, regulatory` |
| `Lesson.kind` | `protocol, rule-of-thumb, anti-pattern, runbook` |
| `Lesson.status` | `tentative, active, retired` - `tentative` lives on a review branch awaiting human merge |
| `Thesis.status` | `active, retired, contradicted` |
| `Meeting.kind` | `ic, board, partner-1on1, pipeline-review, portfolio-1on1, lp-update, founder-call, dd-call, expert-call, internal, external-other` |
| `Meeting.status` | `scheduled, occurred, cancelled, rescheduled` |

## Reference seed data - Fictional Series-A AI-infra fund

The seed populates a fictional Berlin-based AI-infra fund running Fund III ($250M, vintage 2024). Single coherent narrative; exercises all 16 populated node types (`Chunk` is schema-only). **All names, deals, organizations, and people are fabricated.**

| Layer | Count | Includes |
|---|---|---|
| Funds | 2 | Fund II (harvesting), Fund III (investing) |
| Theses | 8 | Vertical AI infra, on-prem inference, agentic CRMs, data-quality moats, etc. |
| Pipeline organizations | 12 | 6 in evaluation, 6 in pipeline |
| Portfolio organizations | 5 | Mix of Series A and B holdings |
| Markets | 6 | AI infra, AI applications, dev tools, vertical SaaS, security, data |
| People | ~25 | 5 team, ~10 founders, 4 LPs, 3 experts, 3 acquirer-DMs, plus 2 venture partners |
| Non-startup Companies | ~14 | Acquirers (hyperscalers, strategic), LP institutions, peer VCs, accelerators, plus 4 source orgs (TechCrunch / PitchBook / Tegus / anon blog) |
| Signals | ~30 | Mix of competitive, fundraise, portfolio-update, market-move |
| Decisions | 6 | invest, pass (×3), follow-on, thesis-level double-down (intros + follow-up actions are Commitments, not Decisions) |
| Patterns / Lessons | 5 / 4 | AI-infra-specific |
| Meetings | 8 | 2 ICs (Axon occurred, Helix upcoming), 2 Aetherbrick boards (Q1 occurred, Q2 upcoming), Helix founder call, Axon expert ref call, partner thesis-review offsite, weekly pipeline |

**Totals (loaded):** 207 nodes across 16 active types, 460 edges across 65 edge types. `Chunk` is schema-only (zero seeded). Bidirectional `Knows` accounts for 28 of those edges (14 unique pairs × 2).

## Example queries - with live output

The seed is shaped to light these up. Each is a single graph traversal that would otherwise require hand-stitching across 4+ systems. Output below is verbatim from `omnigraph read --alias <name> [args]` against the loaded seed.

### Pre-IC brief for a deal

```bash
omnigraph read --alias pre-ic-brief-thesis    deal-helix-series-a
omnigraph read --alias pre-ic-brief-evidence  deal-helix-series-a
omnigraph read --alias pre-ic-brief-questions deal-helix-series-a
omnigraph read --alias debate-stances         deal-helix-series-a
```

**`pre-ic-brief-thesis`** - relevant thesis + grounding assumptions:
```
t.slug                   | t.name                                     | a.slug                            | a.level   | a.confidence
-------------------------+--------------------------------------------+-----------------------------------+-----------+-------------
thesis-on-prem-inference | On-prem inference for regulated industries | asmp-data-sovereignty-mandates    | strategic | high
thesis-on-prem-inference | On-prem inference for regulated industries | asmp-inference-cost-parity-onprem | financial | medium
thesis-on-prem-inference | On-prem inference for regulated industries | asmp-helix-onprem-margin          | financial | medium
```

**`pre-ic-brief-evidence`** - signals contradicting those assumptions:
```
a.slug                            | s.slug                    | s.kind      | s.date     | s.brief
----------------------------------+---------------------------+-------------+------------+--------
asmp-inference-cost-parity-onprem | sig-aws-bedrock-onprem    | competitive | 2026-03-04 | AWS Bedrock on-prem appliance announced…
asmp-helix-onprem-margin          | sig-aws-bedrock-onprem    | competitive | 2026-03-04 | (same)
asmp-helix-onprem-margin          | sig-microsoft-onprem-push | market-move | 2026-01-28 | Microsoft on-prem GPU SKUs for regulated…
```

**`pre-ic-brief-questions`** - open uncertainties:
```
q.slug                | q.priority | q.description
----------------------+------------+--------------
q-helix-onprem-margin | high       | AWS Bedrock now offers on-prem appliances. Does Helix's margin profile hold?
```

**`debate-stances`** - bull + bear Insights grounded in real Signals:
```
i.slug         | i.kind | i.stance | i.summary
---------------+--------+----------+----------
ins-helix-bull | memo   | bull     | Helix is the right team at the right time for the on-prem inference wave…
ins-helix-bear | memo   | bear     | AWS Bedrock on-prem appliance launched in March. Hyperscalers will undercut…
```

### Post-signal portfolio impact

```bash
omnigraph read --alias signal-portfolio-impact sig-vector-forge-aws-deal
```

Walks `Signal → contradicts → Assumption → basedOn(inv) → Decision → regarding → Deal → forOrganization(status=portfolio)`. A new external signal arrives - which committed portfolio decisions just got destabilized?

```
c.slug          | c.name      | dec.slug                       | dec.kind  | a.name
----------------+-------------+--------------------------------+-----------+-------
org-aetherbrick | Aetherbrick | dec-aetherbrick-follow-on-eval | follow-on | Vertical data asymmetry compounds
```

### Exit landscape for a portfolio organization

```bash
omnigraph read --alias exit-landscape                  org-pinion-infer
omnigraph read --alias exit-landscape-decision-makers  org-pinion-infer
```

**`exit-landscape`** - plausible acquirers:
```
o.slug           | o.name       | o.kind   | o.brief
-----------------+--------------+----------+--------
org-aws          | AWS          | acquirer | Hyperscaler. Acquires infra startups for Bedrock + agent stack.
org-microsoft    | Microsoft    | acquirer | Hyperscaler. Active AI-infra M&A.
org-google-cloud | Google Cloud | acquirer | Hyperscaler. Vertex AI ecosystem acquisitions.
```

**`exit-landscape-decision-makers`** - corp-dev contacts at each:
```
o.slug        | o.name    | p.slug                  | p.name
--------------+-----------+-------------------------+-------
org-aws       | AWS       | per-acq-aws-rajiv       | Rajiv Krishnan
org-microsoft | Microsoft | per-acq-microsoft-priti | Priti Joshi
```

### Board-prep pack

```bash
omnigraph read --alias board-prep-pack                  org-aetherbrick
omnigraph read --alias board-prep-open-questions        org-aetherbrick
omnigraph read --alias board-prep-commitments           org-aetherbrick
omnigraph read --alias board-prep-meeting-history       org-aetherbrick   # prior board meetings
omnigraph read --alias board-prep-next-meeting          org-aetherbrick   # scheduled next board
```

**`board-prep-pack`** - recent signals since last board:
```
s.slug                        | s.name                                     | s.date     | s.brief
------------------------------+--------------------------------------------+------------+--------
sig-aetherbrick-series-b-talk | Aetherbrick - early Series B conversations | 2026-04-22 | CEO begins early Series B talks. Sequoia EU likely to lead.
sig-aetherbrick-churn-spike   | Aetherbrick - Q1 churn spike (8.3%)        | 2026-04-07 | Q1 gross churn 8.3% (vs 4.5% Q4). Three mid-market logos lost…
```

**`board-prep-commitments`** - what's owed before the next board:
```
cmt.slug                   | cmt.name                     | cmt.status | cmt.due_date | cmt.detail
---------------------------+------------------------------+------------+--------------+-----------
cmt-aetherbrick-board-prep | Aetherbrick - board prep doc | open       | 2026-06-08   | Compile board prep covering churn analysis + Series B follow-on framework.
```

**`board-prep-next-meeting`** - when the next board is:
```
m.slug                        | m.name                      | m.scheduled_at           | m.location | m.summary
------------------------------+-----------------------------+--------------------------+------------+----------
mtg-aetherbrick-board-q2-2026 | Aetherbrick - Q2 2026 board | 2026-07-09T15:00:00.000Z | Berlin HQ  | Next board. Churn cohort follow-up + Series B framework decision expected.
```

### Meeting history with a deal or organization

```bash
omnigraph read --alias meetings-with-deal               deal-helix-series-a
omnigraph read --alias ic-prep-meeting-history          deal-helix-series-a
omnigraph read --alias ic-prep-open-commitments         deal-helix-series-a
```

**`ic-prep-open-commitments`** - what's still owed before Helix IC:
```
cmt.slug                 | cmt.name                           | cmt.priority | cmt.due_date | cmt.detail
-------------------------+------------------------------------+--------------+--------------+-----------
cmt-helix-second-meeting | Helix - schedule second meeting    | normal       | 2026-04-25   | On-prem mandate validated but need to test margin assumption…
cmt-helix-customer-refs  | Helix - 3 customer reference calls | high         | 2026-06-15   | Schedule and complete 3 customer reference calls before Helix IC.
```

### Intro path to a founder

```bash
omnigraph read --alias direct-team-knowers     per-helix-elena   # 1-hop
omnigraph read --alias intro-path-to-founder   per-helix-yuki    # 2-hop via bridge
```

**`direct-team-knowers per-helix-elena`** - who on the firm already knows her:
```
teammate.slug | teammate.name
--------------+--------------
per-pawel     | Pawel Nowak
```

**`intro-path-to-founder per-helix-yuki`** - 2-hop bridge:
```
teammate.slug | teammate.name | bridge.slug          | bridge.name
--------------+---------------+----------------------+------------
per-cj        | CJ Müller     | per-aetherbrick-jens | Jens Mueller
```

CJ → Jens (Aetherbrick founder + Quito portfolio board member) → Yuki. The same Knows graph that resolves direct intros also resolves bridge intros.

### Contradicted theses

```bash
omnigraph read --alias contradicted-active-theses
```
```
t.slug                   | t.name                                     | t.confidence | s.slug                         | s.date     | s.brief
-------------------------+--------------------------------------------+--------------+--------------------------------+------------+--------
thesis-on-prem-inference | On-prem inference for regulated industries | high         | sig-aws-bedrock-onprem         | 2026-03-04 | AWS Bedrock on-prem appliance…
thesis-agentic-crms      | Agent-first CRMs displace per-seat SaaS    | medium       | sig-pulserate-pass-vindication | 2026-02-12 | PulseRate Series A undersubscribed…
```

Run weekly to catch belief drift before a quarterly review.

### Reserve pressure check

```bash
omnigraph read --alias reserve-pressure fund-iii
```
```
c.slug           | d.slug               | q.slug                 | q.name                                          | q.description
-----------------+----------------------+------------------------+-------------------------------------------------+--------------
org-pinion-infer | deal-pinion-series-a | q-pinion-defensibility | How defensible is Pinion's orchestration layer? | Pinion's wedge is orchestration across on-prem and cloud…
```

Tactyc says *how much* dry powder; the graph says *which organizations are about to need it*.

### Source-reliability revalidation

```bash
omnigraph read --alias publishers                                # TechCrunch, anon blog
omnigraph read --alias databases                                 # PitchBook
omnigraph read --alias expert-networks                           # Tegus
omnigraph read --alias sources-by-reliability low                # who to flag
omnigraph read --alias source-downstream-signals org-techcrunch  # what to revalidate
```

**`publishers`**:
```
o.slug         | o.name              | o.reliability | o.brief
---------------+---------------------+---------------+--------
org-anonblog   | Anonymous tech blog | low           | Pseudonymous blog. Mixed track record. Flag downstream signals for review.
org-techcrunch | TechCrunch          | medium        | Press releases + breaking news. Reliable on facts; commentary low signal.
```

**`source-downstream-signals org-techcrunch`** - if TechCrunch's reliability drops, these signals need revalidation:
```
sig.slug                  | sig.name                                   | sig.kind    | sig.date   | sig.impact
--------------------------+--------------------------------------------+-------------+------------+-----------
sig-eu-ai-act-enforcement | EU AI Act - first major enforcement action | regulatory  | 2026-04-15 | high
sig-aws-bedrock-onprem    | AWS Bedrock launches on-prem appliance     | competitive | 2026-03-04 | high
sig-databricks-acquihire  | Databricks acquires eval startup           | exit        | 2026-02-10 | high
sig-microsoft-onprem-push | Microsoft expands Azure on-prem AI         | market-move | 2026-01-28 | normal
```

That walk - `Organization{reliability=low/medium} ← publishedByOrganization ← Artifact ← signalSourcedFromArtifact ← Signal` - is what justifies collapsing the old `SourceEntity` node into `Organization`. The provenance traversal is identical; one less node type to learn.

### Active lessons (firm protocols)

```bash
omnigraph read --alias lessons-active
```
```
l.slug                         | l.name                                                            | l.kind        | l.confidence
-------------------------------+-------------------------------------------------------------------+---------------+-------------
lsn-onprem-validation-protocol | On-prem demand validation protocol                                | protocol      | high
lsn-shell-anti-pattern         | Pass on vertical-SaaS-with-AI-shell deals absent product-led pull | anti-pattern  | high
lsn-vertical-data-moat-eval    | Score vertical data moat with 5 customer interviews               | rule-of-thumb | high
```

### Team + recent decisions

```bash
omnigraph read --alias team
omnigraph read --alias decisions-recent
```

**`team`** - 5 partners + 2 VPs, all derived from `WorksAt org-quito`:
```
p.slug       | p.name          | p.email               | p.location
-------------+-----------------+-----------------------+-----------
per-cj       | CJ Müller       | cj@quito.example      | Berlin
per-flo      | Florence Yamada | flo@quito.example     | London
per-louis    | Louis Tremblay  | louis@quito.example   | Paris
per-vp-noah  | Noah Adler      | null                  | Berlin
per-pawel    | Pawel Nowak     | pawel@quito.example   | Berlin
per-ricardo  | Ricardo Silva   | ricardo@quito.example | Berlin
per-vp-tegan | Tegan O'Brien   | null                  | Cambridge
```

**`decisions-recent`** - 6 actual Decisions in the seed (no schedule-a-meeting or board-flag entries - those are Commitments):
```
dec.slug                       | dec.name                                  | dec.kind    | dec.decided_at
-------------------------------+-------------------------------------------+-------------+---------------
dec-axon-ic-recommend-invest   | Axon Eval - IC recommend invest           | invest      | 2026-05-12
dec-aetherbrick-follow-on-eval | Aetherbrick - evaluate Series B follow-on | follow-on   | 2026-04-22
dec-onprem-thesis-doubledown   | Double down on on-prem-inference thesis   | double-down | 2026-04-20
dec-vector-forge-pass          | Pass on Vector Forge seed                 | pass        | 2026-01-22
dec-stratopaint-pass           | Pass on Stratopaint seed                  | pass        | 2025-11-15
dec-pulserate-pass             | Pass on PulseRate Series A                | pass        | 2025-08-04
```

## How branches + commits replace audit + tentative-review

**Tentative Lessons - branch-based review.** An agent notices a recurring pattern in three closed deals → creates a `Lesson{kind=rule-of-thumb, status=tentative}` on a branch named `tentative/<date>`. Human reviews with `omnigraph branch diff`; merges if good, deletes if not. The branch *is* the review process.

**Decision counterfactuals.** A `Decision` committed to main is snapshot-pinned to the exact `Assumption`/`Signal`/`Question` state at the moment of decision. Six months later: "what would we have decided if we'd known X?" - branch from the decision's commit, mutate one Assumption, re-run the pre-IC brief query. The diff is the counterfactual.

## Example agent workflows

Five patterns the graph shape uniquely enables. The common shape: **agent proposes on a branch, partner reviews via `branch diff`, merges into `main`**. Each is invocable from `claude -p ...` (or any agent runtime) against the local omnigraph server.

For each agent below: the natural-language **prompt** you'd send it, concrete **pulls** (graph reads it makes) and **writes** (graph mutations it lands on a `tentative/…` branch). Only the first two also consume external data (a transcript or a scout note); the other three are pure graph composition.

### 1. Post-call ingestion · every 10 min (cron)

**Prompt:**
> Fetch new Granola transcripts since `sync-state.granola.last_synced_at`. For each: create the Artifact, resolve mentioned people/orgs (don't fabricate - flag unresolved), derive material Signals tied to the deal's existing Theses/Assumptions, extract action items as Commitments with assignee + due. One branch per meeting, `tentative/ingest-<meeting-slug>`. Update the cursor.

**External:** Granola REST.

**Pulls (per transcript):** the Meeting + attendees · the deal's thesis + grounding assumptions · the deal's open questions · prior similar Signals (so the new one is differentiated, not duplicate).

**Writes (per transcript, on its own branch):** the transcript as an Artifact (source `meeting-tool`, app `granola`) · 0–3 Signals each tied as `supports`/`contradicts` against the right Assumption · 0–N Commitments with assignee + `fromMeeting` back-edge + due-date.

**Why graph:** the Artifact, derived Signals, and extracted Commitments land as one atomic branch - a partial failure in one mutation rolls back the whole call's ingest, no orphan signals.

### 2. Scout-pick triage · daily 08:00 (cron)

**Prompt:**
> For each new external mention since yesterday's run (HN top launches, scout-list inbox, Twitter watches, founder DMs): triage per `Organization.status`. New → create on a tentative branch, enrich with market hub + links to relevant Patterns/Lessons + any open question this is data for. Resurface → tie to the prior pass Decision. Don't fabricate founder names. Respect the daily cap (Cedar policy on `add-signal{kind=discovery}`). Output: digest with one branch per pick.

**External:** HN launches feed · scout-list email inbox · Twitter `@`/keyword watches · founder DM channels.

**Pulls (per mention):** `search-organizations` for the dedup verdict · prior pass Decision if any name-match has `status=passed` · the firm's active Lessons + failure-mode Patterns in the candidate's Market · any open Question this mention is fresh evidence for.

**Writes (per genuinely-new pick, on `tentative/scout-<org>-<date>`):** Organization (`status=watching`, sector hub linked) · discovery Signal · the source mention as a provenance Artifact (`sourcedFromArtifact`) · `informsQuestion` to any live re-evaluation question · neutral Insight if a known anti-pattern matches, citing the Pattern.

**Why graph:** verdict is a structural property of `status` (no policy tree); prior-pass and accumulated lessons surface for free because they're already attached to the candidate's Market and Pattern.

### 3. Pre-X brief · calendar webhook 24h before any IC / board / founder call / 1:1

**Prompt:**
> A meeting is on the calendar in 24h. Look up its kind (IC / board / founder call / partner 1:1 / LP update) and subject (Deal / Org / Thesis / Person). Build the brief that fits: IC → thesis + supporting/contradicting evidence + open questions + bull/bear stances + prior meetings + outstanding commitments + a recommendation. Board → recent signals + open questions + commitments owed since last board + next board cadence. Founder call → person profile + intro path + relevant deals + prior conversations. Cite real evidence; end with the action recommendation the meeting type expects.

**External:** the calendar invite that triggered the webhook (kind + subject + attendees).

**Pulls (IC variant):** deal terms + lead partner · grounding Thesis + Assumptions with confidence · `supports/contradicts` Signals per Assumption (the asymmetry surfaces here) · open Questions by priority · existing bull/bear Insights and which Signals each cites · prior Meetings with attendee + summary · still-open Commitments with due dates.

**Writes:** None - output is the synthesized brief returned via the channel that triggered it.

**Why graph:** ~8 reads against one commit-pinned snapshot; re-runnable at the same commit ID six months later for counterfactual diligence reviews. Asymmetries like "bull defends demand pillar, bear attacks margin pillar" surface mechanically from counting which Assumptions each side's signals attack - not from clever synthesis.

### 4. Multi-agent IC simulation · calendar webhook 48h before a high-conviction IC

**Prompt** (one per agent - bull / bear / neutral fork):
> An IC is in 48h. You are the {bull | bear | neutral} agent. Read the deal's Thesis + Assumptions + recent Signals + related Patterns. Pick the evidence that genuinely supports your stance - overlap with the other agents is expected, that's the point. Write one `Insight{stance=…}` with `add-insight-with-stance` on the shared debate branch, citing Signals via `InsightReliesOnSignal` and any Pattern via `InsightHighlightsPattern`. Don't invent. Neutral agent: name what new evidence would resolve the disagreement.

**External:** the calendar invite for the IC.

**Pulls (each agent):** the Org / Deal / Thesis state · all Signals about the relevant Market · the Org's own recent Signals · the Patterns that aggregate this deal with others · existing Insights so framings aren't duplicated.

**Writes (one Insight per agent, all on a shared `tentative/ic-debate-<deal>` branch):** Insight with stance + summary + body · `InsightAboutDeal` · `InsightReliesOnSignal` per cited Signal · `InsightHighlightsPattern` if a market-shape Pattern is load-bearing.

**Why graph:** bull and bear linking the *same* Pattern with opposite framings makes the disagreement structurally legible. Partner can audit "are they arguing about different evidence, or interpreting the same evidence oppositely?" at a glance - not from re-reading two essays.

### 5. Reflexive learning sweep · quarterly (cron)

**Prompt:**
> Sweep the last quarter's Decisions, active Patterns, and existing Lessons. For any Pattern with ≥3 supporting Decisions and consistent outcome (all-pass / all-invest / all-write-off / all-double-down) that isn't already covered by an active Lesson, propose a tentative Lesson on its own branch, citing the Pattern and the Market it applies to. Output a digest: what landed, what was already covered, where evidence is too thin.

**External:** None.

**Pulls:** Decisions in the 90d window with outcomes · Patterns with their `acrossDecision` aggregations · active Lessons (`distilledFromPattern` already covering this?).

**Writes (only when a Pattern qualifies and isn't already covered):** `Lesson{status=tentative}` with body + `DistilledFromPattern` + `AppliesToMarket`.

**Why graph:** `Pattern.acrossDecision` aggregation makes "this shape recurred N times with consistent outcome" a deterministic query, not a vibes call. The duplicate-check against active Lessons is the same primitive - a sweep that always produces a Lesson would be a hallucinating sweep.

## v1 scope

**Ships:**
- Full 17-node schema with native `Blob` on `Artifact` and `Vector(3072) @embed("text")` on `Chunk`
- Reference seed: 207 nodes, 460 edges across 65 edge types, no embeddings, no blob payloads
- 294 aliases covering reads + mutations for every node/edge type (289 named queries across 12 `.gq` files)
- Example queries enumerated above

**Deferred (extensions, not blockers):**
- **Real blob + embedding examples in seed.** Schema declares the capability. Attach real PDFs/transcripts as `Artifact.blob`, populate `Chunk` rows, then `omnigraph embed --reembed_all` followed by hybrid queries combining `nearest()` / `bm25()` / `rrf()` with graph traversal.
- **Cedar policies** (`policies/`) - per-role access control (team / lp / read-only-portfolio) collapses application-layer permission code into the graph server.
- **Sector-specialist Pattern/Lesson packs.** AI-infra Patterns ship with the reference seed; talent-tech / climate / B2B-SaaS variants are sibling cookbooks.
- **`Measurement` node** for time-series KPIs/cash/runway (currently captured loosely via `Signal{kind=portfolio-update}`).

## Files

```
vc-os/
├── README.md          # this file
├── CLAUDE.md          # scoped agent guidance
├── schema.pg          # 17 nodes, ~62 edges, ~19 enums - source of truth
├── seed.md            # human-readable narrative (twin of seed.jsonl)
├── seed.jsonl         # loadable seed
├── omnigraph.yaml     # CLI config + 294 aliases
└── queries/
    ├── beliefs.gq        # 23 reads
    ├── deals.gq          # 20 reads
    ├── decisions.gq      # 15 reads
    ├── meetings.gq       # 23 reads (incl. IC + board prep + meeting history)
    ├── mutations.gq      # 86 mutations (add_* + link_*)
    ├── organizations.gq  # 28 reads (incl. exit-landscape + co-investor)
    ├── patterns.gq       # 15 reads
    ├── people.gq         # 22 reads
    ├── portfolio.gq      # 17 reads
    ├── signals.gq        # 17 reads
    ├── sources.gq        # 9 reads (provenance via Organization{kind=publisher|database|expert-network} + reliability)
    └── wiki.gq           # 14 reads (markdown artifacts pinned to git commits)
```

Total: 289 named queries, 294 aliases.

## Quick Start

All commands run from `vc-os/`:

```bash
cd vc-os

# 1. Bring up RustFS via Docker (one-time)
docker run -d --name omnigraph-rustfs-vcos \
  -p 127.0.0.1:9000:9000 -p 127.0.0.1:9001:9001 \
  -e RUSTFS_ACCESS_KEY=rustfsadmin -e RUSTFS_SECRET_KEY=rustfsadmin \
  -e RUSTFS_VOLUMES=/data \
  -e RUSTFS_ALLOW_INSECURE_DEFAULT_CREDENTIALS=true \
  -e RUSTFS_ADDRESS=0.0.0.0:9000 -e RUSTFS_CONSOLE_ADDRESS=0.0.0.0:9001 \
  -v /tmp/rustfs-vcos:/data \
  rustfs/rustfs:1.0.0-beta.4   # pinned: ':latest' floats; beta.4 is the image RUSTFS_ALLOW_INSECURE_DEFAULT_CREDENTIALS targets

# 2. Create .env.omni (these are the local RustFS dev creds; .env.omni is gitignored)
cat > .env.omni <<'EOF'
AWS_ACCESS_KEY_ID=rustfsadmin
AWS_SECRET_ACCESS_KEY=rustfsadmin
AWS_REGION=us-east-1
AWS_ENDPOINT_URL=http://127.0.0.1:9000
AWS_ENDPOINT_URL_S3=http://127.0.0.1:9000
AWS_ALLOW_HTTP=true
AWS_S3_FORCE_PATH_STYLE=true
EOF
set -a && source ./.env.omni && set +a

# 3. Lint the schema and queries (pure file check - no server needed)
omnigraph query lint --schema ./schema.pg --query ./queries/deals.gq

# 4. Create the bucket, init the repo, load the seed
curl -s -X PUT http://127.0.0.1:9000/omnigraph-local/ -H 'Host: omnigraph-local.localhost' \
     --user 'rustfsadmin:rustfsadmin' --aws-sigv4 'aws:amz:us-east-1:s3'
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/vc-os
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/vc-os

# 5. Start the local HTTP server (keep it running - separate terminal)
omnigraph-server --config ./omnigraph.yaml

# 6. Query through the server via aliases
omnigraph read --alias team
omnigraph read --alias founders-enriched
omnigraph read --alias pre-ic-brief-thesis      deal-helix-series-a
omnigraph read --alias signal-portfolio-impact  sig-vector-forge-aws-deal
omnigraph read --alias exit-landscape           org-pinion-infer
omnigraph read --alias debate-stances           deal-helix-series-a
omnigraph read --alias board-prep-pack          org-aetherbrick
omnigraph read --alias contradicted-active-theses
omnigraph read --alias intro-path-to-founder    per-helix-yuki
omnigraph read --alias reserve-pressure         fund-iii
omnigraph read --alias lessons-active
omnigraph read --alias publishers                                  # publisher/database/expert-network sources
omnigraph read --alias source-downstream-signals org-techcrunch    # downstream-signal revalidation
omnigraph read --alias person-insights          per-helix-yuki     # founder assessment
omnigraph read --alias observed-organizations                      # PitchBook-imported (no Quito engagement)
```

The aliases are also grouped by meeting view in `omnigraph.yaml` - `VIEW: IC Meeting`, `VIEW: Weekly Pipeline Meeting`, `VIEW: Portfolio Support Meeting`, `VIEW: LPAC / Fund Reporting` - so dashboards map 1:1 to alias bundles.

See the [Omnigraph](https://github.com/ModernRelay/omnigraph) repo for full CLI reference.

## Adapting for your firm

1. **Keep the schema as-is.** Most VC firms fit the 17-node ontology without modification.
2. **Replace the seed.** Use your firm's actual organizations, theses, people, and decisions. Start with current pipeline + portfolio; backfill history as time allows.
3. **Customize the `Market` taxonomy.** Sector-specialist firms (talent-tech, climate, fintech) only need to change `Market` enum-style values and the `Pattern`/`Lesson` content.
4. **Wire your existing tools as ingest sources.** Granola → `Artifact{kind=transcript, source=meeting-tool, source_app=granola}`. Slack → `Artifact{kind=chat-msg, source=chat, source_app=slack}`. Email → `Artifact{kind=email, source=email, source_app=gmail}`. The CRM gets fully replaced; everything else feeds in via mutations.
5. **Run the example queries against your real data.** If any returns empty, your seed is undermodeling the loop the query exercises - fix the seed, not the schema.

## Why this is the first "OS-grade" cookbook

Three properties no other cookbook in this repo delivers together:

1. **All seven workflow stages in one graph** - Find / Evaluate / Decide / Win / Help / Monitor / Learn.
2. **First-class engagement + action + reflexive layers.** `Deal`/`Fund`, `Decision`/`Commitment`, `Pattern`/`Lesson` share priority with `Signal`/`Insight` - they aren't bolted on.
3. **Stack collapse is the design principle.** Schema choices (native `Blob` on `Artifact`, hybrid search via `Chunk`, branch-as-audit, `Organization` as the universal entity-of-the-world) exist *specifically* to let the graph replace CRM + document store + learnings DB + audit log + access control + source-provenance registry.

The same pattern should generalize to other knowledge-work firms - law, consulting, family office, sales-led B2B sales operations.
