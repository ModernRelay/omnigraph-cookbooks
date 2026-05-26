# Reference Seed — Quito Capital (fictional AI-infra fund)

Human-readable twin of `seed.jsonl`. All names, deals, organizations, and people are fabricated. If you change one, update the other.

The firm: **Quito Capital**, Berlin-based, AI-infra focused. Two funds: Fund II ($120M, vintage 2021, harvesting) and Fund III ($250M, vintage 2024, investing). Five-person team in Berlin / London / Paris.

**Totals (loaded):** 207 nodes across 16 active types, 460 edges across 65 edge types. (`Chunk` is declared in the schema but zero rows in the seed — v1 ships no embeddings.) `Knows` is loaded bidirectionally (14 unique pairs × 2 = 28 edges). Source-provenance entities (TechCrunch, PitchBook, Tegus, anon blog) live as `Organization` rows with `kind in (publisher, database, expert-network)` and a `reliability` rating — not as a separate `SourceEntity` node.

## Funds

| Slug | Name | Vintage | Size | Status |
|---|---|---|---|---|
| `fund-ii` | Quito Fund II | 2021 | $120M | harvesting |
| `fund-iii` | Quito Fund III | 2024 | $250M | investing |

## Markets

| Slug | Name | Parent |
|---|---|---|
| `mkt-ai-infra` | AI Infrastructure | — |
| `mkt-ai-applications` | AI Applications | — |
| `mkt-dev-tools` | Developer Tools | `mkt-ai-infra` |
| `mkt-vertical-saas` | Vertical SaaS | `mkt-ai-applications` |
| `mkt-security` | Security | — |
| `mkt-data` | Data Engineering | `mkt-ai-infra` |

## Companies (17)

**Portfolio (5):**

| Slug | Name | Sector | Stage Seen | Sourced |
|---|---|---|---|---|
| `org-aetherbrick` | Aetherbrick | vertical-saas | series-a | Fund II (2021 seed + 2023 A) |
| `org-saltline-ai` | Saltline AI | vertical-saas | seed | Fund II (2022 seed) |
| `org-pinion-infer` | Pinion Infer | ai-infra | series-a | Fund III (2025 A) |
| `org-bramble-data` | Bramble Data | data-engineering | series-a | Fund III (2025 A) |
| `org-quirebench` | QuireBench | dev-tools | seed | Fund III (2025 seed) |

**Evaluating (5):**

| Slug | Name | Sector | Deal |
|---|---|---|---|
| `org-helix-runtime` | Helix Runtime | ai-infra | `deal-helix-series-a` (in-diligence) |
| `org-axon-eval` | Axon Eval | dev-tools | `deal-axon-seed` (ic-ready) |
| `org-mintlayer-data` | Mintlayer Data | data-engineering | `deal-mintlayer-seed` (qualified) |
| `org-sigil-security` | Sigil Security | security | `deal-sigil-seed` (sourced) |
| `org-canon-quality` | Canon Quality | data-engineering | `deal-canon-seed` (in-diligence) |

**Passed (3):**

| Slug | Deal | Reason |
|---|---|---|
| `org-vector-forge` | `deal-vector-forge-seed` | AWS exclusivity killed differentiation |
| `org-stratopaint` | `deal-stratopaint-seed` | Vertical SaaS without product-led pull |
| `org-pulserate` | `deal-pulserate-series-a` | Agentic CRM commoditization risk |

**Pipeline / watching (4):** `org-knurlforge`, `org-claretmd`, `org-buoybase`, `org-orbitwerks`.

## People (28)

**Team (5):** `per-cj` (MP), `per-pawel`, `per-flo`, `per-ricardo`, `per-louis`.
**Venture Partners (2):** `per-vp-noah` (GTM), `per-vp-tegan` (technical).
**Founders (11):** Jens (Aetherbrick), Rohan (Saltline), Anya (Pinion), Tom (Bramble), Sara (QuireBench), Elena + Yuki (Helix), Marcus (Axon), Priya (Mintlayer), Leon (Sigil), Mia (Vector Forge).
**LPs (4):** `per-allianz-arno`, `per-vestland-ina`, `per-grayrock-kai`, `per-grace-tan`.
**Experts (3):** Jordan (on-prem), Malik (GTM), Cora (security CISO).
**Acquirer DMs (3):** Rajiv (AWS), Priti (Microsoft), Leo (Snowflake).

## Non-startup Companies (16)

