# personal-knowledge

A second-brain cookbook: a typed graph of your notes, contacts, conversations, projects, and meeting transcripts pulled from eight personal apps. Built on [Omnigraph](https://github.com/ModernRelay/omnigraph), driven by the [`omnigraph-personal-knowledge`](../skills/omnigraph-personal-knowledge/SKILL.md) skill — the actual user surface. This README is the editor reference.

## What it looks like

The skill auto-runs the headline queries after every successful load. Sample output against the bundled seed:

### Headline

```
Your personal-knowledge graph
─────────────────────────────
   15 Notes from 5 sources (obsidian 5, granola 4, notion 3, apple-notes 2, slack 1)
   12 Persons     → top mentions: Alex Rivera (3×), Jane Park (2×), Aaron Kim (2×)
    3 Conversations across 3 sources (slack: 2, email: 1)
    4 active areas, 4 active projects
    8 cross-source identity candidates flagged for review
```

Numbers above come from the bundled fictional seed (persona "Alex Rivera").

### Aliases

The cookbook ships ~50 named aliases over `omnigraph read` and `omnigraph change`. The skill composes against them; users don't write `.gq` directly. One example:

```
$ omnigraph read --alias notes
15 rows from branch main via recent_notes
n.slug                       | n.name                                          | n.kind     | n.tags                            | n.updatedAt
-----------------------------+-------------------------------------------------+------------+-----------------------------------+------------
note-pk-vision               | PK vision: agents writing into governed context | insight    | [pk, agents, context]             | 2026-05-07
note-aaron-design-feedback   | Aaron's feedback on the spec                    | reflection | [design, aaron, spec]             | 2026-05-06
note-pkm-redesign-principles | PKM redesign — atomic, not hierarchical         | principle  | [pkm, atomic-notes, principle]    | 2026-05-04
note-context-graph-thesis    | Context graph thesis                            | insight    | [thesis, graph, architecture]     | 2026-05-02
note-q2-okr-draft            | Q2 OKRs (draft)                                 | idea       | [okr, q2]                         | 2026-05-01
note-david-fundraise-advice  | David: narrative > numbers in fundraise         | quote      | [fundraise, david, quote]         | 2026-05-01
…
```

Other shipped aliases include `persons`, `conversations`, `notes-about-person <slug>`, `artifacts-from notion`, `inbox`, `next`. Full list in `omnigraph.yaml`.

### Identity resolution

The same person typically shows up under multiple slugs across sources. The wizard finds candidate pairs with three matchers (email-prefix collision, exact-name, first-name alias), gathers contextual evidence per pair (shared email domain, shared org, domain-org match), and **auto-decides** on strong signals. It only prompts when the evidence is ambiguous.

Example from the bundled seed: two Janes — `person-jane-park` (email `jane@kettle.so`, org Kettle) and `person-jane-park-personal` (Slack handle, no email or org). The cross-source candidate query lists them:

```
$ omnigraph read --alias headline-cross-source-persons
8 rows from branch main via headline_cross_source_persons
p.slug                    | p.name         | e.source
--------------------------+----------------+---------
person-jane-park          | Jane Park      | email     ← same person?
person-jane-park-personal | Jane           | slack     ← same person?
person-priya-shah         | Priya Shah     | email     ← same person?
person-priya-shah-work    | Priya Shah     | email     ← same person?
person-aaron-kim          | Aaron Kim      | email     ← already merged (1 slug, 2 sources)
person-aaron-kim          | Aaron Kim      | slack
…
```

For pairs without auto-decidable evidence, the skill prompts via `AskUserQuestion` with the per-person evidence (orgs, email domains, ExternalID sources, mention counts) on screen. On confirmation it writes a `SameAs` edge between the two slugs.

Downstream "show me everything about <person>" calls then unify the slugs via the SameAs-aware traversal pattern (see `skills/omnigraph-personal-knowledge/references/identity-resolution.md`): the skill resolves the `SameAs` closure first, runs the read alias for each slug, and unions the results. A direct `person-mentions person-priya-shah` may return 0 rows; the unified read across the merged Priya slugs returns the Granola customer-interview transcript that was attached to her work persona.

## What you get

A typed, versioned graph of:

- **People** — contacts, colleagues, mentors, family, with cross-source identity (`SameAs` edges merge "Jane on email" with "Jane on Slack").
- **Notes** — atomic ideas, reflections, journals, principles, quotes, captured from any of your apps.
- **Conversations** — Slack threads, WhatsApp chats, LinkedIn DMs, email threads, all sharing a unified `Conversation` shape.
- **Artifacts** — the source-of-truth records each note/message was extracted from. Provenance-first.
- **Life structure** — Areas, Projects, Goals, Tasks, Habits in the GTD + Atomic Habits + PARA shape.
- **Calendar** — Events with attendees, places, and links to the meeting transcripts that recorded them.
- **Email** — first-class type with subjects, threading, addressing.

## Sources (all 8 ship in v1)

| Source | Auth model | Setup |
|---|---|---|
| Obsidian | none | point at vault dir |
| Notion | integration token | create at `notion.so/my-integrations`, add to pages |
| Granola | API token or local export JSON | export your token (or drop a JSON) |
| Slack | bot token | create app at `api.slack.com/apps`, install to workspace |
| Google Workspace | OAuth (Drive / Gmail / Calendar) | client_secret.json from Google Cloud Console |
| Apple Notes | none (Mac only) | AppleScript dump via `osascript` |
| LinkedIn | none | request data export from LinkedIn (CSV ZIP) |
| WhatsApp | none | Export Chat → Without Media |

The skill handles per-source setup: opens the integration page in the browser, captures the token, validates with a one-call round-trip, and persists via `keyring`. Connect any subset. Each source has its own spec doc at `skills/omnigraph-personal-knowledge/references/sources/<source>.md` describing setup, fetch intent, mapping, and known quirks.

## The pipeline

Every source flows through one shape: the skill reads the source-specific spec, composes fetch + map code inline per session, and emits schema-shaped records that `omnigraph load --mode merge` upserts by slug. **No pre-written Python ships with the cookbook** — the spec is the durable artifact; the code is composed each run, fresh against current source-API documentation.

```
your apps                                       governed graph
─────────                                       ──────────────
Obsidian, Notion, Granola,    sources/<X>.md    omnigraph load
Slack, Gmail, Calendar,    →  (agent reads,  →  (idempotent merge,  → skill answers
Apple Notes, LinkedIn,        composes fetch    dedup via stable      user questions
WhatsApp                      + map code         IDs + SyncRun)
                              per session)
```

The agent composes idempotent code (stable IDs upsert) that respects `--since` where the source supports server-side filtering (Notion, Slack, Gmail, Calendar, Drive, Granola). Last-sync timestamps live in the graph itself as `SyncRun` nodes — no external sync DB, no separate state file.

Adding a new app means writing a new spec doc (`skills/.../references/sources/<new>.md`) following the established structure. The schema stays source-neutral; the spec is the durable extension surface.

## The identity layer

The same person typically appears across sources under different identifiers — Jane on email, Jane on Slack, Jane Park on LinkedIn. The graph handles this with a two-layer model:

- **`ExternalID`** records each `(source, identifier)` pair as a first-class node. Every imported `Person` gets one `ExternalID` per source they appear under, linked via `IdentifiesPerson`.
- **`SameAs`** edges between two `Person` slugs assert they're the same human.

The dedup wizard (skill Phase 2.5) finds candidate pairs with three matchers — email-prefix collision, exact-name, first-name alias — then gathers contextual evidence per pair (shared organization, shared email domain, domain-org match). It auto-decides on strong signals and prompts the user only when evidence is ambiguous. On confirmation it writes `SameAs` in both directions.

Read aliases match on exact slugs — they don't follow `SameAs` automatically. The skill compensates at orchestration time: when the user asks "show me everything about X", it resolves the `SameAs` closure first, runs the requested alias for every aliased slug, and unions the results. See `skills/omnigraph-personal-knowledge/references/identity-resolution.md` for the pattern.

## Files

```
personal-knowledge/
├── README.md             # this file
├── AGENTS.md             # authoring contract for cookbook editors
├── CLAUDE.md             # pointer to AGENTS.md
├── EXTENDING.md          # paste-in schema overlays (Health, Finance, etc.)
├── schema.pg             # 16 typed node types, ~45 edge types
├── seed.md               # human-readable tabular seed
├── seed.jsonl            # demo seed (fictional persona "Alex Rivera")
├── omnigraph.yaml        # ~50 CLI aliases
├── queries/
│   └── notes, people, conversations, structure, sync, headline, mutations
└── demo/
    └── test-fixtures/test-vault/   # illustrative data only — no executable code

../skills/omnigraph-personal-knowledge/
├── SKILL.md
└── references/
    ├── sources/                    # one spec per source the agent reads + composes code from
    │   ├── notion.md, obsidian.md, granola.md, slack.md
    │   ├── google-workspace.md, apple-notes.md, linkedin.md, whatsapp.md
    ├── loading-rules.md            # cross-cutting: dedup, dangling edges, SyncRun, stable IDs
    ├── headline-report.md          # 5-numbers playbook + follow-up rules
    ├── identity-resolution.md      # dedup wizard + SameAs-aware traversal pattern
    ├── sync.md                     # incremental-sync contract
    └── extending.md                # adding a new source spec or domain overlay
```

## Schema

15 user-content nodes plus `SyncRun` for sync state. Grouped in three rings:

- **Identity** — `Person`, `Organization`, `Place`, `ExternalID`, `SameAs`
- **Activity** — `Event`, `Conversation`, `Email`, `Artifact`, `Chunk`
- **Structure** (PARA + GTD + Atomic Habits) — `Area`, `Project`, `Goal`, `Task`, `Habit`, `Note`

Edges connect the three rings. See `schema.pg` for the full set.

## Extending

Health tracking, Financing, Inspiration boards, and sales Frames live as paste-in `.pg` snippets in `EXTENDING.md` rather than separate cookbooks. Each overlay is self-contained: it adds nodes and edges that reference spine types without modifying them.

For a new source connector (Day One, Roam, etc.), see `skills/omnigraph-personal-knowledge/references/extending.md`.

## Quick start

Tested against **Omnigraph 0.4.2** (CLI + server). `omnigraph --version` should report `>= 0.4.0`. Install via `brew install ModernRelay/tap/omnigraph` or the install script (see the [Omnigraph README](https://github.com/ModernRelay/omnigraph#quick-install)).

### Bundled demo (fictional seed)

```bash
# Source RustFS credentials
cp .env.omni.example .env.omni
set -a && source ./.env.omni && set +a

# Lint the schema and queries (pure file check)
omnigraph query lint --schema ./schema.pg --query ./queries/*.gq

# Init the repo (one-time — writes to storage)
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/personal-knowledge

# Load the seed (one-time)
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/personal-knowledge

# Start the local HTTP server (keep it running — separate terminal or background)
omnigraph-server --bind 127.0.0.1:8080 s3://omnigraph-local/repos/personal-knowledge &

# All queries go through the server via aliases
omnigraph read --alias notes
omnigraph read --alias headline-top-persons
omnigraph read --alias headline-cross-source-persons
```

### Connect your own data

Connecting your own apps requires an agentskills.io-compatible runtime (Claude Code, Hermes, etc.). The skill reads each source's spec doc (`skills/omnigraph-personal-knowledge/references/sources/<source>.md`) and composes the fetch + map code inline per session — there's no pre-written script to invoke. See `skills/omnigraph-personal-knowledge/SKILL.md` for the orchestration.

This is intentional. Pre-written importers go stale every time a source's API changes; the spec stays stable while the agent's code is fresh against current docs each run.

## Using with other agent frameworks

The skill conforms to the [agentskills.io](https://agentskills.io/specification) spec, so any compatible runtime drives it without modification.

**[Hermes](https://github.com/NousResearch/hermes-agent)** (Nous Research) is one such runtime. Symlink the skill into Hermes's skills directory:

```bash
ln -s "$(pwd)/skills/omnigraph-personal-knowledge" ~/.hermes/skills/omnigraph-personal-knowledge
hermes
# then: /omnigraph-personal-knowledge
```

Hermes adds two affordances on top: querying the graph from Telegram/Discord/Slack/Signal via its messaging gateway, and running the `sync` action on its built-in cron. Both work without extra config.

Other agentskills.io-compatible runtimes follow the same pattern.

## License

MIT — same as the parent repo.
