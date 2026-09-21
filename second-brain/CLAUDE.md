# CLAUDE.md — second-brain

Scoped guidance for the `second-brain/` cookbook. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

An Omnigraph schema + seed for a personal-life "second brain" — people, places, events, notes, tasks, projects, habits, media, plus a provenance layer. Schema, seed data, and queries only — no application code.

The reference seed is **Alex Chen**, a fictional 36-year-old senior product designer in Brooklyn. All seed names, places, and dates are fabricated. The seed exists to shape demo queries, not to model a real person.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — Layered architecture, reference seed description, schema essentials, wow queries.
- `seed.md` / `seed.jsonl` — Seed dataset (human-readable / loadable).
- `queries/*.gq` — Read and mutation queries.
- `cluster.yaml` — Deployment declaration (graph `brain`, schema, stored queries).
- `omnigraph-config.example.yaml` — Example operator config; merge its aliases into your per-user `~/.omnigraph/config.yaml`.

For general Omnigraph ops — schema language, queries, loading, branches,
cluster commands, CLI — see the **omnigraph** skill and
`../CLAUDE.md`. This file covers only what's specific to Second Brain.

## Answering and writing (agents)

- **Answer from the graph, not the files.** Use the aliases / stored queries against the running server; never assemble an answer by reading `seed.jsonl` or `seed.md` — they are load inputs, not the live state.
- **Alias args bind by name to the query's `$params`** (`args: [slug]` fills `$slug`): `omnigraph alias person-tasks-i-owe per-theo` is `omnigraph query person_tasks_i_owe --graph brain --params '{"slug":"per-theo"}'`.
- **Mutations are not aliasable on 0.10** (`'add_x' is a mutation — use omnigraph mutate add_x`). Run them with `omnigraph mutate <name> --params '<json>'`, every non-optional property supplied; signatures live in `queries/mutations.gq`. Working example:

  ```bash
  omnigraph mutate add_task --graph brain --params '{"slug":"tk-theo-whisky","name":"Bring Theo the Lagavulin 16","status":"next","createdAt":"2026-09-14T00:00:00Z","updatedAt":"2026-09-14T00:00:00Z"}'
  omnigraph mutate link_task_for_person --graph brain --params '{"task":"tk-theo-whisky","person":"per-theo"}'
  ```

  With `defaults.server` / `default_graph` from the operator config, `--graph` can be omitted.

## Setup, in order (verified against 0.10)

`cluster import` comes **before** the first `apply` — without it `apply` exits 1
with `state_missing __cluster/state.json: apply requires an existing state.json`.

```bash
cd second-brain
omnigraph cluster import --config .                # once: bootstraps __cluster/state.json
omnigraph cluster apply  --config . --as <you>     # creates graphs/brain.omni, applies schema + stored queries
omnigraph load --data seed.jsonl --mode overwrite graphs/brain.omni
omnigraph-server --cluster . --unauthenticated &   # 127.0.0.1:8080 — refuses to start without this flag or auth
curl -s http://127.0.0.1:8080/healthz              # {"status":"ok",…}; the path is /healthz, /health is 404
```

### `load` addressing

`--data` is the **seed file**; the **graph** is the positional URI. Both are
required, as is `--mode` (`overwrite` | `append` | `merge`).

| Target | Command |
|---|---|
| Local storage, no server | `omnigraph load --data seed.jsonl --mode overwrite graphs/brain.omni` |
| A running server | `omnigraph load --data seed.jsonl --mode overwrite --server http://127.0.0.1:8080 --graph brain --yes` |

One address per command. The engine's own refusals:

- `--graph` next to a positional URI or `--store` → *"--graph selects a graph
  within a server or cluster scope; a positional URI / --store is already a
  single graph"*. `--graph` pairs with `--server`, nothing else.
- `--cluster` on `load` → *"`load` is a data command; --cluster addresses a
  cluster-scoped command and does not apply."*
- `omnigraph load seed.jsonl …` — the positional slot is the **graph**, never the data file.
- `overwrite` through a server prompts, so non-interactive callers add `--yes`.

### Find the query instead of guessing it

- **`omnigraph queries list --cluster . --graph brain`** prints every stored
  query and mutation *with its parameter names*, offline, no server needed. Read
  the signature before writing `--params`: `query media_by_kind($kind: String)`
  takes `{"kind":…}`, not `{"slug":…}`.
- `omnigraph query <name>` resolves a **stored query by name** and needs a
  server — passing query text there fails with *"by-name invocation needs a
  server (the stored-query catalog is server-owned)"*. Ad-hoc GQL goes through
  `-e`, in the same dialect as the `.gq` files:

  ```bash
  omnigraph query -e 'query q($slug: String) { match { $p: Person { slug: $slug } } return { $p.slug, $p.name } }' \
    --params '{"slug":"per-self"}' --store file://$PWD/graphs/brain.omni
  ```

  Filters bind **inside the node's braces** (`$p: Person { slug: $slug }`) — there
  is no `where`, no `filter { … }`, no `Person[slug=="…"]`. The parameter list is
  required even when empty (`query q()`), and `limit N` / `order { … }` sit
  inside the outer braces after `return`, never trailing the string.

