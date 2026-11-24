# CLAUDE.md — binder-campaign

Scoped guidance for the `binder-campaign/` cookbook. Repo-wide conventions
live in `../CLAUDE.md`, and serving a cookbook locally lives in
[local setup](../docs/local-setup.md). For general OmniGraph operations use
the **omnigraph** skill; this file covers only what is specific to this
cookbook.

## What This Is

One AI-run de novo protein design campaign as one typed graph: the targets,
every design that reached a lab and how it was made, the in-silico scores and
the thresholds they were judged against, what each lab measured, and the
claims that a design binds a target with the rules they hold under and the
gaps in the evidence beneath them. Which designs count as binders is derived
by stored queries on every read, never stored. Schema, seed, queries and
policies; no application code and no connectors.

The seed is **real**, where the other cookbooks' seeds are invented:
Anthropic's scorpion-toxin binder design campaign of October 2026.

## Key Files

- `schema.pg` — 21 node types, 33 edge types.
- `queries/claims.gq`, `designs.gq`, `scores.gq`, `assays.gq`,
  `campaign.gq` — 49 stored reads.
- `queries/mutations.gq` — 29 stored writes.
- `seed.jsonl` / `seed.md` — reference seed. Keep them in sync; `seed.md`
  describes the release row type by row type and names the counts that
  surprise people. It does not list what each read returns.
- `policies/graph.policy.yaml` — reader, writer and admin roles. There is no
  `act-agent` role here.
- `README.md` — the cookbook's page, on the shared template in
  "Writing a cookbook README" in `../CLAUDE.md`. Its first paragraph is
  `about` in `site.json`, and its questions table is `site.json`'s questions;
  change the two together.

## The four layers

| Layer | Types |
|---|---|
| Targets | `Target`, `Hotspot` |
| Designs | `Design`, `Designer`, `DesignTool`, `BackboneFamily`, `SequenceMethod` |
| Evidence | `Score`, `Threshold`, `Predictor`, `Measurement`, `Lab`, `SpecificityCheck`, `Control` |
| Claims | `BinderClaim`, `Criterion`, `EvidenceGap` |
| Process | `CampaignWindow`, `SelectionRule`, `AgentRole`, `Source` |

The claims layer carries the weight. A `BinderClaim` is somebody's reading of
the measurements, not the measurements: it links to the `Measurement` rows it
rests on (`ClaimRestsOn`), to every `Criterion` it survives (`ClaimSurvives`),
and to any `EvidenceGap` recorded against it.

## Rules

- Graph id `binders`, not the folder name. Stored queries and parameters:
  `omnigraph queries list --target local --graph binders`.
- Do not add stored fields for anything a query derives: no "is a binder",
  "survives" or "has a gap" flags. Extend the query instead.
- **A claim has three standings, not two.** `status` is `asserted` (holds
  under the applied criterion), `provisional` (only a looser rule admits it,
  and it was never claimed as a binder) or `withdrawn` (asserted once, later
  taken back). A boolean conflated the last two, which hid the difference
  between a claim nobody made and a claim somebody retracted. Nothing deletes
  a claim; `withdraw_claim` moves it to `withdrawn` and the row stays.
- **A claim never carries its own evidence.** Properties on `BinderClaim` say
  who recorded it and when; the binding values live on `Measurement`. Adding
  a value to a claim would make the two disagree the first time a lab refits.
- **A criterion is a node, never a filter in a query.** The report re-counts
  its binders under a dozen rules and gets anything from 7 to 18. Each rule is
  a `Criterion` with the count the report gives it, and `ClaimSurvives` edges
  say who lives under it. Writing one of those rules as a `where` clause moves
  the definition into the query, where no reader can see it.
- **A gap is a fact, not an omission.** Where the record is silent, there is
  an `EvidenceGap` saying so, citing the source that states it. Never fill a
  gap with a plausible value; add a gap instead.
- An absent measurement and a negative measurement are different facts. Write
  no row rather than a false `no_hit`.
