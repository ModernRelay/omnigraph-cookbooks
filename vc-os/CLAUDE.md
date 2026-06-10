# CLAUDE.md — vc-os

Scoped guidance for the `vc-os/` cookbook. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

An Omnigraph schema + seed modeling a venture-capital firm's full operating system. Not just an intelligence layer (signals/patterns/insights) but engagement (deals, funds), action (decisions, commitments), and reflexive learning (patterns, lessons) — all in one typed graph. Schema, seed data, and queries only — no application code.

The reference seed is a **fictional Berlin-based AI-infra fund** ("Quito Capital") running Fund III ($250M, vintage 2024). All names, organizations, deals, and people are fabricated. The seed exists to shape the demo queries, not to model a real firm.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — Design rationale, collapsed stack analysis, killer queries.
- `seed.md` / `seed.jsonl` — Reference seed (human-readable / loadable).
- `queries/*.gq` — Read and mutation queries. One file per domain.
- `omnigraph.yaml` — CLI config with 294 aliases.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

## Schema Language (`.pg`)

- `node` defines entity types; `edge` defines typed relationships (`edge Name: Source -> Target`)
- `@key` marks external identity (always `slug` here)
- `@index`, `@unique`, `@card(min..max)`, `@embed("prop")`
- `?` = optional, `[Type]` = list of scalar (no lists of enum), `enum(...)` = inline closed set
- Comments use `//` not `#`

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

v1 seed ships `Chunk` zero (populate via `omnigraph embed --reembed_all`). All other 16 node types active.

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
- **`Chunk` is implementation detail for hybrid search**, not an ontological commitment. v1 seed has zero Chunks; populate via separate ingest.
- **Native `Blob` on `Artifact`** — collapses Drive into the graph. v1 seed has zero blob payloads; populate via separate ingest.
- **USD-denominated financial fields** (`*_usd_m`) bake in a bias. Convert at recording time. Document if EUR/GBP-native sources require it.
- **`Meeting` is the operational primitive, not a duplicate of `Artifact`.** The transcript / board notes are still `Artifact{kind=transcript|meeting-note}`. The Meeting carries the things an Artifact can't: scheduled time, attendee set, status (scheduled / occurred / cancelled), and the outputs (`DecisionFromMeeting`, `CommitmentFromMeeting`) the meeting produced. When ingesting a Granola call, create the `Meeting` first, then attach the transcript via `ArtifactFromMeeting`.
- **`Meeting` outputs follow the inbound-edge convention** — `Artifact → Meeting`, `Decision → Meeting`, `Commitment → Meeting` (the dependent points to the source), mirroring `ArtifactFromPerson` and `CommitmentFromArtifact`. Don't add reverse `MeetingProduces*` edges; they'd double-count.
- **A `Meeting` can be about multiple subjects.** A partner 1:1 covering 3 deals should load 3 `MeetingAboutDeal` edges, not be split into 3 meetings.

## Conventions enforced by load discipline (not the schema)

As of MR-983 (PR #133, engine v0.6.3+), `@unique(src, dst)` enforces pair-uniqueness as a true composite key (previously it degraded into two per-column checks) — covering single-batch load/insert/update and branch-merge, but not cross-operation duplicates against already-committed rows. These edges don't declare it yet, so the conventions below still live in the loader/reviewer:

- **`Knows` is stored bidirectionally.** If A knows B, also load B knows A. Symmetric context, since, and strength on both sides. Single-direction storage made network queries quietly wrong. (Unaffected by the `@unique` fix — it's about storing the inverse edge, not deduping pairs.)
- **No duplicate `(src, dst)` pairs per edge type.** Now schema-enforceable via `@unique(src, dst)` (within a load/merge); still dedupe across separate write operations.
- **`Decision` provenance chain.** Every Decision should link to: (1) the Deal it regards, (2) the Assumptions it's based on, (3) the open Questions it still depends on, (4) the Person who decided. The graph snapshot at commit-time is the audit trail.

## Known gaps

- **Edge-property projections aren't supported in queries** — `Knows.strength`, `WorksAt.role`, `RoleInDeal.role`, `BoardMemberAt.role`, etc. are stored but cannot be returned in `read` results. Filter in the writer; surface via dedicated read-side helpers if needed.
- **`Chunk` is declared but the seed has zero.** Embeddings come from a separate ingest pipeline (`omnigraph embed --reembed_all`); the static seed can't generate them. Hybrid search is a v1-deferred capability.
- **Alias args bind to query parameters by *name*, not position.** An alias `args: [slug]` only binds to a query that declares `$slug`. Renaming the alias arg to `[deal_slug]` without also renaming `$slug → $deal_slug` in the query silently drops the filter — the query then matches every row instead of one. If you want clearer arg names, rename in *both* places; otherwise add a comment block above the alias group explaining the input semantics.
- **Adding values to an existing enum requires a wipe + re-init + reload (still true as of Omnigraph 0.6.1).** `schema apply` (even with `--allow-data-loss`) rejects enum extensions as destructive type changes (`OG-MF-106` — "changing property type ... not supported in schema migration v1"; `SCHEMA_IR_VERSION` is still 1 in 0.6.1). The migration path is: kill the server, `aws s3 rm s3://<bucket>/repos/<name>/ --recursive` (run twice — first pass leaves a handful of files), `omnigraph init --schema schema.pg`, `omnigraph load --data <stripped-seed>.jsonl --mode overwrite`. Reload takes ~10–15 min for a 200-node / 400-edge seed. Batch multiple enum or property-type changes into one wipe-reload cycle — single-change wipes aren't worth the cost.
- **`omnigraph-server` (v0.6.0+) requires auth or explicit `--unauthenticated`.** Cedar policy enforcement is now engine-wide and the server refuses to start without bearer tokens, a policy file, or `--unauthenticated` (env: `OMNIGRAPH_UNAUTHENTICATED=1`). For local dev, set the env var. For Railway/production, configure a Cedar policy YAML. Note (v0.6.1): with a **named** graph, the policy file must be nested under `graphs.<name>.policy`, not top-level, or the server refuses to boot.
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

## Validation

```bash
omnigraph lint --schema ./schema.pg --query ./queries/deals.gq
```

The `lint` command validates both queries and schema against each other — use after any schema or query edit. Pure file check; no server needed. (`query lint` still works as a deprecated alias.)

## When Editing

- Consult [Omnigraph schema principles](https://github.com/ModernRelay/omnigraph) for design guidance.
- Use `@rename_from(...)` on property/type renames for migration support.
- Keep README.md in sync with schema.pg.
- Prefer semantic edge names (`ContradictsAssumption`, `DecisionBasedOnAssumption`, not `RelatedTo`).
- Required vs optional is deliberate — don't add `?` without reason.
- New node types need a strong case — most concepts fit as a `kind` enum on an existing node.
- New edge types should answer a real query — don't add edges speculatively.
- Resist scope creep: this cookbook is **a VC's full operating system, not other knowledge-work firms**. Adjacent professions (law, consulting, family office) belong in sibling cookbooks that mirror this layering.
