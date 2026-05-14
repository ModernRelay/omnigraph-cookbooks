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
- `omnigraph.yaml` — CLI config with aliases.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

## Schema Language (`.pg`)

- `node` defines entity types; `edge` defines typed relationships (`edge Name: Source -> Target`)
- `@key` marks external identity (always `slug` here)
- `@index`, `@unique`, `@card(min..max)`, `@range(lo..hi)`, `@embed("prop")`
- `?` = optional, `[Type]` = list, `enum(...)` = inline closed set
- Comments use `//` not `#`

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
- **`Person.cadence_days`** is a single number — desired contact frequency *from me to them*. Semantically it belongs on the `Knows` edge, but the query language doesn't expose edge properties to projections; living on `Person` is a single-user pragmatic shortcut. Re-evaluate if the cookbook ever serves more than one user.
- **Edges follow `VerbTargetType` naming** (`NoteAboutPerson`, `TaskForProject`, `HabitFromPrinciple`).
- **Embeddings only on `Chunk`**: `Vector(3072) @embed("text")`. `Chunk` is immutable (no `updatedAt`).
- **Health / finance / hobby tracking lives as `Area` + `Note`** — not new node types. Specialty cookbooks can extend.

## Conventions enforced by load discipline (not the schema)

Omnigraph 0.4.2's `@unique(src, dst)` is parsed as two separate per-column uniqueness
constraints, not pair-uniqueness — so it can't enforce "one edge between A and B."
These conventions therefore live in the loader and reviewer, not in `schema.pg`:

- **`Knows` and `RelatedToPerson` are stored bidirectionally.** If `A knows B`, also load `B knows A`. For `RelatedToPerson`, invert the `relation`: `parent ⇄ child`, `grandparent ⇄ grandchild`. Symmetric relations (`spouse`, `sibling`, `in-law`, `ex`, `partner`) get the same enum on both sides. Single-direction storage made stale-friend / family-tree queries quietly wrong.
- **No duplicate `(src, dst)` pairs per edge type.** Dedupe before insert; the schema won't catch it.
- **`AttendedBy` vs. `EventForPerson` are not redundant**:
  - `AttendedBy` = the person was physically present (any role)
  - `EventForPerson` = the event is *about* them — honoree, subject, milestone
  - Both can apply (Theo's birthday: `AttendedBy={theo, …}` + `EventForPerson={theo}`)
  - `EventForPerson` without `AttendedBy` is for milestones you track from afar (someone's wedding you couldn't attend)

## Known gaps

- **`Note.kind=decision` is not traceable through edges.** A decision-Note can attach to a project via `NoteAboutProject`, but there's no `DecisionRegardingProject` / `DecisionBasedOnBelief` chain. By design (no SPIKE/strategy layer) — but if you later need decision provenance, add explicit edges rather than relying on `kind`.
- **`Chunk` is declared but the seed has zero.** Embeddings come from a separate ingest pipeline; the static seed can't generate them. Semantic search is a future capability, not a demo today.
- **Edge-property projections aren't supported in queries.** This means `Knows.context` and `RelatedToPerson.relation` are stored but can't be returned in `read` results. Filter against them in the writer; surface them via dedicated read-side helpers if needed.

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

```bash
omnigraph query lint --schema ./schema.pg --query ./queries/people.gq
```

The `query lint` command validates both queries and schema against each other — use it after any schema or query edit.

## When Editing

- Consult [Omnigraph schema principles](https://github.com/ModernRelay/omnigraph) for design guidance
- Use `@rename_from(...)` on property/type renames for migration support
- Keep README.md in sync with schema.pg
- Prefer semantic edge names over generic ones (`MediaRecommendedBy` not `RelatedTo`)
- Required vs optional is deliberate — don't add `?` without reason
- New node types need a strong case — most concepts fit as a `kind` enum on an existing node
- New edge types should answer a real query — don't add edges speculatively
- Resist scope creep: this cookbook is *personal life*, not health-record-keeping or full CRM. Specialty extensions belong in sibling cookbooks.
