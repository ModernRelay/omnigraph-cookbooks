# Binder campaign: a protein design run, and whether its results hold up

Protein design is the business of building a protein that does a chosen job:
grip a particular target, catalyse a reaction, carry something somewhere. Most
of the work now happens in software. Generative models propose structures,
structure predictors estimate how well each proposal would fold and how
tightly it would hold its target, and only a short list is ever made and
tested at a bench. A *campaign* is one pass down that funnel against one set
of targets: typically hundreds of thousands of candidates generated, a few
hundred ordered, and a handful that work.

A campaign produces far more knowledge than it produces molecules, and nearly
all of it is about how one stage led to the next — which tool drew a backbone
and from which parent, which predictors scored a design against which target
and against what bar, which designs were selected and under which rule, which
of them expressed, what each lab measured and in how many replicates. Every
stage has its own unit (a backbone, a design, a design-target pair, a well, a
replicate), its own tools and its own file: a scoring notebook, a results
sheet, a contract lab's report, an electronic lab notebook. The links between
those stages are what somebody needs six months later, and they are the part
nobody writes down.

The last link is the one that matters most and survives least. "This design
binds that target" is a judgement under a rule — how strong a signal counts,
how many replicates must agree, whether two labs must agree, what off-target
binding disqualifies. Change the rule and the list changes. Campaigns record
the list and not the rule. This graph holds one campaign end to end with that
link made explicit: a claim, the measurements beneath it, the rule it holds
under, and anything the record does not contain. Tightening the definition is
then a traversal, not a re-analysis. Graph ID `binders`.

