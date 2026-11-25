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
- `README.md` — the landing page, on the shared template (see the root guide);
  everything operational lives here.
- `seed.jsonl` / `seed.md` — reference seed (loadable / human-readable). Keep in sync.
- `queries/queries.gq` — derived reads (ready/blocked/stale, incident root-cause,
  governance), `search_*` semantic queries, and stored mutations.
- `queries/issues-dashboard.gq` — per-issue / per-epic triage reads.
- `cluster.yaml` — deployment (graph `dev`, schema, stored queries). Filesystem-backed.
- `omnigraph-config.example.yaml` — example operator aliases; merge into
  `$OMNIGRAPH_HOME/config.yaml` (per-user, never committed).

## Setup

Use the shared [local setup](../docs/local-setup.md) with cookbook
`dev-graph` and graph `dev`. It owns authentication, the bootstrap apply and
writer lock, readiness, and served seed loading. Apply later configuration edits with
the [live update workflow](../docs/local-setup.md#live-updates).

Graph id `dev`. Stored queries and their parameters: `omnigraph queries list --target local --graph dev`.
Alias parameters bind by name to `$params`: `omnigraph alias issue --params '{"slug":"iss-rate-limit"}'` is `omnigraph query issue_lookup --target local-reader --graph dev --params '{"slug":"iss-rate-limit"}'`.

## Questions and their commands

Each question on the README, with the command that answers it (after merging
`omnigraph-config.example.yaml`, which defines the aliases):

```bash
omnigraph alias ready
omnigraph alias blocked-upstream
omnigraph alias release-prs --params '{"release":"rel-v1-4-0"}'
omnigraph query epic_spec --target local-reader --graph dev --params '{"epic":"epc-offline-sync"}'
```

`epic_spec` has no alias in `omnigraph-config.example.yaml`, so it runs as a
query.

Other derived reads (alias → stored query): `blocked`, `blocked-parent`
(`blocked_by_parent`), `blocked-epic`, `blocked-gate`, `blocked-wait`
(one view per blocking dimension, because GQ has no `OR`), `stale`
(`stale_candidates`; threshold the date client-side), `epic-open`,
`incident-cause` (`incident_root_cause`), `incident-blast`
(`incident_components`), `unheld-invariants`, `gaps`
(`gaps_undermining_invariants`), `assumptions`, `no-spec`
(`components_without_spec`), `no-cap-impl`, `decisions-comp`. The per-issue
triage set is in `queries/issues-dashboard.gq` (`issue_detail`,
`issue_owner`, `issue_blockers`, `open_epics`, …).

## Workflows, step by step

Every workflow: trigger → read through stored queries → act → a person decides.
Agent writes go on a branch (`omnigraph branch create`, write with
`--branch`, then `branch diff` and `branch merge --dry-run` before a person
merges). **Nothing in this cookbook enforces that**: its policy has only
`act-admin`, `act-writer` and `act-reader`, and `act-writer` may change and
merge `main`. There is no agent role. Do not add one without task authorization.

| Workflow | Steps |
|---|---|
| Pull request sync | On a PR event, `create_pr` (needs `githubRef`) or `update_pr_status`; then `link_pr_closes_issue` and `link_issue_implemented_by_pr` for each issue it names |
| Issue intake | `create_issue`, `add_issue_to_epic`, `link_issue_targets_component`, `assign_issue_owner` |
| Deployment log | `record_deployment` for an existing release (no stored write creates a release) |
| Incident close-out | `resolve_incident`, then `record_decision` and `add_learning`; read `incident_root_cause` first |
| Backlog triage | Read `stale_candidates`, filter by date, then `update_issue_status` or `set_issue_priority` |
| Upstream watch | Read `blocked_on_upstream` and `assumptions_for_blocker`; when upstream ships, `mark_blocker_shipped` |
| Invariant check | Read `unheld_invariants` and `gaps_undermining_invariants`; `set_invariant_status`, `update_gap_state` |
| Decision upkeep | `record_decision` the new one, then `supersede_decision` (new, old). That only links the two: no stored write changes the old decision's status or ties the new one to a component, so `decisions_for_component` still returns the old one. Say so in the report |
| Coverage audit | Read `components_without_spec`, `capabilities_without_component`, `assumptions`; no stored write fixes these |
| Review context | Read `decisions_for_component`, `issues_for_component`, `prs_for_component` for the touched component |
| Unblock notice | Read `blocked_on_upstream` and `issue_owner`; draft the message, a person sends it |
| Release and incident brief | `release_prs`, `incident_root_cause`, `incident_components`, `learnings_for_incident` |

Acting workflows send messages and tickets with the agent's own tools; the
record cannot hold that back. To avoid repeats, note the action with
`add_comment_on_issue` (the only record of an outside action; there is none on
PRs, incidents or epics through a stored write) and read `issue_comments`
before acting again.

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

## Schema notes / known drift

- **A `Learning`'s author is its `createdBy` column** — there is **no
  `LearningAuthoredBy` edge** in `schema.pg`. (The upstream ontology prose lists
  one; the schema omits it.) Don't emit that edge; it will dangle.
- `Component` has **no `repo` field** — repo membership is the `RepoHasComponent`
  edge. `Release.artifactsChecklist` is a **JSON string**, not a native list.

## Model reference

- **Layers.** Planning (`Epic`, `SpecFile`, `Decision`), Work (`Issue`,
  `Comment`), Code (`Repo`, `Component`, `PR`, `Commit`), Release (`Release`,
  `Deployment`), Operations (`Incident`, `Learning`), People (`Actor`),
  Governance and substrate (`Invariant`, `Principle`, `Gap`, `ExternalBlocker`,
  `Assumption`, `Capability`), Cross-cutting (`Label`, `Gate`).
- **One `Issue` class.** bug/feature/task/chore/question/risk share fields, so
  `issueType` is a triage label. `Epic` and `SpecFile` are not `Issue` subtypes:
  they have their own lifecycles, owners and edges.
- **Dependencies are typed edges.** Blocking: `IssueBlocksIssue`,
  `EpicBlocksEpic`, `PrBlocksPr`, `*ParentChild*`, `IssueConditionalBlocksIssue`,
  `*WaitsFor{Issue,Gate,Blocker}`. Non-blocking: `IssueRelated`,
  `IssueDiscoveredFrom`.
- **Polymorphic edges are split per target** (`CommentOnIssue`, `CommentOnPr`, …):
  repetition in the schema is cheap, blurred queries are not.
- **Governance.** `Invariant` is checkable (violation is a bug, optional
  `guardRef`). `Principle` is prescriptive (`prescribes`/`forbids`, with a
  `correctAlternative`); a per-PR exception is a record
  (`PrExceptionToPrinciple`), not a status change. `Gap` is debt against an
  Invariant and can be widened by a PR (`PrWidensGap`). `ExternalBlocker` is an
  upstream fix that gates work. `Assumption` is a belief about an outside
  system; one with no `guardRef` is a silent dependency. `Capability` is a
  product capability (`owned`/`inherited`), a different axis from `Component`.
- **Edge groups** (92 in `schema.pg`): containment, specification and decisions,
  work targeting, release/deploy, incident and learning, dependencies,
  ownership/authorship (`*OwnedBy`, `*AuthoredBy`, `PrReviewedBy`),
  discussion and tagging, governance.
- **Identifier scheme.** Slug prefixes: `iss-` Issue, `epc-` Epic, `spc-`
  SpecFile, `dec-` Decision, `cmp-` Component, `repo-` Repo, `pr-` PR,
  `commit-` Commit, `rel-` Release, `dep-` Deployment, `inc-` Incident, `lrn-`
  Learning, `act-` Actor (`agent:<name>` for agents), `gate-` Gate, `lbl-`
  Label, `inv-` Invariant, `prn-` Principle, `gap-` Gap, `blk-`
  ExternalBlocker, `asm-` Assumption, `cap-` Capability.

## Semantic search (optional)

The prose-bearing nodes (`Issue`, `Epic`, `SpecFile`, `Decision`, `Learning`,
`Invariant`, `Principle`, `Gap`, `Capability`, `Incident`, `PR`, `Assumption`,
`Comment`) declare `embedding: Vector(3072)? @embed(...) @index`. The column
stays null until vectors are supplied in input data, so the seed loads without
a provider and the `search_*` queries (alias `sem-issue`, …) return nothing
useful until it is populated. Never read an empty semantic result as "no
matching facts" without checking vector coverage.

1. Provide `GEMINI_API_KEY` in the server environment before starting it.
   Uncomment `providers:` and `graphs.dev.embedding_provider` in
   `cluster.yaml`, then [plan and apply live](../docs/local-setup.md#live-updates).
2. Prepare JSONL with the current node rows and an embedding spec, with the
   same provider and model as the query-time provider:

   ```bash
   export OMNIGRAPH_EMBED_PROVIDER=gemini
   export OMNIGRAPH_EMBED_MODEL=gemini-embedding-2
   omnigraph embed --input rows.jsonl --output rows.embedded.jsonl \
     --spec /path/to/embeddings.json --reembed-all
   omnigraph load --target local --graph dev --data rows.embedded.jsonl --mode merge
   ```

   `omnigraph embed` transforms files; load preserves supplied vectors and does
   not generate them. See the
   [embedding guide](https://github.com/ModernRelay/omnigraph/blob/v0.16.0/docs/user/search/embeddings.md#offline-file-pipeline).
3. `omnigraph alias sem-issue --params '{"q":"tenant isolation"}'`.

## What this does not do

No application code, connectors or sync. It links to, and does not mirror:
customer/CRM data, strategy/OKRs, test results and coverage (query CI),
security findings and CVEs (only `Incident` lives here), alerts and monitoring
(aggregate to `Incident`), doc-site content (link via `SpecFile.url`),
Slack/email threads (link by URL on a `Comment`). `Branch` is not a node (PR
string fields) and `Env` is not a node (`Deployment.env`; the current release
per environment is derived from deployment history). No stored write creates
an incident, release, commit, invariant, gap or assumption.

## Editing the seed

Keep `seed.jsonl` and its human-readable inventory in `seed.md` aligned. Keys
must be unique, edge endpoints must refer to existing nodes, and append-only
records must omit `updatedAt`/`updatedBy`. Validate changes by loading a fresh
demo cluster and running the corresponding stored queries.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).
