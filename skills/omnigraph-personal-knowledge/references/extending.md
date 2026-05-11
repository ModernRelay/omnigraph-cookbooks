# Extending — new sources and new domains

Two distinct kinds of extension. Different shapes.

## Adding a new source spec

User says "I also use Day One / Roam / Mem / Reflect / etc."

The cookbook ships no pre-written importer code; each source is a spec doc the agent reads + composes fetch + map code from. To add a new source, draft a new spec that follows the established shape.

### 1. Pick a template

Match the new source's data-access pattern to the closest existing spec:

| Access pattern | Template to mirror |
|---|---|
| File on disk (Markdown vault, plain-text notes) | `sources/obsidian.md` |
| API + integration token (REST + Bearer auth) | `sources/notion.md` |
| OAuth-app with workspace-scoped scopes | `sources/slack.md` |
| OAuth (Google-style, multi-API) | `sources/google-workspace.md` |
| Native OS scripting (AppleScript / Win COM) | `sources/apple-notes.md` |
| CSV / structured export (LinkedIn-style) | `sources/linkedin.md` |
| Text-log export (chat-style) | `sources/whatsapp.md` |

### 2. Draft `sources/<new_source>.md` with the standard 10-section shape

1. **About** — one paragraph: what the source is, when to use it
2. **Authoritative reference** — links to the source's live API / format docs. The agent fetches these when the spec doesn't match observed behavior (drift handling)
3. **Auth + setup ritual** — what the user does to grant access (token, OAuth, file export, etc.); numbered steps the skill executes; persistence via `keyring` if applicable
4. **Fetch intent** — what data the agent needs (semantic), not specific endpoints. Time-filtering for `--since`
5. **Field extraction intent** — what we want + where the source typically carries it (table form). Loose on source-side syntax (link to docs), tight on intent
6. **Mapping (raw → schema)** — per source record, which graph nodes + edges to emit. Use a concrete block format showing exact field shape. **This is OUR domain — keep detailed.**
7. **Slug derivation** — exact algorithms for each slug pattern (sha256 inputs, prefix conventions). **Stable; never changes.**
8. **Idempotency + `--since`** — re-run behavior, last-sync alias usage, source-specific filter mechanics
9. **Known semi-stable quirks** — the gotchas that have surprised every integrator (rate limit handling, encrypted bodies, locale-specific date formats, etc.)
10. **Sample I/O** — 1 raw record → the schema-shaped records it produces. Anchors the agent's code generation

Target length: 150-220 lines. Tight enough that the agent's generated code is precise; loose enough on the source-API side that drift doesn't break the spec.

### 3. Update schema enums

Add the source's identifier to:

- `Artifact.source` enum
- `ExternalID.source` enum
- `SyncRun.source` enum
- `Conversation.source` enum (if this source produces conversations)

Apply schema changes on a branch:

```bash
omnigraph branch create --from main <new-source>-source-overlay $REPO
# concatenate the new enum value into schema.pg
omnigraph schema apply --schema ./schema.pg --target <new-source>-source-overlay $REPO
# verify, then merge
omnigraph branch merge <new-source>-source-overlay --into main $REPO
```

### 4. Wire into `SKILL.md`

Add the source to the Phase 2.1 multi-select prompt. The skill orchestration in Phase 2.2 will pick it up automatically — there's no per-source dispatch table to update because there's no Python.

### 5. Test against real data

The user provides their own data (vault path, token, export file). The agent composes fetch + map code from the new spec doc and runs end-to-end. Iterate on the spec until the output is clean.

**Never fabricate data to test with.** If the user can't provide real data yet, the spec is unvalidated — mark it as such in the spec's About section.

## Adding a domain overlay (Health, Financing, Inspiration, Frames)

User says "I want to track my labs / fundraise / sales positioning / inspiration boards in this graph."

Domain overlays are not new sources — they're **schema-only** extensions that add specialized node types and edges on top of the spine. The cookbook ships `EXTENDING.md` (in `personal-knowledge/`) with paste-in snippets sourced from the reference Life Graph ontology.

Steps:

1. Read `personal-knowledge/EXTENDING.md`. Find the section matching the domain.
2. Create a branch: `omnigraph branch create --from main <slug>-overlay`.
3. Append the snippet to `schema.pg` (don't replace; append after the spine sections).
4. Apply on the branch: `omnigraph schema apply --schema ./schema-with-overlay.pg --target <slug>-overlay $REPO`. Review with the user.
5. If the overlay needs new mutations or queries, add them under `queries/<overlay>.gq` and aliases in `omnigraph.yaml`. Don't edit existing files unless the overlay genuinely re-uses them.
6. Once user confirms it looks right: `omnigraph branch merge <slug>-overlay --into main $REPO`.

The bundled overlays in `EXTENDING.md`:

- **Health** — HealthRecord, Measurable, Measurement, Condition, ConditionOccurrence, ClinicalStatement, HealthHypothesis, Intervention. Good for tracking labs and clinical visits.
- **Financing** — FinancingRound, FinancingInstrument, InvestorProfile. For founders raising or angels investing.
- **Inspiration & Interest** — Inspiration, Interest curation overlays. Useful for taste/gift memory/aesthetic libraries.
- **Frames & Personas** — AudiencePersona, PositioningFrame, NarrativeFrame, WritingStyle. For sales/positioning/content work.

Each is fully self-contained (its own nodes + edges, references types from the spine but doesn't modify them). User can add any subset.

## What NOT to do when extending

- **Don't introduce executable code into the cookbook.** Sources are specs (Markdown), not scripts. The agent composes code per session.
- **Don't delete or rename existing nodes/edges.** Always append.
- **Don't bypass the branch workflow.** Schema changes go through `branch create → schema apply → branch merge`.
- **Don't stuff source-specific connector logic into the spine schema.** The spine stays domain-neutral; per-source concerns live in the source spec docs.
- **Don't add a domain overlay AS A NEW COOKBOOK.** Overlays live in this same cookbook's `EXTENDING.md`. Only spin up a separate cookbook (e.g. `personal-knowledge-health`) if the overlay is large enough to justify its own seed + queries + skill.
