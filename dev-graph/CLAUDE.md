# CLAUDE.md — dev-graph

Scoped guidance for the `dev-graph/` cookbook. Repo-wide conventions live in
`../CLAUDE.md`. For general Omnigraph ops — schema authoring, queries, loading,
branches, cluster commands, the CLI — use the **omnigraph** skill rather than
re-deriving them here; this file covers only what's specific to dev-graph.

## What This Is

An Omnigraph schema + seed + query set modeling **software-development work** as
one typed graph — planning, code, release, operations, and a governance/substrate
layer — as a **tracker replacement** (Issue/Epic/Decision/SpecFile are native;
the VCS host stays authoritative for code via `githubRef`). Schema, seed, and
queries only — no application code.

The reference seed is a **fictional real-time-collaboration product ("Meridian")**.
All names are fabricated; the seed exists to shape the demo queries.

## Key Files

- `schema.pg` — executable schema. Source of truth. **22 node classes** (17
  pointer, 5 append-only), 92 edge types. Comments are `//`, never `#`.
- `README.md` — the landing page for the use case, in the shared template (see
  `../CLAUDE.md`); `site.json` names its use case, needs and questions.
- `seed.jsonl` / `seed.md` — reference seed (loadable / human-readable). Keep in sync.
- `queries/queries.gq` — derived reads (ready/blocked/stale, incident root-cause,
  governance), `search_*` semantic queries, and stored mutations.
- `queries/issues-dashboard.gq` — per-issue / per-epic triage reads.
- `policies/graph.policy.yaml` — admin, writer and reader roles. No agent role.
- `cluster.yaml` — deployment (graph `dev`, schema, stored queries). Filesystem-backed.
- `omnigraph-config.example.yaml` — example operator aliases; merge into
  `$OMNIGRAPH_HOME/config.yaml` (per-user, never committed).

## Setup

