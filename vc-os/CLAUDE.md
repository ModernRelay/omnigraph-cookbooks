# CLAUDE.md — vc-os

Scoped guidance for the `vc-os/` cookbook. Repo-wide conventions live in `../CLAUDE.md`. For general Omnigraph ops — schema authoring, queries, loading, branches, cluster commands, the CLI — use the **omnigraph** skill rather than re-deriving them here; this file covers only what's specific to VC OS.

## What This Is

An Omnigraph schema + seed modeling a venture-capital firm's full operating system. Not just an intelligence layer (signals/patterns/insights) but engagement (deals, funds), action (decisions, commitments), and reflexive learning (patterns, lessons) — all in one typed graph. Schema, seed data, and queries only — no application code.

The reference seed is a **fictional Berlin-based AI-infra fund** ("Quito Capital") running Fund III ($250M, vintage 2024). All names, organizations, deals, and people are fabricated. The seed exists to shape the demo queries, not to model a real firm.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — The landing page, written to the template in `../CLAUDE.md`. Commands, workflows and modelling rules live in this file, not in the README.
- `seed.md` / `seed.jsonl` — Reference seed (human-readable / loadable).
- `queries/*.gq` — Read and mutation queries. One file per domain.
- `cluster.yaml` — Deployment declaration (graph `vcos`, schema, stored queries).
- `omnigraph-config.example.yaml` — Read aliases. Your operator config is per-user at `$OMNIGRAPH_HOME/config.yaml` (never committed); merge this file's aliases into it. Aliases bind to the stored queries published by `cluster apply`.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

## Setup

