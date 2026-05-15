# Second Brain — Personal Life Ontology

A minimal-but-comprehensive Omnigraph cookbook for individuals. Built on [Omnigraph](https://github.com/ModernRelay/omnigraph).

Where `industry-intel/` and `pharma-intel/` use SPIKE for analytical intelligence, `second-brain/` is opinionated for personal life: people, places, projects, notes, tasks, habits, media — plus the provenance layer needed to capture from any channel. **13 node types, 43 edge types**, designed to feel light when you start and scale up gracefully.

## What This Is

A graph schema for the things people actually want their second brain to answer:

- *Who haven't I talked to in a while that I want to?*
- *What did Sarah recommend that I haven't read yet?*
- *What do I still owe Theo?*
- *What's on my mind about parenting / work / health?*
- *Which projects are blocking which goals?*
- *Where do my principles, habits, and decisions actually connect?*

No SPIKE pattern layer — we deliberately skipped it. This is for individual life, not industry analysis. The strategy layer can come back as an extension if you want belief/decision tracking.

## Layered Architecture

```
   ┌─── People & Roles ────────┐    ┌─── World & Time ─────────┐
   │  Person, Organization     │    │  Place, Event            │
   └───────────────────────────┘    └──────────────────────────┘
                  │                              │
                  └──────────────┬───────────────┘
                                 │
   ┌─── Capture ────────────────────────────────────────────┐
   │  Note (idea / journal / insight / principle /          │
   │        preference / quote / dream / question / decision)│
   └────────────────────────────────────────────────────────┘
                                 │
   ┌─── Action & Structure (GTD + PARA + Atomic Habits) ────┐
   │  Task → Project / Area / Goal                          │
   │  Habit → Area / Goal                                   │
   │  Project → Area                                        │
   └────────────────────────────────────────────────────────┘
                                 │
   ┌─── Media ─────────────────┐  ┌─── Provenance & Search ─┐
   │  Media (12 kinds)         │  │  Artifact, Chunk         │
   └───────────────────────────┘  └──────────────────────────┘
```

## Reference Seed: Alex Chen

The seed populates the life of a fictional 36-year-old senior product designer in Brooklyn — partner Maya, two kids, a side project, a half-marathon, a kitchen renovation, and a preschool decision in progress. All names, places, and dates are fabricated. See `seed.md` for the full layout.

**Totals:** 121 nodes across 12 types, 229 edges across 36 types. `Knows` and `RelatedToPerson` are stored bidirectionally — see `CLAUDE.md` for the load-discipline convention.

| Dimension | Count | Includes |
|---|---|---|
| People | 16 | Self, partner, 2 kids, parents + in-laws, sibling, 4 close friends, 3 colleagues, mentor |
| Organizations | 5 | Employer, partner's firm, side-project LLC, preschool, pediatrician |
| Places | 9 | Home, office, favorite restaurant, park, three out-of-town cities |
| Areas | 5 | Health, Career, Family, Learning, Creativity |
| Goals | 4 | Ship side project beta, run a half-marathon, read 24 books, save $30k |
| Projects | 6 | 4 active + 2 exploring |
| Habits | 5 | Morning pages, 3x weekly run, Sunday family dinner, read before bed, deep work block |
| Events | 12 | 7 past (Theo's birthday, Hannah's visit, Maya's promotion, etc.) + 5 upcoming |
| Notes | 21 | Principles (3), preferences (5), journal (2), insights (3), reflections (2), questions (2), and idea / decision / quote / dream |
| Tasks | 15 | next, waiting, someday, inbox — including `i-owe` and `they-owe` directions |
| Media | 12 | Books finished/want/consuming, podcasts, a documentary recommended by partner |
| Artifacts | 11 | Email, WhatsApp, iMessage, meeting notes, voice memo, calendar invite, web clip, journal — plus 2 derived |

## Schema Essentials

**Nodes (13):** Person · Organization · Place · Event · Note · Task · Project · Area · Goal · Habit · Media · Artifact · Chunk

**The enums that carry the lens:**

| Enum | Values |
|---|---|
| `Person.relation` | `self, family, partner, close-friend, friend, colleague, mentor, mentee, acquaintance, professional` |
| `Note.kind` | `idea, journal, reflection, insight, principle, preference, quote, dream, question, decision` |
| `Task.status` | `inbox, next, waiting, someday, done, cancelled` |
| `Task.direction` | `i-owe, they-owe, mutual` |
| `Task.context` | `phone, computer, errand, home, office, anywhere` |
| `Project.status` | `exploring, active, paused, completed, abandoned` |
| `Area.kind` | `health, career, finance, relationships, learning, creativity, community, spirituality, home, family, other` |
| `Habit.frequency` | `daily, weekly, monthly` |
| `Media.kind` | 13 values: book, article, movie, show, podcast, episode, album, paper, video, game, blog, newsletter, website |
| `Artifact.source` | 16 values: whatsapp, email, slack, telegram, imessage, sms, linkedin, instagram, x, calendar, web, manual, voice, notes-app, readwise, other |

**Edges that carry the work** (everything else is provenance or classification):

| Edge | Route | Meaning |
|---|---|---|
| `Knows` | Person → Person | Friend, colleague, acquaintance — with context and since |
| `RelatedToPerson` | Person → Person | Family/partnership structure, with `relation` enum on the edge |
| `LivesIn` / `WorksAt` | Person → Place / Organization | The "where they are" data |
| `AttendedBy` / `HappenedAt` | Event → Person / Place | Who was there, where it happened |
| `EventForPerson` | Event → Person | Milestones affecting someone (e.g. their wedding) without them "attending" |
| `NoteAbout{Person,Project,Area,Place,Organization,Media}` | Note → world | What this note is about |
| `RelatedNote` | Note → Note | Zettelkasten-style atomic links |
| `HabitFromPrinciple` | Habit → Note | The principle (kind=principle) that motivated the habit |
| `Task.direction = i-owe/they-owe` + `TaskForPerson` | Task → Person | Relationship-debt tracking without a separate Commitment node |
| `MediaRecommendedBy` / `MediaAuthoredBy` | Media → Person | Who pointed you at this; who wrote it |
| `MentionsPerson` / `ArtifactFromPerson` | Artifact → Person | Provenance: who's named, who sent it |
| `DerivedFromArtifact` | Artifact → Artifact | AI/manual transforms with `activity` enum (transcribed, summarized, ocr, etc.) |
| `ChunkOf` | Chunk → Artifact | Embedding-driven semantic search |

**Key design choices:**

- **Slug prefix convention** is mandatory: `per-`, `org-`, `pl-`, `ev-`, `nt-`, `tk-`, `proj-`, `area-`, `goal-`, `hab-`, `med-`, `art-`
- **"Me" convention**: `per-self` with `relation = self`. All edges from self use that slug.
- **Email and conversation collapse into `Artifact`** — `thread_id` property handles threading; `InReplyTo` edges for replies. No separate `Email` or `Conversation` types.
- **Habit completions are a `[Date]` array on the Habit** — no separate `HabitCompletion` node. Promote to a node only if per-completion notes become valuable.
- **Cadence as a single `cadence_days` field** on `Person` — desired contact frequency. Drives "stale close friends" queries. No 3-axis priority — overkill for most lives.
- **Health, finance, hobbies** live as `Area` nodes with `Note`s attached — not their own node types. Domain-specific cookbooks (e.g. a health-intel one) can extend later.
- **Chunk + embedding** stays for semantic search. Population is a separate ingest, not in the static seed.

Full property tables and constraints in [`schema.pg`](./schema.pg).

## Wow Queries — what the seed lights up

```bash
# Close friends and their preferred cadence
omnigraph read --alias close-friends

# What did Theo and I do recently, and what do I owe him
omnigraph read --alias person-recent-events per-theo
omnigraph read --alias person-tasks-i-owe per-theo
omnigraph read --alias preferences-for-person per-theo

# Open relationship debts across everyone
omnigraph read --alias tasks-i-owe
omnigraph read --alias tasks-they-owe

# My operating principles + the habits motivated by them
omnigraph read --alias principles
omnigraph read --alias habit-principle hab-morning-pages

# What's on my mind right now
omnigraph read --alias open-questions
omnigraph read --alias notes-by-kind reflection

# Project rollups: what tasks are open for Quiet Coach, what events are coming up
omnigraph read --alias project-tasks proj-quietcoach
omnigraph read --alias project-events proj-quietcoach

# Area drill-down: everything attached to Family
omnigraph read --alias area-projects area-family
omnigraph read --alias area-tasks area-family
omnigraph read --alias area-habits area-family

# Reading queue + who recommended what
omnigraph read --alias reading-queue
omnigraph read --alias person-recommendations per-kenji

# Life events affecting people I care about
omnigraph read --alias person-recent-events per-maya
omnigraph read --alias events-recent
```

## Files

- `schema.pg` — Executable Omnigraph schema (source of truth)
- `seed.md` / `seed.jsonl` — Reference seed (human-readable / loadable)
- `queries/*.gq` — Read queries (8 files) + mutations (`mutations.gq`)
- `omnigraph.yaml` — CLI config with aliases for all wow queries
- `.env.omni.example` — RustFS credential template

## Quick Start

All commands run from `second-brain/`:

```bash
cd second-brain

# Source RustFS credentials
cp .env.omni.example .env.omni
set -a && source ./.env.omni && set +a

# Lint the schema and queries (pure file check)
omnigraph query lint --schema ./schema.pg --query ./queries/people.gq

# Init the repo (one-time — writes to storage)
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/second-brain

# Load the seed (one-time)
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/second-brain

# Start the local HTTP server (keep running)
omnigraph-server --config ./omnigraph.yaml

# Query through the server via aliases
omnigraph read --alias close-friends
omnigraph read --alias person-recent-events per-theo
omnigraph read --alias tasks-i-owe
```

See the [Omnigraph](https://github.com/ModernRelay/omnigraph) repo for full CLI reference.

## Extending

This schema is the minimal core. Common extensions:

- **Strategy layer** — add `Belief` / `OpenQuestion` / `Decision` as first-class nodes (as in `pharma-intel/`) with `SupportsBelief` / `ContradictsBelief` / `InformsQuestion` edges from `Note` or `Artifact`. Turns this into a *thinking partner*, not just a data store.
- **Health cookbook** — a separate cookbook with full FHIR-grade `HealthRecord` / `Measurement` / `Condition` ontology. Don't fold it in here; keep this lean.
- **Communication style / writing tone** — a `WritingStyle` node per channel/audience for "draft a message in my voice."
- **Pattern emergence** — add a single `Theme` node + `NoteFormsTheme` edge if you want explicit emergent-theme tracking without going full SPIKE.

When in doubt, prefer extending in a sibling cookbook over bloating this one.
