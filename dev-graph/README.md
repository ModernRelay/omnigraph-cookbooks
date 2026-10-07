# dev-graph — a software-development knowledge graph

Opinionated Omnigraph cookbook that models **software-development work** as one
typed graph: planning, code, release, operations, and the governance/substrate
rules that constrain them. Built on [Omnigraph](https://github.com/ModernRelay/omnigraph).
It is a **tracker replacement** — Issue, Epic, Decision, SpecFile, and a whole
governance layer are native here — while your VCS host stays authoritative for
code (`PR`/`Commit`/`Release` carry a `githubRef`).

> For operating Omnigraph — schema authoring, queries, loading, branches, cluster
> ops, the CLI — use the **omnigraph** skill. This README covers only what's
> specific to dev-graph. No object store needed — this is a filesystem-backed cluster.

The reference seed is a **fictional real-time-collaboration product, "Meridian"**
(a self-hostable collaborative document platform). Every name is fabricated; the
seed exists to make the queries land, not to model a real team.

## Why a graph, not another tracker

A stock issue tracker (Linear/Jira) answers "what's assigned to me" well and
everything cross-cutting badly. The questions that actually govern an engineering
org cut *across* stages, and a tracker has no model for them:

- *What's ready to work on, and what's blocking everything else?*
- *Which spec describes this epic? Which components does this PR touch?*
- *Which PRs landed in v1.4.0, and what incident did that release cause?*
- *Which open architectural gaps undermine an invariant we claim holds?*
- *Which issues are stuck on an upstream library fix — and which version ships it?*
- *Semantic:* *"find the work about tenant isolation"* / *"the presence-leak postmortem."*

Every one of these is a 1–3 hop graph traversal here. Dependencies are **typed
edges**, not a flag; work state (**ready / blocked / stale / critical-path**) is
**derived by query**, not stored; and provenance (`createdBy`/`updatedBy`) is
**structural**, on every node. Influences: [beads](https://github.com/gastownhall/beads)
(typed work dependencies), ADR practice (immutable decisions), and SRE
incident-review culture.

## The ontology at a glance — 22 node classes across 8 layers

| Layer | Node classes | Purpose |
|---|---|---|
| **Planning** | `Epic`, `SpecFile`, `Decision` | Why we're building it |
| **Work** | `Issue`, `Comment` | What we're doing day-to-day |
| **Code** | `Repo`, `Component`, `PR`, `Commit` | Where the work lands |
| **Release** | `Release`, `Deployment` | What shipped, where |
| **Operations** | `Incident`, `Learning` | What broke and why |
| **People** | `Actor` | Who did / owns it |
| **Governance & substrate** | `Invariant`, `Principle`, `Gap`, `ExternalBlocker`, `Assumption`, `Capability` | The rules and external dependencies that constrain the work |
| **Cross-cutting** | `Label`, `Gate` | Tagging, gating |

## Design principles (the load-bearing decisions)

1. **Mutability is enforced by node class.** 17 **pointer** nodes update in place;
   5 **append-only** nodes (`Decision`, `Commit`, `Deployment`, `Learning`,
   `Comment`) are never overwritten — corrections create a *new* node linked by a
   `Supersedes` edge. Provenance lives in columns (`createdAt`/`createdBy`, plus
   `updatedAt`/`updatedBy` on pointer nodes), not a separate audit node.
2. **State is queryable, not stored.** "Ready", "blocked", "stale", "critical
   path", "what's in the next release" are **none** of them properties — all are
   derived in `queries/queries.gq`.
3. **Dependencies are typed edges, not generic links.** Whether a relationship
   blocks work (`Blocks`, `ParentChild`, `WaitsFor`, `ConditionalBlocks`), traces
   lineage, or just annotates (`Related`, `DiscoveredFrom`) is the *edge type*.
4. **Identity is stable.** Slugged ids (`iss-a1b2`, `epc-…`, `pr-…`) survive
   rename, retype, rescope. Edges and events follow identity, not labels.
5. **Layer boundaries are explicit.** Planning artifacts connect to code
   artifacts through named edges (`SpecSpecifies`, `PrTouchesComponent`), never by
   string-matching titles or paths.
6. **Polymorphic edges are split per target.** PGSchema penalizes polymorphism, so
   `CommentOnIssue`/`CommentOnPr`/… are separate edges. Repetition in the schema
   is cheap; blurred queries are not.

## The governance & substrate layer (what makes this more than a tracker)

The distinctive part of the model. The split that matters is **checkable
properties** (violation = a bug) vs. **prescriptive rules** (violation = a
rejected PR):

- **`Invariant`** — a checkable property the system maintains ("concurrent edits
  converge", "no document data crosses a tenant boundary"). `status: holds |
  violated`, an optional `guardRef` (the test that enforces it). Violation is a
  *bug*.
- **`Principle`** — a prescriptive design rule reviewed against on every PR;
  violation = rejected PR. Carries a `polarity`: `prescribes` (a must-do) or
  `forbids` (a rejected design, with a `correctAlternative`). Relaxed only via a
  `Decision`; per-PR exceptions are records (`PrExceptionToPrinciple`), not a
  status change.
- **`Gap`** — tracked architectural debt: a desired `Invariant` not yet held. A
  `Gap` can be **widened by a PR** (`PrWidensGap`) — a relationship a generic
  tracker can't express.
- **`ExternalBlocker`** — an upstream issue/PR/release that gates internal work
  (an upstream library fix shipping in a specific version). The durable cousin of
  a `Gate`.
- **`Assumption`** — a checkable belief about an *external* system's behavior,
  optionally guard-backed. The external twin of `Invariant`; an **unguarded**
  Assumption (no `guardRef`) is a silent dependency worth surfacing.
- **`Capability`** — a functional capability of the product, tagged by provenance
  (`owned` vs `inherited`). A *different axis* from `Component` (structural),
  mapped M:N via `CapabilityImplementedBy`.

A `Decision` **establishes** or **relaxes** Invariants and Principles; a `Gap`
**undermines** an Invariant; an `Issue`/`PR` **narrows** (or **widens**) a Gap.
That web is what lets you ask *"which open gaps undermine an invariant we claim
holds, and what PR made one worse?"*

## Node classes

**Pointer (mutable, updated in place):** `Epic` · `SpecFile` · `Component` ·
`Repo` · `PR` · `Release` · `Incident` · `Issue` · `Actor` · `Gate` · `Label` ·
`Invariant` · `Principle` · `Gap` · `ExternalBlocker` · `Assumption` · `Capability`

**Append-only (never overwritten; corrections via `Supersedes`):** `Decision` ·
`Commit` · `Deployment` · `Learning` · `Comment`

`Epic` and `SpecFile` are **not** `Issue` subtypes — they have their own
lifecycles, owners, and edges (Epics target Releases and aggregate Issues;
SpecFiles have a review/approval flow and `Supersedes` chains). Conversely there
is **one** `Issue` class, not per-type subclasses: bug/feature/task/chore/
question/risk share fields and lifecycle, so `issueType` is a triage label, not a
different schema.

## Edge classes

92 edge types, grouped by intent (full list in `schema.pg`):

- **Containment** — `RepoHasComponent`, `ComponentHasSubcomponent`,
  `EpicContainsIssue`, `ReleaseIncludesPr` (single-direction/canonical; traverse
  backward for the inverse).
- **Specification & decisions** — `SpecSpecifies`, `SpecDescribes`,
  `Spec/DecisionSupersedes`, `DecisionAppliesTo{Component,Spec}`,
  `DecisionEmergedFrom{Issue,Incident}`.
- **Work targeting & implementation** — `IssueTargetsComponent`,
  `EpicTargetsRelease`, `IssueImplementedBy`, `PrClosesIssue`,
  `PrTouchesComponent`, `PrIncludesCommit`.
- **Release / deploy** — `ReleaseInRepo`, `ReleaseSupersedes`, `DeploymentOfRelease`.
- **Incident & learning** — `IncidentAffectsComponent`,
  `IncidentCausedBy{Pr,Deployment,Commit}`, `LearningAnalyzesIncident`,
  `LearningAbout{Component,Blocker,Assumption,Gap}`.
- **Dependencies** — blocking: `IssueBlocksIssue`, `EpicBlocksEpic`, `PrBlocksPr`,
  `*ParentChild*`, `IssueConditionalBlocksIssue`, `*WaitsFor{Issue,Gate,Blocker}`;
  non-blocking: `IssueRelated`, `IssueDiscoveredFrom`.
- **Ownership / authorship** — `*OwnedBy`, `*AuthoredBy`, `PrReviewedBy`,
  `IncidentCommandedBy`, `DeploymentTriggeredBy`.
- **Discussion & tagging** — `CommentOn*` + `CommentPostedBy`; `*Tagged → Label`.
- **Governance** — `DecisionEstablishes/Relaxes{Invariant,Principle}`,
  `GapUnderminesInvariant`, `Issue/PrNarrowsGap`, `PrWidensGap`,
  `AssumptionCoversBlocker`, `CapabilityImplementedBy/TrackedBy`, `*DescribedIn → SpecFile`.

## Killer queries (derived — computed, not stored)

Shipped as stored queries in `queries/` and exposed as operator aliases in
`omnigraph-config.example.yaml`. Run with `omnigraph alias <name> [args]`.

| Concept | Alias | What it answers |
|---|---|---|
| **Ready** | `ready` | Backlog/todo issues with no incoming block and no outgoing wait |
| **Blocked** | `blocked` · `blocked-parent` · `blocked-epic` · `blocked-gate` · `blocked-wait` · `blocked-upstream` | One view per blocking dimension (`IssueBlocksIssue` / parent issue / parent epic / `Gate` / `WaitsForIssue` / `ExternalBlocker`), so every issue `ready` excludes shows up in exactly one — GQ has no `OR`, so the dimensions are separate queries |
| **Stale** | `stale` | Non-terminal issues, oldest-updated first (threshold client-side) |
| **Epic completion** | `epic-open` | Open issues remaining in an epic |
| **Release diff** | `release-prs` | PRs in a release (the changeset) |
| **Incident root cause** | `incident-cause` | `Incident → causing PR → its Commits` (multi-hop) |
| **Incident blast radius** | `incident-blast` | Components an incident affected |
| **Unheld invariants** | `unheld-invariants` | Invariants currently `violated` |
| **Gaps undermining invariants** | `gaps` | Open gaps and the invariants they fall short of |
| **Unguarded assumptions** | `assumptions` | Assumptions with an empty `guardRef` (silent dependencies) |
| **Spec coverage** | `no-spec` | Components with no `SpecFile` describing them |
| **Capability coverage** | `no-cap-impl` | Capabilities with no implementing component (planning gap) |
| **Decision impact** | `decisions-comp` | Accepted ADRs applying to a component |

Plus a per-issue triage set in `queries/issues-dashboard.gq`
(`issue-detail`, `issue-blockers`, `issue-comments`, `epic-counts`, `open-epics`, …).

## The reference seed — "Meridian"

A fabricated collaborative-document platform. **102 nodes across all 22 types,
239 edges across 83 edge types.** It's built so every killer query returns
something interesting:

- **Team (`Actor`):** Nadia (eng lead), Ravi (backend), Mei (frontend), Tomas
  (SRE), Priya (PM) + an `agent:orion` triage agent + a `svc-ci` service actor.
- **Components:** `sync-core` (the CRDT engine), `api-gateway`, `auth`,
  `presence`, `web-client`, `storage`, `billing`, `webhooks`.
- **A live storyline:** a **presence memory-leak incident** (`inc-presence-leak`,
  S2) caused by a perf PR → traced to its commit → a hotfix + a backpressure
  `Decision` + a postmortem `Learning`. `incident-cause inc-presence-leak` walks it.
- **Governance in motion:** `inv-single-writer` is **violated**; `gap-single-writer`
  undermines it and was **widened**; a partition-guard PR **narrows** it.
  `gaps` and `unheld-invariants` surface this. One **unguarded assumption**
  (`asm-storage-ordering`) shows up in `assumptions`.
- **Upstream dependency:** `iss-offline-queue` is `blocked-upstream` on
  `blk-crdt-lib` (a fictional `automerge-rs` fix); `asm-crdt-gc` covers it.

See [`seed.md`](seed.md) for the full human-readable inventory (kept in sync with
`seed.jsonl`).

## Quick start

Follow the shared [0.13 local setup](../README.md#local-setup) with
`dev-graph` and graph ID `dev`. Merge this cookbook's
`omnigraph-config.example.yaml` into your operator config, then explore:

```bash
omnigraph alias ready
omnigraph alias blocked-upstream
omnigraph alias incident-cause inc-presence-leak
omnigraph alias gaps
omnigraph query ready --server local --graph dev
```

Use the [live update workflow](../README.md#live-updates) for schema, stored
queries and optional provider configuration.

### Loading

- **Reference seed:** load once into a fresh demo graph through the server,
  following the shared setup. Do not overwrite a working graph from this seed.
- **Ongoing changes:** use the stored mutations in `queries/queries.gq`
  (`create_issue`, `update_issue_status`, `add_comment_on_issue`, `record_decision`,
  …) to preserve the pointer/append-only conventions. Review bulk loads on a
  branch before merging.
- **Dates are ISO strings** (`"2026-07-09"`); `load` accepts ISO for the `Date`
  columns and stores day-granularity. There is no `DateTime` in this schema — the
  mutations take a `$at: Date`, so `now()` (a DateTime) can't be assigned.

## Semantic search (optional)

The prose-bearing nodes (`Issue`, `Epic`, `SpecFile`, `Decision`, `Learning`,
`Invariant`, `Principle`, `Gap`, `Capability`, `Incident`, `PR`, `Assumption`,
`Comment`) declare an embedding column with its source and index:
`embedding: Vector(3072)? @embed("title"|"statement"|"name"|"body") @index`. The
column stays **null until vectors are supplied in input data** — so the seed
loads without a provider. Semantic retrieval needs populated vectors and a
configured query provider.

To enable semantic search:

1. Provide `GEMINI_API_KEY` in the server environment before starting it.
   Uncomment `providers:` and `graphs.dev.embedding_provider` in `cluster.yaml`,
   then [plan and apply live](../README.md#live-updates). Exporting a new secret
   in a client shell does not change the running server's environment.
2. Prepare JSONL containing the current node rows and an embedding spec for their
   source/target fields. Select the same provider and model for the offline
   pipeline:

   ```bash
   export OMNIGRAPH_EMBED_PROVIDER=gemini
   export OMNIGRAPH_EMBED_MODEL=gemini-embedding-2
   omnigraph embed --input rows.jsonl --output rows.embedded.jsonl \
     --spec /path/to/embeddings.json --reembed-all
   omnigraph load --data rows.embedded.jsonl --mode merge --server local --graph dev
   ```

   Set `GEMINI_API_KEY` for this command too. `omnigraph embed` transforms files;
   ordinary load preserves supplied vectors and does not generate them. See the
   [embedding guide](https://github.com/ModernRelay/omnigraph/blob/v0.13.0/docs/user/search/embeddings.md#offline-file-pipeline)
   for the spec format. Use `seed.jsonl` only for a fresh demo.
3. Run `omnigraph alias sem-issue "tenant isolation"`. Structural queries also
   work without embeddings; text-vector queries require the configured provider.

## Identifier scheme

Slug prefixes (hash-based 4–6 char suffix, beads convention):
`iss-` Issue · `epc-` Epic · `spc-` SpecFile · `dec-` Decision · `cmp-` Component ·
`repo-` Repo · `pr-` PR · `commit-` Commit (or raw SHA) · `rel-` Release ·
`dep-` Deployment · `inc-` Incident · `lrn-` Learning · `act-` Actor (`agent:<name>`
for agents) · `gate-` Gate · `lbl-` Label · `inv-` Invariant · `prn-` Principle ·
`gap-` Gap · `blk-` ExternalBlocker · `asm-` Assumption · `cap-` Capability.

## Files

- `schema.pg` — executable Omnigraph schema. Source of truth.
- `queries/queries.gq` — derived reads, semantic search, and stored mutations.
- `queries/issues-dashboard.gq` — per-issue / per-epic triage reads.
- `seed.jsonl` / `seed.md` — reference seed (loadable / human-readable twin).
- `cluster.yaml` — deployment declaration (graph `dev`, schema, stored queries).
- `omnigraph-config.example.yaml` — example operator aliases; merge into
  `~/.omnigraph/config.yaml` (per-user, never committed).

## What this deliberately does NOT model

Linked externally, not mirrored in: customer/CRM data · strategy/OKRs · test
results & coverage (query CI) · security findings/CVEs (only `Incident` lives
here) · alerts/monitoring (aggregate to `Incident`) · doc-site content (link via
`SpecFile.url`) · Slack/email threads (link by URL on a `Comment`) · `Branch` as a
node (folded into PR string fields) · `Env` as a node (folded into
`Deployment.env`; current-release-per-env is derived from deployment history).

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).
