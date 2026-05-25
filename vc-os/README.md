# VC OS — A venture-capital operating system as a knowledge graph

Opinionated Omnigraph cookbook for venture-capital firms. Built on [Omnigraph](https://github.com/ModernRelay/omnigraph), shaped from a first-principles teardown of how a modern AI-era VC actually works. Covers pipeline, diligence, decisions, portfolio, network, audit, and learning — all in one typed graph.

## Why a graph, not another tool

A modern VC's stack typically contains 8–12 systems: a CRM (Airtable / Zendesk), a wiki (Notion), chat (Slack), a call-recording tool (Granola), spreadsheets and drives (Drive / Excel), portfolio modeling (Tactyc), an outbound platform, and per-firm bespoke hacks — a sightings / dedup table, a runtime-rules database, a third-party vector store, local notes for deal memory, a cross-session memory daemon, a homegrown audit log.

Each store solved one problem at one moment. None of them talk to each other natively. Agents end up plumbing the gaps: 4 systems consulted per query, eventual consistency, scattered audit trail, no shared notion of *what is known*. This is fragmentation around tools, not organization around what the firm knows.

With Omnigraph's native capabilities — typed schema + typed mutations, native blobs, hybrid search (vector + BM25 + RRF + FTS) in one runtime, git-style branches/commits, snapshot-pinned reads, policy-as-code — most of that per-firm bespoke storage collapses inward.

## From first principles

A firm is in the business of maintaining a **structured, dated, contradictable set of beliefs** about organizations, founders, and markets — and acting on them.

Every action either:
- **generates** a belief (scout finding, founder call, research brief)
- **updates** a belief (a new signal supports or contradicts an assumption)
- **acts on** a belief (decision, intro, board flag, follow-on)
- **records** the act (memo, log, comment)

The seven jobs a VC does — **Find, Evaluate, Decide, Win, Help, Monitor, Learn** — all collapse into one analytical loop over beliefs. The ontology is shaped to make that loop a 2-hop graph traversal.

## The schema — 7 core + 10 growth-ring

The core is the entities the team can hold in their head, stable for years even as the analytical layer above them compounds. The schema is organized accordingly.

### Core entities (7)

| Node | Purpose |
|---|---|
| **`Organization`** | Any real-world business entity. `kind` carries the role (startup / lp-institution / vc-firm / acquirer / customer / bank / regulator / accelerator / family-office / **publisher / database / expert-network** / …); `status` carries Quito's engagement state for `kind=startup` (nullable otherwise); `reliability` (low/med/high) is meaningful for the source-type kinds. Quito itself is `org-quito` (`kind=vc-firm`). |
| **`Person`** | An individual human. Roles relative to Quito live on edges, not on the node — `WorksAt org-quito` (team), `FounderOf co-x` (founder), `RoleInDeal {role: expert}` (expert). |
| **`Deal`** | A funding event involving an Organization. Quito-engaged Deals have `FromFund` set; externally observed Deals (PitchBook imports) use `outcome=observed`. |
| **`Fund`** | Quito's funds. |
| **`Market`** | Sector/vertical hub. Sector-specialist Theses, Patterns, and Lessons cluster around it. |
| **`Artifact`** | Raw content with native `Blob` — Granola transcripts, pitch decks, emails, screenshots, chat messages, markdown wiki pages. `source` is a coarse category (`email/chat/meeting-tool/web/doc-tool/crm/outbound/manual/derived/repo/other`); `source_app` is the specific vendor name. |
| **`Meeting`** | A scheduled (or ad-hoc) event with attendees, subject, and outputs. The transcript is an `Artifact`; the Meeting binds attendees + agenda + outcomes (Decisions, Commitments) around it. Covers IC, board, founder calls, partner offsites, pipeline reviews, expert calls. |

### Analytical layer

Built on top of the core. These can be added to or refined without touching the core.

| Layer | Nodes | Purpose |
|---|---|---|
| Belief | `Thesis` · `Assumption` · `Question` | The value layer (investing DNA). `Question` is the home for open uncertainties — not `Insight{kind=hypothesis}`. |
| Evidence | `Signal` · `Insight` · `Chunk` | What moves beliefs. `Chunk` is implementation detail for hybrid search, not an ontological commitment. |
| Action | `Decision` · `Commitment` | What we do. `Decision` is one-shot (`decided_at`); `Commitment` is deferred-action with a deadline. Intros, follow-ups, *schedule-another-meeting*, and *flag-at-next-board* are `Commitment`s, not `Decision`s. |
| Reflexive | `Pattern` · `Lesson` | What we learn. `Pattern` aggregates across many subjects; `Insight` interprets one. `Lesson` is operational (changes future behavior); `Insight` is descriptive. |

**17 node types total** (`Chunk` ships zero rows in v1 — populate via `omnigraph embed --reembed_all`). Source-provenance entities (TechCrunch, PitchBook, Tegus, anon blog) live as `Organization` rows with `kind` in `(publisher, database, expert-network)` and a `reliability` rating — no separate `SourceEntity` node.

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
   │  Assumption [leaf — receives reliesOn, supports/contradicts, basedOn]     │
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
   │  Fund         [leaf — receives FromFund + LpInFund]                       │
   │  Deal         → Fund (fromFund), Organization (forOrganization,           │
   │                 leadInvestor, participantInvestor), Person (ledByPerson), │
   │                 Thesis (relevantThesis), Market (relevantMarket)          │
   │  Organization → Market (organizationInMarket), Organization (wouldAcquire │
   │                 — self), Fund (lpInFund, when kind=lp-institution|        │
   │                 family-office)                                            │
   │  Person       → Deal (roleInDeal), Organization (worksAt, founderOf,      │
   │                 boardMemberAt, decisionMakerAt), Person (knows — self,    │
   │                 bidirectional)                                            │
   │  Market       [leaf]                                                      │
   │  Artifact     → Organization (publishedByOrganization,                    │
   │                 artifactAboutOrganization), Deal (artifactAboutDeal),     │
   │                 Person (fromPerson, mentionsPerson), Artifact             │
   │                 (derivedFrom — self), Thesis/Lesson/Pattern (documents),  │
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
| `Organization.status` | `cold, watching, pipeline, evaluating, portfolio, exited, passed, observed` — nullable for non-startup kinds |
| `Organization.reliability` | `low, medium, high` — meaningful for `kind` in (publisher, database, expert-network); null elsewhere |
| `Deal.stage` | `sourced, qualified, in-diligence, ic-ready, decided, closed, dead` |
| `Deal.outcome` | `open, invested, passed, lost, withdrawn, observed` (`observed` = external round we tracked but didn't engage with) |
| `Decision.kind` | `invest, pass, follow-on, double-down, write-off, exit-plan, no-decision` (intros, follow-ups, schedule-another-meeting, flag-at-next-board are `Commitment`s) |
| `Assumption.level` | `market, founder, product, competitive, financial, strategic` |
| `Question.status` | `open, partial, resolved` |
| `Signal.kind` | `discovery, launch, fundraise, exit, founder-event, market-move, competitive, customer, regulatory, team-change, portfolio-update, board-decision` |
| `Insight.kind` | `memo, brief, observation, recap` — open uncertainties live on `Question`, not here |
| `Insight.stance` | `bull, bear, neutral` |
| `Artifact.kind` | `email, ticket, chat-msg, meeting-note, transcript, deck, web-page, screenshot, doc, audio, image, summary, markdown` |
| `Artifact.source` | `email, chat, meeting-tool, web, doc-tool, crm, outbound, manual, derived, repo, other` — coarse category, vendor name in `source_app` |
| `Pattern.kind` | `gtm, pricing, founder-archetype, market-timing, exit, failure-mode, tech-adoption, capital-structure, regulatory` |
| `Lesson.kind` | `protocol, rule-of-thumb, anti-pattern, runbook` |
| `Lesson.status` | `tentative, active, retired` — `tentative` lives on a review branch awaiting human merge |
| `Thesis.status` | `active, retired, contradicted` |
| `Meeting.kind` | `ic, board, partner-1on1, pipeline-review, portfolio-1on1, lp-update, founder-call, dd-call, expert-call, internal, external-other` |
| `Meeting.status` | `scheduled, occurred, cancelled, rescheduled` |

### What's deliberately *not* a node

- **No "Skill" / "Bot" / "MCP" / "Workflow" nodes.** Operations aren't knowledge.
- **No separate "Memory" type.** Memory is queries with snapshot-pinned reads.
- **No "Sighting" type.** A sighting = `Signal{kind=discovery}` with a uniqueness convention on `(organization, source, date)`.
- **No "Thread" / "Conversation" type.** Artifacts have `thread_id` + `ArtifactDerivedFrom` chains.
- **No "Memo" type.** A memo = `Insight{kind=memo, aboutDeal=…}` with a blob.
- **No "PortfolioOrganization" subtype.** It's `Organization.status = portfolio`.
- **No reified "User" / "Team Member".** Quito itself is `org-quito` (Organization kind=vc-firm); team members `WorksAt org-quito`. Authorship and ownership live on edges (`DecisionByPerson`, `CommitmentAssignedTo`).
- **No "Protocol" / "Runbook" type.** They're `Lesson{kind=protocol|runbook}`.
- **No separate "SourceEntity" node.** A source is an `Organization` with `kind` in `(publisher, database, expert-network)` and a `reliability` rating. Reliability-driven revalidation walks the same `published-by-organization` ← Artifact ← `signalSourcedFromArtifact` ← Signal chain that a separate SourceEntity used to.
- **No `hypothesis` value on `Insight.kind`.** An open uncertainty awaiting evidence is a `Question` — that has the right lifecycle (`open/partial/resolved`) and participates in the `DecisionNeedsAnswer` traversal.

## Reference seed — Fictional Series-A AI-infra fund

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

## Example queries — with live output

The seed is shaped to light these up. Each is a single graph traversal that would otherwise require hand-stitching across 4+ systems. Output below is verbatim from `omnigraph read --alias <name> [args]` against the loaded seed.

### Pre-IC brief for a deal

```bash
omnigraph read --alias pre-ic-brief-thesis    deal-helix-series-a
omnigraph read --alias pre-ic-brief-evidence  deal-helix-series-a
omnigraph read --alias pre-ic-brief-questions deal-helix-series-a
omnigraph read --alias debate-stances         deal-helix-series-a
```

**`pre-ic-brief-thesis`** — relevant thesis + grounding assumptions:
```
t.slug                   | t.name                                     | a.slug                            | a.level   | a.confidence
-------------------------+--------------------------------------------+-----------------------------------+-----------+-------------
thesis-on-prem-inference | On-prem inference for regulated industries | asmp-data-sovereignty-mandates    | strategic | high
thesis-on-prem-inference | On-prem inference for regulated industries | asmp-inference-cost-parity-onprem | financial | medium
thesis-on-prem-inference | On-prem inference for regulated industries | asmp-helix-onprem-margin          | financial | medium
```

**`pre-ic-brief-evidence`** — signals contradicting those assumptions:
```
a.slug                            | s.slug                    | s.kind      | s.date     | s.brief
----------------------------------+---------------------------+-------------+------------+--------
asmp-inference-cost-parity-onprem | sig-aws-bedrock-onprem    | competitive | 2026-03-04 | AWS Bedrock on-prem appliance announced…
asmp-helix-onprem-margin          | sig-aws-bedrock-onprem    | competitive | 2026-03-04 | (same)
asmp-helix-onprem-margin          | sig-microsoft-onprem-push | market-move | 2026-01-28 | Microsoft on-prem GPU SKUs for regulated…
```

**`pre-ic-brief-questions`** — open uncertainties:
```
q.slug                | q.priority | q.description
----------------------+------------+--------------
q-helix-onprem-margin | high       | AWS Bedrock now offers on-prem appliances. Does Helix's margin profile hold?
```

**`debate-stances`** — bull + bear Insights grounded in real Signals:
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

Walks `Signal → contradicts → Assumption → basedOn(inv) → Decision → regarding → Deal → forOrganization(status=portfolio)`. A new external signal arrives — which committed portfolio decisions just got destabilized?

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

**`exit-landscape`** — plausible acquirers:
```
o.slug           | o.name       | o.kind   | o.brief
-----------------+--------------+----------+--------
org-aws          | AWS          | acquirer | Hyperscaler. Acquires infra startups for Bedrock + agent stack.
org-microsoft    | Microsoft    | acquirer | Hyperscaler. Active AI-infra M&A.
org-google-cloud | Google Cloud | acquirer | Hyperscaler. Vertex AI ecosystem acquisitions.
```

**`exit-landscape-decision-makers`** — corp-dev contacts at each:
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

**`board-prep-pack`** — recent signals since last board:
```
s.slug                        | s.name                                     | s.date     | s.brief
------------------------------+--------------------------------------------+------------+--------
sig-aetherbrick-series-b-talk | Aetherbrick — early Series B conversations | 2026-04-22 | CEO begins early Series B talks. Sequoia EU likely to lead.
sig-aetherbrick-churn-spike   | Aetherbrick — Q1 churn spike (8.3%)        | 2026-04-07 | Q1 gross churn 8.3% (vs 4.5% Q4). Three mid-market logos lost…
```

**`board-prep-commitments`** — what's owed before the next board:
```
cmt.slug                   | cmt.name                     | cmt.status | cmt.due_date | cmt.detail
---------------------------+------------------------------+------------+--------------+-----------
cmt-aetherbrick-board-prep | Aetherbrick — board prep doc | open       | 2026-06-08   | Compile board prep covering churn analysis + Series B follow-on framework.
```

**`board-prep-next-meeting`** — when the next board is:
```
m.slug                        | m.name                      | m.scheduled_at           | m.location | m.summary
------------------------------+-----------------------------+--------------------------+------------+----------
mtg-aetherbrick-board-q2-2026 | Aetherbrick — Q2 2026 board | 2026-07-09T15:00:00.000Z | Berlin HQ  | Next board. Churn cohort follow-up + Series B framework decision expected.
```

### Meeting history with a deal or organization

```bash
omnigraph read --alias meetings-with-deal               deal-helix-series-a
omnigraph read --alias ic-prep-meeting-history          deal-helix-series-a
omnigraph read --alias ic-prep-open-commitments         deal-helix-series-a
```

**`ic-prep-open-commitments`** — what's still owed before Helix IC:
```
cmt.slug                 | cmt.name                           | cmt.priority | cmt.due_date | cmt.detail
-------------------------+------------------------------------+--------------+--------------+-----------
cmt-helix-second-meeting | Helix — schedule second meeting    | normal       | 2026-04-25   | On-prem mandate validated but need to test margin assumption…
cmt-helix-customer-refs  | Helix — 3 customer reference calls | high         | 2026-06-15   | Schedule and complete 3 customer reference calls before Helix IC.
```

### Intro path to a founder

```bash
omnigraph read --alias direct-team-knowers     per-helix-elena   # 1-hop
omnigraph read --alias intro-path-to-founder   per-helix-yuki    # 2-hop via bridge
```

**`direct-team-knowers per-helix-elena`** — who on the firm already knows her:
```
teammate.slug | teammate.name
--------------+--------------
per-pawel     | Pawel Nowak
```

**`intro-path-to-founder per-helix-yuki`** — 2-hop bridge:
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

**`source-downstream-signals org-techcrunch`** — if TechCrunch's reliability drops, these signals need revalidation:
```
sig.slug                  | sig.name                                   | sig.kind    | sig.date   | sig.impact
--------------------------+--------------------------------------------+-------------+------------+-----------
sig-eu-ai-act-enforcement | EU AI Act — first major enforcement action | regulatory  | 2026-04-15 | high
sig-aws-bedrock-onprem    | AWS Bedrock launches on-prem appliance     | competitive | 2026-03-04 | high
sig-databricks-acquihire  | Databricks acquires eval startup           | exit        | 2026-02-10 | high
sig-microsoft-onprem-push | Microsoft expands Azure on-prem AI         | market-move | 2026-01-28 | normal
```

That walk — `Organization{reliability=low/medium} ← publishedByOrganization ← Artifact ← signalSourcedFromArtifact ← Signal` — is what justifies collapsing the old `SourceEntity` node into `Organization`. The provenance traversal is identical; one less node type to learn.

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

**`team`** — 5 partners + 2 VPs, all derived from `WorksAt org-quito`:
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

**`decisions-recent`** — 6 actual Decisions in the seed (no schedule-a-meeting or board-flag entries — those are Commitments):
```
dec.slug                       | dec.name                                  | dec.kind    | dec.decided_at
-------------------------------+-------------------------------------------+-------------+---------------
dec-axon-ic-recommend-invest   | Axon Eval — IC recommend invest           | invest      | 2026-05-12
dec-aetherbrick-follow-on-eval | Aetherbrick — evaluate Series B follow-on | follow-on   | 2026-04-22
dec-onprem-thesis-doubledown   | Double down on on-prem-inference thesis   | double-down | 2026-04-20
dec-vector-forge-pass          | Pass on Vector Forge seed                 | pass        | 2026-01-22
dec-stratopaint-pass           | Pass on Stratopaint seed                  | pass        | 2025-11-15
dec-pulserate-pass             | Pass on PulseRate Series A                | pass        | 2025-08-04
```

## How branches + commits replace audit + tentative-review

**Tentative Lessons — branch-based review.** An agent notices a recurring pattern in three closed deals → creates a `Lesson{kind=rule-of-thumb, status=tentative}` on a branch named `tentative/<date>`. Human reviews with `omnigraph branch diff`; merges if good, deletes if not. The branch *is* the review process.

**Decision counterfactuals.** A `Decision` committed to main is snapshot-pinned to the exact `Assumption`/`Signal`/`Question` state at the moment of decision. Six months later: "what would we have decided if we'd known X?" — branch from the decision's commit, mutate one Assumption, re-run the pre-IC brief query. The diff is the counterfactual.

## Example agent workflows

Five patterns the graph shape uniquely enables. The common shape: **agent proposes on a branch, partner reviews via `branch diff`, merges into `main`**. Each is invocable from `claude -p ...` (or any agent runtime) against the local omnigraph server.

For each agent below: the natural-language **prompt** you'd send it, concrete **pulls** (graph reads it makes) and **writes** (graph mutations it lands on a `tentative/…` branch). Only the first two also consume external data (a transcript or a scout note); the other three are pure graph composition.

### 1. Post-call ingestion · daily, after every founder/portco call

**Prompt** (real shape):
> A Granola transcript just landed for the Helix follow-up call (`mtg-helix-followup-2026-05`). Ingest it: resolve mentioned people/orgs, derive material signals and tie them to the right Assumptions, extract action items as Commitments. Land everything on `tentative/ingest-helix-2026-05-29`. Don't fabricate; if a mentioned person isn't in the graph, surface that rather than guessing a slug.

**External input:** Granola transcript (text or `Artifact{blob}`).

**Pulls (an example pass against the Helix narrative):**
- Loads the meeting itself — agenda, attendees, prior summary — so the agent knows what was supposed to be discussed (`mtg-helix-followup-2026-05`)
- Resolves the first name "Yuki" from the transcript to the existing founder Person record (`per-helix-yuki` — found via `search-people`)
- Fetches the deal's grounding belief structure so any new signal can be tied in: the active **on-prem inference thesis** and its three backing assumptions (data-sovereignty mandates, on-prem cost parity, Helix's 60%+ margin)
- Reads what's still open on the deal so new signals can be linked to the right question — here, the high-priority **"can Helix sustain margins as cloud catches up?"** (`q-helix-onprem-margin`)

**Writes (on `tentative/ingest-helix-2026-05-29`):**
- Records the transcript itself as an Artifact (source category `meeting-tool`, source_app `granola`), linked back to the meeting and tagged with every attendee mentioned by name
- A new Signal capturing the material observation from the call — "Top-3 customer at 35% ARR, no diversification before IC" — and ties it as **contradicting evidence** against the margin assumption. So the bear case on this deal now has one more structural data point next time the debate is read
- An action item extracted from "we'll send the cohort report before IC": a Commitment owed by Yuki, due 2026-06-12, linked back to this meeting and to the Helix Series A deal — so it shows up automatically in the IC-prep view a week from now
- All three writes share the same branch, so the partner sees them together in `branch diff` and merges atomically

**Why graph:** entity resolution + signal classification + commitment extraction become typed mutations in one atomic transaction. Without typed schema this is 4+ uncoordinated CRM API calls with no consistency guarantee — and no reproducible record of "what did we extract from that call".

### 2. Scout-pick triage · daily, on every inbound mention

**Prompt** (real shape, tested live):
> A scout sent in: *"Saw a launch from Ferrumix on HN — vertical AI for industrial maintenance shops, two ex-Siemens engineers, YC W26, ferrumix.ai. Note: I think we passed on something similar last quarter (Stratopaint?)."* Triage it. Decide new/resurfacing/known/out-of-scope per `Organization.status`. If similar prior decisions exist, surface them. If new, create on a `tentative/scout-<date>` branch and enrich with sector hub, founder info if given, and links to relevant Patterns/Lessons.

**External input:** raw scout note (text, email, HN link).

**Pulls:**
- Searches the graph for Ferrumix — returns zero rows, so the verdict is **new** (not a resurfacing)
- Searches for Stratopaint (the scout's half-memory) — returns the org and its prior **pass decision** from Q4 2025, with the rationale "vertical SaaS without product-led pull"
- Walks from that pass to the firm's accumulated learning on it: the **shell-anti-pattern lesson** ("distribution doesn't fix PMF"), the **5-customer data-moat eval protocol** lesson, and the underlying **vertical-shell-flop pattern** that Stratopaint anchors
- Finds the existing open question "are our shell-pattern passes still right?" — there's a live institutional uncertainty that Ferrumix is fresh data on

**Writes (on `tentative/scout-ferrumix-triage-20260529`):**
- A new Organization for Ferrumix, status `watching`, kind `startup`. The brief captures what the scout actually said — "ex-Siemens engineers, YC W26", website `ferrumix.ai` — and the org is wired into the `mkt-vertical-saas` sector hub so the relevant lessons are reachable from it
- A scout-discovery Signal dated today, linked to Ferrumix
- The HN note itself recorded as an Artifact (so the provenance for the signal isn't just "the scout said")
- A structural link from the new signal to the open re-evaluation question — so the question now has one more datapoint and will surface higher next time it's reviewed
- A neutral-stance Insight that names the tension explicitly: "pattern-matches the vertical-shell failure mode, but ex-Siemens founders in industrial maintenance may have proprietary-data access that flips the call. Run the 5-customer protocol before deciding." It's linked to the vertical-shell-flop pattern so the connection is queryable, not just prose
- Founder Person nodes deliberately **not** created — the scout didn't name them. The agent flags this as the top enrichment gap rather than inventing slugs

**Why graph:** the dedup verdict is a structural property of `Organization.status`, not a tree in `policy.ts`. The Stratopaint linkage surfaces *because* the firm's prior pass is on the same Pattern in the same Market — no semantic-search hack needed. The lessons and the open question come along for free because they're already attached to that pattern.

### 3. Pre-X brief · on-demand for every IC, board, founder call, partner 1:1

**Prompt** (real shape, tested live):
> Pawel is leading the upcoming IC for `deal-helix-series-a` (in-diligence, target close in 3 weeks). Generate a tight markdown brief covering: thesis context, supporting and contradicting evidence, open questions, internal debate to date, prior meetings, outstanding commitments. Cite real evidence — no invented data. End with one of: STRONG INVEST / INVEST WITH CONDITIONS / PASS / NEEDS MORE DILIGENCE.

**External input:** None.

**Pulls:**
- The deal terms themselves — $14M round on $42M pre, our $5M check, target close 2026-07-15 — and the lead partner (Pawel)
- The deal's grounding thesis (**on-prem inference for regulated industries**, active, high confidence) and its three backing assumptions, each with a confidence level — sovereignty mandates (high), cost parity (medium), Helix margin (medium)
- Every signal that **supports or contradicts** any of those assumptions. Both medium-confidence financial pillars come back with multiple contradicting signals (AWS Bedrock on-prem appliance launch; Microsoft's on-prem GPU SKUs); the high-confidence demand pillar comes back fully supported (€42M EU AI Act enforcement; an anchor customer mandating on-prem-only post-DORA)
- The deal's open questions, by priority — surfaces one high-priority one: *"Can Helix sustain margins as cloud catches up?"*
- Both prior internal memos written about this deal — the bull and the bear cases — and which signals each cites
- Every meeting that's already happened or is scheduled about this deal — here just the founder call from April, with attendees and the summary that already named the margin question as the open item
- Every still-open commitment owed before IC — the three customer reference calls (high priority, due in 3 weeks) and the long-overdue second-meeting margin test

**Writes:** None. The output is the synthesized markdown brief returned to the partner — every reproducibility property comes from the snapshot-pinned reads.

**Why graph:** ~8 reads against a single commit-pinned snapshot. The same brief re-run six months later against the same commit returns byte-identical evidence — no other store gives you that. In the live agent run, the synthesis surfaced "bull defends the demand pillar, bear attacks the margin pillar — they aren't arguing about the same thing" and flagged that the margin-testing commitment was a month overdue. Both observations are structural — counting which pillars each side's cited signals attack, and comparing today's date against `Commitment.due_date`. Not clever LLM observation; mechanical graph traversal.

### 4. Multi-agent IC simulation · on-demand for high-conviction deals

**Prompt** (real shape, tested live as two parallel agents):
> You are the **BULL** agent in a parallel IC debate for `org-quirebench` (LLM evaluation platform, portfolio org from a 2025 seed). The question is *follow-on participation in a hypothetical Series A*. The **BEAR** agent is running simultaneously against the same branch (`ic-debate-quirebench-20260529`). Read state, prior signals, related Patterns. Take the bull side. Write an Insight with `add-insight-with-stance`, citing real signals via `InsightReliesOnSignal`. Don't invent. — *(bear agent gets the same prompt with BULL↔BEAR swapped.)*

**External input:** None.

**Pulls (shared between both agents):**
- The portfolio org itself and its grounding thesis (**eval-as-product**, active, zero contradictions)
- All signals about the dev-tools market, surfacing the **state-of-LLM-eval** signal ("14 vendors and growing, no clear leader") and the **Databricks acquihire** ("eval startup acquired for ~$95M")
- The org's own recent signals — most importantly the **board-approved Pro tier launch** (live monetization)
- The **eval-fragmentation pattern**, which aggregates QuireBench, Axon Eval, and 3 other firms

**Bear agent additionally pulls:**
- The **Axon acquihire-rumor signal** — "Databricks pitched acquihire to our own Axon; founder declined". The bull doesn't lean on this because it cuts against the standalone-outcome read.

**Writes (both agents on `tentative/ic-debate-quirebench-20260529`):**
- **Bull memo** — "QuireBench in an open field with an acquirer floor and live monetization; follow-on preserves ownership in the likely category winner." Cites the eval-fragmentation signal (open field), the Databricks acquihire (acquirer floor sets a $95M downside), and the Pro tier board decision (revenue is real). Anchored on the same eval-fragmentation pattern that defines the market.
- **Bear memo** — "Recommend pass. The same $95M Databricks deal was an *acquihire* not a product M&A; the rumored Axon acquihire was *declined*; QuireBench is 1-of-14 with no moat. Pattern reads as commoditization, not opportunity." Cites the eval-fragmentation signal (crowded), the Databricks acquihire (acqui-talent priced — exit ceiling, not floor), and the Axon-rumor (the easy exit was already foreclosed on our own portfolio). Anchored on the *same* eval-fragmentation pattern, interpreted oppositely.
- Read back via `debate-stances deal-quirebench-seed` returns both memos side-by-side with their stance, summary, and the signals they cite.

**Why graph:** both memos linked to the **same Pattern node** with opposite framings is the schema's debate primitive working. The disagreement is structurally legible — the partner can see at a glance "these two agents are arguing about how to read the same evidence" rather than "two LLM essays that happen to disagree". Replaces P9's "3-agent founder tribunal" with first-class persistence partners can audit row-by-row.

### 5. Reflexive learning sweep · quarterly

**Prompt** (shape):
> Scan recent Decisions plus active Patterns. For any Pattern with ≥3 supporting Decisions and consistent outcome (all-pass / all-invest / all-write-off / all-double-down), propose a tentative Lesson on `tentative/lesson-<slug>-<quarter>`. Cite the Pattern via `distilledFromPattern`. End with a digest of what landed (or that nothing did, if the existing Lessons already cover everything).

**External input:** None.

**Pulls:**
- Every Decision from the last quarter — for the v1 seed that's 6 Decisions: three vertical-shell *passes* (PulseRate, Stratopaint, Vector Forge), an Aetherbrick *follow-on evaluation*, an Axon *invest recommendation*, and a thesis-level *double-down on on-prem inference*
- Every Pattern, with its `acrossDecision` aggregations — the **vertical-shell-flop** pattern has three supporting Decisions, all passes, consistent outcome (clear lesson candidate). The **on-prem shift** pattern has the Helix-second-meeting commitment (was a Decision pre-cleanup) plus the double-down — only two, and outcomes diverge (one is a hold-while-testing, the other is an active bet), so no consistent lesson yet
- Every already-active Lesson — discovers that the shell-anti-pattern lesson already exists and documents exactly this shape, so a new Lesson here would be a duplicate

**Writes (only if a genuinely new pattern is found — for the v1 seed, none):**
- A new Lesson with `status=tentative`, body capturing the rule of thumb in operational terms, linked to the Pattern it was distilled from and to the Market(s) it applies to. Partner reviews via `branch diff`; merging promotes `status=tentative → active`, deletion drops the lesson.

For the v1 seed this sweep produces nothing — which is the **right** answer. The existing `lsn-shell-anti-pattern` covers the three vertical-shell passes; the on-prem pattern hasn't accumulated enough closed Decisions yet to distill. A sweep that always produces a Lesson would be a hallucinating sweep.

**Why graph:** `Lesson.status=tentative` + branch-based promote replaces the markdown buffer / promote loop with one primitive. `Pattern.acrossDecision` aggregation is what makes "this shape recurred 3 times with consistent outcome" a deterministic query, not a vibes call. The duplicate-check against existing active Lessons is the same primitive — `lesson distilledFromPattern X` already covered?

## v1 scope

**Ships:**
- Full 17-node schema with native `Blob` on `Artifact` and `Vector(3072) @embed("text")` on `Chunk`
- Reference seed: 207 nodes, 460 edges across 65 edge types, no embeddings, no blob payloads
- 294 aliases covering reads + mutations for every node/edge type (289 named queries across 12 `.gq` files)
- Example queries enumerated above

**Deferred (extensions, not blockers):**
- **Real blob + embedding examples in seed.** Schema declares the capability. Attach real PDFs/transcripts as `Artifact.blob`, populate `Chunk` rows, then `omnigraph embed --reembed_all` followed by hybrid queries combining `nearest()` / `bm25()` / `rrf()` with graph traversal.
- **Cedar policies** (`policies/`) — per-role access control (team / lp / read-only-portfolio) collapses application-layer permission code into the graph server.
- **Sector-specialist Pattern/Lesson packs.** AI-infra Patterns ship with the reference seed; talent-tech / climate / B2B-SaaS variants are sibling cookbooks.
- **`Measurement` node** for time-series KPIs/cash/runway (currently captured loosely via `Signal{kind=portfolio-update}`).

## Files

```
vc-os/
├── README.md          # this file
├── CLAUDE.md          # scoped agent guidance
├── schema.pg          # 17 nodes, ~62 edges, ~19 enums — source of truth
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
  rustfs/rustfs:latest

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

# 3. Lint the schema and queries (pure file check — no server needed)
omnigraph query lint --schema ./schema.pg --query ./queries/deals.gq

# 4. Create the bucket, init the repo, load the seed
curl -s -X PUT http://127.0.0.1:9000/omnigraph-local/ -H 'Host: omnigraph-local.localhost' \
     --user 'rustfsadmin:rustfsadmin' --aws-sigv4 'aws:amz:us-east-1:s3'
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/vc-os
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/vc-os

# 5. Start the local HTTP server (keep it running — separate terminal)
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

The aliases are also grouped by meeting view in `omnigraph.yaml` — `VIEW: IC Meeting`, `VIEW: Weekly Pipeline Meeting`, `VIEW: Portfolio Support Meeting`, `VIEW: LPAC / Fund Reporting` — so dashboards map 1:1 to alias bundles.

See the [Omnigraph](https://github.com/ModernRelay/omnigraph) repo for full CLI reference.

## Adapting for your firm

1. **Keep the schema as-is.** Most VC firms fit the 17-node ontology without modification.
2. **Replace the seed.** Use your firm's actual organizations, theses, people, and decisions. Start with current pipeline + portfolio; backfill history as time allows.
3. **Customize the `Market` taxonomy.** Sector-specialist firms (talent-tech, climate, fintech) only need to change `Market` enum-style values and the `Pattern`/`Lesson` content.
4. **Wire your existing tools as ingest sources.** Granola → `Artifact{kind=transcript, source=meeting-tool, source_app=granola}`. Slack → `Artifact{kind=chat-msg, source=chat, source_app=slack}`. Email → `Artifact{kind=email, source=email, source_app=gmail}`. The CRM gets fully replaced; everything else feeds in via mutations.
5. **Run the example queries against your real data.** If any returns empty, your seed is undermodeling the loop the query exercises — fix the seed, not the schema.

## Why this is the first "OS-grade" cookbook

Three properties no other cookbook in this repo delivers together:

1. **All seven workflow stages in one graph** — Find / Evaluate / Decide / Win / Help / Monitor / Learn.
2. **First-class engagement + action + reflexive layers.** `Deal`/`Fund`, `Decision`/`Commitment`, `Pattern`/`Lesson` share priority with `Signal`/`Insight` — they aren't bolted on.
3. **Stack collapse is the design principle.** Schema choices (native `Blob` on `Artifact`, hybrid search via `Chunk`, branch-as-audit, `Organization` as the universal entity-of-the-world) exist *specifically* to let the graph replace CRM + document store + learnings DB + audit log + access control + source-provenance registry.

The same pattern should generalize to other knowledge-work firms — law, consulting, family office, sales-led B2B sales operations.