- `omnigraph alias <name> [args]` carries its own server and graph — adding
  `--graph`/`--server` errors with *"remove global scope flag(s)"*. **An alias
  name is not a query name:** `queries list` prints `get_person` and
  `people_all`, whose aliases are `person` and `people` — hyphenated, and often
  dropping a `get_` prefix. They are the keys under `aliases:` in
  `omnigraph-config.example.yaml`; there is no `--list`.

## Cluster control plane (two-file model)

This cookbook is a **filesystem-backed cluster** — no object store, no
credentials. `cluster.yaml` is the deployment: graph `brain`, `schema.pg`, and
every stored query, converged with `omnigraph cluster import|plan|apply
--config .` (apply creates `graphs/brain.omni`; schema edits show migration
previews in plan; graph deletion is approval-gated). The per-operator surface
(aliases, CLI defaults, identity for `--as` attribution) lives in your per-user
`~/.omnigraph/config.yaml`, never committed — this cookbook ships
`omnigraph-config.example.yaml` to merge in. Serve with `omnigraph-server
--cluster .` (never reads the operator config). Data flows through `omnigraph
load` / `omnigraph mutate` against `graphs/brain.omni`; invoke aliases with
`omnigraph alias <name> [args]` (or a stored query directly: `omnigraph query
<name> --graph brain [--params …]`). Never commit `__cluster/` or `graphs/`
(gitignored — local state).

## Domain Model

**Six layers, one graph:**

| Layer | Nodes | Purpose |
|---|---|---|
| People & Roles | `Person`, `Organization` | Relationships and affiliations |
| World & Time | `Place`, `Event` | Where and when |
| Capture | `Note` | Everything captured — atomic, with `kind` enum |
| Action & Structure | `Task`, `Project`, `Area`, `Goal`, `Habit` | GTD + PARA + Atomic Habits |
| Media | `Media` | Books, articles, podcasts, etc. |
| Provenance & Search | `Artifact`, `Chunk` | Source-of-truth + embedding search |

**Design choices to preserve:**

- **Slug prefix convention is mandatory** — `per-`, `org-`, `pl-`, `ev-`, `nt-`, `tk-`, `proj-`, `area-`, `goal-`, `hab-`, `med-`, `art-`. Don't break it.
- **`per-self` is "me"** with `relation = self`. All self-references use this slug.
- **One `Note` node, not many** — `kind` enum (idea / journal / insight / principle / preference / quote / dream / question / decision / reflection) is what distinguishes them in queries. Don't promote sub-kinds to their own node types.
- **`Task.direction = i-owe/they-owe/mutual`** is how relationship-debt tracking lives without a separate `Commitment` node.
- **`Task.waiting_on` is intentionally absent.** "Who I'm waiting on" is expressed by `status=waiting` + `TaskForPerson`. Don't reintroduce a string slug-shaped property.
- **Habit completions are a `[Date]` array** on the Habit node. No `HabitCompletion` node.
- **Email and Conversation collapse into `Artifact`** with `thread_id` property and `InReplyTo` edges. No separate types.
- **`Person.cadence_days`** is a single number — desired contact frequency *from me to them*. v0.10 can project a bound edge property (`$me $k:knows $person`, then `$k.context`), but cadence remains on `Person` as a single-user shortcut. Re-evaluate if the cookbook ever serves more than one user.
- **Edges follow `VerbTargetType` naming** (`NoteAboutPerson`, `TaskForProject`, `HabitFromPrinciple`).
- **Embeddings only on `Chunk`**: `Vector(3072) @embed("text")`. `Chunk` is immutable (no `updatedAt`).
- **Health / finance / hobby tracking lives as `Area` + `Note`** — not new node types. Specialty cookbooks can extend.

## Conventions enforced by load discipline (not the schema)

`@unique(src, dst)` on an edge **is** enforced as a
true composite key — pair-uniqueness now works (it was previously degraded into two
independent per-column checks). Enforcement covers single-batch `load` / `insert` / `update`
and branch-merge, but **not** a duplicate written in a *separate* operation against
already-committed rows on the same branch (intra-batch only at the direct-write path). The
edges here don't declare `@unique(src, dst)` yet, so the conventions below still live in the
loader and reviewer — add the constraint if you want the schema to enforce dedupe within a load:

