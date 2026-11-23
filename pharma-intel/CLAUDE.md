# CLAUDE.md — pharma-intel

Scoped guidance for the `pharma-intel/` starter. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

An Omnigraph schema + seed modeling competitive pharma intelligence from a sponsor's perspective. Uses the SPIKE framework for the intelligence layer, plus two additional layers: **external pipeline** (Compound, Mechanism, Trial, Company, Deal, RegulatoryAction) and **internal context** (Program, Assumption, Decision, OpenQuestion). Schema, seed data, and queries only — no application code.

The reference seed is **Viking Therapeutics** (NASDAQ: VKTX), a public GLP-1/GIP dual-agonist sponsor in obesity. All seed data is sourced from SEC filings, investor presentations, clinicaltrials.gov, and press releases — no MNPI.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — The landing page: what the cookbook gives, its workflows and its questions. Commands live here, not there.
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

## Questions

The four questions the README features, as commands (params are the sample
data's):

```bash
omnigraph query assumption_contradicting_signals --target local-reader --graph pharma --params '{"slug":"asmp-oral-displaces-injectable"}'
omnigraph query decisions_upcoming --target local-reader --graph pharma
omnigraph query program_competitors --target local-reader --graph pharma --params '{"slug":"prog-vk2735-sc"}'
omnigraph query compounds_by_mechanism --target local-reader --graph pharma --params '{"mechanism":"mech-gip-glp1-dual"}'
```

`program_competitors` returns every compound on the program's mechanisms,
including the program's own, so the sample returns VK2735 SC itself.

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

## Workflows

The README's workflow table, step by step. Each runs the same way: something
starts it, the agent reads through stored queries, it acts, a person decides.

**Review.** Writers here can change `main` and merge; no role is limited to
branches. An agent must create its own branch
(`omnigraph branch create signals/<date> --target local-writer --graph pharma`),
pass `--branch signals/<date>` to every `omnigraph mutate`, and leave the merge
to a person. Read `omnigraph branch diff signals/<date> --target local-writer
--graph pharma` before merging. Enforcing branches would need an agent role in
`policies/graph.policy.yaml` as company-brain has; this cookbook has none.

**Stored writes only add.** There is no stored write to update a property, so
an agent cannot resolve an open question, record a decision's outcome, change a
compound's phase or retire a stale signal. Say so in its report and leave it to
a person.

**Capture**

- *Signal intake.* Start: a new press release, filing, registry entry or agency
  letter. Read `recent_signals` and `search_signals` to avoid a duplicate.
  Write `add_artifact`, `add_source` if the publisher is new, `add_signal`,
  `link_signal_artifact`, `link_artifact_source`. `add_artifact` takes no URL,
  so the stored writes leave the artifact without its address; a merge load of
  the artifact on the branch can carry it. `add_signal` takes only slug, name, brief and times, so
  `domain` and `description` stay unset.
- *Pipeline tracking.* Start: a new compound, trial, deal or agency action.
  Read `compounds_all`, `trials_by_status`, `deals_all`. Write `add_compound`,
  `add_trial`, `link_compound_mechanism`, `link_compound_company`,
  `link_trial_compound`. `add_deal` and `add_regulatory` take only a name, and
  have no stored link to the parties.
- *Signal mapping.* Start: a new signal on a branch. Read `compounds_all`,
  `mechanisms_all`, `patterns_all`. Write `link_about_compound`,
  `link_about_mechanism`, `link_about_trial`, `link_relevant_company`,
  `link_forms_pattern`, `link_contradicts_pattern`.

**Maintain**

- *Assumption review.* Start: a signal that has no assumption link yet. Read
  `assumptions_all`, `assumption_supporting_signals`,
  `assumption_contradicting_signals`. Write
  `link_signal_supports_assumption` or `link_signal_contradicts_assumption`.
  A person decides whether a signal really contradicts a belief.
- *Open question watch.* Read `questions_open` and `question_signals`; write
  `link_signal_informs_question`.
- *Pattern synthesis.* Read `pattern_signals`, `pattern_contradictions`,
  `pattern_insights`; write `add_insight`, `link_highlights_pattern`,
  `link_drives_pattern`. An insight is a conclusion, so a person reviews it.
- *Landscape check.* Read `program_landscape_signals`,
  `mechanism_signals_via_compound`, `recent_signals`. It writes nothing.

**Act.** None of these has an integration; the agent uses its own tools to
send. Keep them to telling and drafting unless a person approves. The record
cannot show that a message was sent, so the agent tracks that itself.

- *Decision briefing.* Start: a date within a set window of `decision_date`.
  Read `decisions_upcoming`, `decision_assumptions`, `decision_questions`,
  `assumption_contradicting_signals`. Send the decider (`decider` on the
  decision) the assumptions, open questions and contradicting signals.
- *Signal alert.* Start: a merged signal with a `ContradictsAssumption` or
  `InformsQuestion` link. Read `signal_informs_questions`, `questions_open` (it
  has `asked_by`), `signal_contradicts_assumptions`. Tell the asking team.
  Assumptions have no owner field, so name the program team.
- *Competitor digest.* Start: a schedule. Read `recent_signals`,
  `program_competitors`, `deals_all`, `regulatory_recent`.

## Scenarios

To test a what-if, add a signal and its links on a scenario branch, then read
with `--branch`: `omnigraph query assumption_contradicting_signals --target
local-reader --graph pharma --branch scenario/<name> --params '{...}'`. Delete
the branch if the scenario is not adopted.

## When Editing

- Consult [Omnigraph schema principles](https://github.com/ModernRelay/omnigraph) for design guidance
- Use `@rename_from(...)` on property/type renames for migration support
- Keep README.md in sync with schema.pg: its data model names types, and its workflows and questions name stored queries (`python3 scripts/check-cookbooks.py --site` checks both)
- Prefer semantic edge names over generic ones (`ContradictsAssumption` not `RelatedTo`)
- Required vs optional is deliberate — don't add `?` without reason
- No embeddings in this cookbook — the narrative surfaces are graph-structured, not vector-search-driven