All `Organization` rows; the `kind` enum distinguishes them. Includes `org-quito` (Quito itself, kind=vc-firm), `org-grace-tan-fo` (Grace Tan's family-office LP, kind=family-office), and 4 source-provenance orgs (collapsed from the old `SourceEntity` node).

**Acquirers (5):** AWS, Microsoft, Snowflake, Databricks, Google Cloud — all `kind=acquirer`.
**LP institutions (3):** Allianz IM, Vestland, Grayrock Foundation — `kind=lp-institution`.
**VC peer (1):** Sequoia EU — `kind=vc-firm`.
**Accelerator (1):** Y Combinator — `kind=accelerator`.
**Quito itself (1):** `org-quito` — `kind=vc-firm`. Team members `WorksAt` it.
**Family office (1):** `org-grace-tan-fo` — `kind=family-office`. Individual LP modeled this way.
**Publishers (2):** `org-techcrunch` (medium reliability), `org-anonblog` (low reliability) — `kind=publisher`.
**Database (1):** `org-pitchbook` (high reliability) — `kind=database`.
**Expert network (1):** `org-tegus` (high reliability) — `kind=expert-network`.

The four source orgs carry a `reliability` rating; reliability-driven Signal revalidation walks `Organization ← publishedByOrganization ← Artifact ← signalSourcedFromArtifact ← Signal`. The `src-founder-direct` provenance tag from the old schema is gone — content from a founder is queryable via `Artifact → fromPerson → Person → founderOf → Organization`.

## Theses (8)

| Slug | Status | Brief |
|---|---|---|
| `thesis-vertical-ai-infra` | active | Vertical AI infrastructure accumulates data moats |
| `thesis-on-prem-inference` | active | Regulated industries push inference off public cloud |
| `thesis-agentic-crms` | active | Per-seat SaaS collapses to agent workflows |
| `thesis-data-quality-moats` | active | Data quality is the durable AI moat |
| `thesis-eval-as-product` | active | Eval becomes a standalone product category |
| `thesis-security-agentic-attacks` | active | Agent-aware security wins |
| `thesis-vertical-saas-ai-shells` | **contradicted** | Generic AI shells on legacy SaaS — invalidated by 2 contradicting signals |
| `thesis-edge-inference-mobile` | retired | Too constrained by silicon roadmaps |

## Assumptions (12)

12 assumptions across levels (market, financial, product, strategic, competitive). Each Thesis relies on 1-3. Examples:

- `asmp-data-sovereignty-mandates` (strategic) — supports thesis-on-prem-inference; supported by 3 signals
- `asmp-inference-cost-parity-onprem` (financial) — supports thesis-on-prem-inference; **contradicted** by sig-aws-bedrock-onprem
- `asmp-helix-onprem-margin` (financial) — Helix-specific; **contradicted** by sig-aws-bedrock-onprem (the killer query)
- `asmp-vertical-shell-product-pull` (product) — supports thesis-vertical-saas-ai-shells; **contradicted** by sig-vertical-shell-flops + sig-mistral-vertical-launch
- `asmp-vertical-data-asymmetry` (market) — supports thesis-vertical-ai-infra; **contradicted** by sig-vector-forge-aws-deal

## Questions (10)

10 questions across priorities. Examples:

- `q-helix-onprem-margin` (high, open) — informed by sig-aws-bedrock-onprem AND sig-helix-board-onprem-mandate (one supports, one threatens)
- `q-aetherbrick-follow-on` (high, open) — informed by churn spike + Series B talk
- `q-axon-enterprise-pull` (high, open) — informed by databricks acquihire rumor

## Deals (15)

**Closed-invested (6):**
- `deal-aetherbrick-seed`, `deal-aetherbrick-series-a` (same organization, two rounds)
- `deal-saltline-seed`, `deal-pinion-series-a`, `deal-bramble-series-a`, `deal-quirebench-seed`

**Open (6):**
- `deal-helix-series-a` (in-diligence, the killer-query deal)
- `deal-axon-seed` (ic-ready, IC scheduled)
- `deal-mintlayer-seed` (qualified)
- `deal-sigil-seed` (sourced)
- `deal-canon-seed` (in-diligence)
- `deal-knurlforge-seed` (qualified)

**Passed (3):** `deal-vector-forge-seed`, `deal-stratopaint-seed`, `deal-pulserate-series-a`.

## Signals (29)

29 signals across kinds: discovery, launch, fundraise, exit, founder-event, market-move, competitive, customer, regulatory, team-change, portfolio-update, board-decision. Mix of dates from 2025-08 to 2026-05.

Notable signals for killer queries:

- `sig-aws-bedrock-onprem` (2026-03-04, **high impact**, competitive) — contradicts the on-prem margin thesis. Source of the post-signal-portfolio-impact demo.
- `sig-helix-board-onprem-mandate` (2026-04-12, **high impact**, customer) — supports on-prem thesis. The bull-case Helix evidence.
- `sig-eu-ai-act-enforcement` (2026-04-15, **high impact**, regulatory) — €42M fine validates data-sovereignty-mandates.
- `sig-aetherbrick-churn-spike` (2026-04-07, **high impact**, portfolio-update) — drives the board-prep-pack demo.
- `sig-databricks-acquihire` (2026-02-10, **high impact**, exit) — validates eval-as-product thesis.

## Insights (12)

12 insights across kinds (`memo`, `brief`, `observation`, `recap`) and stances (`bull`, `bear`, `neutral`). Open uncertainties live on `Question`, not `Insight{kind=hypothesis}`. Notable:

- `ins-helix-bull` + `ins-helix-bear` — the multi-agent IC simulation demo; both grounded in real Signals.
- `ins-axon-memo` — IC memo for the Axon investment recommendation.
- `ins-vector-forge-pass-rationale` — pass rationale memo.
- `ins-on-prem-trend-observation` — highlights pat-on-prem-shift.

## Artifacts (15)

15 artifacts mixing transcripts (`source=meeting-tool`, `source_app=granola`), emails (`source=email`, `source_app=gmail`), decks, web pages, chat messages (`source=chat`, `source_app=slack`), derived summaries, and git-pinned markdown (`source=repo`, `source_app=github`). All metadata-only in v1 (no blob payloads). One `ArtifactDerivedFrom` chain: board notes → AI summary.

## Decisions (6)

Only true one-shot decisions live here. *Schedule another meeting* and *flag at next board* are `Commitment`s.

| Slug | Kind | Regarding | By |
|---|---|---|---|
| `dec-vector-forge-pass` | pass | deal-vector-forge-seed | per-pawel |
| `dec-pulserate-pass` | pass | deal-pulserate-series-a | per-flo |
| `dec-stratopaint-pass` | pass | deal-stratopaint-seed | per-cj |
| `dec-aetherbrick-follow-on-eval` | follow-on | deal-aetherbrick-series-a | per-cj |
| `dec-axon-ic-recommend-invest` | invest | deal-axon-seed | per-flo |
| `dec-onprem-thesis-doubledown` | double-down | **thesis-on-prem-inference** (the only thesis-level Decision in the seed — exercises `DecisionRegardingThesis`) | per-cj |

Each Decision is linked to: regardingDeal (or regardingThesis), basedOnAssumption (1-2), needsAnswerToQuestion (when applicable), byPerson.

## Commitments (9)

Mix of open / in-progress / done. Includes intros to make, board-prep deliverables, customer-ref calls, follow-up emails to passed founders, and `cmt-helix-second-meeting` (which used to be a Decision but is correctly a Commitment — it has a due_date and an assignee, not a `decided_at`).

## Patterns (5) and Lessons (4)

| Pattern | Kind |
|---|---|
| `pat-on-prem-shift` | market-timing |
| `pat-vertical-data-moats` | gtm |
| `pat-eval-fragmentation` | tech-adoption |
| `pat-vertical-shell-flop` | failure-mode |
| `pat-founder-second-time-infra` | founder-archetype |

| Lesson | Kind | Status |
|---|---|---|
| `lsn-onprem-validation-protocol` | protocol | active |
| `lsn-vertical-data-moat-eval` | rule-of-thumb | active |
| `lsn-shell-anti-pattern` | anti-pattern | active |
| `lsn-second-time-founder-bias` | rule-of-thumb | **tentative** (lives on review branch) |

## Meetings (8)

The operational layer — what the firm actually did with its time. Mix of `occurred` (5) and `scheduled` (3). Every Decision and most Commitments in the seed are tied to a Meeting via `DecisionFromMeeting` / `CommitmentFromMeeting`, so the audit chain extends to "which conversation produced this."

| Slug | Kind | When | Status | Subject |
|---|---|---|---|---|
| `mtg-helix-founder-call-2026-04` | founder-call | 2026-04-12 | occurred | `deal-helix-series-a` + `org-helix-runtime`. Transcript: `art-helix-founder-call-2026-04`. Produced `cmt-helix-second-meeting` + `cmt-helix-customer-refs`. |
| `mtg-helix-ic-2026-06` | ic | 2026-06-20 | scheduled | `deal-helix-series-a`. Full team + `per-vp-tegan`. |
| `mtg-aetherbrick-board-q1-2026` | board | 2026-04-08 | occurred | `org-aetherbrick`. Transcript: `art-aetherbrick-board-q1`. Produced `cmt-aetherbrick-board-prep`. |
| `mtg-aetherbrick-board-q2-2026` | board | 2026-07-09 | scheduled | `org-aetherbrick`. The "next board" for the board-prep demo. |
| `mtg-axon-ic-2026-05` | ic | 2026-05-12 | occurred | `deal-axon-seed`. Produced `dec-axon-ic-recommend-invest` + `cmt-axon-final-check`. |
| `mtg-axon-final-ref-2026-06` | expert-call | 2026-06-09 | scheduled | `deal-axon-seed`. The final reference owed before close. |
| `mtg-partner-onprem-thesis-2026-04` | internal | 2026-04-20 | occurred | `thesis-on-prem-inference`. Produced `dec-onprem-thesis-doubledown`. |
| `mtg-weekly-pipeline-2026-05-13` | pipeline-review | 2026-05-13 | occurred | No subject edges (full-team weekly cadence). |

The `tentative` lesson demonstrates the branch-as-review workflow: an agent identified the pattern, drafted the lesson on a branch, and a human must merge to promote it to `active`.