- **`Knows` and `RelatedToPerson` are stored bidirectionally.** If `A knows B`, also load `B knows A`. For `RelatedToPerson`, invert the `relation`: `parent ⇄ child`, `grandparent ⇄ grandchild`. Symmetric relations (`spouse`, `sibling`, `in-law`, `ex`, `partner`) get the same enum on both sides. Single-direction storage made stale-friend / family-tree queries quietly wrong. (Unaffected by the `@unique` fix — this is about storing the *inverse* edge, not deduping pairs; `@unique` won't auto-create it.)
- **No duplicate `(src, dst)` pairs per edge type.** Now schema-enforceable by declaring `@unique(src, dst)` on the edge (catches dupes within a load/merge); still dedupe across separate write operations, which intake doesn't cross-check.
- **`AttendedBy` vs. `EventForPerson` are not redundant**:
  - `AttendedBy` = the person was physically present (any role)
  - `EventForPerson` = the event is *about* them — honoree, subject, milestone
  - Both can apply (Theo's birthday: `AttendedBy={theo, …}` + `EventForPerson={theo}`)
  - `EventForPerson` without `AttendedBy` is for milestones you track from afar (someone's wedding you couldn't attend)

## Known gaps

- **`Note.kind=decision` is not traceable through edges.** A decision-Note can attach to a project via `NoteAboutProject`, but there's no `DecisionRegardingProject` / `DecisionBasedOnBelief` chain. By design (no SPIKE/strategy layer) — but if you later need decision provenance, add explicit edges rather than relying on `kind`.
- **`Chunk` is declared but the seed has zero.** A separate ingest prepares raw JSONL, runs the offline `omnigraph embed` file pipeline, and loads the output; the command does not mutate a graph. Semantic search is a future capability, not a demo today.
- **Edge-property projections require a bound edge variable.** For example, `$a $k:knows $b` can return `$k.context`; use the same pattern for `RelatedToPerson.relation`.

## The Demo "Wow" Queries

These are the queries the seed is shaped to light up — preserve them when iterating:

| Alias | Input | Expected outcome |
|---|---|---|
| `close-friends` | — | 4 people: Theo, Priya, Marco, Lia, with cadence_days |
| `person-tasks-i-owe` | `per-theo` | "Send Theo Bevelin's book link" |
| `person-tasks-they-owe` | `per-hannah` | "Hannah to call after vet appointment" |
| `preferences-for-person` | `per-theo` | "Theo loves Islay single malts" note |
| `principles` | — | 3 principles: default-yes-family, input-output, no-meetings-fri |
| `open-questions` | — | "Should QC pivot to B2B?", "Which preschool for Sam?" |
| `tasks-i-owe` | — | All open commitments across people |
| `area-projects` | `area-family` | Kitchen reno, Sam's preschool, Japan trip |
| `project-tasks` | `proj-quietcoach` | Onboarding flow + research task |
| `habit-principle` | `hab-morning-pages` | The "capture input separately from output" principle |
| `reading-queue` | — | Books with status=want, including Outlive and Pachinko |
| `media-recommended-by` | (alias takes media slug) | Who recommended this book |
| `person-recommendations` | `per-kenji` | Books Kenji recommended: Outlive, Four Thousand Weeks |
| `person-recent-events` | `per-maya` | Time-sorted events Maya attended |
| `events-recent` | — | Recent events across the graph |

If a schema or seed change breaks any of these, the personal-life lens is not delivering — fix the seed rather than compromising the schema.

## Agent Workflow

Use this cookbook as a personal-context lookup, not a chat log. Typical flow:

1. **Start from intent** — a person, project, area, or upcoming event.
2. **Expand context** with aliases like `person-recent-events`, `person-tasks-i-owe`, `project-tasks`, `area-projects`.
3. **Capture new input** — incoming message, conversation, idea — as an `Artifact` first (raw), then a derived `Note` if synthesized (use `DerivedFromArtifact` with `activity` enum).
4. **Wire mentions** — `MentionsPerson`, `ArtifactFromPerson`, `ArtifactForProject` so future queries can find it.
5. **Promote to action** — if the input implies a commitment, create a `Task` with `direction` and link `TaskFromArtifact`.
6. **Preserve provenance** — every `Note` should ideally link back to the `Artifact` or `Event` it came from via `NoteFromArtifact` / `NoteFromEvent`.

For longer captures, chunk into `Chunk` records linked via `ChunkOf` — semantic search across the graph runs on those embeddings.

## Validation

After any schema or query edit, lint before applying — e.g. `omnigraph lint
--schema schema.pg --query queries/people.gq`. The lint/plan/apply/load loop and
cluster ops are covered in the **omnigraph** skill and
`../CLAUDE.md`; don't repeat them here.

## When Editing

- Use `@rename_from(...)` on property/type renames for migration support
- Keep README.md in sync with schema.pg
- Prefer semantic edge names over generic ones (`MediaRecommendedBy` not `RelatedTo`)
- Required vs optional is deliberate — don't add `?` without reason
- New node types need a strong case — most concepts fit as a `kind` enum on an existing node
- New edge types should answer a real query — don't add edges speculatively
- Resist scope creep: this cookbook is *personal life*, not health-record-keeping or full CRM. Specialty extensions belong in sibling cookbooks.
