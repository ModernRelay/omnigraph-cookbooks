# CLAUDE.md — agent-ops

Scoped guidance for the `agent-ops/` cookbook. Repo-wide conventions live in
`../CLAUDE.md`. For general Omnigraph operations use the **omnigraph** skill;
this file covers only what is specific to this cookbook.

## What This Is

The workflows a team's agents run, every run of them, and the revisions of
their instructions. A `Workflow` holds what a job is for; its instructions
live on a `Revision`, exactly one of which is active. A `Run` records the
revision it ran, its agent and trigger; its `Trace`s say where each agent
session is recorded; its `Output`s are what it did in other tools; and
`Evaluation`s judge it against the workflow's `Criterion`s. Whether a change of
instructions helped, what a revision costs and what is due are stored reads,
never stored fields. Schema, seed, queries and policies; no application code
and no connectors. The seed is an invented team, "Harbor Labs"; every name,
link and figure is made up.

## Key Files

- `schema.pg` — 10 node types, 18 edge types.
- `queries/dispatch.gq`, `queries/runs.gq`, `queries/improvement.gq` — 31
  stored reads.
- `queries/mutations.gq` — 22 stored writes; updates re-check the state they
  move from.
- `seed.jsonl` / `seed.md` — reference seed. Keep them in sync.
- `policies/graph.policy.yaml` — reader, writer, admin, `act-executor` and
  `act-agent` roles.

## Rules

- Graph id `agents`. Stored queries and parameters:
  `omnigraph queries list --target local --graph agents`.
- Instructions live only on revisions. Do not put a prompt on `Workflow`;
  `goal` and `output` say what the job is, and changing them makes a new
  workflow.
- One active revision per workflow. Change it only with `activate_revision`,
  which retires the one it replaces in the same write. Afterwards
  `workflows_with_several_active_revisions` and
  `workflows_without_active_revision` are both empty.
- A run reaches its workflow through its revision. Do not add a run-to-workflow
  edge: the two could then disagree.
- Records are written once. `RunUsedRevision`, `RevisionOf`, `TraceOfRun`,
  `OutputOfRun` and `EvaluationOf` are unkeyed `@card(1..1)` on purpose: a
  write on a slug that exists adds a second such edge and is refused with
  nothing changed. Do not add a `@key` to them. `Agent`, `Skill`, `Workflow`,
  `Trigger` and `Criterion` are replaced by an insert on their slug.
- Name a run `<workflow>@<occurrence>`: the due time for a schedule, the pull
  request and head commit or the issue for an event. The name is the claim, so
  a second start of the same occurrence is refused. A retry is a new slug
  linked with `mark_retry`.
- Name an evaluation `<run>/<criterion>` and a revision `<workflow>-r<number>`.
- `next_due_at` is the one stored derived value: a query cannot expand an
  RFC 5545 rule, so `start_run` stores the next occurrence the executor works
  out. A run that is refused moves nothing.
- Totals on a `Trace` are copied from the trace, never estimated. Leave out
  what the trace does not report. Spans and tool calls stay in the tracing
  tool.
- An outside action is recorded as an `Output` with its link as soon as it is
  taken. Before acting on a link, read `output_at`.
- `act-executor` writes runs, traces and outputs on `main` and nothing else.
  `act-agent` writes evaluations and proposed revisions on its own branch and
  cannot merge. Activating or rejecting a revision is a person's step. The
  shared checker asserts the agent rules; do not widen them.
- After a schema, query or seed change, re-run the reads against a fresh seed
  and update `seed.md`, then run `../scripts/check-cookbooks.py agent-ops`.

## Running it

Use the shared [local setup](../docs/local-setup.md) with folder `agent-ops`
and graph `agents`, and load `seed.jsonl`. It has a target per role: `local`
(admin), `local-writer` for the person who decides, `local-reader`,
`local-executor` for the agent that runs workflows and `local-agent` for the
agents that judge and tune.

The answers the README promises, as commands. `seed.md` lists what each
returns on the fresh seed:

```bash
omnigraph query revision_scorecard --target local-reader --graph agents --params '{"workflow":"wf-review-pr"}'
omnigraph query criterion_failures --target local-reader --graph agents
omnigraph query revision_cost --target local-reader --graph agents
omnigraph query due_workflows --target local-reader --graph agents --params '{"as_of":"2026-11-23T12:00:00Z"}'
omnigraph query runs_to_judge --target local-reader --graph agents
```

