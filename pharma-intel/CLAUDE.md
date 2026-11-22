# CLAUDE.md — pharma-intel

Scoped guidance for the `pharma-intel/` starter. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

An Omnigraph schema + seed modeling competitive pharma intelligence from a sponsor's perspective. Uses the SPIKE framework for the intelligence layer, plus two additional layers: **external pipeline** (Compound, Mechanism, Trial, Company, Deal, RegulatoryAction) and **internal context** (Program, Assumption, Decision, OpenQuestion). Schema, seed data, and queries only — no application code.

The reference seed is **Viking Therapeutics** (NASDAQ: VKTX), a public GLP-1/GIP dual-agonist sponsor in obesity. All seed data is sourced from SEC filings, investor presentations, clinicaltrials.gov, and press releases — no MNPI.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — Reference seed description, schema essentials, quick start.
- `seed.md` / `seed.jsonl` — Seed dataset (human-readable / loadable).
- `queries/*.gq` — Read and mutation queries.
- `omnigraph-config.example.yaml` — Read aliases. Merge its `aliases:` into the operator config from the [local setup](../README.md#local-setup); this cookbook ships no `omnigraph.yaml`.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

## Setup

Use the shared [local setup](../README.md#local-setup) with cookbook
`pharma-intel` and graph `pharma`. It owns authentication, the bootstrap writer-lock
handoff, readiness, and served seed loading. Apply later configuration edits with
the [live update workflow](../README.md#live-updates).

Graph id `pharma`. Stored queries and their parameters: `omnigraph queries list --target local --graph pharma`.
Aliases pass parameters by name: `omnigraph alias assumption-contradictions --params '{"slug":"asmp-oral-displaces-injectable"}'` is `omnigraph query assumption_contradicting_signals --target local-reader --graph pharma --params '{"slug":"asmp-oral-displaces-injectable"}'`.

## Writing

Aliases are read-only; mutations run as `omnigraph mutate <name> --target local-writer --graph pharma --params '<json>'`
with every non-optional property supplied. Signatures live in `queries/mutations.gq`. Working example:

```bash
omnigraph mutate add_signal --target local-writer --graph pharma --params '{"slug":"sig-orforglipron-approval","name":"FDA approves orforglipron","brief":"First oral small-molecule GLP-1 approved for obesity.","stagingTimestamp":"2026-09-14T00:00:00Z","createdAt":"2026-09-14T00:00:00Z","updatedAt":"2026-09-14T00:00:00Z"}'
omnigraph mutate link_about_compound --target local-writer --graph pharma --params '{"signal":"sig-orforglipron-approval","compound":"comp-vk2735-sc"}'
```

`--graph` can be omitted only for a target with `default_graph`; the shared setup's targets have none.

## Domain Model

**External Pipeline:** `Compound`, `Mechanism`, `Trial`, `Company`, `Deal`, `RegulatoryAction`
**SPIKE Intelligence:** `Signal`, `Pattern`, `Insight`
**Provenance:** `SourceEntity`, `InformationArtifact`
**Internal Context:** `Program`, `Assumption`, `Decision`, `OpenQuestion`

**Core analytical loop:** Signals form or contradict Patterns (industry-intel style). But signals also edge to internal `Assumption`s and `OpenQuestion`s, which turns the graph into a live view of *which internal beliefs the latest external evidence supports or threatens*. `Decision`s bind programs, assumptions, and open questions into a single queryable object — so "what's on fire before the 2026-07 interim readout?" becomes a graph traversal, not a spreadsheet.

**Design choices to preserve:**

- Three layers, one graph — do not split into separate graphs
- `Assumption`, `Decision`, `OpenQuestion` are **nodes**, not properties on a program — they have their own evidence chains
- Flat enums everywhere: `phase`, `modality`, `route`, `domain`, `kind`, `level`, `status`
- Edge naming: `VerbTargetType` for pipeline/analytical edges (`FormsPattern`, `DevelopedByCompany`), `SignalIntentInternal` for bridge edges (`SupportsAssumption`, `ContradictsAssumption`, `InformsQuestion`)
- Seed data must be real and publicly sourced — every signal traces to an `InformationArtifact` with a live URL

## The questions the README promises

Run as `local-reader` (or `local-writer`); `seed.md` lists what each returns on the fresh seed:

```bash
omnigraph query assumption_contradicting_signals --target local-reader --graph pharma --params '{"slug":"asmp-oral-displaces-injectable"}'
omnigraph query decisions_upcoming --target local-reader --graph pharma
omnigraph query decision_questions --target local-reader --graph pharma --params '{"slug":"dec-vanquish-interim-readout"}'
omnigraph query program_competitors --target local-reader --graph pharma --params '{"slug":"prog-vk2735-sc"}'
omnigraph query program_landscape_signals --target local-reader --graph pharma --params '{"slug":"prog-vk2735-sc"}'
```

## Workflows

The README names eight. All writes go on a branch (`omnigraph branch create <name> --target local-writer --graph pharma`),
pass `--branch <name>` to `mutate` and `query`, and are reviewed with `omnigraph branch diff` and
`omnigraph branch merge <name> --into main --dry-run` before the merge. There is no `act-agent`
role here: `local-writer` can write `main`, so the branch is a habit the agent must keep, not a
policy.

**Signal intake** (capture). Starts when a source publishes. Per document:

1. Read `search_signals` and `recent_signals` to see whether the event is already recorded. `InformationArtifact.link` is `@unique`, but `add_artifact` does not take it, so nothing stops a duplicate: this search is the only guard. To record the URL, set `link` with `omnigraph mutate -e` after the insert, which also makes a repeat of that URL fail.
2. `add_source` (once per publisher), `add_artifact` with its URL, `add_signal`, then `link_signal_artifact` and `link_artifact_source`.
3. Classify: `link_about_compound`, `link_about_trial`, `link_about_mechanism`, `link_relevant_company`.
4. Keep the Writing example's required fields: `stagingTimestamp`, `createdAt`, `updatedAt`.

**Pipeline update** (capture). When a trial registry, regulator or deal announcement adds an asset: `add_compound`, `add_trial`, `add_deal` or `add_regulatory`, then `link_compound_mechanism`, `link_compound_company`, `link_trial_compound`. There is no stored link for a deal's parties or a regulatory action's target; use `omnigraph mutate -e` with an inline insert of `DealLeadParty`, `DealCounterParty` or `TargetsCompound`, and check it with `deal_parties` or `regulatory_compound`.

**Signal triage** (maintain). Starts when a signal is merged. Read what the signal already links to (`signal_supports_assumptions`, `signal_contradicts_assumptions`, `signal_informs_questions`, `signal_contradictions`, `signal_patterns`), find candidate assumptions with `program_assumptions`, `questions_open` and `patterns_all`, then propose links with `link_signal_supports_assumption`, `link_signal_contradicts_assumption`, `link_signal_informs_question`, `link_forms_pattern`, `link_contradicts_pattern`. A link is a judgement: say in the branch commit why.

**Evidence review** (maintain). For each assumption of a program, compare `assumption_supporting_signals` with `assumption_contradicting_signals`. Report an assumption with more against than for; do not edit it.

**Pattern synthesis** (maintain). Read `pattern_signals` and `pattern_contradictions`; where they add up, `add_insight` and `link_highlights_pattern`. `link_drives_pattern` ties one pattern to another.

**Decision brief** (act). Starts when `decisions_upcoming` shows a date within the agent's lead time. Read `decision_program`, `decision_assumptions` (then `assumption_supporting_signals` and `assumption_contradicting_signals` for each) and `decision_questions`. Draft the brief; send it only with the human's approval, through the agent's own tools.

**Competitor alert** (act). Starts when a merged signal appears in `program_landscape_signals`. Draft a note with `signal_contradicts_assumptions` and `signal_informs_questions`; a person approves it before it goes out.

**Question owner nudge** (act). For each row of `questions_open`, read `question_signals`; if a signal is newer than the last nudge, draft a note to `asked_by`.

Nothing in the schema records that a brief, alert or nudge was sent. The agent must keep that
record itself, or it will repeat them.

## What it does not do

- No `act-agent` role: nothing in policy stops an agent writing `main`.
- No stored mutation updates or retires anything: not an assumption's text, a question's `status` (`open` to `resolved`), a decision's `status` or `outcome`. Use `omnigraph mutate -e` for those and review it as a branch.
- `program_competitors` returns every compound targeting a mechanism the program competes in, including the program's own compounds.
- No connectors, no embeddings, no notifications and no record of what was sent.
- `add_artifact` and `add_signal` set only their required fields; `link`, `description` and `domain` need an inline update.
- `Signal` has no link to the `Decision` it bears on; read it through the assumption or question.

## The Demo "Wow" Queries

These are the queries the seed is shaped to light up — preserve them when iterating:

| Alias | Input | Expected outcome |
|-------|-------|------------------|
| `assumption-contradictions` | `asmp-oral-displaces-injectable` | 2 signals (Pfizer + Structure) contradicting a strategic assumption from a different silo |
| `decision-questions` | `dec-vanquish-interim-readout` | The open question that needs to be answered before the committee meeting |
| `decision-assumptions` | `dec-oral-phase3-start` | Two assumptions — one currently contradicted, one supported |
| `pattern-contradictions` | `pat-oral-glp1-thesis` | The same Pfizer + Structure signals surfaced from the pattern angle |
| `signal-informs-questions` | `sig-pfizer-danuglipron-discontinued` | A Viking clinical-team open question informed by a Pfizer event |
| `program-landscape-signals` | `prog-vk2735-sc` | 5 signals across every compound targeting the program's mechanism, time-sorted — "what's happening in my space" |
| `mechanism-signals-via-compound` | `mech-gip-glp1-dual` | Same fan-out from the mechanism angle (transits Mechanism → Compound → Signal) |

If a schema or seed change breaks any of these, the three-layer model is not delivering — fix the seed rather than compromising the schema.

## Agent Workflow

Use this starter as a decision-intelligence loop, not just a lookup table:

1. Start from a decision, program, assumption, or fresh external signal.
2. Expand internal context with aliases like `decision-assumptions`, `decision-questions`, `program-competitors`, and `program-landscape-signals`.
3. Build the evidence matrix with `assumption-supports` and `assumption-contradictions`.
4. Trace signal impact with `signal-supports-assumptions`, `signal-contradicts-assumptions`, and `signal-informs-questions`.
5. If using web research, map each new public signal to existing graph objects before proposing data changes: `AboutCompound`, `RelevantCompany`, `FormsPattern` / `ContradictsPattern`, `SupportsAssumption` / `ContradictsAssumption`, and `InformsQuestion`.
6. Report the decision impact: what changed, which assumptions moved, which questions remain open, and which graph update should be made.

## When Editing

- Consult [Omnigraph schema principles](https://github.com/ModernRelay/omnigraph) for design guidance
- Use `@rename_from(...)` on property/type renames for migration support
- Keep README.md in sync with schema.pg
- Prefer semantic edge names over generic ones (`ContradictsAssumption` not `RelatedTo`)
- Required vs optional is deliberate — don't add `?` without reason
- No embeddings in this cookbook — the narrative surfaces are graph-structured, not vector-search-driven
