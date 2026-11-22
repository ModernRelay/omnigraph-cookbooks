# CLAUDE.md — second-brain

Scoped guidance for the `second-brain/` cookbook. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

An Omnigraph schema + seed for a personal-life "second brain" — people, places, events, notes, tasks, projects, habits, media, plus a provenance layer. Schema, seed data, and queries only — no application code.

The reference seed is **Alex Chen**, a fictional 36-year-old senior product designer in Brooklyn. All seed names, places, and dates are fabricated. The seed exists to shape demo queries, not to model a real person.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — The landing page: data model, workflows, data sources, questions and sample data, in the shared template (see `../CLAUDE.md`).
- `site.json` — The copy omnigraph.dev shows, and the mr-ops use case (`usecase:agent-memory`) the README is held to.
- `seed.md` / `seed.jsonl` — Seed dataset (human-readable / loadable).
- `queries/*.gq` — Read and mutation queries.
- `cluster.yaml` — Deployment declaration (graph `brain`, schema, stored queries).
- `omnigraph-config.example.yaml` — Read aliases; merge them into the operator config from the [local setup](../README.md#local-setup).

For general Omnigraph ops — schema language, queries, loading, branches,
cluster commands, CLI — see the **omnigraph** skill and
`../CLAUDE.md`. This file covers only what's specific to Second Brain.

## Setup

Use the shared [local setup](../README.md#local-setup) with cookbook
`second-brain` and graph `brain`. It owns authentication, the bootstrap writer-lock
handoff, readiness, and served seed loading. Apply later configuration edits with
the [live update workflow](../README.md#live-updates).

Graph id `brain`. Stored queries and their parameters: `omnigraph queries list --target local --graph brain`.
Aliases pass parameters by name: `omnigraph alias person-tasks-i-owe --params '{"slug":"per-theo"}'` is `omnigraph query person_tasks_i_owe --target local-reader --graph brain --params '{"slug":"per-theo"}'`.

## Writing

Aliases are read-only; mutations run as `omnigraph mutate <name> --target local-writer --graph brain --params '<json>'`
with every non-optional property supplied. Signatures live in `queries/mutations.gq`. Working example:

```bash
omnigraph mutate add_task --target local-writer --graph brain --params '{"slug":"tk-theo-whisky","name":"Bring Theo the Lagavulin 16","status":"next","createdAt":"2026-09-14T00:00:00Z","updatedAt":"2026-09-14T00:00:00Z"}'
omnigraph mutate link_task_for_person --target local-writer --graph brain --params '{"task":"tk-theo-whisky","person":"per-theo"}'
```

`--graph` can be omitted only for a target with `default_graph`; the shared setup's targets have none.

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
- **`Person.cadence_days`** is a single number — desired contact frequency *from me to them*. The engine can project a bound edge property (`$me $k:knows $person`, then `$k.context`), but cadence remains on `Person` as a single-user shortcut. Re-evaluate if the cookbook ever serves more than one user.
- **Edges follow `VerbTargetType` naming** (`NoteAboutPerson`, `TaskForProject`, `HabitFromPrinciple`).
- **Embeddings only on `Chunk`**: `Vector(3072) @embed("text")`. `Chunk` is immutable (no `updatedAt`).
- **Health / finance / hobby tracking lives as `Area` + `Note`** — not new node types. Specialty cookbooks can extend.

## Data conventions

These edges do not declare pair-uniqueness constraints, so loaders and reviewers
must preserve the following conventions:

- **`Knows` and `RelatedToPerson` are stored bidirectionally.** If `A knows B`, also load `B knows A`. For `RelatedToPerson`, invert the `relation`: `parent ⇄ child`, `grandparent ⇄ grandchild`. Symmetric relations (`spouse`, `sibling`, `in-law`, `ex`, `partner`) get the same enum on both sides. Single-direction storage made stale-friend / family-tree queries quietly wrong.
- **No duplicate `(src, dst)` pairs per edge type.** Check existing edges before inserting a new relationship.
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

## Questions

The four questions in `site.json`, as run against the served graph:

```bash
omnigraph query person_tasks_i_owe --target local-reader --graph brain --params '{"slug":"per-theo"}'
omnigraph query tasks_next --target local-reader --graph brain
omnigraph query reading_queue --target local-reader --graph brain
omnigraph query media_recommended_by --target local-reader --graph brain --params '{"slug":"med-outlive-attia"}'
```

## Workflows

Use this cookbook as a personal-context lookup, not a chat log. Run the reads as
`local-reader` and the writes as `local-writer`. Every workflow: something
starts it, the agent reads, it writes on its own branch or tells the user, and
the user decides. Create the branch first, pass `--branch` to every write, then
`omnigraph branch diff <b>` and `omnigraph branch merge <b> --into main --dry-run`
before the user merges. The example policy gives `local-writer` the right to
write `main` and merge, and there is no agent role, so staying on the branch is
the agent's discipline.

```bash
omnigraph branch create agent-intake-0914 --target local-writer --graph brain
```

**Capture**

- *Message intake.* A message arrives. Check `artifacts_by_thread` (param
  `thread_id`) so the thread is not recorded twice. `add_artifact`, then
  `link_artifact_from_person`, `link_mentions_person`, `link_artifact_for_project`
  and, for a reply, `link_in_reply_to`. Resolve people with `people_all` or
  `get_person` first; never invent a `per-` slug.
- *Promise capture.* The message implies a commitment: `add_task`, then
  `link_task_for_person` and `link_task_from_artifact`. `add_task` cannot set
  `direction`, `due` or `kind`; without `direction` the task never appears in
  `tasks_i_owe` or `person_tasks_i_owe`. Set them with an ad hoc
  `omnigraph mutate -e` (an `update Task set ...` statement) on the same
  branch.
- *Notes and preferences.* `add_note`, then `link_note_about_person` or
  `link_note_about_project`, and `link_note_from_artifact` or
  `link_note_from_event`. `add_note` cannot set `content`; set it the same way.
- *Event log.* `add_event`, `link_attended_by`, `link_happened_at`; add
  `link_event_for_person` when the event is about someone.

```bash
omnigraph mutate add_artifact --target local-writer --graph brain --branch agent-intake-0914 --params '{"slug":"art-marco-text-0914","name":"Marco: playdate Saturday?","kind":"message","source":"whatsapp","timestamp":"2026-09-14T09:00:00Z","createdAt":"2026-09-14T09:00:00Z","updatedAt":"2026-09-14T09:00:00Z"}'
omnigraph mutate link_artifact_from_person --target local-writer --graph brain --branch agent-intake-0914 --params '{"artifact":"art-marco-text-0914","person":"per-marco"}'
```

**Maintain**

- *Inbox review.* Read `tasks_inbox` and `projects_active`; link each task with
  `link_task_for_project`, `link_task_for_area` or `link_task_for_goal`.
  Clarifying `status` is an ad hoc update.
- *Note linking.* Read `notes_recent` and `note_related`; add `link_related_note`
  where two notes say related things. Read `open_questions` and list those a
  newer note answers; the user closes them.
- *Stale review.* Read `tasks_next` and `tasks_waiting`; list those whose `due`
  has passed. The user finishes, drops or moves them.
- *Habit streaks.* `Habit.streak_current` and `streak_best` are stored from
  `completions`. When a completion is logged, the same ad hoc update must
  recompute both; `habits_active` shows them.

**Act** (nothing here reviews an outside action; draft and tell, never send to
another person unapproved; use the agent's own tools, as the cookbook has no
integration)

- *Owed and overdue.* `tasks_i_owe`, or `person_tasks_i_owe` per person; tell the
  user what is past `due`.
- *Chase.* `tasks_they_owe`, `tasks_waiting_on_person`; draft a nudge.
- *Stay in touch.* `close_friends` gives `cadence_days`; the last contact is the
  latest of `person_recent_events` and `person_artifacts_from` (no stored query
  computes the gap, so compare in the agent). Draft a message.
- *Briefing.* For an upcoming event from `events_chronological`: `event_attendees`,
  then per person `person_notes`, `preferences_for_person`,
  `person_tasks_i_owe`, `person_recent_events`.

The record has no place to note that a reminder or nudge went out. The agent
keeps that itself, or records a follow-up task with `remind_at` (no stored read
filters on it).

For longer captures, chunk into `Chunk` records linked via `ChunkOf`; semantic
search needs the offline embedding pass first.

## What it does not do

- No connectors; a sync is a script or an agent writing through the stored mutations or a merge load.
- The stored writes only insert and only set core fields. Nothing updates or deletes a row.
- No agent role: nothing enforces branch-only writes.
- No stored read for overdue contacts, past-due tasks or duplicate people.
- No embeddings in the seed; `Chunk` is empty.

## When Editing

- Use `@rename_from(...)` on property/type renames for migration support
- Keep README.md in sync with schema.pg
- Prefer semantic edge names over generic ones (`MediaRecommendedBy` not `RelatedTo`)
- Required vs optional is deliberate — don't add `?` without reason
- New node types need a strong case — most concepts fit as a `kind` enum on an existing node
- New edge types should answer a real query — don't add edges speculatively
- Resist scope creep: this cookbook is *personal life*, not health-record-keeping or full CRM. Specialty extensions belong in sibling cookbooks.
