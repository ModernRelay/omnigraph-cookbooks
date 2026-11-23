# Binder campaign: designs, evidence, and the claims they carry

Build a living record of a protein binder campaign, and the agent workflows
around it. It keeps the targets, every design and how it was made, the scores
that selected it, what each lab measured, and the claim that a design binds a
target — with the rule that claim holds under and the evidence it rests on.
Whether a design counts as a binder is worked out from the measurements under
the rule you name, so tightening the definition re-reads the record instead of
re-analysing it. Agents propose every change on a branch a scientist reviews.

A campaign leaves its designs in one tool, its scores in a notebook, its
assay results in a contract lab's spreadsheet and its verdict in a slide, and
the rule behind that verdict in nobody's hands at all. Six months later the
rule has been forgotten, so the list of binders cannot be re-derived or
argued with. This cookbook sets OmniGraph up as the one place the designs,
the evidence and the claims are held together.

- **A claim names its rule.** "This design binds this target" is recorded
  with the criterion it holds under and the measurements beneath it.
- **Re-counting is a read.** Add a rule and ask who survives it; the old
  answer is still there, because nothing was overwritten.
- **A gap is a fact.** What the record does not hold is written down and
  linked to the claims nobody can check because of it.

> If you are an agent: the commands, roles and workflows are in
> [AGENTS.md](AGENTS.md). Read that file before running anything.

## The data model

```mermaid
graph LR
  Hotspot -- sits on --> Target
  Design -- made with --> DesignTool
  Design -- on backbone --> BackboneFamily
  Design -- sequenced with --> SequenceMethod
  Design -- designed by --> Designer
  Design -- derived from --> Design
  Design -- has domain --> Design
  Design -- intended against --> Target
  Score -- of --> Design
  Score -- against --> Target
  Threshold -- for --> Target
  Threshold -- by predictor --> Predictor
  Measurement -- of --> Design
  Measurement -- at lab --> Lab
  SpecificityCheck -- of --> Design
  Control -- against --> Target
  BinderClaim -- about --> Design
  BinderClaim -- against --> Target
  BinderClaim -- rests on --> Measurement
  BinderClaim -- survives --> Criterion
  EvidenceGap -- affects --> BinderClaim
  EvidenceGap -- cited in --> Source
  SelectionRule -- applied in --> CampaignWindow
```

| Area | Types | Holds |
|---|---|---|
| Targets | `Target`, `Hotspot` | What the campaign designs against, and the residues on each that designs were aimed at contacting |
| Designs | `Design`, `Designer`, `DesignTool`, `BackboneFamily`, `SequenceMethod` | Every design that reached a lab, who made it, the model that drew its backbone, the method that chose its sequence, the design it was redesigned from and the domains a fusion joins |
| Evidence | `Score`, `Threshold`, `Predictor`, `Measurement`, `Lab`, `SpecificityCheck`, `Control` | What selected a design before any lab saw it, and what each lab then measured: kinetic constants, the model fitted to them, binding to proteins it was never meant to bind, and whether the run's controls worked |
| Claims | `BinderClaim`, `Criterion`, `EvidenceGap` | Somebody's verdict on the measurements, every rule it holds under, and what the record does not contain |
| Process | `CampaignWindow`, `SelectionRule`, `AgentRole`, `Source` | How the run was organised, which rules selected designs in which stretch of it, which duties were kept apart, and where each transcribed fact came from |

- **A claim is a node, not a column.** In a results sheet "is a binder" is a
  column somebody computed, and changing the rule overwrites it. Here the
  verdict, the rule and the evidence are three things, so a new rule adds
  rows and the old answer survives.
- **A criterion is a node, never a filter in a query.** Written into a query,
  the definition of a binder moves somewhere no reader can see it. Each rule
  is recorded in words precise enough to apply by hand, with the count its
  source reports, so the graph's own count can be compared with it.
- **A threshold is recorded as set before scoring.** The bar each predictor
  had to clear was fixed from decoys and negative controls first, which is
  why a claim can name the bar it cleared rather than assert one existed. A
  bar set afterwards is recorded as such, because that is a finding.
- **A gap is a fact, not an omission.** Where the record is silent there is
  an `EvidenceGap` citing the source that says so, linked to the claims,
  designs and targets it reaches. Never a plausible value in place of one.
- **An absent result is not a negative result.** A design nobody measured
  against a target has no row; a design measured and found not to bind has
  one. Collapsing the two would turn a missing experiment into evidence.
- **Yours to change.** The model is one file, [`schema.pg`](schema.pg), with
  21 node types and 33 edge types.

## Branching and merging

