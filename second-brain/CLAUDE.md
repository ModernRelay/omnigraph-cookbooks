# CLAUDE.md — second-brain

Scoped guidance for the `second-brain/` cookbook. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

An Omnigraph schema + seed for a personal-life "second brain" — people, places, events, notes, tasks, projects, habits, media, plus a provenance layer. Schema, seed data, and queries only — no application code.

The reference seed is **Alex Chen**, a fictional 36-year-old senior product designer in Brooklyn. All seed names, places, and dates are fabricated. The seed exists to shape demo queries, not to model a real person.

## Where things are

`README.md` is the landing page, written to the template in `../CLAUDE.md`.
It holds no commands: they are here. Keep it in step with `schema.pg`, the
stored queries and `site.json`, and run `python3 ../scripts/check-cookbooks.py
--site` after changing any of them. `seed.md` describes the seed and lists what
the main reads return.

For general Omnigraph ops — schema language, queries, loading, branches,
cluster commands, CLI — see the **omnigraph** skill and
`../CLAUDE.md`. This file covers only what's specific to Second Brain.

## Setup

Use the shared [local setup](../docs/local-setup.md) with cookbook
`second-brain` and graph `brain`. It owns authentication, the bootstrap apply and
writer lock, readiness, and served seed loading. Apply later configuration edits with
the [live update workflow](../docs/local-setup.md#live-updates).

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

## Questions the README promises

`seed.md` lists what each returns on the fresh seed:

```bash
omnigraph query person_tasks_i_owe --target local-reader --graph brain --params '{"slug":"per-theo"}'
omnigraph query tasks_next --target local-reader --graph brain
omnigraph query reading_queue --target local-reader --graph brain
omnigraph query media_recommended_by --target local-reader --graph brain --params '{"slug":"med-pachinko"}'
```

## Access

`policies/graph.policy.yaml` has three roles: `act-reader` reads and invokes
stored queries; `act-writer` and `act-admin` also change data on any branch,
including `main`, and create, delete and merge branches; only `act-admin`
applies schema changes. There is no agent role, so nothing keeps an agent off
`main`. Review of an agent's work is a practice: give it a token that can write
a branch only, and merge it yourself. Do not add or change a role without
authorization.

## Workflows

Each workflow reads through stored queries, writes on a branch, and ends with
the owner merging. Names are the stored queries; run reads with `omnigraph
query` as `local-reader` and writes with `omnigraph mutate` as `local-writer`.

| Workflow | Steps |
|---|---|
| Message capture | `add_artifact`, then `link_artifact_from_person` for the sender, `link_mentions_person` for each name, `link_in_reply_to` for a thread |
| Commitment capture | `add_task`, `link_task_for_person`, `link_task_from_artifact` |
| Note capture | `add_note`, then `link_note_about_person` / `link_note_about_project` / `link_note_about_area`, and `link_note_from_artifact` or `link_note_from_event` |
| Event and reading capture | `add_event`, `link_attended_by`, `link_happened_at`; `add_media`, `link_media_recommended_by` |
| Relationship upkeep | `person_knows` and `person_family` per person; add the missing inverse with `link_knows` or `link_related` (invert `relation`) |
| Weekly review | `projects_active`, `project_tasks`, `goal_tasks`; draft a reflection with `add_note` and link it with `link_note_about_project` |
| Open questions | `open_questions`, `principles_all`, `notes_by_kind`; draft an insight note |
| Morning briefing | `tasks_next`, `tasks_waiting`, `events_chronological` (it lists past events too; filter by `when`) |
| Stay in touch | `close_friends` for `cadence_days`, `person_recent_events` for the last event; compare. No stored read gives last contact |
| Follow-up draft | `tasks_they_owe`, `tasks_waiting_on_person` |
| Meeting prep | `event_attendees`, `preferences_for_person`, `person_tasks_i_owe` per attendee |

The act workflows (briefing, stay in touch, follow-up, prep) tell the owner or
draft a message. Sending to another person is the owner's step; the record
cannot hold an outside action back, and has no field that says a reminder was
sent.

## What the cookbook does not do

- No stored write sets `Task.direction`, `due`, `status`, `priority`,
  `remind_at` or `context`; `add_task` takes only slug, name, status and
  timestamps. A commitment captured with it does not appear in `tasks_i_owe`
  until its direction is set by another route.
- No stored write completes a task, logs a habit completion or streak, edits a
  record, retires one or merges duplicates.
- `add_artifact` does not take `content`, `thread_id` or `url`; there is no
  stored write for `Chunk`.
- No stored read lists the sources of a note. `note_from_artifact` takes an
  artifact and returns the notes drawn from it, so a check for notes with no
  source cannot run on the stored reads.
- No connectors and no automatic sync. The example policy has no agent role.

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

## Agent Workflow

Use this cookbook as a personal-context lookup, not a chat log. Typical flow:

1. **Start from intent** — a person, project, area, or upcoming event.
2. **Expand context** with aliases like `person-recent-events`, `person-tasks-i-owe`, `project-tasks`, `area-projects`.
3. **Capture new input** — incoming message, conversation, idea — as an `Artifact` first (raw), then a derived `Note` if synthesized (use `DerivedFromArtifact` with `activity` enum).
4. **Wire mentions** — `MentionsPerson`, `ArtifactFromPerson`, `ArtifactForProject` so future queries can find it.
5. **Promote to action** — if the input implies a commitment, create a `Task` with `direction` and link `TaskFromArtifact`.
6. **Preserve provenance** — every `Note` should ideally link back to the `Artifact` or `Event` it came from via `NoteFromArtifact` / `NoteFromEvent`.

For longer captures, chunk into `Chunk` records linked via `ChunkOf` — semantic search across the graph runs on those embeddings.

## When Editing

- Use `@rename_from(...)` on property/type renames for migration support
- Keep README.md in sync with schema.pg
- Prefer semantic edge names over generic ones (`MediaRecommendedBy` not `RelatedTo`)
- Required vs optional is deliberate — don't add `?` without reason
- New node types need a strong case — most concepts fit as a `kind` enum on an existing node
- New edge types should answer a real query — don't add edges speculatively
- Resist scope creep: this cookbook is *personal life*, not health-record-keeping or full CRM. Specialty extensions belong in sibling cookbooks.