The seed is **real**, where the other cookbooks' seeds are fictional:
Anthropic's scorpion-toxin binder campaign of October 2026. Its targets are
the neurotoxins in scorpion venom that jam sodium channels in nerve cells,
which is what makes a sting dangerous; a binder covering the face a toxin uses
to grip the channel should block it, which is roughly how an antivenom works.
The campaign generated 318,484 designs, tested 211 at two contract labs and
reported **17** binders — while its own report re-counts them under a dozen
other rules and gets anything from **7 to 18**. The designs, scores and both
labs' results are public under CC BY 4.0; the process and the criteria are
transcribed from the technical report and cited. See [seed.md](seed.md) and
[References](#references).

Sibling cookbook: [pharma-intel](../pharma-intel/) is the business around a
drug program — compounds, trials, deals, and the sponsor's own assumptions.
This one sits a rung lower, at a single experimental campaign and the evidence
beneath its claims.

## Quick start

Use the shared [local setup](../README.md#local-setup) with folder
`binder-campaign` and graph `binders`, then load `seed.jsonl`. With the server
and gateway up:

```bash
omnigraph query binder_claims --target local-reader --graph binders
omnigraph query claims_by_target --target local-reader --graph binders
omnigraph query criteria_all --target local-reader --graph binders
omnigraph query claims_lost_under --target local-reader --graph binders \
  --params '{"criterion":"crit:aahi-mature-mass"}'
omnigraph query evidence_gaps --target local-reader --graph binders
```

`binder_claims` lists the 17, and `claims_by_target` splits them: Cn2 7,
AaH II 4, AaH I 4, LqhIII 2, and none at all against Ts1. `criteria_all` is
the interesting one — ten different rules for calling a design a binder, each
with the count the report gives it, from 18 down to 11. (The report's table
reaches 7 under several rules at once, but it does not say which designs those
drop, so they are not seeded.)

`claims_lost_under` then shows what a rule costs. Scored at AaH I's documented
mature mass it drops `AaHI-B1` through `AaHI-B4`, because the construct
actually used in the assay was never written down — which is also the first
row `evidence_gaps` returns. Four of seventeen claims rest on a protein
nobody recorded.

Merge the `aliases:` of
[`omnigraph-config.example.yaml`](omnigraph-config.example.yaml) into
`$OMNIGRAPH_HOME/config.yaml` for a short name per read, such as
`omnigraph alias claims` or
`omnigraph alias lost-under --params '{"criterion":"crit:no-ovalbumin"}'`.

## Why not a notebook?

For one campaign, analysed once, by one person: use a notebook. The released
CSVs load into a dataframe in a line, and the sensitivity analysis above is a
dozen lines of filtering. A graph is overhead you do not need, and it is
better to say so than to pretend otherwise.

Four things change that answer.

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
  author on a branch, and a person merging. That is the part a dataframe has
  no answer for.

None of this argues for a graph database over any other. If that is the
question rather than whether, see
[open source graph databases compared](https://www.omnigraph.dev/guide/open-source-graph-databases)
and [graph databases and agent memory](https://www.omnigraph.dev/graph-databases).
What this cookbook leans on specifically is a typed schema checked on every
write, branches reviewed before they merge, and history that can be read back
as it stood when a claim was made.

## Does it fit another campaign?

Tested against [ProteinBase](https://huggingface.co/datasets/adaptyvbio/proteinbase)
(Adaptyv Biosystems, ODC-BY), which holds 4,280 designs against 40 targets —
these five scorpion toxins among them, and 35 that are nothing like them.

The spine takes a non-toxin slice unchanged. Nipah glycoprotein G there is
1,030 designs, 103 that bound and 928 that did not, from 206 independent
designers using 98 design methods. `Target`, `Design`, `DesignTool`,
`Measurement`, `Lab`, `BinderClaim`, `Criterion` and `EvidenceGap` all take it
as they stand.

Four fields exist here because that slice needs them, even though this seed
leaves three of them empty:

- `Designer` — 206 of them against one target there; one here, standing for
  the campaign's agents. A benchmark is many people designing against the same
  protein, and that has to be a node.
- `kon_per_ms` and `koff_per_s` — recorded there, absent here. A KD is not
  observed: it is what a model returns from the rate constants.
- `fit_model` — **populated here**, and the reason the pair above matters.
  Every value in this seed comes from a 1:1 fit.
- `binding_strength`, `replicates`, `measured_on` — an ordinal call, a count
  and a date that the release does not carry and ProteinBase does.

An empty column is not an admission; it is the shape of what a second campaign
would fill. The one that is filled, `fit_model`, is there because a value
whose model nobody wrote down cannot be reproduced —
`values_without_a_fit_model` finds those, and against this seed it returns
nothing.

## Model

[`schema.pg`](schema.pg) has 20 node types and 32 edge types in four layers,
plus the campaign's own process. The spine:

```mermaid
---
config:
  flowchart:
    wrappingWidth: 320
---
flowchart LR
  classDef L0 fill:#e8f0fe,stroke:#4a6fd1,color:#1d1d1f,stroke-width:1.5px
  Target["<b>Target</b>"]:::L0
  Hotspot["<b>Hotspot</b>"]:::L0
  classDef L1 fill:#e7f6ec,stroke:#3c9a5f,color:#1d1d1f,stroke-width:1.5px
  Design["<b>Design</b><br/><small>↻ derived from, has domain</small>"]:::L1
  DesignTool["<b>DesignTool</b>"]:::L1
  classDef L2 fill:#f3e8fd,stroke:#8a4fd1,color:#1d1d1f,stroke-width:1.5px
  Score["<b>Score</b>"]:::L2
  Threshold["<b>Threshold</b>"]:::L2
  Measurement["<b>Measurement</b>"]:::L2
  Lab["<b>Lab</b>"]:::L2
  classDef L3 fill:#fdf0e2,stroke:#d08a2b,color:#1d1d1f,stroke-width:1.5px
  BinderClaim["<b>BinderClaim</b>"]:::L3
  Criterion["<b>Criterion</b>"]:::L3
  EvidenceGap["<b>EvidenceGap</b>"]:::L3
  classDef L4 fill:#eeeeee,stroke:#888888,color:#1d1d1f,stroke-width:1.5px
  Source["<b>Source</b>"]:::L4
  Hotspot -->|"on"| Target
  Design -->|"made with"| DesignTool
  Design -->|"intended against"| Target
  Score -->|"of"| Design
  Score -->|"against"| Target
  Threshold -->|"for"| Target
  Measurement -->|"of"| Design
  Measurement -->|"at lab"| Lab
  BinderClaim -->|"about"| Design
  BinderClaim -->|"against"| Target
  BinderClaim -->|"rests on"| Measurement
  BinderClaim -->|"survives"| Criterion
  EvidenceGap -->|"affects"| BinderClaim
  EvidenceGap -->|"cited in"| Source
  Criterion -->|"cited in"| Source
```

Blue is what the campaign aimed at, green what it made, purple what it
measured, orange what anyone concluded from that, grey where a transcribed
fact came from. Each arrow is an edge type in its schema direction; a `↻` line
in a box is an edge between two nodes of that type.

| Layer | Types | Holds |
|---|---|---|
| Targets | `Target`, `Hotspot` | What the campaign designs against, and the residues on each chosen for designs to contact |
| Designs | `Design`, `Designer`, `DesignTool`, `BackboneFamily`, `SequenceMethod` | Every tested design, who made it, the tool that drew its backbone, the design it was redesigned from, the two domains a fusion joins |
| Evidence | `Score`, `Threshold`, `Predictor`, `Measurement`, `Lab`, `SpecificityCheck`, `Control` | What selected a design before any lab saw it, and what each lab then measured — rate constants, the model fitted to them, and binding to things it was never meant to bind |
| Claims | `BinderClaim`, `Criterion`, `EvidenceGap` | Somebody's verdict on the measurements, the rule it holds under, and what the record does not contain. A claim is `asserted`, `provisional` or `withdrawn` — provisional was never claimed, withdrawn was claimed and taken back |
| Process | `CampaignWindow`, `SelectionRule`, `AgentRole`, `Source` | How the run itself was organised, and where each transcribed fact comes from |

Three rules keep the claims layer honest, and the cookbook's
[`CLAUDE.md`](CLAUDE.md) spells them out for agents:

- **A claim never carries its own evidence.** Binding values live on
  `Measurement`. A value copied onto the claim would disagree with the lab the
  first time anyone refits it.
- **A criterion is a node, never a `where` clause.** Written into a query, the
  definition moves somewhere no reader can see it.
- **A gap is a fact, not an omission.** Where the record is silent there is an
  `EvidenceGap` citing the source that says so — never a plausible value.

## Reading it

61 stored queries, 43 of them reads, in six files. `omnigraph queries list`
names them all with their parameters.

| File | Answers |
|---|---|
| [`claims.gq`](queries/claims.gq) | Which designs are claimed to bind; what each claim rests on; who survives a rule; what a rule drops; where the evidence has holes |
| [`designs.gq`](queries/designs.gq) | How a design was made; what it was derived from; which domains a fusion joins; which tools produced binders |
| [`scores.gq`](queries/scores.gq) | Every bar, fixed before scoring; what one design scored; the score behind a claim; what cleared every threshold and still did not bind |
| [`assays.gq`](queries/assays.gq) | What each lab measured; where the two disagree; which values are only upper limits; off-target binding; whether the controls worked |
| [`campaign.gq`](queries/campaign.gq) | The windows the run passed through, the rules that changed between them, and the duties the agents were held to |
| [`mutations.gq`](queries/mutations.gq) | The writes below |

`cleared_but_did_not_bind` with `{"target":"target:ts1"}` is worth running on
its own. It returns **131** designs that cleared every predictor's threshold
against Ts1, not one of which bound it — the report reaches the same
conclusion, that the final score tracked success rates across design sets but
did not pick out binders within one.

## Writing to it

The campaign's record is history and does not change. What people add is the
editorial layer: a rule to count under, a gap someone notices, a claim
withdrawn when the evidence beneath it moves. Those writes run on a branch:

```bash
omnigraph branch create review/ova-rule --from main --target local-writer --graph binders
omnigraph mutate add_criterion --target local-writer --graph binders --branch review/ova-rule \
  --params '{"slug":"crit:strict","name":"Strict","rule":"No signal against any unrelated protein.","applied":false,"binders_under_rule":9,"recorded_at":"2026-11-19T00:00:00.000Z"}'
omnigraph branch merge review/ova-rule --into main --target local-writer --graph binders
```

Evidence comes before the claim that rests on it: `assert_binder_claim`
records a reading of the results with a name and a date, and `ground_claim`
ties it to a `Measurement` already in the graph. Retire a claim with
`withdraw_claim`, which sets its status to `withdrawn`, rather than deleting it — a
claim that was once made is part of the record.

## What it does not hold

- **No neutralisation data.** Binding is shown; stopping the toxin is not.
  The campaign tested none, in cells or in animals, so neither does this.
- **No untested designs.** 318,484 were generated; the 211 that reached a lab
  are here.
- **No per-design campaign window.** The report gives the three windows and
  the selection rules that changed between them, but not which window chose
  each design. The windows are campaign-level facts; no design links to one.
- **No raw instrument traces.** The release holds the sensorgrams; the graph
  holds the fitted values and the flags on them.

## Standards

**There is no community ontology or reporting standard for de novo protein
design.** Not from Rosetta Commons, the IPD, a journal or a consortium.
Treat a claim otherwise with suspicion. The nearest thing to a shared schema
is [Proteinbase](https://huggingface.co/datasets/adaptyvbio/proteinbase)
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

## References

| What | Where |
|---|---|
| Designs, scores, assay results, controls | [Scorpion toxin binder design: data release](https://huggingface.co/datasets/Anthropic/scorpion-toxin-binder-design) — Anthropic, 20 October 2026, CC BY 4.0 |
| Campaign process, criteria, evidence gaps | [De novo design of protein binders against scorpion toxins with Claude](https://assets.claude.com/31ac578806cffd8b3d92d8affe6edc4c04d502e1.pdf) — technical report, 20 October 2026 |
| What the seed holds, and how it was built | [seed.md](seed.md) |
| Domain model and the rules for adding to it | [CLAUDE.md](CLAUDE.md) |
| Setup, roles, tokens, upgrades | [root README](../README.md) |

Both sources are in the graph as `Source` nodes with the day they were read,
so `omnigraph query sources` answers this table from the data. Every fact
transcribed from the report carries an edge to it.