A change is made on a branch, which is a version of the whole record, and the
baseline moves only when someone merges it.

- **A re-count under a new rule.** Add a criterion on a branch, record which
  claims survive it, and read the counts as they would be before anyone else
  sees them.
- **A lab's results.** Load a run's measurements on a branch, read them
  against the claims they touch, and merge once a scientist has checked them
  against the lab's own report.
- **Two reviewers at once.** Each works on their own branch against the same
  base, and both merge, because adding a rule and recording a gap do not
  collide. Two branches that change the same row do, and the second merge
  reports it instead of silently winning.
- **A write-up's evidence, as it stood.** Every commit is readable, so the
  claims and gaps behind a paper can be read back as they were on the day it
  was submitted.

Review here is a practice, not a rule the graph enforces.
[`policies/graph.policy.yaml`](policies/graph.policy.yaml) gives readers,
writers and admins: a writer may write `main` and merge into it, and only an
admin may change the schema. There is no actor confined to branches, so an
agent given a writer's token can reach `main` — give agents their own actor
and keep them to branches if you need that enforced.

## Agents and workflows

Agents bring results in, keep the claims honest against the evidence, and
tell people what needs a scientist. The verdicts stay with people.

| Kind | Workflow | What it does | Stored queries |
|---|---|---|---|
| Capture | Assay result intake | Records each measurement a contract lab returned, with its design, its target and the lab, in one write | `add_measurement`, `measurements_for_design` |
| Capture | Source refresh | Re-reads a report or data release, moves the day it was last read, and records a source nobody had cited | `add_source`, `mark_source_fetched`, `sources`, `uncited_gaps` |
| Maintain | Verdict from the evidence | Reads the measurements for a design and target, records the claim, and ties it to the rows it rests on | `assert_binder_claim`, `ground_claim`, `claim_evidence` |
| Maintain | Re-count under a rule | Adds a rule for calling a design a binder and records which claims survive it, then compares the graph's count with the count its source reports | `add_criterion`, `claim_survives_criterion`, `criterion_survivor_counts`, `claims_lost_under` |
| Maintain | Unevidenced claim sweep | Finds claims resting on nothing recorded and either grounds them or withdraws them | `claims_with_gaps`, `claims_fully_evidenced`, `ground_claim`, `withdraw_claim` |
| Maintain | Gap register | Writes down what the record does not hold, cites the source that states the absence, and links it to the claims and targets it reaches | `record_gap`, `cite_gap`, `gap_affects_claim`, `gap_affects_target` |
| Maintain | Value quality review | Finds designs the two labs call differently, values that are only an upper limit, and values recorded without the kinetic model fitted to produce them, and records what each costs | `lab_disagreements`, `upper_limit_only`, `values_without_a_fit_model`, `record_gap` |
| Maintain | Assay validity review | Finds runs whose control did not work, and designs that bound a protein they were never aimed at, and records which claims each undermines | `failed_controls`, `off_target_hits`, `specificity_for_design`, `gap_affects_claim` |
| Act | Claim-change notice | When a rule is added or a claim is withdrawn, tells whoever relied on it which claims moved and why | `claims_lost_under`, `withdrawn_claims` |
| Act | Evidence request | For each claim resting on one lab or on an upper limit, asks the lab for the run that would settle it | `claims_with_gaps`, `upper_limit_only` |
| Act | Pre-publication gap report | Before a write-up goes out, sends the authors every gap that blocks a check, the claims it reaches, and the claims that rest on nothing | `evidence_gaps`, `gap_reach`, `claims_fully_evidenced` |
| Act | Round scorecard | Reports which design tools produced claimed binders, and which cleared every bar and bound nothing, for the next round | `tools_behind_binders`, `cleared_but_did_not_bind`, `scores_from_rerun` |

Every workflow has the same four parts:

1. Something starts it: a lab returns a run, a claim or rule changes in the
   record, or a write-up is due.
2. The agent reads the state it needs through stored queries.
3. It acts. It writes to the record on its own branch, or it tells someone
   outside the record.
4. A scientist decides. They review the branch and merge it, or act on what
   they were told.

- **An agent does not reach a verdict alone.** Asserting that a design binds
  a target, and withdrawing that assertion, are recorded with a name and a
  day, and they belong to a person. An agent proposes them on a branch.
- **The campaign's own record is history.** Designs, scores, specificity
  checks, controls, windows, rules and roles have no stored write: they
  arrive once, by a bulk load, and nothing edits them afterwards. What agents
  add is the editorial layer above them.
- **Outside actions are not held back by the record.** A message or a request
  to a lab goes out through the agent's own tools, and nothing here reviews it
  first. Keep those workflows to telling and drafting unless a scientist
  approves the action, and give the agent only the outside access it needs.
