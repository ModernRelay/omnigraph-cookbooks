# CLAUDE.md — vc-os

Scoped guidance for the `vc-os/` cookbook. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

An Omnigraph schema + seed modeling a venture-capital firm's full operating system. Not just an intelligence layer (signals/patterns/insights) but engagement (deals, funds), action (decisions, commitments), and reflexive learning (patterns, lessons) — all in one typed graph. Schema, seed data, and queries only — no application code.

The reference seed is a **fictional Berlin-based AI-infra fund** ("Quito Capital") running Fund III ($250M, vintage 2024). All names, companies, deals, and people are fabricated. The seed exists to shape the demo queries, not to model a real firm.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — Design rationale, collapsed stack analysis, killer queries.
- `seed.md` / `seed.jsonl` — Reference seed (human-readable / loadable).
- `queries/*.gq` — Read and mutation queries. One file per domain.
- `omnigraph.yaml` — CLI config with ~140 aliases.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

## Schema Language (`.pg`)

- `node` defines entity types; `edge` defines typed relationships (`edge Name: Source -> Target`)
- `@key` marks external identity (always `slug` here)
- `@index`, `@unique`, `@card(min..max)`, `@embed("prop")`
- `?` = optional, `[Type]` = list of scalar (no lists of enum), `enum(...)` = inline closed set
- Comments use `//` not `#`

## Domain Model

**Core (6) + Growth ring (11) = 17 nodes total.** The core is stable for years; the growth ring evolves as the firm learns.

**Core:**
| Node | Purpose |
|---|---|
| `Company` | Universal entity. `kind` enum: startup/lp-institution/vc-firm/acquirer/customer/bank/regulator/accelerator/family-office/etc. Quito itself is `co-quito` (kind=vc-firm). |
| `Person` | Individual human. Roles relative to Quito live on edges, not on the node. |
| `Deal` | A funding event involving a Company. `outcome=observed` for external rounds with no Quito participation. |
| `Fund` | Quito's funds. |
| `Market` | Sector/vertical hub. |
| `Artifact` | Raw content with native Blob. |

**Growth ring:**
| Layer | Nodes | Purpose |
|---|---|---|
| Belief | `Thesis`, `Assumption`, `Question` | Investing DNA |
| Evidence | `Signal`, `Insight`, `SourceEntity`, `Chunk` | What moves beliefs. `SourceEntity` enables reliability-driven signal revalidation. `Chunk` is implementation detail. |
| Action | `Decision`, `Commitment` | What we do. Decisions are one-shot; Commitments are deferred actions with deadlines. |
| Reflexive | `Pattern`, `Lesson` | What we learn |

v1 seed ships `Chunk` zero (populate via `omnigraph embed --reembed_all`). All other 16 active.

**Core analytical loops:**

1. **Engagement** — Deal/Fund/Company structure plus the relationship graph (`Person knows`, `decisionMakerAt`, `WouldAcquire`)
2. **Belief + Evidence** — Signal supports/contradicts Assumption|Thesis; Thesis reliesOn Assumption; Insight reliesOnSignal
3. **Decision + Learning** — Decision basedOnAssumption + needsAnswerToQuestion; Pattern across Signals/Decisions; Lesson distilledFromPattern

**Design choices to preserve:**

- **Slug prefix convention is mandatory** — `co-` (all Companies, regardless of kind), `per-`, `mkt-`, `deal-`, `fund-`, `art-`, `thesis-`, `asmp-`, `q-`, `sig-`, `ins-`, `src-`, `chk-`, `dec-`, `cmt-`, `pat-`, `lsn-`. Don't break it.
- **One `Company` covers everything.** Startups, LPs, acquirers, peer VCs, customers — all `Company` with different `kind` values. Don't reintroduce a separate `Organization` node.
- **`co-quito` is Quito itself** — a `Company` with `kind=vc-firm`. Team members `WorksAt co-quito` (this replaces the dropped `Person.primary_relation = team` enum). Funds reference Quito implicitly via `LpInFund` from external LPs.
- **`Person` is intrinsic** — no `primary_relation` enum. Roles are derived from edges: `WorksAt co-quito` (team), `FounderOf` (founder), `LpInFund` source via `WorksAt` (LP contact), `RoleInDeal {role: expert|customer-ref|venture-partner}` (deal-scoped roles), `DecisionMakerAt $co {kind: acquirer}` (acquirer DM).
- **`Person` enrichment fields** (`prior_exits`, `years_operating`, `education`, `prior_companies`, `founder_score`, `last_enriched_at`) are populated by a scraping/enrichment skill, refreshed periodically.
- **One `Company` can have many `Deal`s.** A deal is a round-level engagement. Decisions attach to Deals, not Companies. `outcome=observed` for external rounds (e.g., PitchBook imports) where Quito didn't participate.
- **`Insight.kind`** is `memo, brief, observation, hypothesis, recap`. `stance` (bull/bear/neutral) is separate. Don't conflate; don't reintroduce `debate-bull/bear` kinds.
- **`Decision.kind`** is one-shot only: `invest, pass, follow-on, board-flag, double-down, write-off, exit-plan, second-meeting, no-decision`. Intros and follow-ups are `Commitment`s, not Decisions.
- **`Decision` regards Deals (or Theses), not Companies directly.** Portco-level decisions chain via the company's most recent Deal.
- **`SourceEntity`** carries provenance + reliability. When a source's reliability drops, all `Signal`s sourced from `Artifact`s `PublishedBySource` it can be flagged via `source-downstream-signals`.
- **`Lesson.kind=protocol`** is the runtime-rules use case (declarative behavior rules the team wants agents to follow). `Lesson.status=tentative` lives on a review branch awaiting human merge.
- **Edges follow `VerbTargetType` naming** (`SignalAboutCompany`, `DecisionBasedOnAssumption`, `LessonDistilledFromPattern`).
- **Edge traversal in queries is lowerCamelCase** even though the schema declares PascalCase (`$d forCompany $c`).
- **`Chunk` is implementation detail for hybrid search**, not an ontological commitment. v1 seed has zero Chunks; populate via separate ingest.
- **Native `Blob` on `Artifact`** — collapses Drive into the graph. v1 seed has zero blob payloads; populate via separate ingest.
- **USD-denominated financial fields** (`*_usd_m`) bake in a bias. Convert at recording time. Document if EUR/GBP-native sources require it.