Merge the `aliases:` of [`omnigraph-config.example.yaml`](omnigraph-config.example.yaml)
into `$OMNIGRAPH_HOME/config.yaml` for a short name per read, such as
`omnigraph alias scorecard --params '{"workflow":"wf-review-pr"}'`.

## Workflows

### Dispatch due work and record the run

The executor picks what is due, loads what to run and claims the occurrence:

```bash
omnigraph query due_workflows --target local-executor --graph agents --params '{"as_of":"2026-11-23T10:00:00Z"}'
omnigraph query active_revision --target local-executor --graph agents --params '{"workflow":"wf-triage-support"}'
omnigraph query workflow_skills --target local-executor --graph agents --params '{"workflow":"wf-triage-support"}'
omnigraph query workflow_criteria --target local-executor --graph agents --params '{"workflow":"wf-triage-support"}'
omnigraph query last_covered --target local-executor --graph agents --params '{"workflow":"wf-triage-support"}'
omnigraph mutate start_run --target local-executor --graph agents --params '{
  "slug":"wf-triage-support@2026-11-23T10","revision":"wf-triage-support-r1","agent":"agent-desk",
  "trigger":"trg-support-hourly","now":"2026-11-23T10:00:00Z","next_due_at":"2026-11-23T11:00:00Z"}'
```

A refused `start_run` means another executor holds that occurrence; read the
run with `recent_runs` and move on. The workflow's criteria go into the
prompt, so the agent knows what it is judged against. A run over a stream
starts from `last_covered`.

While it works and when it ends:

```bash
omnigraph mutate record_output --target local-executor --graph agents --params '{
  "slug":"out-triage-support-2026-11-23T10-1","run":"wf-triage-support@2026-11-23T10","kind":"other",
  "title":"Routed 2 emails","url":"https://help.harbor.example/views/triage-2026-11-23T10","now":"2026-11-23T10:02:00Z"}'
omnigraph mutate attach_trace --target local-executor --graph agents --params '{
  "slug":"trace-triage-support-2026-11-23T10","run":"wf-triage-support@2026-11-23T10","source":"langsmith",
  "session_id":"ls-10f0","url":"https://smith.langchain.example/harbor/runs/ls-10f0","model":"claude-haiku-5-5",
  "input_tokens":13800,"output_tokens":800,"cost_usd":0.028,"tool_calls":4}'
omnigraph mutate record_loaded_skill --target local-executor --graph agents --params '{"run":"wf-triage-support@2026-11-23T10","skill":"skill-support-routing"}'
omnigraph mutate finish_run --target local-executor --graph agents --params '{
  "slug":"wf-triage-support@2026-11-23T10","status":"succeeded","summary":"Routed 2 emails.",
  "now":"2026-11-23T10:02:00Z","covered_from":"2026-11-23T09:00:00Z","covered_through":"2026-11-23T10:00:00Z"}'
```

An event trigger is the same with the event's occurrence in the slug and no
`next_due_at`. Before commenting on a pull request, `output_at` with its link
says whether a run already did.

### Judge runs, on a branch

```bash
omnigraph branch create judge-2026-11-23 --target local-agent --graph agents
omnigraph query runs_to_judge --target local-agent --graph agents
omnigraph query run_traces --target local-agent --graph agents --params '{"run":"wf-review-pr@pr-414"}'
omnigraph query run_outputs --target local-agent --graph agents --params '{"run":"wf-review-pr@pr-414"}'
omnigraph mutate record_evaluation --target local-agent --graph agents --branch judge-2026-11-23 --params '{
  "slug":"wf-review-pr@pr-414/crit-review-cites-lines","run":"wf-review-pr@pr-414",
  "criterion":"crit-review-cites-lines","agent":"agent-judge","verdict":"pass",
  "rationale":"All four findings are given as path:line.","method":"model","now":"2026-11-23T06:05:00Z"}'
```

The judge opens the trace at its `url` to read the session; the record holds
only where it is. A person checks a sample and merges:

```bash
omnigraph branch diff judge-2026-11-23 --target local-writer --graph agents
omnigraph branch merge judge-2026-11-23 --into main --target local-writer --graph agents
```

A person's own judgment, as from an annotation queue, goes straight to `main`:

