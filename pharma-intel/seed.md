# Pharma Intel — Seed Dataset

Seed data for `schema.pg`. Scope: the GLP-1 obesity competitive landscape, seeded from the perspective of **Viking Therapeutics (VKTX)** as the public-company sponsor. Current date frame: **2026-04-17**. All external data points are real, dated, and URL-sourced.

---

## Companies (13)

| slug | name | ticker | type |
|------|------|--------|------|
| `co-viking-therapeutics` | Viking Therapeutics | VKTX | biotech |
| `co-novo-nordisk` | Novo Nordisk | NVO | pharma |
| `co-eli-lilly` | Eli Lilly | LLY | pharma |
| `co-pfizer` | Pfizer | PFE | pharma |
| `co-amgen` | Amgen | AMGN | pharma |
| `co-roche` | Roche | RHHBY | pharma |
| `co-boehringer-ingelheim` | Boehringer Ingelheim | — | pharma |
| `co-zealand-pharma` | Zealand Pharma | ZEAL | biotech |
| `co-structure-therapeutics` | Structure Therapeutics | GPCR | biotech |
| `co-express-scripts` | Express Scripts (Cigna) | — | payer |
| `co-carmot-therapeutics` | Carmot Therapeutics | — | biotech |
| `co-versanis-bio` | Versanis Bio | — | biotech |
| `co-metsera` | Metsera | — | biotech |

## Mechanisms (6)

| slug | name | validation |
|------|------|------------|
| `mech-glp1r-agonist` | GLP-1 receptor agonist | approved |
| `mech-gip-glp1-dual` | GIP / GLP-1 dual agonist | approved |
| `mech-glp1-amylin` | GLP-1 + amylin | clinical |
| `mech-triple-agonist` | GLP-1 / GIP / glucagon triple agonist | clinical |
| `mech-glucagon-glp1-dual` | GLP-1 / glucagon dual | clinical |
| `mech-glp1r-gipr-antagonist` | GLP-1R agonist + GIPR antagonist | clinical |

## Compounds (12)

| slug | name | sponsor | mechanism | route | phase |
|------|------|---------|-----------|-------|-------|
| `comp-vk2735-sc` | VK2735 (subcutaneous) | Viking | gip-glp1-dual | subcutaneous | phase-3 |
| `comp-vk2735-oral` | VK2735 (oral) | Viking | gip-glp1-dual | oral | phase-2 |
| `comp-semaglutide` | semaglutide (Wegovy/Ozempic) | Novo | glp1r-agonist | subcutaneous/oral | approved |
| `comp-tirzepatide` | tirzepatide (Zepbound/Mounjaro) | Lilly | gip-glp1-dual | subcutaneous | approved |
| `comp-cagrisema` | CagriSema (cagrilintide + semaglutide) | Novo | glp1-amylin | subcutaneous | phase-3 |
| `comp-orforglipron` | orforglipron | Lilly | glp1r-agonist | oral | phase-3 |
| `comp-retatrutide` | retatrutide | Lilly | triple-agonist | subcutaneous | phase-3 |
| `comp-maritide` | MariTide (maridebart cafraglutide) | Amgen | glp1r-gipr-antagonist | subcutaneous | phase-3 |
| `comp-danuglipron` | danuglipron | Pfizer | glp1r-agonist | oral | discontinued |
| `comp-survodutide` | survodutide | BI/Zealand | glucagon-glp1-dual | subcutaneous | phase-3 |
| `comp-gsbr-209` | GSBR-209 | Structure | glp1r-agonist | oral | phase-2 |
| `comp-ct-996` | CT-996 | Roche | glp1r-agonist | oral | phase-1 |

## Trials (8)

| slug | name | nct_id | phase | status | sponsor | readout |
|------|------|--------|-------|--------|---------|---------|
| `trial-venture` | VENTURE | NCT05930405 | phase-2 | completed | Viking | 2024-02 |
| `trial-vanquish` | VANQUISH | NCT06781983 | phase-3 | enrolling | Viking | 2026-H2 |
| `trial-vk2735-oral-p2` | VK2735 Oral Phase 2 | NCT06153758 | phase-2 | ongoing | Viking | 2026-H2 |
| `trial-redefine` | REDEFINE 1 (CagriSema) | NCT05567796 | phase-3 | completed | Novo | 2024-12 |
| `trial-attain-1` | ATTAIN-1 (orforglipron) | NCT05051579 | phase-3 | completed | Lilly | 2025-Q3 |
| `trial-triumph-4` | TRIUMPH-4 (retatrutide obesity) | NCT05882045 | phase-3 | ongoing | Lilly | 2026 |
| `trial-surmount-5` | SURMOUNT-5 (tirzepatide vs sema) | NCT05822830 | phase-3 | completed | Lilly | 2024-12 |
| `trial-maritime` | MARITIME (MariTide) | NCT06440460 | phase-3 | enrolling | Amgen | 2027 |

