# CLAUDE.md — vc-os

Scoped guidance for the `vc-os/` cookbook. Repo-wide conventions live in `../CLAUDE.md`. For general Omnigraph ops — schema authoring, queries, loading, branches, cluster commands, the CLI — use the **omnigraph** skill rather than re-deriving them here; this file covers only what's specific to VC OS.

## What This Is

An Omnigraph schema + seed modeling a venture-capital firm's full operating system. Not just an intelligence layer (signals/patterns/insights) but engagement (deals, funds), action (decisions, commitments), and reflexive learning (patterns, lessons) — all in one typed graph. Schema, seed data, and queries only — no application code.

The reference seed is a **fictional Berlin-based AI-infra fund** ("Quito Capital") running Fund III ($250M, vintage 2024). All names, organizations, deals, and people are fabricated. The seed exists to shape the demo queries, not to model a real firm.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — The landing page: data model, workflows, sources, questions. Follows the root template; commands live here, not there.
- `seed.md` / `seed.jsonl` — Reference seed (human-readable / loadable).
- `queries/*.gq` — Read and mutation queries. One file per domain.
- `cluster.yaml` — Deployment declaration (graph `vcos`, schema, stored queries).
- `omnigraph-config.example.yaml` — Read aliases. Your operator config is per-user at `$OMNIGRAPH_HOME/config.yaml` (never committed); merge this file's aliases into it. Aliases bind to the stored queries published by `cluster apply`.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

## Setup

