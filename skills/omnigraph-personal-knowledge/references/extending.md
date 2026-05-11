# Extending — new sources and new domains

Two distinct kinds of extension. Different shapes.

## Adding a new source connector

User says "I also use Day One" / Roam / Mem / Reflect / etc.

1. Pick the closest existing importer as a template:
   - **File-based source** (Markdown vault, JSON export, etc.) → mirror `import_obsidian.py`
   - **API-based source with token** → mirror `import_notion.py`
   - **API-based source with OAuth** → mirror `import_google_workspace.py`
   - **CSV export** (LinkedIn-style) → mirror `import_linkedin.py`
   - **Text-log export** (chat-style) → mirror `import_whatsapp.py`

2. Build `personal-knowledge/demo/import_<source>.py`. Required interface:
   - `--workspace-name <name>` (required)
   - `--out <path>` (default stdout)
   - `--since <iso>` (optional; respect if the source allows it; ignore if not)
   - Plus source-specific flags (`--vault`, `--input`, `--export-dir`, etc.)
   - Emits one rich raw JSON object per record per line, with at minimum: `_source`, `_source_format`, `id` (stable), `workspace_name`, `title`, plus whatever else the source naturally provides.
   - Stable `id` is non-negotiable. Re-running with the same input must produce the same `id`. Hash a source-native identifier when needed.
   - Exit 0 on success, 1 on argument/auth/network error.
   - `if __name__ == "__main__": sys.exit(main())` at the bottom — don't forget.

3. Add a transform function in `transform.py` and register it in `DISPATCH`. Decide what schema-shaped records each raw record yields:
   - Almost always: 1 `Artifact` + 1 `ExternalID`.
   - Often: 1 `Note` derived via `NoteFromArtifact`.
   - Sometimes: `Person`(s) extracted from mentions/authors, with `IdentifiesPerson` edges.
   - Source-specific: `Conversation` for messaging sources, `Event` for calendar/meeting sources, `Email` for email sources.

4. Add the source value to the relevant enums in `schema.pg`:
   - `Artifact.source`
   - `ExternalID.source`
   - `Conversation.source` (if applicable)
   - `SyncRun.source`
   Run `omnigraph schema diff` and apply on a branch — schema changes are not applied directly to `main`.

5. Document the credentials/setup in a new section of `references/source-setup.md`.

6. Add the source to the multi-select prompt in `SKILL.md` Phase 2.1.

7. Test against real data the user provides. **Never invent data** to test with.

## Adding a domain overlay (Health, Financing, Inspiration, Frames)

User says "I want to track my labs / fundraise / sales positioning / inspiration boards in this graph."

Domain overlays are not new connectors — they're **schema-only** extensions that add specialized node types and edges on top of the spine. The cookbook ships `EXTENDING.md` (in `personal-knowledge/`) with paste-in snippets sourced from the reference Life Graph ontology.

Steps:

1. Read `personal-knowledge/EXTENDING.md`. Find the section matching the domain.
2. Create a branch in the user's graph: `omnigraph branch create --from main <slug>-overlay`.
3. Append the snippet to `schema.pg` (don't replace; append to the right section).
4. Run `omnigraph schema diff` — review the additions with the user.
5. Run `omnigraph schema apply --branch <slug>-overlay`.
6. If the overlay needs new mutations or queries, add them under `queries/<overlay>.gq` and aliases in `omnigraph.yaml`. Don't edit existing files unless the overlay genuinely re-uses them.
7. Once user confirms it looks right: `omnigraph branch merge <slug>-overlay --into main`.

The bundled overlays in `EXTENDING.md`:

- **Health** — HealthRecord, Measurable, Measurement, Condition, ConditionOccurrence, ClinicalStatement, HealthHypothesis, Intervention. Good for tracking labs and clinical visits.
- **Financing** — FinancingRound, FinancingInstrument, InvestorProfile. For founders raising or angels investing.
- **Inspiration & Interest** — Inspiration, Interest curation overlays. Useful for taste/gift memory/aesthetic libraries.
- **Frames & Personas** — AudiencePersona, PositioningFrame, NarrativeFrame, WritingStyle. For sales/positioning/content work.

Each is fully-self-contained (its own nodes + edges, references types from the spine but doesn't modify them). User can add any subset.

## What NOT to do when extending

- Don't delete or rename existing nodes/edges. Always append.
- Don't bypass the branch workflow. Schema changes go through `branch create → diff → apply → merge`.
- Don't stuff source-specific connector logic into the spine schema. The spine stays domain-neutral.
- Don't add a domain overlay AS A NEW COOKBOOK. Overlays live in this same cookbook's `EXTENDING.md`. Only spin up a separate cookbook (e.g. `personal-knowledge-health`) if the overlay is large enough to justify its own seed + queries + skill.