## Deals (3)

| slug | name | value | date |
|------|------|-------|------|
| `deal-roche-carmot` | Roche acquires Carmot Therapeutics | $3.1B | 2023-12 |
| `deal-lilly-versanis` | Lilly acquires Versanis Bio | $1.925B | 2023-08 |
| `deal-pfizer-metsera` | Pfizer acquires Metsera | $4.9B | 2025-11 |

## Regulatory Actions (4)

| slug | name | agency | type | date |
|------|------|--------|------|------|
| `reg-wegovy-cvd-label` | Wegovy CV risk reduction label | FDA | label-change | 2024-03 |
| `reg-zepbound-osa` | Zepbound OSA approval | FDA | approval | 2024-12 |
| `reg-medicare-glp1-cvd` | Medicare Part D coverage for GLP-1 in CVD | CMS | guidance | 2024-03 |
| `reg-fda-glp1-gi-class` | FDA class-label warning, GI adverse events | FDA | guidance | 2023-09 |

---

## Patterns (4)

| slug | name | kind |
|------|------|------|
| `pat-glp1-pipeline-explosion` | GLP-1 Pipeline Explosion | dynamic |
| `pat-oral-glp1-thesis` | Oral GLP-1 Displaces Injectable | disruption |
| `pat-efficacy-ceiling` | Efficacy Ceiling Debate | dynamic |
| `pat-payer-pushback` | Payer Pushback on GLP-1 Pricing | challenge |

## Signals (18)

| slug | name | date | supports/contradicts |
|------|------|------|---------------------|
| `sig-pfizer-danuglipron-discontinued` | Pfizer discontinues danuglipron | 2025-04 | **contradicts oral thesis** |
| `sig-redefine-cagrisema-readout` | CagriSema REDEFINE 1: 22.7% weight loss, missed consensus | 2024-12 | contradicts efficacy-matches-tirzepatide |
| `sig-viking-venture-p2` | Viking VENTURE Ph2: 14.7% weight loss, 13 weeks | 2024-02 | supports Viking efficacy |
| `sig-viking-vanquish-init` | Viking initiates VANQUISH Ph3 | 2025-03 | supports Viking program |
| `sig-viking-oral-p2-init` | Viking initiates VK2735 oral Ph2 | 2024-11 | supports oral program |
| `sig-lilly-attain-positive` | Lilly orforglipron ATTAIN-1: 14.7% weight loss (oral) | 2025-08 | supports oral thesis, competitive threat |
| `sig-lilly-retatrutide-p2` | Lilly retatrutide Ph2: 24.2% weight loss | 2023-11 | supports efficacy-ceiling-not-reached |
| `sig-lilly-surmount-5-headhead` | SURMOUNT-5: tirzepatide beats semaglutide head-to-head | 2024-12 | establishes competitive benchmark |
| `sig-amgen-maritide-p2` | Amgen MariTide Ph2: ~20% weight loss, durability debated | 2025-03 | supports mechanism diversification |
| `sig-roche-carmot-acq` | Roche acquires Carmot for $3.1B | 2023-12 | supports pipeline explosion |
| `sig-pfizer-metsera-acq` | Pfizer acquires Metsera for $4.9B | 2025-11 | supports pipeline explosion (Pfizer re-enters) |
| `sig-wegovy-cvd-label-expansion` | FDA expands Wegovy to CV risk reduction | 2024-03 | supports payer-coverage-sustainable |
| `sig-express-scripts-exclusion` | Express Scripts moves GLP-1s to prior auth | 2024-06 | contradicts payer-coverage-sustainable |
| `sig-cms-medicare-glp1-cvd` | CMS allows GLP-1 Medicare coverage for CVD | 2024-03 | supports payer access |
| `sig-zepbound-osa-approval` | Zepbound approved for obstructive sleep apnea | 2024-12 | supports label expansion |
| `sig-viking-q4-2025-earnings` | Viking Q4 2025 earnings: cash runway through readout | 2026-02 | supports program execution |
| `sig-structure-gsbr-p2a-disappointing` | Structure GSBR-209 Ph2a misses bar | 2026-01 | contradicts oral-small-molecule thesis |
| `sig-viking-cmo-capacity` | Viking signs two CMOs for VK2735 manufacturing | 2025-09 | resolves manufacturing question |

