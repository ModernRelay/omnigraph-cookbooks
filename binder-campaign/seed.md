# Seed data

`seed.jsonl` holds 11,395 rows describing one de novo protein design
campaign: Anthropic's scorpion-toxin binder campaign of October 2026.

## Where it comes from

| Part | Source |
|---|---|
| Targets, designs, scores, measurements, specificity checks, controls | the [data release](https://huggingface.co/datasets/Anthropic/scorpion-toxin-binder-design), CC BY 4.0 |
| Hotspot residues, criteria, evidence gaps, windows, selection rules, agent roles | the [technical report](https://assets.claude.com/31ac578806cffd8b3d92d8affe6edc4c04d502e1.pdf), transcribed |

Everything transcribed from the report carries a `Source` edge to it. The
data release files are read as tables; nothing in the graph is inferred from
them beyond the threshold comparison described below.

## What is in it

| Type | Rows | Notes |
|---|---|---|
| `Target` | 5 | Cn2, Ts1, AaH II, AaH I, LqhIII |
| `Hotspot` | 25 | five per target, with how many released design models reach each |
| `Design` | 211 | the designs that reached a lab |
| `DesignTool` | 10 | the tools that drew backbones |
| `BackboneFamily` | 85 | |
| `SequenceMethod` | 6 | |
| `Predictor` | 3 | ESMFold2, ESMFold2-Fast, Protenix v2 |
| `Threshold` | 15 | one per target and predictor, fixed before scoring |
| `Score` | 665 | one per design and intended target |
| `Lab` | 2 | Adaptyv Bio (cell-free), Twist Bioscience (HEK, Fc fusion) |
| `Measurement` | 1,477 | every non-empty result cell, at either lab |
| `SpecificityCheck` | 523 | CLEC12A (two runs), ovalbumin, baculovirus particles |
| `Control` | 70 | published binders run alongside, per target, lab and replicate |
| `BinderClaim` | 21 | 17 asserted, 4 admitted only by a looser rule |
| `Criterion` | 10 | the applied rule and nine others the report counts under |
| `EvidenceGap` | 7 | what the record does not hold |
| `CampaignWindow` | 3 | |
| `SelectionRule` | 3 | including the one that replaced the diversity caps |
| `AgentRole` | 4 | generate, score, select, orchestrate |
| `Source` | 2 | the report and the data release |

Edges follow the same counts: 665 `IntendedAgainst`, 1,477 each of
`MeasurementOf`, `MeasurementAgainst` and `MeasurementAtLab`, 140
`ClaimSurvives`, 36 `DerivedFrom`, 33 `HasDomain`.

## The one derived field

`Score.cleared_thresholds` is computed, not copied. A design cleared a target
when all three predictors reported an ipSAE at or above that target's
threshold for that predictor, and a scDockQ of at least 0.23. The thresholds
come from `supporting_tables/ipSAE_thresholds.csv`; the scores from
`in_silico_scores.csv`. Both are in the graph, so the derivation can be
checked rather than trusted.

Everything else is carried across as written.

## Counts that surprise people

**17 binders, 21 claims.** Four claims carry `asserted: false`: designs that
only a looser rule admits, recorded so that "no limit on the binding value"
has something to point at.

**15 claims in the sensitivity analysis, not 17.** Two LqhIII claims were
assessed at one lab only, so the report's table varies the other 15. The
`ClaimSurvives` edges cover those 15 and follow the report's own rows.

**More measurements than designs times targets intended.** The labs measured
beyond intent — Twist tested 133 to 140 designs against each target. That is
what makes "no hit against a target it was not made against" a rule anyone can
check here.

**Blank is not zero.** A result cell that is empty produces no `Measurement`
row at all, rather than a row saying "no hit". An absent measurement and a
negative measurement are different facts, and `claims_with_gaps` depends on
the difference.

## Rebuilding it

The seed was generated from the released CSVs by a one-off script. To rebuild
it, download the dataset's `design.csv`, `in_silico_scores.csv`,
`targets.csv`, `controls.csv`, `BVP_ELISA.csv` and the `supporting_tables/`
files `origin.csv`, `ipSAE_thresholds.csv` and `OVA.csv`, and re-run that
script. Facts transcribed from the report are literals inside it, each beside
the table it came from.