- **A repeat is not prevented.** The schema has nowhere to note that a message
  was sent or a lab was asked, so an agent that notifies has to keep that
  outside the record, or the same request goes twice. A gap or a criterion is
  different: writing one under a slug that exists is refused, so recording
  the same finding twice changes nothing.
- **Bring your own agent.** It connects through OmniGraph's MCP server from
  Claude Code, Codex, Cursor or another MCP client, and each stored read is a
  tool call. The cookbook ships no skill of its own;
  [AGENTS.md](AGENTS.md) is what an agent reads first.

## Data sources

The record holds the designs, the evidence and the claims that connect your
tools. Each tool stays the authority for its own data.

| Source | Examples | Feeds |
|---|---|---|
| Design models | RFdiffusion, BindCraft, Genie, Chai Discovery, Boltz, AlphaFold | `DesignTool`, `BackboneFamily`, `SequenceMethod`, `Design` |
| Structure predictors and scoring | ESMFold, Protenix, Boltz, in-house scoring pipelines | `Predictor`, `Threshold`, `Score` |
| Contract and in-house labs | Adaptyv Bio, Twist Bioscience, Charles River | `Lab`, `Measurement`, `Control` |
| Binding instruments | Carterra for SPR, Gator Bio for BLI, Biacore, Octet | `Measurement`, `SpecificityCheck` |
| Electronic lab notebooks and LIMS | Benchling, Dotmatics, PipeBio | `Design`, `Measurement` |
| Public design releases and benchmarks | ProteinBase, Hugging Face datasets, PDB, UniProt | `Design`, `Measurement`, `Target`, `Source` |
| Reports, preprints and papers | a campaign's own technical report, bioRxiv | `Source`, `Criterion`, `EvidenceGap`, `AgentRole` |

The cookbook includes no connectors. A sync is a script, or an agent, that
reads from the tool and writes through the stored mutations; a lab's whole run
goes in as a merge load. A design that arrives with its tool, backbone and
parent keeps that lineage, because provenance is edges rather than a column of
notes.

## Questions you can ask

Nobody keeps a binder list, a sensitivity table or a caveats section up to
date for these.

| Question | Stored query |
|---|---|
| Which binder claims survive a stricter rule? | `claims_under_criterion` |
| Which claims rest on evidence nobody can check? | `claims_with_gaps` |
| How was a design made, and what did it come from? | `design_provenance` |
| Which score selected a design, and against which bar? | `score_behind_claim` |

The cookbook has 49 stored reads and 13 stored writes.
[AGENTS.md](AGENTS.md) lists them.

## Sample data

The seed is a real campaign, not an invented one: Anthropic's scorpion-toxin
binder design of October 2026, from its public data release under CC BY 4.0,
with the process and the criteria transcribed from its technical report and
cited. It holds 5 targets, 211 designs that reached a lab, 665 scores, 1,477
measurements at 2 labs, 523 specificity checks, 70 controls, 21 claims, 10
rules for calling a design a binder, and 8 recorded gaps. On a fresh load, the
questions above return:

- Under the rule that both labs resolve a value and agree within a factor of
  ten, 11 of the 17 asserted claims survive; the rule the campaign applied
  admits 15.
- 7 claims carry a recorded gap. Four against AaH I rest on a construct
  nobody documented, two against LqhIII were assessed at one lab only, and
  Cn2-B1's value is an upper limit at both labs.
- Cn2-B1 came off an RFdiffusion3 backbone in family F02, sequenced with
  SolubleMPNN, after six rounds of redesign.
- The score behind the claim on Cn2-B1 is 0.9222, and it cleared all three
  predictors: ESMFold2 and ESMFold2-Fast at an ipSAE bar of 0.15, Protenix v2
  at 0.54, each with a scDockQ bar of 0.23.

[seed.md](seed.md) describes the release, row type by row type, says which
two facts came from the report rather than the data, and names the counts that
surprise people.

## Run it

Paste this prompt into a coding agent such as Claude Code or Codex:

```text
Read https://www.omnigraph.dev/onboarding.md and set up Omnigraph for me with the binder campaign cookbook: https://github.com/ModernRelay/omnigraph-cookbooks/tree/main/binder-campaign
```

The agent installs OmniGraph if needed, creates the graph, loads the campaign
and runs the questions above.

To do it by hand, follow the shared [local setup](../docs/local-setup.md)
using folder `binder-campaign` and Graph ID `binders`.
[AGENTS.md](AGENTS.md) has the exact command for each question and workflow on
this page.