## Insights (3)

| slug | name | highlights pattern |
|------|------|--------------------|
| `ins-mechanism-validated-formulation-is-moat` | Mechanism is validated; formulation is the moat | oral-glp1-thesis |
| `ins-pfizer-failure-is-formulation-not-mechanism` | Pfizer danuglipron failure is formulation, not mechanism | oral-glp1-thesis |
| `ins-cagrisema-miss-is-about-expectations-not-ceiling` | CagriSema "miss" is about expectations, not an efficacy ceiling | efficacy-ceiling |

---

## Internal Context — Viking Therapeutics (sponsor)

### Programs (2)

| slug | name | compound | phase |
|------|------|----------|-------|
| `prog-vk2735-sc` | VK2735 Subcutaneous Program | VK2735 SC | phase-3 |
| `prog-vk2735-oral` | VK2735 Oral Program | VK2735 Oral | phase-2 |

### Assumptions (5)

| slug | name | level |
|------|------|-------|
| `asmp-best-in-class-tolerability` | VK2735 has best-in-class GI tolerability profile | competitive |
| `asmp-efficacy-matches-tirzepatide` | VK2735 SC will match or beat tirzepatide efficacy (~20%+ weight loss) | competitive |
| `asmp-oral-displaces-injectable` | Oral GLP-1 will displace injectable in primary care | strategic |
| `asmp-mechanism-safe-at-scale` | Dual GLP-1/GIP mechanism is safe at scale (hepatic, CV, GI) | scientific |
| `asmp-payer-coverage-sustainable` | Payer coverage will expand, not contract, at current pricing | investment |

### Decisions (2)

| slug | name | status | decision_date |
|------|------|--------|---------------|
| `dec-vanquish-interim-readout` | VANQUISH interim readout go/no-go | upcoming | 2026-07-15 |
| `dec-oral-phase3-start` | Move VK2735 oral to Phase 3 | upcoming | 2026-09-30 |

### Open Questions (4)

| slug | name | asked_by |
|------|------|----------|
| `q-pfizer-failure-mechanism-risk` | Does Pfizer danuglipron's liver toxicity translate to Viking oral? | Clinical |
| `q-orforglipron-competitive-window` | Does Lilly orforglipron close the Viking oral competitive window? | Strategy |
| `q-payer-coverage-trajectory` | Is payer coverage expanding or contracting at current pricing? | Commercial |
| `q-manufacturing-capacity-p3` | Can CMO capacity meet Phase 3 VANQUISH demand? | CMC/Ops |

---

## Key demo edges (the "wow" moments)

| Edge | From | To | Why it matters |
|------|------|----|----------------|
| ContradictsAssumption | `sig-pfizer-danuglipron-discontinued` | `asmp-oral-displaces-injectable` | A public external signal directly challenges a public Viking strategic bet |
| ContradictsAssumption | `sig-redefine-cagrisema-readout` | `asmp-efficacy-matches-tirzepatide` | The bar of "~20% weight loss = bullish" got reset when CagriSema missed at 22.7% |
| ContradictsAssumption | `sig-express-scripts-exclusion` | `asmp-payer-coverage-sustainable` | The investment thesis weakens when named payers pull back |
| InformsQuestion | `sig-lilly-attain-positive` | `q-orforglipron-competitive-window` | A competitor's Phase 3 win directly informs a Viking open question |
| InformsQuestion | `sig-pfizer-danuglipron-discontinued` | `q-pfizer-failure-mechanism-risk` | A cross-silo connection: regulatory/safety signal surfaces to clinical team's concern |
| ContradictsPattern | `sig-structure-gsbr-p2a-disappointing` | `pat-oral-glp1-thesis` | One pattern, one counter-signal — visible as first-class data |
| ContradictsPattern | `sig-redefine-cagrisema-readout` | `pat-efficacy-ceiling` | The "more weight loss is always better" assumption gets challenged |

**Totals:** 113 nodes, 200 edges.

---

## What every stored read returns

On a fresh load of `seed.jsonl`, each stored read in `queries/` (the mutations excluded) returns the following. Params are the slug or value used; the last column is the first rows, by slug.

