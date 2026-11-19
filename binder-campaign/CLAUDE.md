# Binder campaign agent guide

Read the [root guide](../CLAUDE.md) first; it owns setup, validation and
deployment. This file owns the domain model.

Graph ID is `binders`, not the folder name.

## What the graph is

One AI-run de novo protein design campaign, end to end, in four layers:

| Layer | Types |
|---|---|
| Targets | `Target`, `Hotspot` |
| Designs | `Design`, `DesignTool`, `BackboneFamily`, `SequenceMethod` |
| Evidence | `Score`, `Threshold`, `Predictor`, `Measurement`, `Lab`, `SpecificityCheck`, `Control` |
| Claims | `BinderClaim`, `Criterion`, `EvidenceGap` |
| Process | `CampaignWindow`, `SelectionRule`, `AgentRole`, `Source` |

The claims layer carries the weight. A `BinderClaim` is somebody's reading of
the measurements, not the measurements: it links to the `Measurement` rows it
rests on (`ClaimRestsOn`), to every `Criterion` it survives (`ClaimSurvives`),
and to any `EvidenceGap` recorded against it. Three rules follow.

**A claim never carries its own evidence.** Properties on `BinderClaim` say
who recorded it and when; the binding values live on `Measurement`. Adding a
value to a claim would make the two disagree the first time a lab refits.

**A criterion is a node, never a filter in a query.** The report re-counts its
binders under a dozen rules and gets anything from 7 to 18. Each rule is a
`Criterion` with the count the report gives it, and `ClaimSurvives` edges say
who lives under it. Writing one of those rules as a `where` clause moves the
definition into the query, where no reader can see it.

**A gap is a fact, not an omission.** Where the record is silent, there is an
`EvidenceGap` saying so, citing the source that states it. Never fill a gap
with a plausible value; add a gap instead.

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

## Enum values use underscores

`no_hit`, `single_domain`, `alpha_like`, `blocks_check`. The query language
cannot filter an enum whose value carries a hyphen, and an enum cannot be
matched as a literal in a binding block at all — compare it in a filter line:

```gq
$m: Measurement
$m.result = "hit"
```

## Seed data and its limits

`seed.jsonl` is built from the public
[data release](https://huggingface.co/datasets/Anthropic/scorpion-toxin-binder-design)
(CC BY 4.0) plus facts transcribed from the
[technical report](https://assets.claude.com/31ac578806cffd8b3d92d8affe6edc4c04d502e1.pdf).
Everything transcribed cites a `Source`.

Counts that trip people up:

- **17 asserted claims, 21 claims in all.** Four are recorded with
  `asserted: false`: designs only a looser rule admits.
- **15, not 17, in the sensitivity analysis.** Two LqhIII claims were
  assessed at one lab only, so the report's table varies the other 15. The
  `ClaimSurvives` edges follow the report and cover those 15.
- **1,477 measurements, 665 scores.** Scores exist only for the toxins a
  design was intended against; the labs measured beyond intent, which is what
  makes "no hit against a toxin it was not made against" a usable criterion.
- **No per-design window.** The report gives the three windows and the rules
  that changed between them, but not which window selected each design.
  `CampaignWindow` and `SelectionRule` are campaign-level; do not invent edges
  from designs to them.

When the seed changes, keep `seed.md` and `seed.jsonl` consistent, and re-run
`python3 scripts/check-cookbooks.py binder-campaign` from the repo root.

## Adding to it

Writes go through `queries/mutations.gq` on a branch, merged after review.
Evidence first: `ground_claim` refuses to be useful if the measurement is not
already there. Retire a claim with `withdraw_claim` rather than deleting it,
so the record still shows it was made.