- Enum values use underscores: `no_hit`, `single_domain`, `blocks_check`. The
  query language cannot filter an enum whose value carries a hyphen, and an
  enum cannot be matched as a literal in a binding block at all — compare it
  in a filter line instead:

  ```gq
  $m: Measurement
  $m.result = "hit"
  ```

- Keep the seed faithful to its sources and keep the CC BY 4.0 attribution.
  Everything transcribed from the report cites a `Source`.
- After a schema, query or seed change, re-run the reads against a fresh seed,
  update `seed.md`, and run `python3 ../scripts/check-cookbooks.py
  binder-campaign` from the repository root.

## A node arrives with its required edges

`MeasurementOf`, `MeasurementAgainst`, `MeasurementAtLab`, `ClaimAbout` and
`ClaimAgainst` are `@card(1..1)`. A write is refused when it leaves a node it
inserted outside those bounds, so a `Measurement` or a `BinderClaim` has to
arrive in the same mutation as its links. `add_measurement` takes `$design`,
`$target` and `$lab`, and `assert_binder_claim` takes `$design` and `$target`,
for exactly that reason. There are no separate linking writes, and adding one
would produce a write that always fails.

`ClaimRestsOn` is unbounded, which is why `ground_claim` is separate: the
measurements have to be in the graph before a claim can rest on them, and a
claim resting on nothing is a finding that `claims_with_gaps` surfaces rather
than an error.

The same applies to a bulk load: `Score`, `SpecificityCheck`, `Control`,
`Threshold` and `Hotspot` all have required edges, so each arrives in the same
batch as its own. Their stored writes are built that way too: `record_scores`,
`record_specificity_check`, `add_control`, `set_threshold` and `add_hotspot`
each insert the node and its required edges in one query.

## Descriptions are the interface, not the comments

Every node, most edges and the properties that need it carry `@description`,
and the types with write rules carry `@instruction`. They are what
`omnigraph schema show` hands an agent; a `//` comment reaches nobody but
someone reading the file. When you add a type, describe it there — say what it
is for and what it is not, not what its name already says.

## An empty field is not a defect

`kon_per_ms`, `koff_per_s`, `binding_strength`, `replicates` and `measured_on`
are null throughout this seed. They are not speculative: ProteinBase records
every one of them, and the schema has to hold a second campaign, not only this
one. Do not strip them because the seed does not use them, and do not
back-fill them with a plausible value — if a campaign records them, populate
them; if it does not, leave them and let the absence show.

`src:technical-report` carries no `licence`, and that is the field working
as its description says: what the data may be reused for, absent where
nothing grants it. The report states CC BY 4.0 for the data release and
no licence for itself, so the row claims none. `src:data-release` carries
it. Do not copy a licence across sources because they were published
together.

`fit_model` is the exception that earns the rest. A KD is derived from the
rate constants by a chosen model, so a value whose model nobody recorded
cannot be reproduced. The report states every value here came from a 1:1 fit,
so every measurement carrying a value names it, and
`values_without_a_fit_model` returns nothing against this seed. Run it against
your own and it probably will not.

## Does it fit another campaign?