## Conventions enforced by load discipline (not the schema)

Omnigraph 0.4.x's `@unique(src, dst)` is two separate per-column constraints, not pair-uniqueness. These conventions therefore live in the loader/reviewer:

- **`Knows` is stored bidirectionally.** If A knows B, also load B knows A. Symmetric context, since, and strength on both sides. Single-direction storage made network queries quietly wrong.
- **No duplicate `(src, dst)` pairs per edge type.** Dedupe before insert.
- **`Decision` provenance chain.** Every Decision should link to: (1) the Deal it regards, (2) the Assumptions it's based on, (3) the open Questions it still depends on, (4) the Person who decided. The graph snapshot at commit-time is the audit trail.

## Known gaps

- **Edge-property projections aren't supported in queries** — `Knows.strength`, `WorksAt.role`, `RoleInDeal.role`, `BoardMemberAt.role`, etc. are stored but cannot be returned in `read` results. Filter in the writer; surface via dedicated read-side helpers if needed.
- **`Chunk` is declared but the seed has zero.** Embeddings come from a separate ingest pipeline (`omnigraph embed --reembed_all`); the static seed can't generate them. Hybrid search is a v1-deferred capability.
- **`Artifact.blob` is declared but the seed uses none.** Same status as Chunks — populate via separate ingest.

## The Demo "Wow" Queries

These are the queries the seed is shaped to light up. Preserve them when iterating.

**Engagement / network:**
| Alias | Input | Expected outcome |
|---|---|---|
| `team` | — | 7 people: CJ, Pawel, Flo, Ricardo, Louis + 2 VPs (via WorksAt co-quito) |
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
| `exit-landscape` | `co-pinion-infer` | AWS, Microsoft, Google Cloud as plausible acquirers |
| `exit-landscape-decision-makers` | `co-pinion-infer` | Plus corp-dev contacts at each |
| `board-prep-pack` | `co-aetherbrick` | Recent signals (churn spike, Series B talk) |
| `reserve-pressure` | `fund-iii` | Portfolio cos in Fund III with open high-priority questions |
| `portfolio-recent-signals` | — | Cross-portco feed of changes, time-sorted |
| `observed-companies` | — | Stripe (PitchBook-imported, no Quito engagement) |

**Provenance / source reliability:**
| Alias | Input | Expected outcome |
|---|---|---|
| `sources` | — | 5 SourceEntity rows with reliability |
| `source-downstream-signals` | `src-techcrunch` | All Signals from medium-reliability TechCrunch artifacts |
| `sources-by-reliability` | `low` | Anonymous blog source flagged |

**Reflexive:**
| Alias | Input | Expected outcome |
|---|---|---|
| `lessons-active` | — | 3 active firm lessons (on-prem protocol, vertical-moat eval, shell anti-pattern) |
| `lessons-tentative` | — | The "second-time founder bias" lesson awaiting review |

If a schema or seed change breaks any of these, the OS lens is not delivering — fix the seed rather than compromising the schema.

## Agent Workflow

Use this cookbook as a decision-intelligence + audit loop, not a lookup table:

1. **Start from intent** — a Deal, a Signal, a Thesis, an upcoming board meeting.
2. **Expand context** with aliases like `deal-signals`, `deal-decisions`, `thesis-assumptions`, `board-prep-pack`.
3. **Trace evidence** with `assumption-supports` / `assumption-contradictions`, `signal-supports-assumptions` / `signal-contradicts-assumptions`.
4. **Capture new input** as an `Artifact` first (raw), then derived `Insight` / `Signal` if synthesized (use `ArtifactDerivedFrom` with `activity` enum).
5. **Wire mentions** — `SignalAboutCompany`, `ArtifactMentionsPerson`, etc., so future queries find it.
6. **Promote to action** — Decision or Commitment with the full provenance chain.
7. **Distill into Lessons** — when a Pattern emerges across multiple Decisions, capture as a `Lesson` on a branch; merge after human review.

For longer-form captures (transcripts, decks), chunk into `Chunk` records linked via `ChunkOfArtifact`. Hybrid search runs on those once embeddings are populated.

## Validation

```bash
omnigraph query lint --schema ./schema.pg --query ./queries/deals.gq
```

The `query lint` command validates both queries and schema against each other — use after any schema or query edit. Pure file check; no server needed.

## When Editing

- Consult [Omnigraph schema principles](https://github.com/ModernRelay/omnigraph) for design guidance.
- Use `@rename_from(...)` on property/type renames for migration support.
- Keep README.md in sync with schema.pg.
- Prefer semantic edge names (`ContradictsAssumption`, `DecisionBasedOnAssumption`, not `RelatedTo`).
- Required vs optional is deliberate — don't add `?` without reason.
- New node types need a strong case — most concepts fit as a `kind` enum on an existing node.
- New edge types should answer a real query — don't add edges speculatively.
- Resist scope creep: this cookbook is **a VC's full operating system, not other knowledge-work firms**. Adjacent professions (law, consulting, family office) belong in sibling cookbooks that mirror this layering.