Use the shared [local setup](../README.md#local-setup) with cookbook
`vc-os` and graph `vcos`. It owns authentication, the bootstrap writer-lock
handoff, readiness, and served seed loading. Apply later configuration edits with
the [live update workflow](../README.md#live-updates).

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
- **Preview schema edits through served `cluster plan`.** Apply supported changes live. If planning refuses a type change, design a data migration or rebuild into a separate fresh cluster; never delete a managed graph root behind its ledger. See [upgrading](../README.md#upgrading).
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

## Questions

The four questions `site.json` features, and the command for each:

```bash
omnigraph query contradicted_active_theses --target local-reader --graph vcos
omnigraph query pre_ic_brief_evidence --target local-reader --graph vcos --params '{"slug":"deal-helix-series-a"}'
omnigraph query intro_path_to_founder --target local-reader --graph vcos --params '{"slug":"per-helix-yuki"}'
omnigraph query board_prep_pack --target local-reader --graph vcos --params '{"slug":"org-aetherbrick"}'
```

`board_prep_pack` returns every signal about the organization, newest first. It does not cut at the last board meeting; compare dates with `board_meetings_for_organization`.

## Workflows

Common shape: the agent proposes on a branch (`omnigraph branch create <name> --target local-writer --graph vcos`, then `--branch <name>` on each mutation), a partner reads `omnigraph branch diff` and `omnigraph branch merge <name> --into main --dry-run`, then merges. Agents never invent slugs or people: run `search_organizations`, `search_people` or `search_signals` first and flag what does not resolve. Slugs use the prefixes under "Design choices". Every write supplies `createdAt` and `updatedAt`.

### Call intake (capture)

Starts: a call ends. Reads: `get_meeting`, `meeting_attendees`, the deal's `pre_ic_brief_thesis` and `deal_open_questions`, and `search_signals` so a new signal is not a duplicate. Branch `ingest-<meeting-slug>`.

```bash
omnigraph mutate add_artifact --target local-writer --graph vcos --branch ingest-mtg-x --params '{"slug":"art-x","name":"Call transcript","kind":"transcript","source":"meeting-tool","source_app":"granola","date":"2026-09-14","captured_at":"2026-09-14T12:00:00Z","createdAt":"2026-09-14T12:00:00Z","updatedAt":"2026-09-14T12:00:00Z"}'
omnigraph mutate link_artifact_from_meeting --target local-writer --graph vcos --branch ingest-mtg-x --params '{"artifact":"art-x","meeting":"mtg-x"}'
```

Then `add_signal` with `link_signal_sourced_from_artifact`, `link_signal_about_organization` and `link_supports_assumption` or `link_contradicts_assumption`; and `add_commitment` with `link_commitment_from_meeting` and `link_commitment_assigned_to`. Create the Meeting first with `add_meeting` if none exists. Person: a partner reviews the branch. Repeat: the transcript's Artifact exists, so check `search_signals` and `meeting_artifacts` before ingesting the same meeting.

### Signal intake (capture)

Starts: an article, scout note, founder update or outbound reply. Reads `search_organizations` (a name that matches a passed deal: read `deal_decisions` and tie to the pass), `search_signals`. Writes on `signal-<org>-<date>`: `add_artifact` for the source, `link_published_by_organization`, `add_signal`, `link_signal_about_organization`, `link_signal_sourced_from_artifact`, and `link_informs_question` where a live question is concerned. Add a new organization only when search finds none.

### Wiki sync (capture)

Starts: a commit to the partners' notes repository. Writes `add_markdown_artifact` (see its signature) and `link_artifact_documents_thesis`, `link_artifact_documents_lesson` or `link_artifact_documents_pattern`. Reads `markdown_artifacts_in_repo`, `theses_active_for_doc_review`.

### Belief check (maintain)

Starts: a signal is merged. Reads `signal_contradicts_assumptions`, `signal_contradicts_theses`, `signal_portfolio_impact`, `signal_engagement_impact`, `contradicted_active_theses`. Writes on a branch: `add_question` (status open) and `link_question_about_deal` where the contradiction needs an answer. It does not change a thesis's status; the stored mutations only add. A partner decides what a contradicted thesis means.

### Source reliability sweep (maintain)

Starts: a source's `reliability` drops. Reads `sources_by_reliability`, then `source_downstream_signals` for each source. Output is the list of signals to re-read; no stored mutation changes a rating or a signal.

### IC debate (maintain)

Starts: an IC meeting 48 hours away. Three agents (bull, bear, neutral) read `pre_ic_brief_thesis`, `pre_ic_brief_evidence`, `debate_stances`, then each writes one insight on the shared branch `ic-debate-<deal>`:

```bash
omnigraph mutate add_insight_with_stance --target local-writer --graph vcos --branch ic-debate-deal-x --params '{"slug":"ins-x-bear","name":"Bear case","kind":"memo","stance":"bear","summary":"...","createdAt":"2026-09-14T00:00:00Z","updatedAt":"2026-09-14T00:00:00Z"}'
```

Link it with `link_insight_about_deal` and `link_insight_relies_on_signal` for each cited signal. Cite only linked signals. The neutral agent names the evidence that would settle the disagreement.

### Learning sweep (maintain)

Starts: quarter end. Reads `patterns_all`, `pattern_decisions`, `lessons_active`. For a pattern with three or more decisions of one outcome and no active lesson, write on `tentative-<date>`:

```bash
omnigraph mutate add_lesson --target local-writer --graph vcos --branch tentative-2026-q3 --params '{...}'   # status tentative, as in Writing above
omnigraph mutate link_lesson_distilled_from --target local-writer --graph vcos --branch tentative-2026-q3 --params '{"lesson":"lsn-x","pattern":"pat-x"}'
```

Add `link_lesson_applies_to_market`. A partner merges or deletes the branch; `lessons_tentative` lists what waits. Report what was already covered and what had too little evidence.

### Pre-IC brief (act)

Starts: `meetings_upcoming` shows an IC within 24 hours. Reads, all with the deal slug: `pre_ic_brief_organization`, `pre_ic_brief_thesis`, `pre_ic_brief_evidence`, `pre_ic_brief_questions`, `pre_ic_brief_debate`, `ic_prep_meeting_history`, `ic_prep_open_commitments`. Writes nothing. The agent drafts the brief for the partners and sends it with its own tools; the record keeps no note that it went out, so the agent tracks that. Re-running is harmless.

### Board prep pack (act)

Starts: `upcoming_board_meetings_for_organization` returns a meeting within the week. Reads `board_prep_pack`, `board_prep_open_questions`, `board_prep_commitments`, `board_meetings_for_organization`. Keep only signals dated after the last board. Draft and send to the lead partner. No record of sending.

### Commitment nudges (act)

Starts: a daily date check. Reads `commitments_open`, `portfolio_open_commitments`, `commitment_assigned_to`. Messages each owner with the open commitments past `due_date`. The record has no reminder field, and no stored mutation sets a commitment's status or `completed_at`, so the agent keeps its own log and a partner closes a commitment with an ad-hoc `omnigraph mutate -e` on a branch.

### Intro requests (act)

Starts: a partner asks for an intro to a founder. Reads `direct_team_knowers`, then `intro_path_to_founder`. Drafts the ask to the person in between; a partner sends it.

### Agents and access

The policy has `act-admin`, `act-writer` and `act-reader` only. `act-writer` can write `main` and merge. Run read-only agents as `local-reader`. For an agent that writes, add an `act-agent` role as in `../hardware-program/policies/graph.policy.yaml` through `cluster plan` and `apply`, with task authorization. Until then, review is by convention: the agent writes on a branch and every commit records its actor. Over MCP, `omnigraph mcp --target local-reader --graph vcos` relays reads.

## What it does not do

- No connectors: Granola, Gmail, Slack, CRMs, PitchBook and the rest are read by your own script or agent.
- No stored mutation updates or deletes: `add_*` and `link_*` only. Changing a commitment's status, a thesis's status or a rating, merging duplicate organizations, or retiring a stale signal needs an ad-hoc mutation on a branch.
- No agent role in the access policy (see above).
- No place to record that a brief or reminder was sent.
- No embeddings, blobs or `Chunk` rows in the seed, so hybrid search returns nothing until you ingest.
- Money fields are USD only.

## When Editing

- Consult [Omnigraph schema principles](https://github.com/ModernRelay/omnigraph) for design guidance.
- Use `@rename_from(...)` on property/type renames for migration support.
- Keep README.md in sync with schema.pg.
- Prefer semantic edge names (`ContradictsAssumption`, `DecisionBasedOnAssumption`, not `RelatedTo`).
- Required vs optional is deliberate — don't add `?` without reason.
- New node types need a strong case — most concepts fit as a `kind` enum on an existing node.
- New edge types should answer a real query — don't add edges speculatively.
- Resist scope creep: this cookbook is **a VC's full operating system, not other knowledge-work firms**. Adjacent professions (law, consulting, family office) belong in sibling cookbooks that mirror this layering.