Tested against [ProteinBase](https://huggingface.co/datasets/adaptyvbio/proteinbase)
(Adaptyv Biosystems, ODC-BY), which holds 4,280 designs against 40 targets —
these five scorpion toxins among them, and 35 that are nothing like them.

The spine takes a non-toxin slice unchanged. Nipah glycoprotein G there is
1,030 designs, 103 that bound and 928 that did not, from 206 independent
designers using 98 design methods. `Target`, `Design`, `DesignTool`,
`Measurement`, `Lab`, `BinderClaim`, `Criterion` and `EvidenceGap` all take it
as they stand.

`Designer` is a node and not a property for that slice's sake: 206 of them
against one target there, one here standing for the campaign's agents. A
public benchmark is many people designing against the same protein, and that
has to be a node.

## The known gap in the model: a design run is not a node

`MadeWithTool` goes straight from a `Design` to a `DesignTool`, which does two
jobs at once. In PROV-O terms the tool is an **Agent** and the run is an
**Activity**, and a backbone `wasGeneratedBy` the run, not by the tool. The
run is where seeds, parameters and compute belong, and collapsing it loses
them.

This schema collapses it on purpose: the data release records which tool drew
each backbone and nothing about the run that drew it, and a `DesignRun` node
with no properties would be modelling theatre. If your campaign records its
runs — and it should — insert one:

```
Design --generatedBy--> DesignRun --ranTool--> DesignTool
```

with the seed, parameters and wall time on `DesignRun`. That is the first
extension to make, and the one that makes a campaign reproducible rather than
merely attributed.

## Why a graph rather than a notebook

For one campaign, analysed once, by one person: use a notebook. The released
CSVs load into a dataframe in a line, and a sensitivity analysis is a dozen
lines of filtering. A graph is overhead you do not need, and it is better to
say so than to pretend otherwise. Four things change that answer.

- **The question goes more than one hop.** Design lineage is a redesign of a
  redesign, or a fusion of two domains that were themselves selected. Asked of
  tables, that is a join against itself, as many times as the chain is long,
  rewritten whenever the question changes. Here it is `derivedFrom{1,3}`.
- **A claim is not a column.** In a results sheet, "is a binder" is a column
  somebody computed, and when the rule changes the column is overwritten.
  There is nowhere to put who decided, under which rule, and on what evidence.
  Separate the three and changing the rule adds a row instead of destroying
  one.
- **A gap has no column either.** "The construct used in this assay was never
  written down" is not a value that fits in a results sheet. It ends up in a
  footnote in a PDF, which is where it was. As a node it links to the four
  claims it undermines, and a query finds them.
- **More than one writer.** A notebook has one author. When several people and
  agents propose changes, you want a schema enforced on every write, each
  author on a branch, and a person merging.

## Running it

Use the shared [local setup](../docs/local-setup.md) with folder
`binder-campaign` and graph `binders`, and load `seed.jsonl`. Its targets are
the roles used below: `local` (admin), `local-writer` for scientists, and
`local-reader`. There is no agent target, because this cookbook's policy has
no agent actor; an agent runs as `local-writer` and keeps to its own branch by
convention.

The answers the README promises, as commands. The README's Sample data
section says what each returns on the fresh seed:

```bash
omnigraph query claims_under_criterion --target local-reader --graph binders --params '{"criterion":"crit:kd-within-tenfold"}'
omnigraph query claims_with_gaps --target local-reader --graph binders
omnigraph query design_provenance --target local-reader --graph binders --params '{"slug":"design:888c8f04"}'
omnigraph query score_behind_claim --target local-reader --graph binders --params '{"claim":"claim:cn2-b1-cn2"}'
```

Merge the `aliases:` of [`omnigraph-config.example.yaml`](omnigraph-config.example.yaml)
into `$OMNIGRAPH_HOME/config.yaml` for a short name per read, such as
`omnigraph alias claims` or
`omnigraph alias survives --params '{"criterion":"crit:no-ovalbumin"}'`.

## Derived reads

Every verdict is a stored read, never a stored field:

| Question | Stored query |
|---|---|
| What is claimed to bind, and where? | `binder_claims`, `claims_by_target`, `claims_by_status` |
| What does one claim rest on? | `claim_evidence`, `claims_fully_evidenced` |
| Which rules exist, and who survives each? | `criteria_all`, `criterion_survivor_counts`, `claims_under_criterion`, `claims_lost_under` |
| What cannot be checked? | `claims_with_gaps`, `evidence_gaps`, `gap_reach`, `uncited_gaps` |
| What was only ever provisional, or taken back? | `provisional_claims`, `withdrawn_claims` |
| How was a design made, and from what? | `get_design`, `design_provenance`, `design_lineage`, `fusion_domains` |
| Which tools and designers produced what? | `designs_by_tool`, `tools_behind_binders`, `designers`, `designs_by_designer` |
| What was it aimed at? | `design_targets`, `multi_target_designs`, `targets`, `hotspots` |
| Which bars were set, and what cleared them? | `thresholds_all`, `design_scores`, `score_behind_claim`, `top_scores`, `cleared_against` |
| What scored well and bound nothing? | `cleared_but_did_not_bind`, `scores_from_rerun`, `designs_added_after` |
| What did the labs measure? | `measurements_for_design`, `tightest_binding`, `upper_limit_only`, `lab_disagreements` |
| Did the assay work, and was it specific? | `failed_controls`, `controls_for_target`, `off_target_hits`, `specificity_for_design` |
| Can a value be reproduced? | `values_without_a_fit_model` |
| How was the campaign run? | `campaign_windows`, `selection_rules`, `rules_that_replaced`, `agent_roles`, `sources` |

`cleared_but_did_not_bind` with `{"target":"target:ts1"}` is worth running on
its own. It returns **131** designs that cleared every predictor's threshold
against Ts1, not one of which bound it — the report reaches the same
conclusion, that the final score tracked success rates across design sets but
did not pick out binders within one.

## Workflows

Two layers write here. The campaign as it runs — a target chosen, an epitope
picked, a bar registered, a design generated, a predictor's reading, a lab's
result — and the editorial layer above it: a rule to count under, a gap someone
notices, a claim withdrawn when the evidence beneath it moves. Every write
runs on a branch.

### A round of the campaign: aim, generate, score, shortlist

The loop an agent runs. Each node arrives with its required edges, so the
`add_hotspot`, `set_threshold` and `record_scores` calls below cannot leave a
half-built row behind.

```bash
omnigraph branch create run/round-7 --target local-writer --graph binders
# 1. Aim: the target, the epitope residues, and the bar, before any scoring.
omnigraph mutate add_target --target local-writer --graph binders --branch run/round-7 --params '{
  "slug":"target:test-toxin","name":"Test toxin","family":"beta","binding_site":"site 4",
  "organism":"Test sp.","region":null,"uniprot":null,"length_aa":66,"sequence":"AAAA",
  "structure_used":"PDB 0TST","structure_is_predicted":false}'
omnigraph mutate add_hotspot --target local-writer --graph binders --branch run/round-7 --params '{"slug":"hotspot:test-e15","target":"target:test-toxin","residue":"E15","design_models_in_contact":12}'
omnigraph mutate set_threshold --target local-writer --graph binders --branch run/round-7 --params '{
  "slug":"threshold:test-esmfold2","target":"target:test-toxin","predictor":"pred:esmfold2",
  "ipsae":0.15,"scdockq":0.23,"set_before_scoring":true}'
# 2. Generate: register the tool and the agent, then the design with its provenance.
omnigraph mutate add_design_tool --target local-writer --graph binders --branch run/round-7 --params '{"slug":"tool:your-generator","name":"Your generator"}'
omnigraph mutate add_designer --target local-writer --graph binders --branch run/round-7 --params '{"slug":"act:scout-agent","name":"Scout agent","kind":"agent","affiliation":null}'
omnigraph mutate add_backbone_family --target local-writer --graph binders --branch run/round-7 --params '{"slug":"family:F99","name":"F99"}'
omnigraph mutate add_design --target local-writer --graph binders --branch run/round-7 --params '{
  "slug":"design:test-1","uuid":"test0001","name":"Test-B1","design_set":1,"rank_in_set":1,
  "format":"single_domain","length_aa":104,"sequence":"MMMM","redesign_round":0,
  "substitutions_from_parent":null,"linker":null,"added_after_campaign":false,
  "designer":"act:scout-agent","tool":"tool:your-generator","backbone_family":"family:F99",
  "sequence_method":"method:solublempnn","target":"target:test-toxin"}'
# 3. Score: read the sequence and the bar, co-fold outside, record the reading.
omnigraph query get_design --target local-reader --graph binders --branch run/round-7 --params '{"slug":"design:test-1"}'
omnigraph query thresholds_all --target local-reader --graph binders --branch run/round-7
omnigraph mutate record_scores --target local-writer --graph binders --branch run/round-7 --params '{
  "slug":"score:test-1","design":"design:test-1","target":"target:test-toxin","final_score":0.81,
  "ipsae_esmfold2":0.72,"ipsae_esmfold2_fast":0.66,"ipsae_protenix":0.70,
  "scdockq_esmfold2":0.91,"scdockq_esmfold2_fast":0.88,"scdockq_protenix":0.90,
  "cleared_thresholds":true,"from_later_rerun":false}'
# 4. Shortlist: what cleared, under the campaign's own rules. Then a scientist reviews.
omnigraph query cleared_against --target local-reader --graph binders --branch run/round-7 --params '{"target":"target:test-toxin"}'
omnigraph query selection_rules --target local-reader --graph binders --branch run/round-7
omnigraph branch diff run/round-7 --target local-writer --graph binders
```

A redesign keeps its parent, and a fusion its two domains. The child is a
design in its own right, so it arrives the same way:

```bash
omnigraph mutate add_design --target local-writer --graph binders --branch run/round-7 --params '{
  "slug":"design:test-2","uuid":"test0002","name":"Test-B2","design_set":1,"rank_in_set":2,
  "format":"single_domain","length_aa":104,"sequence":"MMMN","redesign_round":1,
  "substitutions_from_parent":"M4N","linker":null,"added_after_campaign":false,
  "designer":"act:scout-agent","tool":"tool:your-generator","backbone_family":"family:F99",
  "sequence_method":"method:solublempnn","target":"target:test-toxin"}'
omnigraph mutate derive_design_from --target local-writer --graph binders --branch run/round-7 --params '{"design":"design:test-2","parent":"design:test-1"}'
omnigraph mutate add_fusion_domain --target local-writer --graph binders --branch run/round-7 --params '{"design":"design:test-2","domain":"design:test-1","position":"a"}'
omnigraph mutate intend_design_against --target local-writer --graph binders --branch run/round-7 --params '{"design":"design:test-2","target":"target:cn2"}'
```

The order and the assay are not in here. `cleared_against` and
`selection_rules` give the agent the shortlist and the rules it has to respect;
placing the order with a vendor and queueing the run at a lab happen through
the agent's own tools, and nothing in the record holds them back or records
that they happened. Keep them to drafting until a scientist approves.

### A new rule, and who survives it

```bash
omnigraph branch create review/ova-rule --target local-writer --graph binders
omnigraph mutate add_criterion --target local-writer --graph binders --branch review/ova-rule --params '{
  "slug":"crit:strict","name":"Strict","rule":"No signal against any unrelated protein.",
  "applied":false,"binders_under_rule":9,"recorded_at":"2026-11-23T00:00:00.000Z"}'
omnigraph mutate claim_survives_criterion --target local-writer --graph binders --branch review/ova-rule --params '{"claim":"claim:cn2-b2-cn2","criterion":"crit:strict"}'
omnigraph query criterion_survivor_counts --target local-reader --graph binders --branch review/ova-rule
omnigraph branch diff review/ova-rule --target local-writer --graph binders
omnigraph branch merge review/ova-rule --into main --dry-run --target local-writer --graph binders
omnigraph branch merge review/ova-rule --into main --target local-writer --graph binders
```

`criterion_survivor_counts` puts the graph's own count beside the count the
rule's source reports. Where the two disagree, the seed is incomplete, not the
rule. Only one criterion carries `applied: true`; adding a second applied rule
is a modelling error no check catches.

### A lab's results, then the verdict

Evidence comes before the claim that rests on it:

```bash
omnigraph mutate add_measurement --target local-writer --graph binders --branch intake-run-7 --params '{
  "slug":"measure:888c8f04-cn2-twist-r2","design":"design:888c8f04","target":"target:cn2",
  "lab":"lab:twist-bioscience","method":"spr","result":"hit","kd_nm":4.1,
  "kd_is_upper_limit":false,"rmax_ratio":0.94,"note":"Second run, 1:1 fit."}'
omnigraph query measurements_for_design --target local-reader --graph binders --branch intake-run-7 --params '{"slug":"design:888c8f04"}'
omnigraph mutate assert_binder_claim --target local-writer --graph binders --branch intake-run-7 --params '{
  "slug":"claim:cn2-b8-cn2","design":"design:888c8f04","target":"target:cn2",
  "statement":"Cn2-B8 binds Cn2 and meets the applied criterion.","status":"asserted",
  "recorded_at":"2026-11-23T00:00:00.000Z","recorded_by":"R. Comerford"}'
omnigraph mutate ground_claim --target local-writer --graph binders --branch intake-run-7 --params '{"claim":"claim:cn2-b8-cn2","measurement":"measure:888c8f04-cn2-twist-r2"}'
omnigraph query claim_evidence --target local-reader --graph binders --branch intake-run-7 --params '{"claim":"claim:cn2-b8-cn2"}'
```

A claim's `recorded_by` is a person, and asserting or withdrawing one is a
person's step. An agent proposes it on a branch and a scientist merges.

### Recording a gap

```bash
omnigraph mutate record_gap --target local-writer --graph binders --branch gaps-2026-11 --params '{
  "slug":"gap:ts1-no-binders","what":"No design bound Ts1 at either lab.",
  "effect":"Nothing supports a claim against Ts1, and 131 designs cleared every bar.",
  "severity":"noted","recorded_at":"2026-11-23T00:00:00.000Z"}'
omnigraph mutate gap_affects_target --target local-writer --graph binders --branch gaps-2026-11 --params '{"gap":"gap:ts1-no-binders","target":"target:ts1"}'
omnigraph mutate cite_gap --target local-writer --graph binders --branch gaps-2026-11 --params '{"gap":"gap:ts1-no-binders","source":"src:technical-report"}'
omnigraph query uncited_gaps --target local-reader --graph binders --branch gaps-2026-11
omnigraph query gap_reach --target local-reader --graph binders --branch gaps-2026-11
```

`uncited_gaps` returns nothing on the fresh seed, which is the point: every
gap cites the source that states the absence. `gap_affects_claim` and
`gap_affects_design` link a gap to the claims and designs it reaches.

### Withdrawing a claim

```bash
omnigraph mutate withdraw_claim --target local-writer --graph binders --branch retract-lqhiii --params '{
  "slug":"claim:lqhiii-b1-lqhiii",
  "statement":"Withdrawn: assessed at one lab only, and the second lab did not reproduce it."}'
omnigraph query withdrawn_claims --target local-reader --graph binders --branch retract-lqhiii
```

The row stays, with status `withdrawn`, so a reader can see it was once made.
A deletion would hide that.

### Keeping a source current

```bash
omnigraph mutate mark_source_fetched --target local-writer --graph binders --branch refresh --params '{"slug":"src:data-release","fetched_on":"2026-11-23"}'
omnigraph query sources --target local-reader --graph binders --branch refresh
```

The first read sets `fetched_on`; every re-read moves it, even one that
changed nothing, so a stale copy can be told from a current one.

### Agents over MCP

`omnigraph mcp` relays an agent host's MCP over stdio to the server through a
registered target, so the token never enters the agent's configuration:

```json
{"command": "omnigraph", "args": ["mcp", "--target", "local-writer", "--graph", "binders"],
 "env": {"OMNIGRAPH_HOME": "/Users/you/.omnigraph-cookbooks", "OG_LOCAL_WRITER_TOKEN": "local-writer-token"}}
```

Each stored read is a call to the `query` tool. Add `--write` to the bridge
for the write tools. This cookbook's policy has no actor confined to branches,
so nothing stops a writer's token reaching `main`: the branch is a convention
here, and the review before a merge is the only check. Add an `act-agent`
actor and a rule that refuses `change` on `main` if you need it enforced —
`company-brain` and `hardware-program` have one to copy.

## Seed data and its limits

`seed.jsonl` is built from the public
[data release](https://huggingface.co/datasets/Anthropic/scorpion-toxin-binder-design)
(CC BY 4.0) plus facts transcribed from the
[technical report](https://assets.claude.com/31ac578806cffd8b3d92d8affe6edc4c04d502e1.pdf).
Everything transcribed cites a `Source`.

Counts that trip people up:

- **17 asserted claims, 21 claims in all.** Four are `provisional`: designs
  only a looser rule admits, never claimed as binders.
- **15, not 17, in the sensitivity analysis.** Two LqhIII claims were
  assessed at one lab only, so the report's table varies the other 15. The
  `ClaimSurvives` edges follow the report and cover those 15, which is why
  `claims_lost_under` returns 4 rather than 6 for a rule that admits 11.
- **1,477 measurements, 665 scores.** Scores exist only for the toxins a
  design was intended against; the labs measured beyond intent, which is what
  makes "no hit against a toxin it was not made against" a usable criterion.
- **Three windows, four follow-ups.** The report describes an initial prompt
  and four follow-ups. The seed keeps the three stretches in which the
  design sets themselves changed: the original window, the first follow-up
  and the third. The second asked only that nothing go to Twist Bioscience
  before review, and the fourth appears instead as `rule:toxins-passed-order`,
  the selection rule that replaced the diversity caps for set 8.
- **No per-design window.** The report says which rules changed between the
  windows, but not which window selected each design. `CampaignWindow` and
  `SelectionRule` are campaign-level; do not invent edges from designs to
  them.
- **No gap touches a design.** `GapAffectsDesign` exists and the seed uses
  none of it: every recorded gap reaches claims or targets.

## Standards

**There is no community ontology or reporting standard for de novo protein
design.** Not from Rosetta Commons, the IPD, a journal or a consortium.
Treat a claim otherwise with suspicion. The nearest thing to a shared schema
is [ProteinBase](https://huggingface.co/datasets/adaptyvbio/proteinbase)
(Adaptyv Biosystems), where each design carries a `designMethod` and a list of
evaluations shaped `{type, metric, unit, value, target, method}` — close to
the Designs and Evidence layers here, and worth matching if you publish
designs. It does not claim to be a standard.

What does exist covers the layers either side of the design itself, and this
schema borrows from three of them at the cost of one property each.

| Standard | Covers | Here |
|---|---|---|
| [PROV-O](https://www.w3.org/TR/prov-o/) — W3C Recommendation, 2013 | Provenance: entities, activities, agents, `wasDerivedFrom` | `DerivedFrom` is `prov:wasDerivedFrom` under another name |
| [PSI-MI](https://www.psidev.info/groups/molecular-interactions) — HUPO-PSI, maintained | Controlled vocabulary for molecular interactions and how they were detected | `Measurement.detection_method_id` carries `MI:0107`, surface plasmon resonance |
| [ECO](https://evidenceontology.org) — v2026-07-10 | The kind of evidence behind an assertion | `Measurement.evidence_type_id` carries `ECO:0001127`, SPR evidence |
| [OBI](https://obi-ontology.org) — v2026-11-03 | Assays as planned processes; `OBI:0002105` is a dissociation-constant assay | Named, not modelled |
| [Pfam / InterPro](https://www.ebi.ac.uk/interpro/) — Pfam 39.0 | Protein families | A natural target has an accession; a de novo backbone has none, which is the point |

Those two ids cost nothing and make the binding values joinable with IntAct
and IMEx, and the evidence readable by anything that speaks ECO.

Not adopted, deliberately: **OBI** and **BAO** wholesale, because importing
either drags in BFO's upper-ontology commitments and this is a cookbook, not a
reference ontology; **SEPIO**, which models assertion, evidence line and
criterion much as the claims layer here does and is worth reading as prior
art, but whose OWL form is abandoned and whose LinkML successor is
mid-migration and variant-interpretation-centric; **Allotrope** and **MIAPE**,
which describe instrument files and proteomics, a layer below this one.
**MIMIx**, the PSI-MI minimum-information guideline for interaction
experiments, is the closest existing checklist to the Evidence layer if you
need one.

## Extending

- Add a `DesignRun` node, as above. It is the first extension worth making.
- Add a stored write per campaign-record type if you are loading a campaign
  incrementally rather than in one batch. Each one has to carry its required
  edges, as "A node arrives with its required edges" says.
- Add a place to note that an outside action was taken — a lab asked, an
  author told — if you run the acting workflows in the README. Nothing in the
  schema holds that today.
- Add an `act-agent` actor to `policies/graph.policy.yaml`, kept to
  unprotected branches, if agents are to write without reaching `main`.

Change the schema with `cluster plan` and `cluster apply` against the running
server, as in [live updates](../docs/local-setup.md#live-updates).

## What it does not do

- **No neutralisation data.** Binding is shown; stopping the toxin is not.
  The campaign tested none, in cells or in animals, so neither does this.
- **No untested designs.** 318,484 were generated; the 211 that reached a lab
  are here.
- **No structures.** A design has a sequence and no structure, and nothing
  holds the predicted complex a predictor produced. `Target.structure_used`
  is a string naming a PDB chain, not a structure the graph has. This bites
  hardest at scoring: scDockQ is the DockQ between the predicted complex and
  the design model, so the record keeps the number while neither structure it
  comes from is reachable. The release ships them under `structures/`, one
  folder per design. Holding them as Blob values, with a predicted complex
  linked to the design and the predictor that produced it, is what would let
  an agent run a predictor and leave the structure behind rather than two
  floating numbers.
- **No raw instrument traces.** The release holds the sensorgrams; the graph
  holds the fitted values and the flags on them.
- **No stored write for `CampaignWindow`, `SelectionRule` or `AgentRole`**,
  and none for the citation edges except `GapCitedIn`. Those are the
  campaign's narrative, transcribed from the report when the seed is loaded.
  Everything else — targets, hotspots, designs, scores, thresholds,
  measurements, controls, specificity checks, tools, labs, designers — has
  one.
- **No reading per predictor.** `Score` holds one column for each of the three
  predictors this campaign ran. A bar can be registered for any `Predictor`,
  because `ThresholdByPredictor` is an edge, but a reading from a fourth
  predictor has no column to go in. Making `Score` a row per predictor, the
  way `Measurement` is a row per lab, is the change that would let a new
  predictor join the scoring step.
- **No enforced review.** The policy has no actor confined to branches, so a
  writer may write `main` and merge. Review is a practice here.
- **No connectors and no automatic sync.** A lab's run arrives as a merge
  load, or through `add_measurement` row by row.
- **No place to record that a message was sent.** An agent that notifies has
  to avoid repeats outside the record.
- **No semantic search.** No property carries `@embed` and the seed has no
  vectors. Full-text reads work on the properties declared `@index`.

## References

| What | Where |
|---|---|
| Designs, scores, assay results, controls | [Scorpion toxin binder design: data release](https://huggingface.co/datasets/Anthropic/scorpion-toxin-binder-design) — Claude Science, Nathaniel Horwitz, James van Geelen, Kat Kajderowicz and Amir Shanehsazzadeh, 20 October 2026, CC BY 4.0 |
| Campaign process, criteria, evidence gaps | [De novo design of protein binders against scorpion toxins with Claude](https://assets.claude.com/31ac578806cffd8b3d92d8affe6edc4c04d502e1.pdf) — Claude Science, Nathaniel Horwitz, James van Geelen, Kat Kajderowicz and Amir Shanehsazzadeh, 20 October 2026 |
| What the seed holds, and how it was built | [seed.md](seed.md) |
| Serving it, roles, tokens, upgrades | [local setup](../docs/local-setup.md) |
| How a cookbook is changed and checked | [`../CLAUDE.md`](../CLAUDE.md) |

Both sources are in the graph as `Source` nodes with the day they were read,
so `omnigraph query sources` answers the first two rows from the data. Every
fact transcribed from the report carries an edge to it.