Use the shared [local setup](../docs/local-setup.md) with cookbook
`vc-os` and graph `vcos`. It owns authentication, the bootstrap writer-lock
handoff, readiness, and served seed loading. Apply later configuration edits with
the [live update workflow](../docs/local-setup.md#live-updates).

Graph id `vcos`. Stored queries and their parameters: `omnigraph queries list --target local --graph vcos`.
Alias parameters bind by name to `$params`: `omnigraph alias pre-ic-brief-thesis --params '{"slug":"deal-helix-series-a"}'` is `omnigraph query pre_ic_brief_thesis --target local-reader --graph vcos --params '{"slug":"deal-helix-series-a"}'`.

## Writing

Aliases are read-only; mutations run as `omnigraph mutate <name> --target local-writer --graph vcos --params '<json>'` with every
non-optional property supplied. Signatures live in `queries/mutations.gq`. Working example:

```bash
omnigraph mutate add_lesson --target local-writer --graph vcos --params '{"slug":"lsn-ref-calls-before-ic","name":"Finish customer reference calls before IC","kind":"rule-of-thumb","body":"No IC vote while a reference call is still open.","status":"tentative","createdAt":"2026-09-14T00:00:00Z","updatedAt":"2026-09-14T00:00:00Z"}'
omnigraph mutate link_lesson_distilled_from --target local-writer --graph vcos --params '{"lesson":"lsn-ref-calls-before-ic","pattern":"pat-on-prem-shift"}'
```

The shared operator config sets no `default_graph`, so every command passes `--graph vcos`.

## Schema Language (`.pg`)

Schema-language reference (node/edge syntax, `@key`/`@index`/`@unique`/`@embed`, `?`/`[Type]`/`enum(...)`) lives in the **omnigraph** skill. VC-OS-specific note: comments use `//` not `#`, and `[Type]` lists hold scalars only (no lists of enum).

## Domain Model

**Core (7) + Growth ring (10) = 17 nodes total.** The core is stable for years; the growth ring evolves as the firm learns.

**Core:**
| Node | Purpose |
|---|---|
| `Organization` | Universal entity. `kind` enum: startup/lp-institution/vc-firm/acquirer/customer/bank/regulator/accelerator/family-office/**publisher/database/expert-network**/other. Quito itself is `org-quito` (kind=vc-firm). Source-provenance entities (TechCrunch, PitchBook, Tegus, anon blog) live here with `kind` in (publisher, database, expert-network) plus a `reliability` rating. |
| `Person` | Individual human. Roles relative to Quito live on edges, not on the node. |
| `Deal` | A funding event involving an Organization. `outcome=observed` for external rounds with no Quito participation. |
| `Fund` | Quito's funds. |
| `Market` | Sector/vertical hub. |
| `Artifact` | Raw content with native Blob. `source` is a coarse category (`email/chat/meeting-tool/web/doc-tool/crm/outbound/manual/derived/repo/other`); `source_app` carries the specific vendor name (`gmail`, `granola`, `slack`, `github`, etc.). |
| `Meeting` | Scheduled (or ad-hoc) event with attendees, subject, outputs. Transcript lives as `Artifact{kind=transcript|meeting-note}` linked via `ArtifactFromMeeting`. |

**Growth ring:**
| Layer | Nodes | Purpose |
|---|---|---|
| Belief | `Thesis`, `Assumption`, `Question` | Investing DNA. `Question` is the home for open uncertainties — *not* `Insight{kind=hypothesis}`. |
| Evidence | `Signal`, `Insight`, `Chunk` | What moves beliefs. `Chunk` is implementation detail. Source-reliability lives on the publishing Organization, not on a separate node. |
| Action | `Decision`, `Commitment` | What we do. Decisions are one-shot (`decided_at`); Commitments are deferred actions with deadlines. Schedule-another-meeting and flag-at-next-board are Commitments, not Decisions. |
| Reflexive | `Pattern`, `Lesson` | What we learn |

The seed contains no `Chunk` records. Create raw Chunk JSONL, run the offline `omnigraph embed --input ... --output ... --spec ... --reembed-all` file pipeline, then load the output. All other 16 node types are active.

**Core analytical loops:**

1. **Engagement** — Deal/Fund/Organization structure plus the relationship graph (`Person knows`, `decisionMakerAt`, `WouldAcquire`)
2. **Belief + Evidence** — Signal supports/contradicts Assumption|Thesis; Thesis reliesOn Assumption; Insight reliesOnSignal
3. **Decision + Learning** — Decision basedOnAssumption + needsAnswerToQuestion; Pattern across Signals/Decisions; Lesson distilledFromPattern
4. **Operational (Meetings)** — Meeting `meetingAboutDeal|Organization|Thesis|Market`; `meetingAttendedBy Person {role}`; `Artifact|Decision|Commitment fromMeeting`. Powers "show me every interaction with X" and "what was committed at the last board."

**Design choices to preserve:**

- **Slug prefix convention is mandatory** — `org-` (all Organizations, including the four source-provenance orgs `org-techcrunch`/`org-pitchbook`/`org-tegus`/`org-anonblog`), `per-`, `mkt-`, `deal-`, `fund-`, `art-`, `mtg-`, `thesis-`, `asmp-`, `q-`, `sig-`, `ins-`, `chk-`, `dec-`, `cmt-`, `pat-`, `lsn-`. The old `src-` prefix is gone — those nodes are now Organizations. Don't reintroduce it.
- **One `Organization` covers everything.** Startups, LPs, acquirers, peer VCs, customers — all `Organization` with different `kind` values. Don't reintroduce a separate `Organization` node.
- **`org-quito` is Quito itself** — a `Organization` with `kind=vc-firm`. Team members `WorksAt org-quito` (this replaces the dropped `Person.primary_relation = team` enum). Funds reference Quito implicitly via `LpInFund` from external LPs.
- **`Person` is intrinsic** — no `primary_relation` enum. Roles are derived from edges: `WorksAt org-quito` (team), `FounderOf` (founder), `LpInFund` source via `WorksAt` (LP contact), `RoleInDeal {role: founder|customer-ref|expert|co-investor-lead|co-investor-participant|board-candidate|venture-partner}` (deal-scoped roles — keep this list in sync with the enum in `schema.pg`), `DecisionMakerAt $co {kind: acquirer}` (acquirer DM).
- **`Person` enrichment fields** (`prior_exits`, `years_operating`, `education`, `prior_organizations`, `founder_score`, `last_enriched_at`) are populated by a scraping/enrichment skill, refreshed periodically.
- **One `Organization` can have many `Deal`s.** A deal is a round-level engagement. Decisions attach to Deals, not Companies. `outcome=observed` for external rounds (e.g., PitchBook imports) where Quito didn't participate.
- **`Insight.kind`** is `memo, brief, observation, recap`. `stance` (bull/bear/neutral) is separate. **`hypothesis` was removed** — open uncertainties belong on `Question`, which has the right lifecycle. Don't conflate; don't reintroduce `debate-bull/bear` kinds.
- **`Decision.kind`** is one-shot only: `invest, pass, follow-on, double-down, write-off, exit-plan, no-decision`. **Intros, follow-ups, schedule-a-second-meeting, and flag-at-next-board are `Commitment`s, not Decisions** — they have due dates and assignees, not `decided_at` timestamps. Don't reintroduce `second-meeting` or `board-flag` as Decision kinds.
- **`Decision` regards Deals (or Theses), not Companies directly.** Portco-level decisions chain via the organization's most recent Deal.
- **Source provenance lives on Organization, not on a separate node.** A publishing source (TechCrunch, PitchBook, Tegus, anon blog) is an `Organization` with `kind` in `(publisher, database, expert-network)` and a `reliability` enum (low/medium/high). When reliability drops, walk `Organization ← publishedByOrganization ← Artifact ← signalSourcedFromArtifact ← Signal` to flag downstream signals (`source-downstream-signals` alias). Don't reintroduce a separate `SourceEntity` node.
- **`Artifact.source` is a coarse category, vendor names go in `source_app`.** Use the category enum (`email, chat, meeting-tool, web, doc-tool, crm, outbound, manual, derived, repo, other`) for filtering; put the specific vendor (`gmail`, `granola`, `slack`, `github`, `lemlist`, `notion`, `zendesk`, …) in `source_app`. This keeps the schema stable when the firm switches CRM tools.
- **`Lesson.kind=protocol`** is the runtime-rules use case (declarative behavior rules the team wants agents to follow). `Lesson.status=tentative` lives on a review branch awaiting human merge.
- **Edges follow `VerbTargetType` naming** (`SignalAboutOrganization`, `DecisionBasedOnAssumption`, `LessonDistilledFromPattern`).
- **Edge traversal in queries is lowerCamelCase** even though the schema declares PascalCase (`$d forOrganization $c`).
- **`Chunk` is implementation detail for hybrid search**, not an ontological commitment. The seed has zero Chunks; populate via separate ingest.
- **Native `Blob` on `Artifact`** — collapses Drive into the graph. The seed has zero Blob payloads; populate via separate ingest.
- **USD-denominated financial fields** (`*_usd_m`) bake in a bias. Convert at recording time. Document if EUR/GBP-native sources require it.
- **`Meeting` is the operational primitive, not a duplicate of `Artifact`.** The transcript / board notes are still `Artifact{kind=transcript|meeting-note}`. The Meeting carries the things an Artifact can't: scheduled time, attendee set, status (scheduled / occurred / cancelled), and the outputs (`DecisionFromMeeting`, `CommitmentFromMeeting`) the meeting produced. When ingesting a Granola call, create the `Meeting` first, then attach the transcript via `ArtifactFromMeeting`.
- **`Meeting` outputs follow the inbound-edge convention** — `Artifact → Meeting`, `Decision → Meeting`, `Commitment → Meeting` (the dependent points to the source), mirroring `ArtifactFromPerson` and `CommitmentFromArtifact`. Don't add reverse `MeetingProduces*` edges; they'd double-count.
- **A `Meeting` can be about multiple subjects.** A partner 1:1 covering 3 deals should load 3 `MeetingAboutDeal` edges, not be split into 3 meetings.

## Data conventions

These edges do not declare pair-uniqueness constraints, so loaders and reviewers
must preserve the following conventions:

- **`Knows` is stored bidirectionally.** If A knows B, also load B knows A. Symmetric context, since, and strength on both sides. Single-direction storage made network queries quietly wrong.
- **No duplicate `(src, dst)` pairs per edge type.** Check existing edges before inserting a new relationship.
- **`Decision` provenance chain.** Every Decision should link to: (1) the Deal it regards, (2) the Assumptions it's based on, (3) the open Questions it still depends on, (4) the Person who decided. The graph snapshot at commit-time is the audit trail.

## Known gaps

- **Edge-property projections use a bound edge variable** — for example, `$p $r:roleInDeal $d` and `return { $r.role }`. `deal_role_participants` demonstrates the syntax.
- **`Chunk` is declared but the seed has zero.** Embeddings come from an offline JSONL-to-JSONL pipeline; the static seed cannot generate them and `omnigraph embed` does not mutate a graph. Hybrid search needs a separate ingest.
- **Alias parameters bind to query parameters by name.** Keep each alias's `--params` comment in `omnigraph-config.example.yaml` equal to the query's parameter names.
- **Preview schema edits through served `cluster plan`.** Apply supported changes live. If planning refuses a type change, design a data migration or rebuild into a separate fresh cluster; never delete a managed graph root behind its ledger. See [upgrading](../docs/local-setup.md#upgrading).
- **`Artifact.blob` is declared but the seed uses none.** Same status as Chunks — populate via separate ingest.

## The Demo "Wow" Queries

These are the queries the seed is shaped to light up. Preserve them when iterating.

**Engagement / network:**
| Alias | Input | Expected outcome |
|---|---|---|
| `team` | — | 7 people: CJ, Pawel, Flo, Ricardo, Louis + 2 VPs (via WorksAt org-quito) |
| `founders` | — | All Persons with at least one FounderOf edge |
| `founders-enriched` | — | Founders + enrichment fields (prior_exits, years_operating, founder_score) |
| `lp-contacts` | — | Persons working at Companies of kind=lp-institution |
| `acquirer-decision-makers` | — | DMs at Companies of kind=acquirer |
| `intro-path-to-founder` | `per-helix-yuki` | CJ → Jens → Yuki (2-hop traversal) |
| `direct-team-knowers` | `per-helix-elena` | per-pawel directly knows Elena |

**Belief / evidence:**
| Alias | Input | Expected outcome |
|---|---|---|
| `signal-portfolio-impact` | `sig-vector-forge-aws-deal` | Aetherbrick follow-on Decision flagged via contradicted Assumption |
| `pre-ic-brief-thesis` | `deal-helix-series-a` | On-prem-inference thesis + 3 grounding assumptions |
| `pre-ic-brief-evidence` | `deal-helix-series-a` | AWS-Bedrock + Microsoft-on-prem signals contradicting Helix margin |
| `debate-stances` | `deal-helix-series-a` | bull + bear Insights (now `kind=memo, stance=bull/bear`) |
| `person-insights` | `per-helix-yuki` | Founder-assessment Insight via `InsightAboutPerson` |
| `contradicted-active-theses` | — | thesis-on-prem-inference + thesis-agentic-crms |

**Portfolio + dashboards:**
| Alias | Input | Expected outcome |
|---|---|---|
| `exit-landscape` | `org-pinion-infer` | AWS, Microsoft, Google Cloud as plausible acquirers |
| `exit-landscape-decision-makers` | `org-pinion-infer` | Plus corp-dev contacts at each |
| `board-prep-pack` | `org-aetherbrick` | Recent signals (churn spike, Series B talk) |
| `reserve-pressure` | `fund-iii` | Portfolio cos in Fund III with open high-priority questions |
| `portfolio-recent-signals` | — | Cross-portco feed of changes, time-sorted |
| `observed-organizations` | — | Stripe (PitchBook-imported, no Quito engagement) |

**Provenance / source reliability:**
| Alias | Input | Expected outcome |
|---|---|---|
| `publishers` | — | TechCrunch (medium) + anon blog (low) — `Organization{kind=publisher}` |
| `databases` | — | PitchBook (high) — `Organization{kind=database}` |
| `expert-networks` | — | Tegus (high) — `Organization{kind=expert-network}` |
| `source-downstream-signals` | `org-techcrunch` | 4 Signals from medium-reliability TechCrunch artifacts |
| `sources-by-reliability` | `low` | Anonymous blog flagged |

**Reflexive:**
| Alias | Input | Expected outcome |
|---|---|---|
| `lessons-active` | — | 3 active firm lessons (on-prem protocol, vertical-moat eval, shell anti-pattern) |
| `lessons-tentative` | — | The "second-time founder bias" lesson awaiting review |

**Operational (Meetings):**
| Alias | Input | Expected outcome |
|---|---|---|
| `meetings-upcoming` | — | Helix IC (June 20), Aetherbrick Q2 board (July 9), Axon final ref (June 9) |
| `meetings-with-organization` | `org-aetherbrick` | Q1 board (occurred April 8) + Q2 board (scheduled July 9) |
| `meetings-with-deal` | `deal-helix-series-a` | Founder call (April 12, occurred) + IC (June 20, scheduled) |
| `board-meetings-for-organization` | `org-aetherbrick` | The Q1 board (occurred) — head row for the "last board" view |
| `meeting-decisions` | `mtg-axon-ic-2026-05` | `dec-axon-ic-recommend-invest` |
| `meeting-commitments` | `mtg-aetherbrick-board-q1-2026` | `cmt-aetherbrick-board-prep` |
| `ic-prep-meeting-history` | `deal-helix-series-a` | Helix founder call (April) — what was discussed before IC |
| `ic-prep-open-commitments` | `deal-helix-series-a` | `cmt-helix-customer-refs` — what's still owed before IC |

If a schema or seed change breaks any of these, the OS lens is not delivering — fix the seed rather than compromising the schema.

## Agent Workflow

Use this cookbook as a decision-intelligence + audit loop, not a lookup table:

1. **Start from intent** — a Deal, a Signal, a Thesis, an upcoming board meeting.
2. **Expand context** with aliases like `deal-signals`, `deal-decisions`, `thesis-assumptions`, `board-prep-pack`.
3. **Trace evidence** with `assumption-supports` / `assumption-contradictions`, `signal-supports-assumptions` / `signal-contradicts-assumptions`.
4. **Capture new input** as an `Artifact` first (raw), then derived `Insight` / `Signal` if synthesized (use `ArtifactDerivedFrom` with `activity` enum).
5. **Wire mentions** — `SignalAboutOrganization`, `ArtifactMentionsPerson`, etc., so future queries find it.
6. **Promote to action** — Decision or Commitment with the full provenance chain.
7. **Distill into Lessons** — when a Pattern emerges across multiple Decisions, capture as a `Lesson` on a branch; merge after human review.

For longer-form captures (transcripts, decks), chunk into `Chunk` records linked via `ChunkOfArtifact`. Hybrid search runs on those once embeddings are populated.

## Commands for the README's questions

Aliases come from `omnigraph-config.example.yaml`; each is `omnigraph query <name> --target local-reader --graph vcos`.

| Question | Command |
|---|---|
| Which active theses has new evidence contradicted? | `omnigraph alias contradicted-active-theses` |
| Before investment committee, what contradicts the assumptions behind this deal? | `omnigraph alias pre-ic-brief-evidence --params '{"slug":"deal-helix-series-a"}'` |
| Who on the team can get an introduction to this founder? | `omnigraph alias intro-path-to-founder --params '{"slug":"per-helix-yuki"}'` |
| What have the portfolio companies reported recently? | `omnigraph query portfolio_updates_recent --target local-reader --graph vcos` |

More reads, with the alias bundles grouped by meeting view in the example config (`VIEW: IC Meeting`, `VIEW: Weekly Pipeline Meeting`, `VIEW: Portfolio Support Meeting`, `VIEW: LPAC / Fund Reporting`):

```bash
omnigraph alias team
omnigraph alias founders-enriched
omnigraph alias signal-portfolio-impact --params '{"slug":"sig-vector-forge-aws-deal"}'
omnigraph alias exit-landscape --params '{"slug":"org-pinion-infer"}'
omnigraph alias debate-stances --params '{"slug":"deal-helix-series-a"}'
omnigraph alias board-prep-pack --params '{"slug":"org-aetherbrick"}'
omnigraph alias reserve-pressure --params '{"fund_slug":"fund-iii"}'
omnigraph alias lessons-active
omnigraph alias source-downstream-signals --params '{"slug":"org-techcrunch"}'
omnigraph alias observed-organizations
```

`board_prep_pack` returns every signal about the organization, newest first. It does not cut at the last board meeting. Pair it with `board_meetings_for_organization` and compare dates yourself.

## Workflows, step by step

The README's table names the workflows; the detail is here. All writes go on a branch (`--branch tentative/<topic>`), and a partner merges. Nothing in the policy forces this: `act-writer` may write and merge `main` (see `policies/graph.policy.yaml`). There is no agent role, so run agents with their own branch and review the commit actors before merging.

The record has no stored write that updates an existing node: the 87 stored writes are `add_*` and `link_*`. So a workflow cannot close a commitment, resolve a question, change a thesis's status, activate a tentative lesson, lower a source's reliability or note that a reminder was sent. A person does these, or an ad-hoc mutation on a branch that a person reviews. The README does not document an ad-hoc mutation as the way.

### Call intake (capture)

Starts when a call recording lands (for example Granola). Read the Meeting and attendees, the deal's thesis and assumptions, its open questions and prior similar signals (`ic_prep_meeting_history`, `deal_open_questions`, `thesis_assumptions`). Write on `tentative/ingest-<meeting-slug>`: the transcript as an Artifact (`source=meeting-tool`, `source_app=granola`), `link_artifact_from_meeting`, 0–3 Signals each linked `supports`/`contradicts` against the right Assumption, and Commitments with an assignee (`link_commitment_assigned_to`) and `link_commitment_from_meeting`; `add_commitment` takes no due date, so a person sets it. Resolve mentioned people and organizations; flag the ones that do not resolve instead of inventing them. One atomic branch, so a failed mutation leaves no orphan signals. The agent keeps its own cursor of the last call it ingested.

### Scout triage (capture)

Starts daily, from the scout list, launch feeds, watches or founder messages. For each mention run `search_organizations` for the dedup verdict. A match with `status=passed` resurfaces the prior pass Decision (`organization_deals`, `deal_decisions`). A new one gets `add_organization`, `link_organization_in_market`, a discovery Signal and the source as an Artifact (`link_signal_sourced_from_artifact`), on `tentative/scout-<org>-<date>`. `add_organization` sets no `status`, so the new organization is not in `organizations_by_status` until a person sets it. Look at active Lessons and failure-mode Patterns in the market (`market_lessons`). Do not invent founder names.

### Evidence check and thesis review (maintain)

Starts when a signal lands. Run `recent_contradictions` and `signal_portfolio_impact` for it, then `contradicted_active_theses` and `thesis_contradictions_via_assumptions`. The result is a report for a partner; changing a thesis's status is a person's edit.

### Bull and bear cases (maintain)

Starts 48 hours before a high-conviction IC. One agent per stance reads the deal, thesis, assumptions, market signals and existing insights, then writes one Insight on the shared branch `tentative/ic-debate-<deal>`:

```bash
omnigraph mutate add_insight_with_stance --target local-writer --graph vcos --branch tentative/ic-debate-<deal> --params '{…}'
```

Cite signals with `link_insight_relies_on_signal`, the deal with `link_insight_about_deal` and any pattern with `link_insight_highlights_pattern`. The neutral agent names the evidence that would settle the disagreement. Bull and bear linking the same pattern with opposite framings makes the disagreement legible.

### Learning sweep (maintain)

Starts quarterly. Read the window's Decisions, Patterns with `pattern_decisions`, and `lessons_active`. A Pattern with three or more supporting Decisions and one consistent outcome, not already covered by an active Lesson, gets a tentative `add_lesson` with `link_lesson_distilled_from` and `link_lesson_applies_to_market` on its own branch. Report what landed, what was covered and where evidence is thin; a sweep that always proposes a lesson is hallucinating.

### Pre-IC brief, board prep, founder call brief (act)

Start from the calendar (`meetings_upcoming`), 24 hours ahead. Read by meeting kind. IC: `pre_ic_brief_organization`, `pre_ic_brief_thesis`, `pre_ic_brief_evidence`, `pre_ic_brief_questions`, `pre_ic_brief_debate`, `ic_prep_meeting_history`, `ic_prep_open_commitments`; all take the Deal slug. Board: `board_prep_pack`, `board_prep_open_questions`, `board_prep_commitments`. Founder call: `get_person`, `person_insights`, `intro_path_to_founder`. These write nothing; the brief goes back through the channel that asked. About eight reads against one commit-pinned snapshot, so the brief can be re-run at the same commit months later.

## Key enums

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


## What this cookbook does not do

- No connectors. Syncs are scripts or agents calling the stored mutations.
- No stored update, so status changes need an ad-hoc mutation on a branch.
- No agent role limited to branches (unlike company-brain and hardware-program).
- No embeddings or blobs in the seed; real ones are a separate ingest (see Known gaps).
- Deferred: firm-specific authorization for team, LP and portfolio access; sector-specialist Pattern and Lesson packs as sibling cookbooks; a `Measurement` node for KPI, cash and runway time series (today loosely `Signal{kind=portfolio-update}`).

## Adapting for your firm

1. Keep the schema; most firms fit the 17 nodes.
2. Replace the seed with your organizations, theses, people and decisions: current pipeline and portfolio first, history later.
3. Change `Market` rows and the Pattern and Lesson content for a different sector focus.
4. Wire tools as ingest: Granola → `Artifact{kind=transcript, source=meeting-tool, source_app=granola}`; Slack → `Artifact{kind=chat-msg, source=chat, source_app=slack}`; email → `Artifact{kind=email, source=email, source_app=gmail}`. The CRM is replaced; everything else feeds in by mutation.
5. Run the example reads on your data. An empty one means the seed under-models the loop; fix the seed, not the schema.

## When Editing

- Consult [Omnigraph schema principles](https://github.com/ModernRelay/omnigraph) for design guidance.
- Use `@rename_from(...)` on property/type renames for migration support.
- Keep README.md in sync with schema.pg: it names types, and the check reads them.
- Prefer semantic edge names (`ContradictsAssumption`, `DecisionBasedOnAssumption`, not `RelatedTo`).
- Required vs optional is deliberate — don't add `?` without reason.
- New node types need a strong case — most concepts fit as a `kind` enum on an existing node.
- New edge types should answer a real query — don't add edges speculatively.
- Resist scope creep: this cookbook is **a VC's full operating system, not other knowledge-work firms**. Adjacent professions (law, consulting, family office) belong in sibling cookbooks that mirror this layering.
