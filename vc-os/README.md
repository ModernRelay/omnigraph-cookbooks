# VC OS — A venture-capital operating system as a knowledge graph

Opinionated Omnigraph cookbook for venture-capital firms. Built on [Omnigraph](https://github.com/ModernRelay/omnigraph), shaped from a first-principles teardown of how a modern AI-era VC actually works. Covers pipeline, diligence, decisions, portfolio, network, audit, and learning — all in one typed graph.

## Why a graph, not another tool

A modern VC's stack typically contains 8–12 systems: a CRM (Airtable / Zendesk), a wiki (Notion), chat (Slack), a call-recording tool (Granola), spreadsheets and drives (Drive / Excel), portfolio modeling (Tactyc), an outbound platform (Sapien / Lemlist), and per-firm bespoke hacks — a sightings / dedup table, a runtime-rules database, a third-party vector store, local notes for deal memory, a cross-session memory daemon, a homegrown audit log.

Each store solved one problem at one moment. None of them talk to each other natively. Agents end up plumbing the gaps: 4 systems consulted per query, eventual consistency, scattered audit trail, no shared notion of *what is known*. This is fragmentation around tools, not organization around what the firm knows.

With Omnigraph's native capabilities — typed schema + typed mutations, native blobs, hybrid search (vector + BM25 + RRF + FTS) in one runtime, git-style branches/commits, snapshot-pinned reads, policy-as-code — most of that per-firm bespoke storage collapses inward.

## The reframe — beliefs, not documents

A VC firm is not in the business of producing documents. It is in the business of maintaining a **structured, dated, contradictable set of beliefs** about organizations, founders, and markets — and acting on them.

Every action either:
- **generates** a belief (scout finding, founder call, research brief)
- **updates** a belief (a new signal supports or contradicts an assumption)
- **acts on** a belief (decision, intro, board flag, follow-on)
- **records** the act (memo, log, comment)

The seven jobs a VC does — **Find, Evaluate, Decide, Win, Help, Monitor, Learn** — all collapse into one analytical loop over beliefs. The ontology is shaped to make that loop a 2-hop graph traversal.

## The schema — 7 core + 11 growth-ring

The core should be 5–7 entities that the team can hold in their head, that stay stable for years even as the analytical layer above them compounds. The schema is organized accordingly.

### Core (7) — the stable mental model

These seven names and shapes should not change for years. They are the entities the team thinks about every day.

| Node | Purpose |
|---|---|
| **`Organization`** | Any real-world business entity. `kind` carries the role (startup / lp-institution / vc-firm / acquirer / customer / bank / regulator / accelerator / family-office / …); `status` carries Quito's engagement state for `kind=startup` (nullable otherwise). Quito itself is `org-quito` (`kind=vc-firm`). |
| **`Person`** | An individual human. Roles relative to Quito live on edges, not on the node — `WorksAt org-quito` (team), `FounderOf co-x` (founder), `RoleInDeal {role: expert}` (expert). |
| **`Deal`** | A funding event involving a Organization. Quito-engaged Deals have `FromFund` set; externally observed Deals (PitchBook imports) use `outcome=observed`. |
| **`Fund`** | Quito's funds. |
| **`Market`** | Sector/vertical hub. Sector-specialist Theses, Patterns, and Lessons cluster around it. |
| **`Artifact`** | Raw content with native `Blob` — Granola transcripts, pitch decks, emails, screenshots, slack messages. |
| **`Meeting`** | A scheduled (or ad-hoc) event with attendees, subject, and outputs. The transcript is an `Artifact`; the Meeting binds attendees + agenda + outcomes (Decisions, Commitments) around it. Covers IC, board, founder calls, partner offsites, pipeline reviews, expert calls. |

### Growth ring (11) — the analytical layer that compounds

Built on top of the core. These can be added to or refined without touching the core.

| Layer | Nodes | Purpose |
|---|---|---|
| Belief | `Thesis` · `Assumption` · `Question` | The value layer (investing DNA). |
| Evidence | `Signal` · `Insight` · `SourceEntity` · `Chunk` | What moves beliefs. `SourceEntity` carries reliability — when a source proves unreliable, all downstream `Signal`s can be flagged for revalidation. `Chunk` is implementation detail for hybrid search, not an ontological commitment. |
| Action | `Decision` · `Commitment` | What we do. `Decision` is one-shot (`decided_at`); `Commitment` is deferred-action with a deadline. Intros and follow-ups are `Commitment`s, not `Decision`s. |
| Reflexive | `Pattern` · `Lesson` | What we learn. `Pattern` aggregates across many subjects; `Insight` interprets one. `Lesson` is operational (changes future behavior); `Insight` is descriptive. |

**18 nodes total** (`Chunk` ships zero rows in v1 — populate via `omnigraph embed --reembed_all`).

Slug prefixes: `org- per- mkt- deal- fund- art- mtg- thesis- asmp- q- sig- ins- src- chk- dec- cmt- pat- lsn-`.

### Three loops, one graph

Each box is a node type; arrows are edge types. Read each loop top-to-bottom.

**Loop 1 — Engagement (the CRM grain).** A `Deal` is a single funding event for an `Organization`; the firm itself is an `Organization` with `kind=vc-firm` that its team `WorksAt`. `Knows` is symmetric.

```
                ┌─────────┐           ┌──────────────┐           ┌──────────┐
                │  Fund   │◀─fromFund─│     Deal     │─forOrg───▶│   Org    │
                └─────────┘           └──────────────┘           └──────────┘
                     ▲                  │ │   │  │                 ▲    │  │
                     │                  │ │   │  └─lead/participant┘    │  │
                  lpInFund              │ │   relevantThesis            │  │
                     │                  │ │                             │  │
                ┌─────────┐    ┌────────┘ │                          founder│companyInMarket
                │  Org    │    │ ledByPerson                            Of  │  │
                │ (kind=  │  ┌────────┐    ┌────────┐    knows   ┌─────────┐ │
                │ lp-inst,│  │ Person │◀──▶│ Person │◀──────────▶│ Person  │ │
                │ vc-firm,│  └────────┘    └────────┘            └─────────┘ │
                │ acquirer│      │             ▲                      ▲      │
                │ etc.)   │  decisionMakerAt   │ roleInDeal           │      ▼
                └────┬────┘      ▼             │                      │   ┌────────┐
                     │      ┌────────┐    ┌────────┐                  │   │ Market │
                     ▼      │  Org   │    │  Deal  │              boardMemberAt
                wouldAcquire│ (kind= │    └────────┘                  │   └────────┘
                     │     │acquirer)│                                 │
                     │      └────────┘                                 │
                     └─────────────────────────────────────────────────┘
```

**Loop 2 — Belief + Evidence (SPIKE+).** `Signal` moves Beliefs (`Thesis`, `Assumption`, `Question`). `Artifact` carries the source content; `SourceEntity` tracks reliability so contaminated sources can be revalidated downstream. `Chunk` indexes blob content for hybrid search.

```
   ┌──────────────┐         ┌─────────────┐         ┌──────────────┐
   │    Thesis    │◀──relies│ Assumption  │supports/│    Signal    │
   │ (active /    │   On    │  (market,   │contra-  │ (discovery,  │
   │  contradicted│         │  financial, │dicts    │  fundraise,  │
   │  / retired)  │         │  product…)  │◀────────│  competitive,│
   └──────────────┘         └─────────────┘         │  …)          │
          ▲                        ▲                └──────┬───────┘
          │                        │                       │
          │supports/contradicts    │ basedOn               │ informs / about
          │                        │                       ▼
   ┌──────┴───────┐         ┌──────┴──────┐         ┌──────────────┐
   │    Signal    │         │  Decision   │         │   Question   │
   └──────────────┘         └─────────────┘         │ (open /      │
                                                    │  partial /   │
                                                    │  resolved)   │
                                                    └──────────────┘

   ┌──────────────┐  reliesOn  ┌─────────────┐  highlights  ┌──────────────┐
   │   Insight    │───────────▶│    Signal   │              │   Pattern    │
   │ (memo, brief,│            └─────────────┘              │ (gtm,        │
   │  stance:     │     ┌─────────────────────────────────▶ │  market-time,│
   │  bull/bear/  │─────┘                                   │  fail-mode…) │
   │  neutral)    │                                         └──────────────┘
   └──────┬───────┘
          │ aboutDeal / aboutOrg / aboutPerson
          ▼
   ┌──────────────┐  sourcedFrom  ┌─────────────┐  publishedBy  ┌──────────────┐
   │   Signal     │──────────────▶│   Artifact  │──────────────▶│ SourceEntity │
   └──────────────┘               │ (transcript,│               │ (reliability:│
                                  │  deck, web, │               │  high/med/low│
                                  │  email; Blob)│              └──────────────┘
                                  └──────┬──────┘
                                         │ chunkOf
                                         ▼
                                  ┌─────────────┐
                                  │    Chunk    │ (Vector(3072) for
                                  │             │  hybrid search)
                                  └─────────────┘
```

**Loop 3 — Decision + Learning (audit + feedback).** Every `Decision` snapshots its dependencies (`Assumption`s it rested on, open `Question`s, the `Deal` or `Thesis` it regards). `Commitment` is the deferred-action twin of `Decision`. The reflexive `Pattern → Lesson` layer turns repeating shapes into operational rules.

```
   ┌────────────┐  regardingDeal  ┌────────────┐
   │  Decision  │────────────────▶│    Deal    │
   │ (invest,   │                 └────────────┘
   │  pass,     │  regardingThesis ┌────────────┐
   │  follow-on,│────────────────▶ │   Thesis   │
   │  board-flag│                  └────────────┘
   │  …)        │  basedOnAssumption ┌──────────┐
   │            │──────────────────▶ │Assumption│
   │            │  needsAnswer       └──────────┘
   │            │──────────────────▶ ┌──────────┐
   │            │                    │ Question │
   │            │  byPerson          └──────────┘
   │            │────────────────▶ ┌────────────┐
   └────────────┘                  │   Person   │
                                   └────────────┘

   ┌────────────┐  forPerson      ┌────────────┐
   │ Commitment │────────────────▶│   Person   │
   │ (status:   │                 └────────────┘
   │  open /    │  assignedTo     ┌────────────┐
   │  in-prog / │────────────────▶│   Person   │
   │  done /    │                 └────────────┘
   │  dropped)  │  regardingDeal  ┌────────────┐
   │            │────────────────▶│    Deal    │
   │            │                 └────────────┘
   │            │  fromArtifact   ┌────────────┐
   │            │────────────────▶│  Artifact  │
   └────────────┘                 └────────────┘

   ┌────────────┐  acrossDecision ┌────────────┐
   │  Pattern   │────────────────▶│  Decision  │
   │            │  acrossSignal   ┌────────────┐
   │            │────────────────▶│   Signal   │
   │            │  acrossOrg      ┌────────────┐
   │            │────────────────▶│    Org     │
   └─────┬──────┘                 └────────────┘
         │
         │ distilledFromPattern
         ▼
   ┌────────────┐  appliesToMarket ┌────────────┐
   │   Lesson   │─────────────────▶│   Market   │
   │ (protocol, │                  └────────────┘
   │  rule-of-  │
   │  thumb,    │
   │  anti-pat, │
   │  runbook;  │
   │  status:   │
   │  tentative │
   │  /active)  │
   └────────────┘
```

**Loop 4 — Operational (Meetings).** A `Meeting` is the operational primitive — it binds attendees, a subject (`Deal` / `Organization` / `Thesis` / `Market`), and the outputs that came of it. The transcript or board notes live as an `Artifact{kind=transcript|meeting-note}` linked via `ArtifactFromMeeting`; `Decision`s and `Commitment`s the meeting produced point back via `DecisionFromMeeting` and `CommitmentFromMeeting`. This is what powers "show me every interaction we've had with Helix" and "what was committed at the last Aetherbrick board" — single-hop traversals that previously required Granola + calendar + Notion stitching.

```
   ┌────────────┐  meetingAboutDeal       ┌────────────┐
   │  Meeting   │────────────────────────▶│    Deal    │
   │ (ic, board,│  meetingAboutOrg        ┌────────────┐
   │ founder-   │────────────────────────▶│    Org     │
   │ call, dd-  │  meetingAboutThesis     ┌────────────┐
   │ call,      │────────────────────────▶│   Thesis   │
   │ partner-   │  meetingAboutMarket     ┌────────────┐
   │ 1on1,      │────────────────────────▶│   Market   │
   │ pipeline-  │                         └────────────┘
   │ review,    │
   │ portfolio- │  meetingAttendedBy      ┌────────────┐
   │ 1on1, lp-  │────────────────────────▶│   Person   │
   │ update,    │  {role: host/attendee/  └────────────┘
   │ expert-    │   optional/declined}
   │ call,      │
   │ internal,  │                         ┌────────────┐
   │ external-  │◀─artifactFromMeeting────│  Artifact  │
   │ other;     │                         └────────────┘
   │ status:    │                         ┌────────────┐
   │ scheduled  │◀─decisionFromMeeting────│  Decision  │
   │ /occurred/ │                         └────────────┘
   │ cancelled/ │                         ┌────────────┐
   │ resched-   │◀─commitmentFromMeeting──│ Commitment │
   │ uled)      │                         └────────────┘
   └────────────┘
```

### Key enums (the lens)

| Enum | Values |
|---|---|
| `Organization.status` | `cold, watching, pipeline, evaluating, portfolio, exited, passed, observed` — nullable for non-startup kinds |
| `Deal.stage` | `sourced, qualified, in-diligence, ic-ready, decided, closed, dead` |
| `Deal.outcome` | `open, invested, passed, lost, withdrawn, observed` (`observed` = external round we tracked but didn't engage with — e.g. PitchBook import) |
| `Decision.kind` | `invest, pass, follow-on, board-flag, double-down, write-off, exit-plan, second-meeting, no-decision` (intros are `Commitment`s, not Decisions) |
| `Organization.kind` | `startup, lp-institution, vc-firm, acquirer, customer, bank, regulator, association, accelerator, university, family-office, other` |
| `Assumption.level` | `market, founder, product, competitive, financial, strategic` |
| `Question.status` | `open, partial, resolved` |
| `Signal.kind` | `discovery, launch, fundraise, exit, founder-event, market-move, competitive, customer, regulatory, team-change, portfolio-update, board-decision` |
| `Insight.kind` | `memo, brief, observation, hypothesis, recap` |
| `Insight.stance` | `bull, bear, neutral` |
| `Pattern.kind` | `gtm, pricing, founder-archetype, market-timing, exit, failure-mode, tech-adoption, capital-structure, regulatory` |
| `Lesson.kind` | `protocol, rule-of-thumb, anti-pattern, runbook` |
| `Lesson.status` | `tentative, active, retired` — `tentative` lives on a review branch awaiting human merge |
| `Thesis.status` | `active, retired, contradicted` |
| `Meeting.kind` | `ic, board, partner-1on1, pipeline-review, portfolio-1on1, lp-update, founder-call, dd-call, expert-call, internal, external-other` |
| `Meeting.status` | `scheduled, occurred, cancelled, rescheduled` |

### What's deliberately *not* a node

These omissions are what keep the model coherent.

- **No "Skill" / "Bot" / "MCP" / "Workflow" nodes.** Operations aren't knowledge. The graph holds *outputs*.
- **No separate "Memory" type.** Memory is queries with snapshot-pinned reads.
- **No "Sighting" type.** A sighting = `Signal{kind=discovery}` with a uniqueness convention on `(organization, source, date)`.
- **No "Thread" / "Conversation" type.** Artifacts have `thread_id` + `ArtifactDerivedFrom` chains.
- **No "Memo" type.** A memo = `Insight{kind=memo, aboutDeal=…}` with a blob.
- **No "PortfolioOrganization" subtype.** It's `Organization.status = portfolio`.
- **No reified "User" / "Team Member".** Quito itself is `org-quito` (Organization kind=vc-firm); team members `WorksAt org-quito`. Authorship and ownership live on edges (`DecisionByPerson`, `CommitmentAssignedTo`).
- **No "Protocol" / "Runbook" type.** They're `Lesson{kind=protocol|runbook}`.

## Reference seed — Fictional Series-A AI-infra fund

The seed populates a fictional Berlin-based AI-infra fund running Fund III ($250M, vintage 2024). Single coherent narrative; exercises all 17 active node types (`Chunk` is schema-only). **All names, deals, organizations, and people are fabricated.**

| Layer | Count | Includes |
|---|---|---|
| Funds | 2 | Fund II (harvesting), Fund III (investing) |
| Theses | 8 | Vertical AI infra, on-prem inference, agentic CRMs, data-quality moats, etc. |
| Pipeline organizations | 12 | 6 in evaluation, 6 in pipeline |
| Portfolio organizations | 5 | Mix of Series A and B holdings |
| Markets | 6 | AI infra, AI applications, dev tools, vertical SaaS, security, data |
| People | ~25 | 5 team, ~10 founders, 4 LPs, 3 experts, 3 acquirer-DMs, plus VPs |
| Non-startup Companies | ~10 | Acquirers (hyperscalers, strategic), LP institutions, peer VCs, accelerators — all `Organization` with `kind` set |
| Signals | ~30 | Mix of competitive, fundraise, portfolio-update, market-move |
| Decisions | 7 | invest, pass (×3), follow-on, second-meeting, thesis-level double-down |
| Patterns / Lessons | 5 / 4 | AI-infra-specific |
| Meetings | 8 | 2 ICs (Axon occurred, Helix upcoming), 2 Aetherbrick boards (Q1 occurred, Q2 upcoming), Helix founder call, Axon expert ref call, partner thesis-review offsite, weekly pipeline |

**Totals (loaded):** 205 nodes across 17 active types, 464 edges across 62 edge types. `Chunk` is schema-only (zero seeded). Bidirectional `Knows` accounts for 28 of those edges (14 unique pairs × 2).

## Killer queries

The seed is shaped to light these up. Each is a single graph traversal that would otherwise require hand-stitching across 4+ systems.

### Pre-IC brief for a deal

```bash
omnigraph read --alias pre-ic-brief-thesis    deal-helix-series-a
omnigraph read --alias pre-ic-brief-evidence  deal-helix-series-a
omnigraph read --alias pre-ic-brief-questions deal-helix-series-a
omnigraph read --alias pre-ic-brief-debate    deal-helix-series-a
```
Returns the relevant thesis + grounding assumptions, signals contradicting those assumptions, open questions, and bull/bear stances — in one snapshot-pinned response. (The brief is split into four named aliases so each result table stays human-readable; agents recombine them.)

### Post-signal portfolio impact

```bash
omnigraph read --alias signal-portfolio-impact sig-vector-forge-aws-deal
```
A new external signal arrives — which committed portfolio decisions just got destabilized? Walks `Signal → contradicts → Assumption → basedOn(inv) → Decision → regarding → Deal → forOrganization(status=portfolio)`. Returns Aetherbrick's follow-on Decision in the reference seed.

### Exit landscape for a portfolio organization

```bash
omnigraph read --alias exit-landscape                  org-pinion-infer
omnigraph read --alias exit-landscape-decision-makers  org-pinion-infer
```
Who could acquire this organization (AWS, Microsoft, Google Cloud in the seed), who runs M&A at each potential acquirer, and — via `Person knows Person` — who on our team has a path in. Airtable physically can't compute this; the graph does it in two hops.

### Multi-agent IC simulation

```bash
omnigraph read --alias debate-stances deal-helix-series-a
```
Bull and bear `Insight`s grounded in real `Signal`s. Two agents run in parallel — one writes `Insight{stance=bull}`, the other `Insight{stance=bear}`, each tying to the same Deal. The output is a graph query, not prose synthesis.

### Board-prep pack

```bash
omnigraph read --alias board-prep-pack                  org-aetherbrick
omnigraph read --alias board-prep-open-questions        org-aetherbrick
omnigraph read --alias board-prep-commitments           org-aetherbrick
omnigraph read --alias board-prep-meeting-history       org-aetherbrick   # prior board meetings
omnigraph read --alias board-prep-next-meeting          org-aetherbrick   # scheduled next board
```
What's changed since the last board meeting, what's still open, what was committed last time, when the next board is. Cross-references portfolio `Signal`s, open `Question`s, open `Commitment`s, and the `Meeting` cadence.

### Meeting history with a deal or organization

```bash
omnigraph read --alias meetings-with-deal               deal-helix-series-a
omnigraph read --alias meetings-with-organization       org-aetherbrick
omnigraph read --alias ic-prep-meeting-history          deal-helix-series-a
omnigraph read --alias ic-prep-open-commitments         deal-helix-series-a
```
"Show me every interaction we've had with this deal/org" — single-hop traversal that previously required stitching Granola + calendar + Notion. `ic-prep-meeting-history` is the IC pre-read view; `ic-prep-open-commitments` returns commitments still outstanding from prior meetings about the deal (e.g., the three customer-reference calls owed before Helix IC).

### Intro path to a founder

```bash
omnigraph read --alias direct-team-knowers     per-helix-elena   # 1-hop
omnigraph read --alias intro-path-to-founder   per-helix-yuki    # 2-hop via bridge
```
For each team member, who do they `Knows` that knows the founder. Replaces the "Direct History / Mutual Connections / Network" agents at most firms with a single graph query.

### Contradicted theses

```bash
omnigraph read --alias contradicted-active-theses
```
Which active theses now have signals contradicting their core assumptions. Run weekly to catch belief drift before a quarterly review.

### Reserve pressure check

```bash
omnigraph read --alias reserve-pressure fund-iii
```
Which portfolio organizations in this fund have open follow-on-trigger questions. Tactyc says *how much* dry powder; the graph says *which organizations are about to need it*.

## How branches + commits replace audit + tentative-review

Two operational use cases get covered without any application-layer state:

**Tentative Lessons — branch-based review replaces tentative-then-review pipelines.**
An agent notices a recurring pattern in three closed deals → creates a `Lesson{kind=rule-of-thumb, status=tentative}` on a branch named `tentative/<date>`. Human reviews with `omnigraph branch diff`; merges if good, deletes if not. The branch *is* the review process. Replaces "tentative-learnings.md → review → promote to Notion" with one primitive.

**Decision counterfactuals.**
A `Decision` committed to main is snapshot-pinned to the exact `Assumption`/`Signal`/`Question` state at the moment of decision. Six months later: "what would we have decided if we'd known X?" — branch from the decision's commit, mutate one Assumption, re-run the pre-IC brief query. The diff is the counterfactual. Replaces hand-built post-mortems.

## v1 scope — what ships, what's deferred

This v1 prioritizes a coherent narrative-and-graph demo over running embeddings or attached blobs.

**Ships in v1:**
- Full 17-node schema with native `Blob` on `Artifact` and `Vector(3072) @embed("text")` on `Chunk`
- Reference seed: 197 nodes, 415 edges across 55 edge types, no embeddings, no blob payloads
- ~70 aliases covering reads + mutations for every node/edge type
- Killer queries enumerated above

**Deferred (extensions, not blockers):**
- **Real blob + embedding examples in seed.** Schema declares the capability. To enable: attach real PDFs/transcripts as `Artifact.blob`, populate `Chunk` rows, then `omnigraph embed --reembed_all` followed by hybrid queries combining `nearest()` / `bm25()` / `rrf()` with graph traversal.
- **Cedar policies** (`policies/`) — per-role access control (team / lp / read-only-portfolio) collapses application-layer permission code into the graph server. See Omnigraph's policy-as-code reference.
- **Sector-specialist Pattern/Lesson packs.** AI-infra Patterns ship with the reference seed; talent-tech / climate / B2B-SaaS variants are sibling cookbooks.
- **LP reporting layer.** Add `LPUpdate` and tighter `OrgLpInFund` reporting if structured LP reports become first-class.
- **Fund-of-funds layer.** If the firm itself invests in other funds, `Organization{kind=vc-firm}` plus `LpInFund` already covers it; no schema change.

## Files

```
vc-os/
├── README.md          # this file
├── CLAUDE.md          # scoped agent guidance
├── schema.pg          # 18 nodes, ~59 edges, ~19 enums — source of truth
├── seed.md            # human-readable narrative (twin of seed.jsonl)
├── seed.jsonl         # loadable seed
├── omnigraph.yaml     # CLI config + ~190 aliases
└── queries/
    ├── deals.gq           # 20 reads
    ├── organizations.gq   # 28 reads (incl. exit-landscape + co-investor)
    ├── people.gq          # 21 reads
    ├── signals.gq         # 16 reads
    ├── beliefs.gq         # 23 reads
    ├── decisions.gq       # 15 reads
    ├── patterns.gq        # 15 reads
    ├── portfolio.gq       # 17 reads
    ├── sources.gq         # 7 reads (provenance + reliability)
    ├── meetings.gq        # 23 reads (incl. IC + board prep + meeting history)
    └── mutations.gq       # 18 add_* + 64 link_* = 82 mutations
```

Total: 258 named queries, ~190 aliases.

## Quick Start

All commands run from `vc-os/`:

```bash
cd vc-os

# 1. Create .env.omni (these are the local RustFS dev creds; .env.omni is gitignored)
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

# 2. Lint the schema and queries (pure file check — no server needed)
omnigraph query lint --schema ./schema.pg --query ./queries/deals.gq

# 3. Init the repo (one-time — writes to storage)
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/vc-os

# 4. Load the seed (one-time)
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/vc-os

# 5. Start the local HTTP server (keep it running — separate terminal)
omnigraph-server --config ./omnigraph.yaml

# 6. Query through the server via aliases
omnigraph read --alias team                       # who's on the firm (via WorksAt org-quito)
omnigraph read --alias founders-enriched          # founders with prior_exits / years_operating
omnigraph read --alias pre-ic-brief-thesis      deal-helix-series-a
omnigraph read --alias pre-ic-brief-evidence    deal-helix-series-a
omnigraph read --alias signal-portfolio-impact  sig-vector-forge-aws-deal
omnigraph read --alias exit-landscape           org-pinion-infer
omnigraph read --alias debate-stances           deal-helix-series-a
omnigraph read --alias board-prep-pack          org-aetherbrick
omnigraph read --alias contradicted-active-theses
omnigraph read --alias intro-path-to-founder    per-helix-yuki
omnigraph read --alias reserve-pressure         fund-iii
omnigraph read --alias lessons-active
omnigraph read --alias sources                    # source reliability table
omnigraph read --alias source-downstream-signals src-techcrunch
omnigraph read --alias person-insights          per-helix-yuki  # founder assessment
omnigraph read --alias observed-organizations         # PitchBook-imported (no Quito engagement)
```

The aliases are also grouped by meeting view in `omnigraph.yaml` — `VIEW: IC Meeting`, `VIEW: Weekly Pipeline Meeting`, `VIEW: Portfolio Support Meeting`, `VIEW: LPAC / Fund Reporting` — so dashboards map 1:1 to alias bundles.

See the [Omnigraph](https://github.com/ModernRelay/omnigraph) repo for full CLI reference.

## Adapting for your firm

This cookbook is **schema- and tool-agnostic**. To adapt:

1. **Keep the schema as-is.** Most VC firms fit the 17-node ontology without modification.
2. **Replace the seed.** Use your firm's actual organizations, theses, people, and decisions. Start with current pipeline + portfolio; backfill history as time allows.
3. **Customize the `Market` taxonomy.** Sector-specialist firms (talent-tech, climate, fintech) only need to change `Market` enum-style values and the `Pattern`/`Lesson` content.
4. **Wire your existing tools as ingest sources.** Granola → `Artifact{kind=transcript, source=granola}`. Slack → `Artifact{kind=slack-msg}`. Email → `Artifact{kind=email}`. The CRM gets fully replaced; everything else feeds in via mutations.
5. **Run the killer queries against your real data.** If any returns empty, your seed is undermodeling the loop the query exercises — fix the seed, not the schema.

## Why this is the first "OS-grade" cookbook

Three properties no other cookbook in this repo delivers together:

1. **All seven workflow stages in one graph** — Find / Evaluate / Decide / Win / Help / Monitor / Learn.
2. **First-class engagement + action + reflexive layers.** `Deal`/`Fund`, `Decision`/`Commitment`, `Pattern`/`Lesson` share priority with `Signal`/`Insight` — they aren't bolted on.
3. **Stack collapse is the design principle.** Schema choices (native `Blob` on `Artifact`, hybrid search via `Chunk`, branch-as-audit) exist *specifically* to let the graph replace CRM + document store + learnings DB + audit log + access control.

The same pattern should generalize to other knowledge-work firms — law, consulting, family office, sales-led B2B sales operations. Future "OS-grade" cookbooks should mirror this layering.
