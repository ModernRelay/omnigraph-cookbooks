# Pharma Intel — Viking Therapeutics (GLP-1 Obesity)

Knowledge graph starter modeling competitive pharma intelligence from the perspective of a public biotech sponsor. Built on [Omnigraph](https://github.com/ModernRelay/omnigraph) using the [SPIKE framework](../README.md#spike-framework) plus two additional layers — an **external pipeline** layer (compounds, trials, deals, regulatory actions) and an **internal context** layer (programs, assumptions, decisions, open questions).

Where `industry-intel/` demos SPIKE as a pure intelligence lens, `pharma-intel/` demos the same lens grounded against a real sponsor's investment thesis — so the graph surfaces which external signals contradict which internal assumptions, and what still needs to be answered before an upcoming decision.

## The Three Layers

```
                          ┌─────────── External Pipeline ───────────┐
                          │                                          │
                          │   Compound ── targetsMechanism ──▶ Mechanism
                          │       │                                  │
                          │       ├── developedByCompany ──▶ Company │
                          │       │                                  │
                          │   Trial ── investigatesCompound ──▶ Compound
                          │                                          │
                          │   Deal, RegulatoryAction                 │
                          └──────────────────────────────────────────┘
                                         ▲
                                         │ aboutCompound / aboutMechanism /
                                         │ aboutTrial / relevantCompany
                                         │
     ┌────── SPIKE Intelligence ──────┐  │
     │                                │  │
     │   Signal ── FormsPattern ────▶ Pattern ◀── HighlightsPattern ── Insight
     │      │     ContradictsPattern                                    │
     │      │                                                           │
     │      │                               ReliesOnElement /           │
     │      │                               (pipeline node)             │
     │      └── SpottedInArtifact ──▶ InformationArtifact ── PublishedBySource ──▶ SourceEntity
     │                                                                  │
     └──────────────────────────────────────────────────────────────────┘
                                         │
                    SupportsAssumption / ContradictsAssumption / InformsQuestion
                                         ▼
     ┌─────── Internal Context (the value layer) ──────┐
     │                                                  │
     │   Program ── ProgramDependsOnAssumption ──▶ Assumption
     │                                                  │
     │   Decision ── DecisionRegardingProgram ──▶ Program
     │       │                                          │
     │       ├── DecisionBasedOnAssumption ──▶ Assumption
     │       └── DecisionNeedsAnswer ────────▶ OpenQuestion
     │                                                  │
     └──────────────────────────────────────────────────┘
```

Each signal is an external fact. Each pattern is a theme. But because the signal also edges to internal `Assumption`s and `OpenQuestion`s, the graph answers questions like:

- *"Which signals contradict my oral-displaces-injectable thesis?"*
- *"Before the Phase 3 start decision, which assumptions need re-validation?"*
- *"What open questions from my clinical team does this new regulatory signal inform?"*

## Reference Seed: Viking Therapeutics, Mid-2026

Viking Therapeutics (NASDAQ: VKTX) is a real public company with a GLP-1/GIP dual-agonist pipeline competing in obesity. All data in the seed is sourced from SEC filings, investor presentations, clinicaltrials.gov, and press releases — no MNPI.

**External pipeline (what's happening in the market):**

| Dimension | Count | Includes |
|-----------|-------|----------|
| Compounds | 12 | VK2735 (SC + oral), tirzepatide, semaglutide, CagriSema, orforglipron, retatrutide, MariTide, danuglipron (discontinued), CT-996, GSBR-209, survodutide |
| Mechanisms | 6 | GLP-1/GIP dual, GLP-1 mono, triple agonist, oral small-molecule GLP-1, amylin co-agonist, GLP-1/glucagon |
| Trials | 8 | Real NCT IDs including VANQUISH (NCT05930405), SURMOUNT-5, SELECT, ATTAIN-1, REDEFINE-1 |
| Deals | 3 | Roche/Carmot ($3.1B, Dec 2023), Lilly/Versanis ($1.925B, Aug 2023), Pfizer/Metsera ($4.9B, Nov 2025) |
| Regulatory | 4 | Zepbound OSA approval, Wegovy CV label, CMS Medicare memo, ERAs |
| Companies | 13 | Viking, Novo, Lilly, Pfizer, Amgen, Roche, BI, Zealand, Structure, Express Scripts, Carmot, Versanis, Metsera |

**Four live patterns in GLP-1 obesity:**

| Pattern | Kind | What it captures |
|---------|------|------------------|
| **GLP-1 Pipeline Explosion** | dynamic | 30+ candidates across 10+ sponsors racing an addressable market ≥$150B |
| **Oral GLP-1 Thesis** | dynamic | Primary-care unlock via oral formulation — *and the signals contradicting it* |
| **Efficacy Ceiling** | challenge | Weight-loss magnitude plateauing; tolerability now the differentiator |
| **Payer Pushback** | challenge | PBM prior-auth + CMS coverage ambiguity squeezing commercial upside |

**Internal context (Viking's thesis as a structured object):**

| Dimension | Count | Includes |
|-----------|-------|----------|
| Programs | 2 | VK2735 SC (Phase 3), VK2735 oral (Phase 2) |
| Assumptions | 5 | Oral displaces injectable · efficacy matches tirzepatide · best-in-class tolerability · payer coverage sustainable · mechanism safe at scale |
| Upcoming decisions | 2 | VANQUISH interim readout go/no-go (2026-07-15) · Phase 3 start for oral (2026-09-30) |
| Open questions | 4 | Pfizer failure mechanism risk · orforglipron competitive window · payer coverage trajectory · manufacturing scale-up path |

**Demo edges** (surfaced by the graph, not buried in prose):

| Signal | Edge | Internal target | Why it matters |
|--------|------|-----------------|----------------|
| Pfizer discontinues danuglipron (liver injury) | `ContradictsAssumption` | `asmp-oral-displaces-injectable` | Regulatory event invalidates a strategic assumption from a completely different silo |
| CagriSema REDEFINE miss (22.7% vs consensus) | `ContradictsAssumption` | `asmp-efficacy-matches-tirzepatide` | Competitor readout directly resets the efficacy bar Viking is targeting |
| Express Scripts adds prior-auth | `ContradictsAssumption` | `asmp-payer-coverage-sustainable` | Payer signal challenges investment-layer assumption |
| Lilly orforglipron ATTAIN-1 positive | `InformsQuestion` | `q-orforglipron-competitive-window` | Competitive readout answers (partially) a Viking open question |
| Pfizer danuglipron discontinuation | `InformsQuestion` | `q-pfizer-failure-mechanism-risk` | Cross-sponsor hepatotoxicity risk flagged for Viking's clinical team |

**Totals:** 113 nodes across 15 node types, 200 edges across 34 edge types.

## Schema Essentials

**Nodes (15):** `Compound`, `Mechanism`, `Trial`, `Company`, `Deal`, `RegulatoryAction` · `Signal`, `Pattern`, `Insight` · `SourceEntity`, `InformationArtifact` · `Program`, `Assumption`, `Decision`, `OpenQuestion`

**Enums that carry the analytical lens:**

| Enum | Values |
|------|--------|
| **Phase** | `preclinical, phase-1, phase-2, phase-3, approved, discontinued, withdrawn` |
| **Modality** | `small-molecule, peptide, biologic, antibody, gene-therapy, cell-therapy` |
| **Route** | `oral, subcutaneous, iv, intranasal, other` |
| **Domain** (Signal) | `obesity, t2d, nash, cardiovascular, neuro, oncology, rare, payer, regulatory, manufacturing` |
| **PatternKind** | `challenge, disruption, dynamic` |
| **AssumptionLevel** | `investment, scientific, competitive, strategic` |
| **DecisionStatus** | `upcoming, decided, deferred` |
| **QuestionStatus** | `open, resolved` |

**Edges that carry the analytical logic** (everything else is classification or provenance):

| Edge | Route | Meaning |
|------|-------|---------|
| `FormsPattern` / `ContradictsPattern` | Signal → Pattern | evidence for/against a theme |
| `HighlightsPattern` | Insight → Pattern | synthesis lens on a theme |
| `DrivesPattern` | Pattern → Pattern | causal relationship between themes |
| `AboutCompound` / `AboutMechanism` / `AboutTrial` / `RelevantCompany` | Signal → pipeline node | what the signal is about |
| `SupportsAssumption` / `ContradictsAssumption` | Signal → Assumption | external → internal bridge |
| `InformsQuestion` | Signal → OpenQuestion | external event answers an internal question |
| `ProgramDependsOnAssumption` | Program → Assumption | what the program rests on |
| `DecisionRegardingProgram` | Decision → Program | which program a decision affects |
| `DecisionBasedOnAssumption` / `DecisionNeedsAnswer` | Decision → Assumption/OpenQuestion | decision prerequisites |
| `TargetsMechanism` / `DevelopedByCompany` / `InvestigatesCompound` | pipeline structure | industry topology |
| `SpottedInArtifact` / `PublishedBySource` | provenance | evidence chain |

**Key design choices:**

- Three stacked layers: external pipeline, SPIKE intelligence, internal context — each layer adds a perspective, not another domain
- Assumption / Decision / OpenQuestion are **first-class nodes**, not just properties — so they can be queried, traced, and edged to signals
- `slug` is external identity everywhere (`comp-`, `mech-`, `trial-`, `co-`, `deal-`, `reg-`, `sig-`, `pat-`, `ins-`, `src-`, `art-`, `prog-`, `asmp-`, `dec-`, `q-`)
- Flat `kind` / `level` / `status` enums — no interfaces or subtypes
- No embeddings in v1 — narrative surfaces are graph-structured, not vector-search-driven

Full property tables and constraints in `schema.pg`.

## Files

- `schema.pg` — Executable Omnigraph schema (source of truth)
- `seed.md` / `seed.jsonl` — Seed dataset (human-readable / loadable)
- `queries/*.gq` — Read queries (5 files, 70 queries) + mutations (1 file, 35 queries)
- `omnigraph.yaml` — CLI config with aliases for all reads + mutations
- `.env.omni` — RustFS credentials (not committed; see `.env.omni.example`)

## Quick Start

All commands run from `pharma-intel/`:

```bash
cd pharma-intel

# Source RustFS credentials
cp .env.omni.example .env.omni
set -a && source ./.env.omni && set +a

# Lint the schema and queries (pure file check)
omnigraph query lint --schema ./schema.pg --query ./queries/signals.gq

# Init the repo (one-time — writes to storage)
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/pharma-intel

# Load the seed (one-time)
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/pharma-intel

# Start the local HTTP server (keep it running — separate terminal or background)
omnigraph-server --config ./omnigraph.yaml

# All queries go through the server via aliases
omnigraph read --alias assumption-contradictions asmp-oral-displaces-injectable
omnigraph read --alias decision-questions dec-vanquish-interim-readout
omnigraph read --alias pattern-contradictions pat-oral-glp1-thesis
omnigraph read --alias decisions-upcoming
```

## Demo Walkthrough

Four queries that show the three-layer model in action:

```bash
# 1. Cross-silo contradiction: a regulatory-domain signal hits a strategic assumption
omnigraph read --alias assumption-contradictions asmp-oral-displaces-injectable
# → Pfizer danuglipron discontinued + Structure GSBR-209 Phase 2a disappoints

# 2. Pre-committee briefing: what rests on the upcoming Phase 3 start decision?
omnigraph read --alias decision-assumptions dec-oral-phase3-start
# → asmp-oral-displaces-injectable (now contradicted) + asmp-mechanism-safe-at-scale

# 3. Competitive landscape: all compounds targeting the same mechanism
omnigraph read --alias program-competitors prog-vk2735-sc
# → tirzepatide, VK2735 oral (self), VK2735 SC — mechanism peers across phase

# 4. Proactive alert: what internal questions does a new signal inform?
omnigraph read --alias signal-informs-questions sig-pfizer-danuglipron-discontinued
# → q-pfizer-failure-mechanism-risk (Viking clinical team)

# 5. Landscape feed: every signal touching any compound in my mechanism
omnigraph read --alias program-landscape-signals prog-vk2735-sc
# → 5 signals across VK2735 (SC + oral) + tirzepatide, time-sorted
```

## Agent Analyst Loop

Agents should operate the graph in this order:

```bash
# 1. Pick a decision and expand its dependencies
omnigraph read --alias decisions-upcoming
omnigraph read --alias decision-assumptions dec-oral-phase3-start
omnigraph read --alias decision-questions dec-oral-phase3-start

# 2. Gather evidence for the key assumptions
omnigraph read --alias assumption-supports asmp-oral-displaces-injectable
omnigraph read --alias assumption-contradictions asmp-oral-displaces-injectable

# 3. Trace a new or existing signal into internal impact
omnigraph read --alias signal-contradicts-assumptions sig-pfizer-danuglipron-discontinued
omnigraph read --alias signal-informs-questions sig-pfizer-danuglipron-discontinued
```

For fresh web findings, first map the signal to existing companies, compounds, patterns, assumptions, and open questions; then propose the minimal seed or mutation update.

See the [Omnigraph](https://github.com/ModernRelay/omnigraph) repo for full CLI reference.