| Stored query | Params | Rows | First rows |
|---|---|---|---|
| `get_compound` | `comp-vk2735-sc` | 1 | `comp-vk2735-sc` |
| `compounds_all` | none | 12 | `comp-semaglutide`, `comp-tirzepatide`, `comp-danuglipron` |
| `compounds_by_phase` | `phase-3` | 6 | `comp-cagrisema`, `comp-maritide`, `comp-vk2735-sc` |
| `compounds_by_mechanism` | `mech-gip-glp1-dual` | 3 | `comp-tirzepatide`, `comp-vk2735-oral`, `comp-vk2735-sc` |
| `compound_sponsor` | `comp-vk2735-sc` | 1 | `co-viking-therapeutics` |
| `compound_trials` | `comp-vk2735-sc` | 2 | `trial-venture`, `trial-vanquish` |
| `compound_signals` | `comp-vk2735-sc` | 2 | `sig-viking-vanquish-init`, `sig-viking-venture-p2` |
| `get_mechanism` | `mech-gip-glp1-dual` | 1 | `mech-gip-glp1-dual` |
| `mechanisms_all` | none | 6 | `mech-gip-glp1-dual`, `mech-glp1-amylin`, `mech-triple-agonist` |
| `mechanism_compounds` | `mech-gip-glp1-dual` | 3 | `comp-tirzepatide`, `comp-vk2735-oral`, `comp-vk2735-sc` |
| `mechanism_signals` | `mech-gip-glp1-dual` | 1 | `sig-lilly-surmount-5-headhead` |
| `mechanism_signals_via_compound` | `mech-gip-glp1-dual` | 5 | `sig-viking-vanquish-init`, `sig-zepbound-osa-approval`, `sig-lilly-surmount-5-headhead` |
| `get_pattern` | `pat-oral-glp1-thesis` | 1 | `pat-oral-glp1-thesis` |
| `patterns_all` | none | 4 | `pat-efficacy-ceiling`, `pat-glp1-pipeline-explosion`, `pat-oral-glp1-thesis` |
| `patterns_by_kind` | `disruption` | 1 | `pat-oral-glp1-thesis` |
| `pattern_signals` | `pat-oral-glp1-thesis` | 2 | `sig-lilly-attain-positive`, `sig-viking-oral-p2-init` |
| `pattern_contradictions` | `pat-oral-glp1-thesis` | 2 | `sig-structure-gsbr-p2a-disappointing`, `sig-pfizer-danuglipron-discontinued` |
| `pattern_drives` | `pat-glp1-pipeline-explosion` | 1 | `pat-efficacy-ceiling` |
| `pattern_contradicts_patterns` | `pat-oral-glp1-thesis` | 0 | none |
| `pattern_insights` | `pat-oral-glp1-thesis` | 1 | `ins-pfizer-failure-is-formulation-not-mechanism` |
| `get_trial` | `trial-vanquish` | 1 | `trial-vanquish` |
| `trials_by_status` | `enrolling` | 2 | `trial-maritime`, `trial-vanquish` |
| `trial_sponsor` | `trial-vanquish` | 1 | `co-viking-therapeutics` |
| `get_deal` | `deal-roche-carmot` | 1 | `deal-roche-carmot` |
| `deals_all` | none | 3 | `deal-pfizer-metsera`, `deal-roche-carmot`, `deal-lilly-versanis` |
| `deal_parties` | `deal-roche-carmot` | 1 | `co-roche` |
| `get_regulatory` | `reg-zepbound-osa` | 1 | `reg-zepbound-osa` |
| `regulatory_recent` | none | 4 | `reg-zepbound-osa`, `reg-medicare-glp1-cvd`, `reg-wegovy-cvd-label` |
| `regulatory_compound` | `reg-zepbound-osa` | 1 | `comp-tirzepatide` |
| `get_company` | `co-viking-therapeutics` | 1 | `co-viking-therapeutics` |
| `company_compounds` | `co-viking-therapeutics` | 2 | `comp-vk2735-oral`, `comp-vk2735-sc` |
| `get_insight` | `ins-mechanism-validated-formulation-is-moat` | 1 | `ins-mechanism-validated-formulation-is-moat` |
| `insights_all` | none | 3 | `ins-mechanism-validated-formulation-is-moat`, `ins-pfizer-failure-is-formulation-not-mechanism`, `ins-cagrisema-miss-is-about-expectations` |
| `insight_patterns` | `ins-mechanism-validated-formulation-is-moat` | 1 | `pat-glp1-pipeline-explosion` |
| `get_program` | `prog-vk2735-sc` | 1 | `prog-vk2735-sc` |
| `programs_all` | none | 2 | `prog-vk2735-oral`, `prog-vk2735-sc` |
| `program_compound` | `prog-vk2735-sc` | 1 | `comp-vk2735-sc` |
| `program_mechanism` | `prog-vk2735-sc` | 1 | `mech-gip-glp1-dual` |
| `program_assumptions` | `prog-vk2735-sc` | 4 | `asmp-best-in-class-tolerability`, `asmp-efficacy-matches-tirzepatide`, `asmp-payer-coverage-sustainable` |
| `program_decisions` | `prog-vk2735-sc` | 1 | `dec-vanquish-interim-readout` |
| `program_competitors` | `prog-vk2735-sc` | 3 | `comp-tirzepatide`, `comp-vk2735-oral`, `comp-vk2735-sc` |
| `program_signals` | `prog-vk2735-sc` | 2 | `sig-viking-vanquish-init`, `sig-viking-venture-p2` |
| `program_landscape_signals` | `prog-vk2735-sc` | 5 | `sig-viking-vanquish-init`, `sig-zepbound-osa-approval`, `sig-lilly-surmount-5-headhead` |
| `get_assumption` | `asmp-oral-displaces-injectable` | 1 | `asmp-oral-displaces-injectable` |
| `assumptions_all` | none | 5 | `asmp-efficacy-matches-tirzepatide`, `asmp-best-in-class-tolerability`, `asmp-payer-coverage-sustainable` |
| `assumption_supporting_signals` | `asmp-oral-displaces-injectable` | 1 | `sig-lilly-attain-positive` |
| `assumption_contradicting_signals` | `asmp-oral-displaces-injectable` | 2 | `sig-structure-gsbr-p2a-disappointing`, `sig-pfizer-danuglipron-discontinued` |
| `get_decision` | `dec-oral-phase3-start` | 1 | `dec-oral-phase3-start` |
| `decisions_upcoming` | none | 2 | `dec-vanquish-interim-readout`, `dec-oral-phase3-start` |
| `decisions_all` | none | 2 | `dec-vanquish-interim-readout`, `dec-oral-phase3-start` |
| `decision_program` | `dec-oral-phase3-start` | 1 | `prog-vk2735-oral` |
| `decision_questions` | `dec-vanquish-interim-readout` | 1 | `q-payer-coverage-trajectory` |
| `decision_assumptions` | `dec-oral-phase3-start` | 2 | `asmp-oral-displaces-injectable`, `asmp-mechanism-safe-at-scale` |
| `get_question` | `q-pfizer-failure-mechanism-risk` | 1 | `q-pfizer-failure-mechanism-risk` |
| `questions_open` | none | 3 | `q-orforglipron-competitive-window`, `q-pfizer-failure-mechanism-risk`, `q-payer-coverage-trajectory` |
| `question_signals` | `q-pfizer-failure-mechanism-risk` | 1 | `sig-pfizer-danuglipron-discontinued` |
| `get_signal` | `sig-pfizer-danuglipron-discontinued` | 1 | `sig-pfizer-danuglipron-discontinued` |
| `recent_signals` | none | 18 | `sig-viking-q4-2025-earnings`, `sig-structure-gsbr-p2a-disappointing`, `sig-pfizer-metsera-acq` |
| `search_signals` | `danuglipron` | 1 | `sig-pfizer-danuglipron-discontinued` |
| `signals_by_domain` | `obesity` | 13 | `sig-viking-q4-2025-earnings`, `sig-structure-gsbr-p2a-disappointing`, `sig-pfizer-metsera-acq` |
| `signal_patterns` | `sig-viking-venture-p2` | 1 | `pat-glp1-pipeline-explosion` |
| `signal_contradictions` | `sig-structure-gsbr-p2a-disappointing` | 1 | `pat-oral-glp1-thesis` |
| `signal_compound` | `sig-pfizer-danuglipron-discontinued` | 1 | `comp-danuglipron` |
| `signal_mechanism` | `sig-pfizer-danuglipron-discontinued` | 1 | `mech-glp1r-agonist` |
| `signal_trial` | `sig-viking-vanquish-init` | 1 | `trial-vanquish` |
| `signal_companies` | `sig-pfizer-danuglipron-discontinued` | 1 | `co-pfizer` |
| `signal_supports_assumptions` | `sig-viking-venture-p2` | 2 | `asmp-best-in-class-tolerability`, `asmp-efficacy-matches-tirzepatide` |
| `signal_contradicts_assumptions` | `sig-pfizer-danuglipron-discontinued` | 1 | `asmp-oral-displaces-injectable` |
| `signal_informs_questions` | `sig-pfizer-danuglipron-discontinued` | 1 | `q-pfizer-failure-mechanism-risk` |
| `signal_artifacts` | `sig-pfizer-danuglipron-discontinued` | 1 | `art-pfizer-danuglipron-pr` |

One read is empty on the seed by construction: `pattern_contradicts_patterns`, because the seed links no pattern as contradicting another.
