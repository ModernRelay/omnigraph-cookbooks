# AGENTS.md — personal-knowledge

Single source of agent context for the `personal-knowledge` cookbook — design rationale, editing conventions, routing rules, and the moments where you should stop and ask the user.

User-facing onboarding lives in the [`omnigraph-personal-knowledge`](../skills/omnigraph-personal-knowledge/SKILL.md) skill, not here. This file is for editors and any agent that arrives at the folder.

Read top to bottom on first contact, then jump to the section the user's intent maps to.

## About

`personal-knowledge` is the first inward-facing cookbook in [Omnigraph](https://github.com/ModernRelay/omnigraph). Every other cookbook in this repo (`industry-intel`, `gtm-for-infra`, `pharma-intel`) models a market, industry, or account list. This one models *the user's own knowledge* — notes, contacts, conversations, projects, decisions.

The cookbook owns three things:

1. **A spine schema** (`schema.pg`) — 16 typed nodes (15 user-content + `SyncRun` for sync state), ~45 edges. Domain-neutral. Add Health, Financing, Frames, etc. as overlays via `EXTENDING.md`.
2. **Eight raw importers** (`demo/import_*.py`) — Obsidian, Notion, Granola, Slack, Google Workspace, Apple Notes, LinkedIn CSV, WhatsApp chat export. Each emits rich JSONL.
3. **A transform** (`demo/transform.py`) — maps raw JSONL → schema-shaped JSONL ready for `omnigraph load --mode merge`. Per-source dispatch; one function per source.

Everything user-facing lives in the **skill** (`../skills/omnigraph-personal-knowledge/`). The cookbook is the substrate; the skill is the UX.

## First-contact onboarding

If the user has just opened this folder, route them based on intent:

1. **"How do I use this?"** → Tell them to invoke the skill: `claude` then `/omnigraph-personal-knowledge`. Stop.
2. **"How do I extend this?"** → Send them to `EXTENDING.md` (for schema overlays) or the skill's `references/extending.md` (for new source connectors).
3. **"What's the schema?"** → Send them to `schema.pg`. Optionally walk through the three rings (identity, activity, structure) — see `README.md`.
4. **"Run the demo"** → Stop. The skill does this. Don't run init/load directly from this folder unless the user explicitly asks for raw CLI.

## Conventions

- **Slug-as-key**, prefixed by type: `note-`, `person-`, `art-`, `conv-`, `event-`, `email-`, `ext-`, `sync-`, etc.
- **`createdAt` and `updatedAt`** on every user-content node.
- **Comments use `//`** in `.pg` and `.gq` files.
- **Section dividers** use the `═══════════` box-drawing line for visual scan.
- **Tags as `[String]?`** arrays — no separate `Topic` node.
- **Enums adopted from the reference Life Graph** stay verbatim (Person.relation, Event.kind, Place.kind, etc.). They're well-considered.
- **Idempotent imports**: every `import_*.py` produces stable IDs; every record either inserts new or upserts via `--mode merge`.

## When editing the cookbook

### Adding a new source connector

1. Pick a template based on auth model — see `../skills/omnigraph-personal-knowledge/references/extending.md`.
2. Build `demo/import_<source>.py`. Required interface: `--workspace-name`, `--out`, `--since`, plus source-specific flags.
3. Add a transform function in `transform.py`, register in `DISPATCH`.
4. Update enums in `schema.pg`: `Artifact.source`, `ExternalID.source`, `SyncRun.source`. Run via `omnigraph schema diff` on a branch — never apply directly to main.
5. Add the source to the multi-select prompt in `SKILL.md` Phase 2.1.
6. Document in `references/source-setup.md`.
7. Test against real data the user provides. **Never fabricate data.**

### Adding a domain overlay (schema-only)

Schema overlays live in `EXTENDING.md` as paste-in `.pg` snippets. Don't create new files for overlays — they go in the same `schema.pg` once the user picks them. Workflow:

1. User reads `EXTENDING.md`, picks an overlay (e.g. Health).
2. `omnigraph branch create --from main health-overlay`
3. Append the snippet to `schema.pg`.
4. `omnigraph schema apply --branch health-overlay` → review diff.
5. `omnigraph branch merge health-overlay --into main`.

### Editing existing types

- **Adding fields to existing nodes**: append, don't reorder. Existing seeds + user data stay valid.
- **Renaming or removing**: don't, except via a major version bump. Breaks seed + user data.
- **Adding edges**: stay in the same edges section by topic.

### Editing seed.jsonl

- Real-looking, fictional. The bundled seed uses persona "Alex Rivera". Stay in that universe.
- Coherent: pick a project, build artifacts/notes/people around it.
- Demonstrates cross-source identity — make sure there are at least 2-3 dedup candidates.

### Editing queries

- Queries are read by the skill (for headline / sync / mutations) and Claude (for user questions). NOT by end users.
- Every alias in `omnigraph.yaml` must point at a query that exists. Lint via `omnigraph query lint --schema ./schema.pg --query ./queries/*.gq` before committing.

## When to stop and ask the user

- **Before any `omnigraph schema apply`** — schema is shared state; review the diff.
- **Before importing more than ~1k records on first run** — Notion/Gmail in particular can pull large workspaces. Offer to scope or cap.
- **Before committing real personal data** to seed or fixtures. No real names, emails, messages.
- **Before changing the schema in a backwards-incompatible way** — propose a migration path.
- **Before adding a new cookbook** for an overlay that could fit in `EXTENDING.md`. Most don't justify a new cookbook.

## Roadmap (post-v1)

- **Hosted webhook receivers** for Notion + Slack + Calendar — push-based sync. Lives in a separate `omnigraph-sync-server` project, not this cookbook.
- **Embedding pipeline** — automatic Chunk extraction + embedding for semantic queries. Currently the schema has Chunk + `embedding: Vector(3072) @embed("text") @index` but no automated pipeline.
- **Bidirectional Slack/Notion** — write graph state back to source apps. Would need governance work + per-source write APIs.

## Out of scope (and that's fine)

- Webhooks (push sync) — separate project.
- Cross-skill orchestration ("wire this into morning-briefing") — emerges from Claude composing skills, not this cookbook.
- A web/visual graph explorer — that's `omnigraph-ui`'s problem.
- Per-source bidirectional write — write-back is a different cookbook, if at all.
