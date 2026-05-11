# AGENTS.md — personal-knowledge

Single source of agent context for the `personal-knowledge` cookbook — design rationale, editing conventions, routing rules, and the moments where you should stop and ask the user.

User-facing onboarding lives in the [`omnigraph-personal-knowledge`](../skills/omnigraph-personal-knowledge/SKILL.md) skill, not here. This file is for editors and any agent that arrives at the folder.

Read top to bottom on first contact, then jump to the section the user's intent maps to.

## About

`personal-knowledge` is the first inward-facing cookbook in [Omnigraph](https://github.com/ModernRelay/omnigraph). Every other cookbook in this repo (`industry-intel`, `gtm-for-infra`, `pharma-intel`) models a market, industry, or account list. This one models *the user's own knowledge* — notes, contacts, conversations, projects, decisions.

The cookbook owns three things:

1. **A spine schema** (`schema.pg`) — 16 typed nodes (15 user-content + `SyncRun` for sync state), ~45 edges. Domain-neutral. Add Health, Financing, Frames, etc. as overlays via `EXTENDING.md`.
2. **A skill** (`../skills/omnigraph-personal-knowledge/`) — the user-facing orchestration. Reads per-source specs (`references/sources/*.md`), composes fetch + map code inline per session, runs the headline report, walks the dedup wizard.
3. **A demo seed** (`seed.md`, `seed.jsonl`) — fictional persona "Alex Rivera" for users who want to play with the graph shape before connecting their own apps.

**There is no pre-written Python code** in this cookbook. The agent composes fetch + map code each session from the per-source spec docs. This is deliberate — see the README's "The pipeline" section for the reasoning.

## First-contact onboarding

If the user has just opened this folder, route them based on intent:

1. **"How do I use this?"** → Tell them to invoke the skill: `claude` then `/omnigraph-personal-knowledge`. Stop.
2. **"How do I extend this?"** → Send them to `EXTENDING.md` (for schema overlays) or the skill's `references/extending.md` (for adding a new source spec).
3. **"What's the schema?"** → Send them to `schema.pg`. Optionally walk through the three rings (identity, activity, structure) — see `README.md`.
4. **"Run the demo"** → Stop. The skill does this. Don't run init/load directly from this folder unless the user explicitly asks for raw CLI against the bundled seed.

## Conventions

- **Slug-as-key**, prefixed by type: `note-`, `person-`, `art-`, `conv-`, `event-`, `email-`, `ext-`, `sync-`, etc.
- **`createdAt` and `updatedAt`** on every user-content node.
- **Comments use `//`** in `.pg` and `.gq` files.
- **Section dividers** use the `═══════════` box-drawing line for visual scan.
- **Tags as `[String]?`** arrays — no separate `Topic` node.
- **Enums adopted from the reference Life Graph** stay verbatim (`Person.relation`, `Event.kind`, `Place.kind`, etc.). They're well-considered.
- **Idempotent imports**: the per-source specs define stable-ID algorithms. The agent's composed code emits stable IDs; `--mode merge` upserts cleanly on re-run.
- **No pre-written importers.** Don't introduce Python (or any language's) ingestion code into the cookbook. Specs describe the contract; the agent composes code per session.

## When editing the cookbook

### Adding a new source spec

User says they also use Day One / Roam / Mem / Reflect / etc.

1. Pick the closest existing source spec as a structural template:
   - File-on-disk source → mirror `references/sources/obsidian.md`
   - API + token source → mirror `references/sources/notion.md`
   - OAuth-app source → mirror `references/sources/slack.md` or `references/sources/google-workspace.md`
   - CSV-export source → mirror `references/sources/linkedin.md`
   - Text-log-export source → mirror `references/sources/whatsapp.md`
2. Draft `references/sources/<new_source>.md` with the standard 10-section shape: About, Authoritative reference, Auth + setup ritual, Fetch intent, Field extraction intent, Mapping (raw → schema), Slug derivation, Idempotency + `--since`, Known quirks, Sample I/O.
3. Update enums in `schema.pg`: `Artifact.source`, `ExternalID.source`, `SyncRun.source`, optionally `Conversation.source`. Apply via `omnigraph schema apply --schema schema-with-new-source.pg` on a branch — never directly to main.
4. Add the source to the multi-select prompt in `SKILL.md` Phase 2.1.
5. Test against real data the user provides. **Never fabricate data.**

For source-spec authoring guidance in depth, see `../skills/omnigraph-personal-knowledge/references/extending.md`.

### Adding a domain overlay (schema-only)

Domain overlays (Health, Financing, Inspiration, Frames) live in `EXTENDING.md` as paste-in `.pg` snippets. Workflow:

1. User reads `EXTENDING.md`, picks an overlay.
2. `omnigraph branch create --from main <overlay>-overlay`
3. Append the snippet to `schema.pg`.
4. `omnigraph schema apply --schema schema-with-overlay.pg` → review on the branch.
5. `omnigraph branch merge <overlay>-overlay --into main`.

### Editing existing types

- **Adding fields to existing nodes**: append, don't reorder. Existing seeds + user data stay valid.
- **Renaming or removing**: don't, except via a major version bump. Breaks seed + user data.
- **Adding edges**: stay in the same edges section by topic.

### Editing seed.jsonl

- Real-looking, fictional. The bundled seed uses persona "Alex Rivera". Stay in that universe.
- Coherent: pick a project, build artifacts/notes/people around it.
- Demonstrates cross-source identity — make sure there are at least 2-3 dedup candidates so the wizard has something to do on the demo path.

### Editing queries

- Queries are read by the skill (for headline / sync / mutations) and Claude (for user questions). NOT by end users.
- Every alias in `omnigraph.yaml` must point at a query that exists. Lint via `omnigraph query lint --schema ./schema.pg --query ./queries/*.gq` before committing.

## When to stop and ask the user

- **Before any `omnigraph schema apply`** — schema is shared state; review the diff.
- **Before importing more than ~1k records on first run** — Notion / Gmail in particular can pull large workspaces. Offer to scope or cap.
- **Before committing real personal data** to seed or fixtures. No real names, emails, messages.
- **Before changing the schema in a backwards-incompatible way** — propose a migration path.
- **Before adding a new cookbook** for an overlay that could fit in `EXTENDING.md`. Most don't justify a new cookbook.

## Roadmap (post-v1)

- **Hosted webhook receivers** for Notion + Slack + Calendar — push-based sync. Lives in a separate `omnigraph-sync-server` project, not this cookbook.
- **Embedding pipeline** — automatic Chunk extraction + embedding for semantic queries. Currently the schema has `Chunk.embedding: Vector(3072) @embed("text") @index` but no automated pipeline.
- **Bidirectional Slack/Notion** — write graph state back to source apps. Would need governance work + per-source write APIs.

## Out of scope (and that's fine)

- Webhooks (push sync) — separate project.
- Cross-skill orchestration ("wire this into morning-briefing") — emerges from Claude composing skills, not this cookbook.
- A web/visual graph explorer — that's `omnigraph-ui`'s problem.
- Per-source bidirectional write — write-back is a different cookbook, if at all.
- Pre-written importer scripts — explicitly out by design. Specs > scripts.
