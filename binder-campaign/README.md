# Binder campaign

A de novo protein design campaign as a graph: every tested design, how it was
made, the scores that selected it, the assays that tested it, and the gaps
under every claim.

Seeded from Anthropic's scorpion-toxin binder campaign of October 2026, whose
designs, scores and assay results are public under CC BY 4.0. An agent
generated 318,484 designs against five sodium-channel neurotoxins, 211 were
tested at two contract research organisations, and 17 were reported as
binders.

## What this graph is for

A results table answers "which designs bound". It cannot answer the questions
that decide whether to believe it:

- **Tighten the definition and the count moves.** The campaign's own report
  re-counts its 17 binders under a dozen other rules; the answer ranges from
  7 to 18. Here each rule is a `Criterion` node and each claim links to the
  rules it survives, so swapping the rule is a traversal rather than a
  re-analysis.
- **Some claims rest on evidence nobody recorded.** Scored at AaH I's
  documented mature mass, four claims do not survive, because the construct
  actually used was never written down. That is an `EvidenceGap` node, linked
  to the claims it blocks and to the source that states it.
- **A design has a lineage.** It came from a backbone a tool drew, possibly
  through several rounds of redesign, possibly joined to a second domain.
  `DerivedFrom` and `HasDomain` make that a traversal.
- **A score means nothing without the bar it cleared.** Thresholds were fixed
  per toxin and predictor before any design was scored. They are nodes, so a
  claim can name the bar rather than asserting one existed.

The four layers are targets, designs, evidence and claims. The fourth is the
point: a binder claim is a node with edges to its evidence, its criterion and
its gaps, not a cell in a spreadsheet.

## The data

Everything under "Targets", "Designs" and "Evidence" comes from the
[data release](https://huggingface.co/datasets/Anthropic/scorpion-toxin-binder-design)
(CC BY 4.0). The campaign process — windows, selection rules, agent duties —
and the criteria and evidence gaps are transcribed from the
[technical report](https://assets.claude.com/31ac578806cffd8b3d92d8affe6edc4c04d502e1.pdf),
and each cites it through a `Source` node. Nothing here is invented; where
the record is silent, there is an `EvidenceGap` saying so rather than a
guess.

| Layer | What it holds |
|---|---|
| Targets | 5 toxins, 25 hotspot residues the agent chose to aim at |
| Designs | 211 tested designs, 10 design tools, 85 backbone families, their lineage |
| Evidence | 665 scores, 15 thresholds, 1,477 measurements at 2 labs, 523 specificity checks, 70 controls |
| Claims | 21 claims, 10 criteria, 7 recorded gaps |
| Process | 3 campaign windows, 3 selection rules, 4 agent roles, 2 sources |

Two counts worth knowing before reading results. 17 designs are claimed as
binders; 15 of those were measured at both labs, and the report's sensitivity
analysis varies those 15. Four further claims are recorded with
`asserted: false` — designs that only a looser rule admits.

## Local setup

See [local setup](../README.md#local-setup) in the root README for fresh
roots and the operator file. Then, from this directory:

```bash
omnigraph cluster plan --config .
omnigraph cluster apply --config . --as act-admin
omnigraph load --data seed.jsonl --mode append --target <root> --graph binders
```

`omnigraph-config.example.yaml` holds operator aliases for the reads below.
The server takes its tokens from `OMNIGRAPH_SERVER_BEARER_TOKENS_JSON`, and
the CLI picks an actor with `OMNIGRAPH_BEARER_TOKEN`; the root README owns
that setup.

## Worked reads

Start here. Every name is a stored query; `omnigraph queries list` shows them
all with their parameters.

```bash
# The 17 claims, design by design.
omnigraph query binder_claims --target <t> --graph binders

# Every rule the report counted under, and the count it gives for each.
omnigraph query criteria_all --target <t> --graph binders

# Who survives the strictest one. Four claims against AaH I do not.
omnigraph query claims_under_criterion --params '{"criterion":"crit:aahi-mature-mass"}' --target <t> --graph binders

# Which claims that rule drops.
omnigraph query claims_lost_under --params '{"criterion":"crit:aahi-mature-mass"}' --target <t> --graph binders

# Every recorded gap, what it blocks, and the source that states it.
omnigraph query evidence_gaps --target <t> --graph binders

# How one design was made, and what it came from.
omnigraph query design_provenance --params '{"slug":"design:02090d8c"}' --target <t> --graph binders
omnigraph query design_lineage    --params '{"slug":"design:02090d8c"}' --target <t> --graph binders

# The score that selected a claimed binder, with the bars it was judged against.
omnigraph query score_behind_claim --params '{"claim":"claim:cn2-b1-cn2"}' --target <t> --graph binders

# Where the two labs disagree on the same design and toxin.
omnigraph query lab_disagreements --target <t> --graph binders

# Designs that cleared every threshold and still did not bind.
omnigraph query cleared_but_did_not_bind --params '{"toxin":"toxin:ts1"}' --target <t> --graph binders
```

`cleared_but_did_not_bind` against Ts1 is the one to run first. Every
threshold cleared, nothing bound, and the report says so too: the final score
tracked success rates across design sets but did not pick out binders within
a set.

## Writing to it

The campaign's record is history and does not change. What people add is the
editorial layer: a criterion to count under, a gap someone notices, a claim
withdrawn when the evidence under it moves. Those writes are in
`queries/mutations.gq`, and they run on a branch:

```bash
omnigraph branch create review/ova-rule --from main --target <t> --graph binders
omnigraph mutate add_criterion --target <t> --graph binders --branch review/ova-rule \
  --params '{"slug":"crit:strict","name":"Strict","rule":"...","applied":false,"binders_under_rule":9,"recorded_at":"2026-11-19T00:00:00.000Z"}'
omnigraph branch merge review/ova-rule --into main --target <t> --graph binders
```

Evidence comes before the claim that rests on it: `assert_binder_claim`
records somebody's reading of the results, with their name and the day, and
`ground_claim` ties it to a measurement already in the graph. A claim is
withdrawn, not deleted — `withdraw_claim` sets `asserted` to false so a
reader can still see it was once made.

## What this graph does not hold

- No neutralisation data, in cells or in animals. Binding is shown; stopping
  the toxin is not. The campaign tested none.
- No sequences for the 318,273 designs that were generated and never tested.
  Only the 211 that reached a lab are here.
- No per-design window membership. The report states that the campaign ran in
  three windows and that selection rules changed between them, but not which
  window selected each design, so the windows are recorded as campaign-level
  facts and the designs do not link to them.
- No raw sensorgram traces. The release holds them; the graph holds the
  fitted values and the flags on them.