```bash
omnigraph mutate record_human_evaluation --target local-writer --graph agents --params '{
  "slug":"wf-triage-support@2026-11-23T09/crit-triage-routes-owner","run":"wf-triage-support@2026-11-23T09",
  "criterion":"crit-triage-routes-owner","verdict":"pass","rationale":"All three went to their owners.",
  "now":"2026-11-23T11:00:00Z"}'
```

### Propose a revision, on a branch

```bash
omnigraph query criterion_failures --target local-agent --graph agents
omnigraph query failures_to_answer --target local-agent --graph agents --params '{"workflow":"wf-review-pr"}'
omnigraph query revision_history --target local-agent --graph agents --params '{"workflow":"wf-review-pr"}'
omnigraph query active_revision --target local-agent --graph agents --params '{"workflow":"wf-review-pr"}'
omnigraph branch create tune-wf-review-pr-r3 --target local-agent --graph agents
omnigraph mutate propose_revision --target local-agent --graph agents --branch tune-wf-review-pr-r3 --params '{
  "slug":"wf-review-pr-r3","workflow":"wf-review-pr","previous":"wf-review-pr-r2","agent":"agent-tuner","number":3,
  "instructions":"Review the diff for correctness and missing tests. Give every finding as path:line and the reason. Raise no point about formatting or a name the linter accepts. Summarise the findings in one comment.",
  "rationale":"Pull request 412 asked to rename a variable the linter accepts.","now":"2026-11-24T07:10:00Z"}'
omnigraph mutate cite_evaluation --target local-agent --graph agents --branch tune-wf-review-pr-r3 --params '{
  "revision":"wf-review-pr-r3","evaluation":"wf-review-pr@pr-412/crit-review-no-style-nits"}'
```

Propose only from failures that repeat, at most one revision per workflow at a
time, and never what `revision_history` shows a person rejected. A revision
that answers a failure under a retired revision answers nothing: the active
instructions already changed.

### Decide a revision

The person reads the proposal beside the instructions it replaces, and the
runs it cites:

```bash
omnigraph query proposed_revisions --target local-writer --graph agents --branch tune-wf-review-pr-r3
omnigraph query revision_instructions --target local-writer --graph agents --branch tune-wf-review-pr-r3 --params '{"revision":"wf-review-pr-r3"}'
omnigraph query revision_evidence --target local-writer --graph agents --branch tune-wf-review-pr-r3 --params '{"revision":"wf-review-pr-r3"}'
omnigraph branch diff tune-wf-review-pr-r3 --target local-writer --graph agents
```

Then activates or rejects it on the branch, and merges either way, so a
rejection and its reason stay on record:

```bash
omnigraph mutate activate_revision --target local-writer --graph agents --branch tune-wf-review-pr-r3 --params '{
  "revision":"wf-review-pr-r3","previous":"wf-review-pr-r2","note":"Agreed; the linter owns naming.","now":"2026-11-24T09:00:00Z"}'
omnigraph mutate reject_revision --target local-writer --graph agents --branch tune-wf-review-pr-r3 --params '{
  "revision":"wf-review-pr-r3","note":"Renames inside a public API are not lint.","now":"2026-11-24T09:00:00Z"}'
omnigraph branch merge tune-wf-review-pr-r3 --into main --target local-writer --graph agents
omnigraph branch delete tune-wf-review-pr-r3 --target local-writer --graph agents --yes
```

Run one of the two. The next run of the workflow uses the new active revision.

### Check a change

```bash
omnigraph query revision_scorecard --target local-reader --graph agents --params '{"workflow":"wf-review-pr"}'
omnigraph query revision_cost --target local-reader --graph agents
```

Compare a revision with the one before it on the runs each ran, not on totals
across the workflow. A few runs decide little; say how many. To go back,
propose a revision that copies the earlier instructions, so the history shows
the step back.

### Close stuck runs and check the record

```bash
omnigraph query stuck_runs --target local-executor --graph agents --params '{"before":"2026-11-23T00:00:00Z"}'
omnigraph mutate finish_run --target local-executor --graph agents --params '{
  "slug":"wf-review-pr@pr-415","status":"unknown","summary":"The session stopped without closing the run.",
  "error_type":"not-closed","now":"2026-11-23T08:00:00Z"}'
omnigraph query runs_without_trace --target local-reader --graph agents
omnigraph query workflows_without_active_revision --target local-reader --graph agents
omnigraph query workflows_with_several_active_revisions --target local-reader --graph agents
```