Use the shared [local setup](../README.md#local-setup) with cookbook
`dev-graph` and graph `dev`. It owns authentication, the bootstrap writer-lock
handoff, readiness, and served seed loading. Apply later configuration edits with
the [live update workflow](../README.md#live-updates).

Graph id `dev`. Stored queries and their parameters: `omnigraph queries list --target local --graph dev`.
Alias parameters bind by name to `$params`: `omnigraph alias issue --params '{"slug":"iss-rate-limit"}'` is `omnigraph query issue_lookup --target local-reader --graph dev --params '{"slug":"iss-rate-limit"}'`.

## Answering the README's questions

Targets come from the shared local setup: `local` (admin), `local-writer`,
`local-reader`. Run the aliases from `omnigraph-config.example.yaml`, or the
stored query directly. `seed.md` shows what the fresh seed returns.

```bash
omnigraph query ready --target local-reader --graph dev
omnigraph query blocked_on_upstream --target local-reader --graph dev
omnigraph query epic_spec --target local-reader --graph dev --params '{"epic":"epc-offline-sync"}'
omnigraph query release_prs --target local-reader --graph dev --params '{"release":"rel-v1-4-0"}'
omnigraph query incident_root_cause --target local-reader --graph dev --params '{"incident":"inc-presence-leak"}'
```

The other reads, by what they answer (alias names are in the example config):

- Blocked, one view per reason, since GQ has no `OR`: `blocked`,
  `blocked_by_parent`, `blocked_by_epic`, `blocked_by_gate`,
  `blocked_by_wait`, `blocked_on_upstream`. Every issue `ready` leaves out is in
  exactly one. `stale_candidates` lists open issues oldest-updated first; apply
  the age threshold in the caller.
- Triage per issue or epic (`issues-dashboard.gq`): `issue_detail`,
  `issue_owner`, `issue_blockers`, `issue_comments`, `epic_issue_counts`,
  `open_epics`, and the rest of that file.
- Code and release: `epic_open_issues`, `issue_implementations`,
  `prs_for_component`, `issues_for_component`.
- Incidents: `incident_components`, `learnings_for_incident`.
- Governance: `unheld_invariants`, `gaps_undermining_invariants`,
  `assumptions` (empty `guardRef` is a silent dependency),
  `decisions_for_component`, `components_without_spec`,
  `capabilities_without_component`, `capabilities_by_tier`.
- Read as of a past state: add `--snapshot <COMMIT_ID>`; on a branch, `--branch <name>`.

## Workflows

Each workflow below is one row of the README table. The agent writes with
`local-writer` on its own branch and never on `main`. No role enforces that
here (see "Roles"), so check `omnigraph branch list` before and after.

### Capture

**Pull request intake.** Starts when a pull request opens, changes state or
merges in the Git host.

```bash
omnigraph branch create intake-pr-208 --target local-writer --graph dev
omnigraph mutate create_pr --target local-writer --graph dev --branch intake-pr-208 --params '{"slug":"pr-flaky-fix","title":"Stabilise convergence test","status":"open","githubRef":"meridian#208","actor":"agent:orion","at":"2026-09-20"}'
omnigraph mutate link_pr_closes_issue --target local-writer --graph dev --branch intake-pr-208 --params '{"pr":"pr-flaky-fix","issue":"iss-flaky-sync-test"}'
omnigraph mutate update_pr_status --target local-writer --graph dev --branch intake-pr-208 --params '{"slug":"pr-flaky-fix","status":"merged","actor":"agent:orion","at":"2026-09-21"}'
```

Components a pull request touches have no stored mutation; add one before
automating that. Then diff and preview: `omnigraph branch diff intake-pr-208
--target local-writer --graph dev`, then `omnigraph branch merge intake-pr-208
--into main --dry-run --target local-writer --graph dev`. A person merges.

**Issue intake.** Starts when a tracker creates an issue. `create_issue`, then
`add_issue_to_epic`, `link_issue_targets_component`, `assign_issue_owner`, on a
branch. First run `issue_lookup` for the slug: a repeat would collide.

**Deploy and incident log.** Starts when CI finishes a deploy or an incident
closes: `record_deployment`; `resolve_incident`, `add_learning`,
`record_decision` (append-only; correct with `supersede_decision`).
Incidents and their causing-PR links have no stored create; load them with a
reviewed `load --mode merge` on a branch.

**Upstream release.** Starts when a library release ships a fix:
`mark_blocker_shipped` with `status` and `shippedInVersion`. Then run the
unblock notice.

### Maintain

Each starts on a schedule or after a merge, and reads, concludes, then proposes
on a branch.

- **Backlog triage.** Read `ready`, the `blocked_*` views and
  `stale_candidates`. Propose `update_issue_status` (a stale issue that is done)
  or `link_issue_blocks_issue` (a missing dependency). Never set a state a query
  derives.
- **Governance audit.** Read `unheld_invariants`, `gaps_undermining_invariants`,
  `assumptions`. Propose `set_invariant_status` or `update_gap_state` with the
  evidence in the pull request or comment. An unguarded assumption is reported
  to a person; the agent does not invent a `guardRef`.
- **Coverage audit.** Read `components_without_spec` and
  `capabilities_without_component`. These are reports; the fix is a spec or a
  link a person decides.
- **Decision upkeep.** Read `decisions_for_component`. When a new decision
  replaces an old one, `record_decision` then `supersede_decision` (new, old).

### Act

These act outside the record. The policy cannot stop a message, so the agent
drafts or notifies only, with its own tools; the cookbook has no integrations.
Get a person's approval before any message that is not a draft.

- **Review brief.** Starts when a pull request needs review. Read the
  `components` it touches, then `decisions_for_component`,
  `prs_for_component`, `issues_for_component`, and `epic_spec` for its epic.
  Output is a brief for the reviewer or a coding agent; nothing is written.
- **Release notes.** Starts when a release is cut. `release_prs`, then
  `epic_open_issues` for each epic that targets it (no stored read lists
  them; use an ad-hoc `-e` query over `epicTargetsRelease`);
  `issue_implementations` for the issues. Output is a draft.
  The record has nowhere to say the notes were published.
- **Unblock notice.** Starts after `mark_blocker_shipped`. Read
  `blocked_on_upstream`, then `issue_owner` per issue. Check `issue_comments`
  for an earlier notice; if none, send it and `add_comment_on_issue` saying so.
- **Stale nudge.** Starts on a schedule. Read `stale_candidates`, drop issues
  updated inside the threshold, `issue_owner`, check `issue_comments` for a
  nudge in the window, send, record it with `add_comment_on_issue`.
- **Incident summary.** Starts when an incident opens or closes.
  `incident_root_cause`, `incident_components`, `learnings_for_incident`.
  Output is a report; the record does not note it was sent.

### Roles

`policies/graph.policy.yaml` defines `act-admin`, `act-writer` and
`act-reader`. A writer may create and merge branches, so an agent given the
writer token can merge. Do not widen roles or add `act-agent` without task
authorization; if one is added, follow hardware-program's rules for it and have
the checker assert them.

## Writing

Aliases are read-only; mutations run as `omnigraph mutate <name> --target local-writer --graph dev --params '<json>'` with every
non-optional property supplied. Signatures live at the bottom of `queries/queries.gq`. Working example:

```bash
omnigraph mutate create_issue --target local-writer --graph dev --params '{"slug":"iss-flaky-presence-test","title":"Presence integration test is flaky","status":"todo","issueType":"bug","actor":"act-admin","at":"2026-09-14"}'
omnigraph mutate add_issue_to_epic --target local-writer --graph dev --params '{"issue":"iss-flaky-presence-test","epic":"epc-observability"}'
```

The shared operator config sets no `default_graph`, so every command passes `--graph dev`.

## The mutability model (do not bend it)

The single most load-bearing rule. Enforced by node class:

- **Pointer nodes** (Epic, SpecFile, Component, Repo, PR, Release, Incident,
  Issue, Actor, Gate, Label, Invariant, Principle, Gap, ExternalBlocker,
  Assumption, Capability) **update in place** — `update … where slug`. They carry
  `createdAt`/`createdBy` **and** `updatedAt`/`updatedBy`; stamp `updatedAt`/
  `updatedBy` on every write.
- **Append-only nodes** (Decision, Commit, Deployment, Learning, Comment) are
  **never overwritten** — insert only. They carry `createdAt`/`createdBy` **and
  have no `updatedAt`/`updatedBy` columns** (do not emit those). Corrections are a
  *new* node linked by a `Supersedes` edge (`DecisionSupersedes`, `SpecSupersedes`,
  `ReleaseSupersedes`).
- There are intentionally **no `delete` mutations**: removal is a status
  transition (`canceled`/`abandoned`/`superseded`/`retired`).
- **State is derived, not stored.** Never add a `ready`/`blocked`/`stale` property
  — those are queries over the edges. Ownership/authorship/targets are **edges**,
  not fields.

## Loading

- **Load the reference seed only into a fresh demo graph.** Use served `load`
  after the shared setup. For ongoing work, the stored mutations preserve the
  pointer/append-only conventions; bulk loads should be reviewed on a branch.
- **Dates are `Date` (day-granularity), passed as ISO strings** (`"2026-07-09"`).
  `load` accepts ISO for `Date` columns. There is **no `DateTime`** in this
  schema, so mutations take `$at: Date` — `now()` (a DateTime) can't be assigned;
  the caller supplies the date.
- **Every non-nullable property must be supplied** on insert or lint/load fails
  (e.g. `PR.githubRef`, `Release.versionTag`, `Incident.startedAt`,
  `Commit.sha`/`authoredAt`, `Deployment.env`/`outcome`/`startedAt`).
- `@unique` columns to keep distinct across a load batch: `Component.name`,
  `Repo.name`, `Actor.name`, `Label.name`, `Capability.name`, `Release.versionTag`,
  `Commit.sha`.

## Query authoring notes

- **Bind nodes explicitly** when introducing a traversal (`$i: Issue`,
  `$b: Issue`, then `$b issueBlocksIssue $i`), as the shipped queries do.
- **Edge verb = the schema edge name, first letter lowercased**
  (`EpicContainsIssue` → `epicContainsIssue`).
- **`nearest()`/`bm25()`/`rrf()` need a trailing `limit N`.** The `search_*`
  queries have it; keep it on any new ranked query.
- **Lint after every edit:** `omnigraph lint --schema schema.pg --query
  queries/<file>.gq` (no server needed). Warnings like "X exists in schema but no
  update query sets it" are informational.

## Modelling rules

- **Layer boundaries are named edges** (`SpecSpecifies`, `PrTouchesComponent`),
  never title or path matching.
- **Identity is a stable slug** that survives rename and retype. Prefixes (hash
  suffix of 4-6 characters): `iss-` Issue, `epc-` Epic, `spc-` SpecFile, `dec-`
  Decision, `cmp-` Component, `repo-` Repo, `pr-` PR, `commit-` Commit (or the
  SHA), `rel-` Release, `dep-` Deployment, `inc-` Incident, `lrn-` Learning,
  `act-` Actor (`agent:<name>` for agents), `gate-` Gate, `lbl-` Label, `inv-`
  Invariant, `prn-` Principle, `gap-` Gap, `blk-` ExternalBlocker, `asm-`
  Assumption, `cap-` Capability.
- **Polymorphic edges are split per target** (`CommentOnIssue`, `CommentOnPr`).
  Repetition in the schema is cheap; blurred queries are not.
- **Blocking is a distinct edge type** (`IssueBlocksIssue`, `*ParentChild*`,
  `IssueConditionalBlocksIssue`, `*WaitsFor*`); `IssueRelated` and
  `IssueDiscoveredFrom` annotate only. Each blocking dimension has its own
  `blocked_*` read.
- **Epic and SpecFile are not Issue subtypes**: own lifecycles and edges. There
  is one `Issue` class; `issueType` is a triage label.
- **Invariant vs Principle.** An `Invariant` is checkable (`holds | violated`,
  optional `guardRef`); violation is a bug. A `Principle` is prescriptive
  (`prescribes | forbids`); violation is a rejected PR, relaxed only by a
  `Decision`, with per-PR exceptions as `PrExceptionToPrinciple` records. A
  `Gap` is an Invariant not yet held; a PR can widen or narrow it.
- **Capability is a product axis**, mapped many-to-many to `Component` by
  `CapabilityImplementedBy`; it is not structure.

## Semantic search (optional)

The prose-bearing types (`Issue`, `Epic`, `SpecFile`, `Decision`, `Learning`,
`Invariant`, `Principle`, `Gap`, `Capability`, `Incident`, `PR`, `Assumption`,
`Comment`) declare `embedding: Vector(3072)? @embed(...) @index`. It stays null
until vectors are in the input data, so the seed loads without a provider.

1. Put `GEMINI_API_KEY` in the server environment before it starts. Uncomment
   `providers:` and `graphs.dev.embedding_provider` in `cluster.yaml`, then
   [plan and apply live](../README.md#live-updates). A secret exported in a
   client shell does not reach a running server.
2. Prepare JSONL of the node rows and an embedding spec, using the same
   provider and model as the server:

   ```bash
   export OMNIGRAPH_EMBED_PROVIDER=gemini
   export OMNIGRAPH_EMBED_MODEL=gemini-embedding-2
   omnigraph embed --input rows.jsonl --output rows.embedded.jsonl \
     --spec /path/to/embeddings.json --reembed-all
   omnigraph load --target local --graph dev --data rows.embedded.jsonl --mode merge
   ```

   `GEMINI_API_KEY` is needed for this command too. Load never generates
   vectors. See the
   [embedding guide](https://github.com/ModernRelay/omnigraph/blob/v0.15.0/docs/user/search/embeddings.md#offline-file-pipeline).
3. `omnigraph query search_issues --target local-reader --graph dev --params '{"q":"tenant isolation"}'`
   (also `search_epics`, `_specs`, `_decisions`, `_learnings`, `_invariants`,
   `_principles`, `_gaps`, `_capabilities`, `_prs`, `_incidents`).

An empty semantic result does not prove nothing matches: check the `ranking`
object's `exhaustive` flag and vector coverage. Structural reads need no
embeddings.

## What it does not do

No code index: the Git host holds code, `PR`/`Commit`/`Release` carry its
reference. Linked, not mirrored: customer and CRM data, strategy and OKRs,
test results and coverage (query CI), security findings and CVEs (only
`Incident` lives here), alerts (aggregate to `Incident`), doc-site content
(`SpecFile.url`), Slack and email threads (a URL on a `Comment`). `Branch` and
`Env` are not nodes: they fold into PR string fields and `Deployment.env`.
There are no connectors, no webhooks, no automatic sync, no agent role and no
enforced review of an agent's branch.

## Schema notes / known drift

- **A `Learning`'s author is its `createdBy` column** — there is **no
  `LearningAuthoredBy` edge** in `schema.pg`. (The upstream ontology prose lists
  one; the schema omits it.) Don't emit that edge; it will dangle.
- `Component` has **no `repo` field** — repo membership is the `RepoHasComponent`
  edge. `Release.artifactsChecklist` is a **JSON string**, not a native list.

## Editing the seed

Keep `seed.jsonl` and its human-readable inventory in `seed.md` aligned. Keys
must be unique, edge endpoints must refer to existing nodes, and append-only
records must omit `updatedAt`/`updatedBy`. Validate changes by loading a fresh
demo cluster and running the corresponding stored queries.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).
