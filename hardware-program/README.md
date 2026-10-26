# Hardware program: requirements to verification

One typed graph for a hardware program: requirements and how they flow down,
the architecture blocks and interfaces they constrain, the design values that
feed budgets, the tests that verify them, and the iterations, reviews, risks,
decisions and standards around them. Graph ID `program`.

Requirement tools, spreadsheets, CAD and test reports each hold one slice of a
program, so the questions engineers actually ask are joins nobody maintains:
*does the mass budget still close, what does this requirement change touch,
which passing tests no longer prove anything, what blocks the next design
review?* Here each is a stored query, derived from the current graph on every
read. Nothing stores a "verified" or "over budget" flag that can drift from the
evidence.

The seed is **Petrel**, a fictional 150 kg Earth-observation smallsat midway
through its engineering-model iteration; see [seed.md](seed.md). Every name and
number in it is invented.

## Quick start

Use the shared [local setup](../README.md#local-setup) with folder
`hardware-program` and graph `program`, and load `seed.jsonl`. Its four
targets are the roles used below: `local` (admin), `local-writer` for
engineers, `local-reader`, and `local-agent` for an AI agent. With the server
and gateway up:

```bash
omnigraph query budget_rollup --target local-reader --graph program
omnigraph query gate_not_passing --target local-reader --graph program \
  --params '{"milestone":"ms-cdr"}'
```

`budget_rollup` shows the launch mass closing at 142.6 kg of 150, while the
payload, at 30.8 kg, is over its 28 kg allocation: its row says
`violated: true`. `gate_not_passing` lists the failed thermal vacuum test and
the two tests not yet run that stand between the program and its critical
design review.

Merge the `aliases:` of [`omnigraph-config.example.yaml`](omnigraph-config.example.yaml)
into `$OMNIGRAPH_HOME/config.yaml` for a short name per read, such as
`omnigraph alias budgets` or
`omnigraph alias gate-failing --params '{"milestone":"ms-cdr"}'`.

## Model

[`schema.pg`](schema.pg) has 15 node types and 27 edge types.

| Area | Types | Holds |
|---|---|---|
| Requirements | `Requirement`, `Assumption`, `Standard` | Mission goals, system requirements and design criteria; the assumptions they rest on; external standards |
| Architecture | `Block`, `Interface`, `Parameter`, `Variant` | The system/subsystem/component tree, contracts between blocks, design values such as mass and power, product configurations |
| Verification | `TestCase`, `TestRun`, `Iteration`, `Milestone` | Verification activities and each run's evidence, design-build-test loops, reviews and the commit each one baselined |
| Program | `Risk`, `Decision`, `Finding`, `Engineer` | Failure modes, trade decisions, check results, and the people and agents who own work |

The links carry the engineering:

- `DerivesFrom` makes requirements a web, not a tree: a design criterion can
  serve several parents, and impact analysis follows every path.
- `AllocatedTo` puts a requirement on a block. A requirement with a
  `quantity`, `comparator` and `limit_value` is a budget: `budget_rollup` adds
  every `Parameter` of that quantity on the blocks beneath it.
- `Verifies` links a test case to requirements; `Measures` names the design
  value it actually measures, and `Bounds` the value a requirement limits.
- `InScope` puts requirements in an iteration; the `Milestone` that `Closes`
  the iteration checks them.
- `CompliesWith` records a stance (`comply`, `deviate`, `not_applicable`) and
  justification per clause of a standard.
- `AppliesTo` scopes a requirement to a variant. No link means every variant,
  so variants are data, not copies of the requirement set.

### Derived, not stored

| Question | Stored query |
|---|---|
| Does each budget close? | `budget_rollup`, `budget_contributors` |
| Does each single value meet its limit? | `limit_check`, `limit_violations` |
| What is not yet verified, or failing? | `unverified_requirements`, `failing_requirements`, `test_status_summary` |
| Which passes no longer hold? | `stale_verification`: a passing test that ran before its requirement last changed |
| Is a test measuring the right thing? | `measurement_mismatch` |
| What does a change touch? | `impacted_requirements`, `impacted_tests`, `impacted_interfaces` |
| Why does this exist? | `trace_up`, `why_exists`, `unexplained_components` |
| What blocks the review? | `gate_unverified`, `gate_not_passing`, `gate_unfrozen_interfaces`, `gate_stale_verification` |
| What is fragile? | `assumptions_under_frozen_work`, `assumptions_due`, `open_risks`, `unmitigated_risks`, `untested_interfaces` |
| What needs a person? | `awaiting_review`, `open_findings`, `unowned_requirements`, `untraced_requirements` |
| Where do we stand on a standard? | `compliance_matrix` |

`omnigraph queries list --target local --graph program` prints all 39 reads
and 21 mutations with their parameters. `budget_rollup` and `limit_check`
compare each value with its limit by the requirement's comparator and return
`violated`; how close counts as too close (say, a 10% margin at preliminary
design) stays your policy.

A budget adds up values on the blocks *beneath* its allocation. Attach a
non-additive value, such as a first natural frequency or a temperature, to the
block its requirement is allocated to; it then appears in `limit_check`, not in
a roll-up.

## Workflows

Engineers run these as `local-writer`; every read also works as `local-reader`.

### A requirement change on a branch

The launch provider cuts the mass allowance. Before touching anything, see
what the change reaches:

```bash
omnigraph query impacted_requirements --target local-writer --graph program --params '{"slug":"req-lv-mass"}'
omnigraph query impacted_tests --target local-writer --graph program --params '{"slug":"req-lv-mass"}'
omnigraph query requirement_tests --target local-writer --graph program --params '{"slug":"req-lv-mass"}'
```

Make the change on a branch, so the review sees it whole:

```bash
omnigraph branch create cr-lv-mass --target local-writer --graph program
omnigraph query requirement --target local-writer --graph program --branch cr-lv-mass \
  --params '{"slug":"req-lv-mass"}' --json        # note updated_at
omnigraph mutate revise_requirement --target local-writer --graph program --branch cr-lv-mass --params '{
  "slug":"req-lv-mass","expected":"2026-09-29T10:00:00.000Z",
  "title":"Launch mass at most 145 kg",
  "statement":"The spacecraft shall have a launch mass of 145 kg or less, including propellant.",
  "rationale":"Second slot change.","quantity":"mass","comparator":"max",
  "limit_value":145.0,"unit":"kg","review_status":"human_reviewed"}'
omnigraph query budget_rollup --target local-writer --graph program --branch cr-lv-mass
omnigraph query stale_verification --target local-writer --graph program --branch cr-lv-mass
```

Review exactly what the branch changed, field by field, and preview the merge
without writing it:

```bash
omnigraph branch diff cr-lv-mass --target local-writer --graph program
omnigraph branch merge cr-lv-mass --into main --dry-run --target local-writer --graph program
omnigraph branch merge cr-lv-mass --into main --target local-writer --graph program
```

`revise_requirement` is a compare-and-swap on `updated_at`: if someone changed
the requirement since you read it, it matches nothing and you re-read. The
revision stamps a new `updated_at`, so every test that passed against the old
wording shows up in `stale_verification` until it is re-run.

### A trade study

Run each option on its own branch and compare the derived results:

```bash
omnigraph branch create trade-optics-light --target local-writer --graph program
omnigraph mutate set_parameter --target local-writer --graph program --branch trade-optics-light \
  --params '{"slug":"p-mass-optics","value":21.4,"basis":"estimated"}'
omnigraph query budget_rollup --target local-writer --graph program --branch trade-optics-light   # dc-pl-mass: 27.7 kg, closes
omnigraph query budget_rollup --target local-writer --graph program                               # main: 30.8 kg, violated
omnigraph branch diff trade-optics-light --target local-writer --graph program
```

A branch is cheap and holds the whole option: parameters, revised
requirements and new test cases together. Two options that change the same
value cannot both merge: once one has, `branch merge --dry-run` on the other
reports a `divergent_update` conflict on that value and writes nothing. Merge
the winner, delete the others, and record why with `record_decision`.

### Test results

```bash
omnigraph mutate record_test_run --target local-writer --graph program --params '{
  "run":"run-tvac-v1b","test":"tc-tvac","iteration":"it-v1","outcome":"pass",
  "measured_value":66.2,"unit":"degC","notes":"With the copper heat spreader.",
  "run_at":"2026-10-08T15:00:00.000Z"}'
omnigraph blob put node TestRun run-tvac-v1b report --file tvac-run-2.pdf --target local-writer --graph program
omnigraph blob get node TestRun run-tvac-v1b report --out tvac-run-2.pdf --target local-reader --graph program
```

The run and the test case's latest status land in one commit, so a reader
never sees one without the other. The report is stored in the graph as a Blob
of up to 32 MiB; `blob put` adds it in a second commit, or pass it in the same
commit as `record_test_run`'s `report` parameter (`"base64:<bytes>"`). An
aborted run goes through `record_aborted_run`, which leaves the status alone.

### Check the merged result before publishing

A merge can wait unpublished, so the review gate runs against exactly what
`main` would become:

```bash
omnigraph branch merge cr-obc-heatsink --into main --as-commit --target local-writer --graph program --json
# "commit": {"graph_commit_id": "<COMMIT_ID>", "published": false, ...}
omnigraph query gate_not_passing --target local-reader --graph program \
  --params '{"milestone":"ms-cdr"}' --snapshot <COMMIT_ID>
omnigraph query limit_violations --target local-reader --graph program --snapshot <COMMIT_ID>
omnigraph commit publish <COMMIT_ID> --target local-writer --graph program   # or: commit drop <COMMIT_ID>
```

`main` does not move until `commit publish`. An unpublished commit expires if
another write reaches `main` first; merge again then. This is a review habit,
not an approval boundary: whoever may merge may also merge directly.

### Review baselines

A review is a snapshot. When the critical design review passes, record the
commit it reviewed:

```bash
omnigraph commit list --target local-writer --graph program --json        # the newest commit is first
omnigraph mutate record_baseline --target local-writer --graph program --params \
  '{"milestone":"ms-cdr","status":"passed_with_actions","commit":"<COMMIT_ID>"}'
```

Any read can then run against the program exactly as the review saw it, for
example `omnigraph query budget_rollup --target local-reader --graph program
--snapshot <COMMIT_ID>`. To work from that state, start a branch there:
`omnigraph branch create cdr-actions --from-commit <COMMIT_ID> --target
local-writer --graph program`. The history is the graph's commit log; no
export or document copy is needed.

### Agents

The graph policy gives an AI agent its own actor, `act-agent`. It reads
everything and invokes stored queries, but it can only write on unprotected
branches and cannot merge, publish or delete a branch, so every agent change
reaches `main` through an engineer's merge. `omnigraph access` shows it:

```bash
omnigraph access --target local-agent --graph program --branch main
omnigraph branch create agent-review-jitter --target local-agent --graph program
omnigraph mutate raise_finding --target local-agent --graph program --branch agent-review-jitter --params '{
  "slug":"fnd-jitter-units","check":"requirement_quality","severity":"warning",
  "message":"No quantity or limit.","requirement":"dc-adcs-jitter","raised_by":"agent-checker"}'
omnigraph mutate raise_finding --target local-agent --graph program --params '{...}'   # on main: forbidden, effects none
```

An agent host such as Claude Code or Codex can reach the same reads over MCP.
`omnigraph mcp` relays the agent's MCP over stdio to the server through a
registered target, so the token never enters the agent's configuration:

```json
{"command": "omnigraph", "args": ["mcp", "--target", "local-agent", "--graph", "program"],
 "env": {"OMNIGRAPH_HOME": "/Users/you/.omnigraph-cookbooks", "OG_LOCAL_AGENT_TOKEN": "local-agent-token"}}
```

Each stored read is then a call to the `query` tool. Write tools appear only
when the server runs with `--mcp-allow-writes` and the bridge with `--write`,
and the policy still refuses the agent on `main`. The MCP `mutate` tool takes
GQ text rather than a stored mutation's name, so have the agent write through
`omnigraph mutate <stored-mutation> --target local-agent`, which keeps it on
the reviewed write shapes.

[`skill/SKILL.md`](skill/SKILL.md) is a skill for such an agent: the checks to
run, how to write a checkable requirement, and the guardrails. Agents mark what
they draft `review_status: ai_generated`; `awaiting_review` lists it until a
person reviews it. The policy cannot limit which stored queries an agent runs,
so before merging an agent's branch, check its `branch diff` and its commits for
decisions that belong to engineers, such as `review_requirement` or
`record_baseline`.

### Reacting to changes

The change feed reports every committed row change with its before and after
values. An agent can follow it and re-run the checks when requirements or
results move:

```bash
omnigraph changes poll --target local-agent --graph program --start after:<COMMIT_ID> \
  --type Requirement --type TestCase --json
```

Keep the returned cursor and pass it back with `--cursor` on the next poll.

## Similar requirements (optional)

`Requirement.embedding` holds a 3072-dimension vector of the statement for
`similar_requirements`, which finds near-duplicate or conflicting requirements
by meaning. The seed has no vectors. Generate them with the offline
`omnigraph embed` pipeline, which embeds the statement text exactly as a
`nearest` query embeds its text, load the result, then enable the provider in
[`cluster.yaml`](cluster.yaml) and apply it through the running server. See
[live updates](../README.md#live-updates). `search_requirements` needs none of
this; it ranks the indexed titles and statements by text.

## Extending

- Add a `Supplier` node and a `SuppliedBy` edge to tie parts to vendors and
  lead times.
- Link blocks to CAD, PLM or simulation artifacts by an external ID property,
  keeping those tools authoritative for geometry and models.
- Make budgets variant-aware: link blocks to the variants that carry them and
  filter `budget_rollup` on that link.

Change the schema with `cluster plan` and `cluster apply` against the running
server, as in [live updates](../README.md#live-updates).