A run whose outcome nobody can account for is `unknown`, not `failed`. Check
the tool it acted in before running the occurrence again.

### Failure alert and weekly report

```bash
omnigraph query last_covered --target local-executor --graph agents --params '{"workflow":"wf-weekly-report"}'
omnigraph query failed_runs --target local-executor --graph agents --params '{"since":"2026-11-21T16:00:00Z"}'
omnigraph query workflow_scorecard --target local-executor --graph agents
omnigraph query proposed_revisions --target local-executor --graph agents --branch tune-wf-review-pr-r3
```

The agent posts with its own Slack tools and records the message with
`record_output`. The report's run covers the week since the last report's
`covered_through`, so a failure is reported once.

### Add a workflow

```bash
omnigraph mutate add_workflow --target local-writer --graph agents --params '{
  "slug":"wf-label-issues","name":"Label new issues","goal":"Every new issue carries an area label within a day.",
  "output":"Labels on each new issue; nothing when there are none.","revision":"wf-label-issues-r1",
  "instructions":"Read issues opened since the last run and add the area label each belongs to.","now":"2026-11-24T09:00:00Z"}'
omnigraph mutate add_trigger --target local-writer --graph agents --params '{
  "slug":"trg-label-daily","workflow":"wf-label-issues","name":"Every morning","kind":"time",
  "schedule":"FREQ=DAILY;BYHOUR=7;BYMINUTE=0","next_due_at":"2026-11-25T07:00:00Z"}'
omnigraph mutate add_criterion --target local-writer --graph agents --params '{
  "slug":"crit-label-one-area","workflow":"wf-label-issues","name":"One area","statement":"Each issue gets exactly one area label."}'
omnigraph mutate use_skill --target local-writer --graph agents --params '{"workflow":"wf-label-issues","skill":"skill-github"}'
```

`add_agent`, `add_skill`, `grant_skill`, `set_trigger_status`,
`set_workflow_status` and `set_agent_status` keep the rest of the catalogue.

### Agents over MCP

`omnigraph mcp` relays an agent host's MCP over stdio to the server through a
registered target, so the token never enters the agent's configuration:

```json
{"command": "omnigraph", "args": ["mcp", "--target", "local-executor", "--graph", "agents"],
 "env": {"OMNIGRAPH_HOME": "/Users/you/.omnigraph-cookbooks", "OG_LOCAL_EXECUTOR_TOKEN": "local-executor-token"}}
```

Give the judging and tuning agents `local-agent` instead. Add `--write` to the
bridge for the write tools; the graph policy still refuses `act-agent` on
`main`.

## Extending

- Give skills revisions the way workflows have them, when skills change often
  enough to compare.
- Add a `Dataset` of fixed inputs when the team wants offline experiments as
  well as judgments of live runs.
- Add an `Opportunity`, `Task` or other record of your own and link each
  `Output` to what it acted on.

Change the schema with `cluster plan` and `cluster apply` against the running
server, as in [live updates](../docs/local-setup.md#live-updates).

## What it does not do

- No connectors and no scheduler. An executor of your own reads
  `due_workflows` and runs the agent; the record keeps what it should run and
  what happened.
- It does not expand recurrence rules. The executor works out the next
  occurrence and passes it to `start_run`.
- It is not a tracing tool. It keeps one row per agent session with a link and
  totals; spans, tool calls and replay stay in Claude Code, LangSmith,
  Langfuse or Braintrust.
- It does not judge runs or write prompts. Agents and people do, through the
  stored writes.
- The claim on an occurrence is the refused second write on `main`, checked
  one write after another. It is not a lease: a run whose agent stopped stays
  `running` until `stuck_runs` finds it.
- The policy cannot keep `act-executor` to runs, or say which stored query
  `act-agent` runs on its branch. Every commit records its actor; the review
  before a merge is the check.
- Nothing stops an agent's outside action. Keep workflows that act outside to
  commenting and notifying, and record each action as an `Output`.
- Skills have no revisions; `content` is replaced in place.
- `activate_revision` cannot check that `previous` is the active revision. The
  two checks above find the result of a wrong one.
- Reads that take a time (`due_workflows`, `stuck_runs`, `failed_runs`) give
  different answers as time passes.
