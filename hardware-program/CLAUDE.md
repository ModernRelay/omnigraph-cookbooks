# CLAUDE.md — hardware-program

Scoped guidance for the `hardware-program/` cookbook. Repo-wide conventions
live in `../CLAUDE.md`. For general OmniGraph operations use the **omnigraph**
skill; this file covers only what is specific to this cookbook.

## What This Is

Requirements, architecture, design values, verification and program state of a
hardware program as one typed graph. Budget closure, verification status,
staleness, change impact and review readiness are derived by stored queries on
every read, never stored. Schema, seed, queries, policies and an agent skill;
no application code. The seed is a fictional smallsat program, "Petrel"; all
names and numbers are invented.

## Key Files

- `schema.pg` — 15 node types, 27 edge types.
- `queries/program.gq` — 39 stored reads.
- `queries/mutations.gq` — 21 stored writes; updates re-check their state.
- `seed.jsonl` / `seed.md` — reference seed. Keep them in sync; `seed.md`
  lists what each read must return on the fresh seed.
- `policies/graph.policy.yaml` — reader, writer, admin and `act-agent` roles.
- `skill/SKILL.md` — guidance for an agent working on a program graph.

## Rules

- Graph id `program`. Stored queries and parameters:
  `omnigraph queries list --target local --graph program`.
- Do not add stored status fields for anything a query derives: no
  "verified", "over budget", "stale" or "ready for review" flags. Extend the
  query instead.
- A budget is a requirement with `quantity`, `comparator` and `limit_value`,
  allocated to a block; `budget_rollup` sums parameters of that quantity on
  the blocks strictly beneath it. Non-additive values (frequency, temperature)
  sit on the block their requirement is allocated to, so no roll-up adds them.
- Every requirement write stamps `updated_at = now()`; `stale_verification`
  depends on it. Field edits use `expected` as a compare-and-swap.
- `record_test_run` writes the run and the test case's status in one commit.
  Keep them together.
- `act-agent` writes only on unprotected branches and cannot merge, publish or
  delete a branch. The shared checker asserts this; do not widen the agent
  rules. Writers may publish and drop unpublished commits, for the review gate
  on a merge written `as commit`.
- `budget_rollup`, `limit_check` and `limit_violations` share one comparison
  rule (`max`: value above the limit; `min`: below). Change them together.
- Keep the seed vendor-neutral and fictional. Standards are cited by public
  identifier with descriptive clause names, never invented clause numbers.
- After a schema, query or seed change, re-run the reads against a fresh seed
  and update `seed.md`, then run `../scripts/check-cookbooks.py`.

## Running it

Use the shared [local setup](../README.md#local-setup) with folder
`hardware-program` and graph `program`, and load `seed.jsonl`. Its four
targets are the roles used below: `local` (admin), `local-writer` for
engineers, `local-reader`, and `local-agent` for an AI agent.

The answers the README promises, as commands. `seed.md` lists what each
returns on the fresh seed:

```bash
omnigraph query budget_rollup --target local-reader --graph program
omnigraph query impacted_tests --target local-reader --graph program --params '{"slug":"req-lv-mass"}'
omnigraph query trace_up --target local-reader --graph program --params '{"slug":"dc-adcs-jitter"}'
omnigraph query unverified_requirements --target local-reader --graph program
omnigraph query gate_not_passing --target local-reader --graph program --params '{"milestone":"ms-cdr"}'
```

Merge the `aliases:` of [`omnigraph-config.example.yaml`](omnigraph-config.example.yaml)
into `$OMNIGRAPH_HOME/config.yaml` for a short name per read, such as
`omnigraph alias budgets` or
`omnigraph alias gate-failing --params '{"milestone":"ms-cdr"}'`.

## Derived reads

Every status is a stored read, never a stored field:

| Question | Stored query |
|---|---|
| Does each budget close? | `budget_rollup`, `budget_contributors` |
| Does each single value meet its limit? | `limit_check`, `limit_violations` |
| What is not yet verified, or failing? | `unverified_requirements`, `failing_requirements`, `test_status_summary` |
| Which passes no longer hold? | `stale_verification` |
| Is a test measuring the right thing? | `measurement_mismatch` |
| What does a change touch? | `impacted_requirements`, `impacted_tests`, `impacted_interfaces` |
| Why does this exist? | `trace_up`, `why_exists`, `unexplained_components` |
| What blocks the review? | `gate_unverified`, `gate_not_passing`, `gate_unfrozen_interfaces`, `gate_stale_verification` |
| What is fragile? | `assumptions_under_frozen_work`, `assumptions_due`, `open_risks`, `unmitigated_risks`, `untested_interfaces` |
| What needs a person? | `awaiting_review`, `open_findings`, `unowned_requirements`, `untraced_requirements` |
| Where do we stand on a standard? | `compliance_matrix` |

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

`omnigraph branch list --detailed --target local-writer --graph program` lists
every open change request with its head and when it last moved, in one read
rather than a history read per branch.

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
another write reaches `main` first; merge again then.

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

Each stored read is then a call to the `query` tool. Add `--write` to the
bridge for the write tools; there is no server flag for them, so the graph
policy is the only thing that decides what the agent may run, and it still
refuses `act-agent` on `main`. The `mutate` tool runs a stored mutation by
`name`, so an agent reaches the same reviewed write shapes as `omnigraph
mutate <stored-mutation>` without composing GQ. A ranked read's result carries
a `ranking` object, so the agent can tell an exhaustive search from one that
stopped early.

[`skill/SKILL.md`](skill/SKILL.md) is a skill for such an agent: the checks to
run, how to write a checkable requirement, and the guardrails. Before merging
an agent's branch, check its `branch diff` and its commits for decisions that
belong to engineers, such as `review_requirement` or `record_baseline`.

### Reacting to changes

The change feed reports every committed row change with its before and after
values. An agent can follow it and re-run the checks when requirements or
results move:

```bash
omnigraph changes poll --target local-agent --graph program --start after:<COMMIT_ID> \
  --type Requirement --type TestCase --json
```

Keep the returned cursor and pass it back with `--cursor` on the next poll.

## Semantic search (optional)

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

## What it does not do

- A limit is one-sided: `comparator` is `max` or `min`. A two-sided limit or a
  protocol requirement has no checkable limit and appears in no budget or
  limit check.
- `budget_rollup` and `limit_check` return `violated` when a value breaks its
  limit. How close counts as too close, say a 10% margin at preliminary
  design, is not modelled.
- A roll-up adds every block beneath the allocation, whichever variant carries
  it.
- Trace and impact reads follow at most eight levels of derivation.
- The policy cannot say which stored query an agent runs or whose unprotected
  branch it writes on. Every commit records its actor; the review before a
  merge is the check.
- Checking a merge before publishing is a habit, not an approval boundary:
  whoever may merge may also merge directly.
- `similar_requirements` returns nothing until embeddings are loaded. The seed
  carries none.
- There is no interface of its own and no connector to CAD, PLM or test tools.
