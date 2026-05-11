---
name: omnigraph-personal-knowledge
description: 'Bootstrap and maintain a personal knowledge graph (second brain) on Omnigraph. Pulls notes, contacts, conversations, calendar, and meeting transcripts from Obsidian, Notion, Granola, Slack, Google Workspace (Drive/Gmail/Calendar), Apple Notes, LinkedIn (CSV export), and WhatsApp (chat export) into one governed graph the user controls. Handles first-time setup with a demo path, source-by-source connect path, idempotent imports with --since incremental sync, an identity-resolution wizard for cross-source person dedup, and an auto-run headline report after every load. Use this skill any time the user wants to set up, refresh, query, or extend their personal knowledge graph in Omnigraph.'
---

# omnigraph-personal-knowledge

The user-facing surface for the `personal-knowledge` cookbook in `omnigraph-cookbooks`. The cookbook ships the schema, queries, importers, and seed; this skill orchestrates everything end-to-end so the user never types more than one or two commands.

> **First principle**: the user interacts with their graph through Claude. They never need to learn `.gq` syntax. When they ask a question, you compose a query against the schema; you don't push them at a query language.

## When to invoke

- "Set up my personal knowledge graph" / "graph my second brain" / "import my Notion (or Obsidian, Slack, etc.) into Omnigraph"
- "Sync my personal-knowledge graph" / "pull in updates from <source>"
- "Show me what's in my graph" / "who do I talk to most" / similar exploratory questions about an existing PK graph
- Any time the user references the `personal-knowledge/` cookbook directly

If the user is on `omnigraph-cookbooks/personal-knowledge/` but their intent is editorial (changing `schema.pg`, adding a new `import_*.py`), route them to the cookbook's `AGENTS.md` instead — that's the editor's contract; this is the user's contract.

## Phase 0 — first-contact branch

If the user has just opened the cookbook, or said something vague ("what is this?" / "help me with personal-knowledge"), ask once. If the answer is unambiguous already, skip the question and go to the matching phase.

```
AskUserQuestion:
  question: "How do you want to use your personal knowledge graph?"
  options:
    - "Try with sample data first (no credentials)"
    - "Connect my own apps now (I have ~5 minutes)"
```

- **Sample data** → Phase 1
- **Connect** → Phase 2

## Phase 1 — demo path (sample data, no credentials)

Goal: graph populated and headline report on screen in under 30 seconds.

```bash
REPO=/tmp/personal-knowledge/repo
omnigraph init   --schema ./schema.pg "$REPO"
omnigraph load   --data ./seed.jsonl --mode overwrite "$REPO"
omnigraph-server --bind 127.0.0.1:8080 "$REPO" >/tmp/pk-server.log 2>&1 &
sleep 1
```

Then **run the headline report** (see `references/headline-report.md`) and present its 5 numbers with brief commentary. Offer 3 follow-up queries the user can ask Claude to run next ("who do I mention most?", "what conversations span more than 30 days?", etc.).

Demo data is fictional. Make sure the user knows: when they're ready to connect their own apps, the next step is "switch to my own data" → Phase 2 against a fresh repo.

## Phase 2 — connect-real-sources path

### Step 2.1 — multi-select sources

```
AskUserQuestion (multiSelect: true):
  question: "Which apps do you want to connect? Pick any combination."
  options:
    - "Obsidian (vault on disk — no token)"
    - "Notion (free integration token)"
    - "Granola (API token or local export)"
    - "Slack (bot token; needs an app you create)"
    - "Google Workspace (Drive / Gmail / Calendar via OAuth)"
    - "Apple Notes (Mac only; AppleScript dump)"
    - "LinkedIn (CSV export — request from linkedin.com)"
    - "WhatsApp (chat export — Export Chat from the app)"
```

Honor the selection: only walk through setup for what they picked. Skipping any source is fully supported — pieces of the schema (Email, Conversation, etc.) just stay empty.

### Step 2.2 — per-source setup

For each selected source, follow the recipe in `references/source-setup.md`. Each recipe handles:
- One-line description of what the source provides
- Browser-deep-link to the credentials page (when applicable)
- AskUserQuestion to capture the token / path
- Validate immediately (1 round-trip API call or path-exists check) — fail fast on bad input
- Persist the credential via `keyring` (so re-runs don't re-prompt)

### Step 2.3 — init and import

```bash
REPO=s3://omnigraph-local/repos/personal-knowledge   # or a /tmp path for first-runners
omnigraph init --schema ./schema.pg "$REPO"

# For each connected source, run its importer. Use --since when a prior SyncRun
# exists (see Phase 4 / references/sync.md). On first run, --since is omitted.

python demo/import_obsidian.py --vault "$VAULT_PATH"     --workspace-name "$WORKSPACE" --out /tmp/raw-obsidian.jsonl
python demo/import_notion.py    --workspace-name "$WORKSPACE" --out /tmp/raw-notion.jsonl
# … one per connected source

# Stitch raw → schema-shaped:
python demo/transform.py /tmp/raw-*.jsonl --out /tmp/patch.jsonl

# Load into the graph:
omnigraph load --data /tmp/patch.jsonl --mode merge "$REPO"
```

While each importer runs, narrate to the user. Don't sit on a silent prompt — read `schema.pg` aloud, explain the node types they're about to see, surface progress as it streams.

### Step 2.4 — headline report

After load completes, **always** run the headline report (`references/headline-report.md`). It's the payoff moment.

### Step 2.5 — identity-resolution wizard

If the user connected more than one source, propose the dedup wizard (`references/identity-resolution.md`). Skip if only one source connected — there's nothing to merge.

### Step 2.6 — what-next

Offer 3-5 follow-up queries Claude can run on demand. Tie them to what the user has in their graph (e.g., "you have 4 active projects — want to see open tasks across them?").

## Phase 3 — exploratory queries (existing graph)

When the user asks a natural-language question about their graph:

1. Read `schema.pg` (cached from previous loads in this conversation).
2. Compose a `.gq` query against the schema. Prefer adding a one-off query inline; if it's the kind of question they'll ask repeatedly, offer to save it as an alias in `omnigraph.yaml`.
3. Run it via `omnigraph read`.
4. Format the result for the user — never dump raw JSON unless they ask for it.
5. Suggest a follow-up.

Example flow: user says "who have I been talking to about onboarding?" → you compose a query joining `Note.tags` containing "onboarding" with `NoteAboutPerson` → run → present a ranked list of 3-5 people with the note titles that mention them.

## Phase 4 — sync (refresh existing graph)

The user invokes you with "sync my graph" or "pull in new stuff." Steps:

1. For each connected source: query `last_sync_for_source($source)` via the `last-sync` alias. Take the `completed_at` as `--since`.
2. Run each importer with `--since $LAST_COMPLETED_AT`.
3. Run `transform.py`, then `omnigraph load --mode merge`.
4. The transform automatically appends a `SyncRun` record with the new timestamp.
5. Run a slim headline-delta report ("X new notes since last sync, Y new artifacts, Z new persons") instead of the full one.

If a source has never synced, treat as first-run for that source (no `--since`). See `references/sync.md` for the contract details.

## Phase 5 — extending

If the user says "I also use <X>" where X is a new source not in v1: read an existing `import_*.py` as a template, generate `import_<X>.py` matching the contract (rich raw JSONL, stable IDs, idempotent, optional `--since`), wire it into `transform.py`'s `DISPATCH`, document the credentials. Do not promise it works without testing on real data.

If the user wants to add domain-specific concepts (Health, Financing, Inspiration, Frames, etc.): see the cookbook's `EXTENDING.md` (in `personal-knowledge/`) — those are paste-in `.pg` snippets, NOT new files. Copy the relevant snippet into `schema.pg`, run `omnigraph schema apply` (after a `omnigraph branch create` so the user can review the diff before merging).

## Conventions

- **Idempotent imports**: every importer + transform combination is safe to re-run. Stable IDs guarantee `omnigraph load --mode merge` upserts cleanly.
- **Credentials in keyring**: paste once, ever. `keyring set omnigraph-pk <source>-token` (Python `keyring` lib).
- **No raw JSON dumps to the user**. Always present query results as structured prose, tables, or named lists.
- **No teaching `.gq`** unless the user asks. They interact through you.
- **Real seed only**: never invent fake personal data and load it into the user's actual graph. The bundled `seed.jsonl` is for demo mode only and uses a fictional persona ("Alex Rivera").
- **One-source-at-a-time setup**: even if the user picked 8 sources, walk through them one by one. Don't AskUserQuestion 8 tokens upfront — that's the worst version of this UX.

## Common failure modes — handle gracefully

- **Bad credential**: importer's validation step fails. Re-prompt with the specific error. Don't proceed to import on a bad token.
- **Empty source**: importer emits zero records. That's fine, not an error. Note it in the summary.
- **`omnigraph` CLI missing**: explain `brew install ModernRelay/tap/omnigraph` and stop.
- **Schema drift**: if the cookbook's `schema.pg` doesn't match what's loaded in the graph, run `omnigraph schema diff` and offer to apply on a branch.
- **Rate limit (Slack, Google)**: importers self-throttle and retry; don't panic if a long run pauses for 30s.

## References

- `references/source-setup.md` — per-source token rituals + validation
- `references/headline-report.md` — the 5-numbers playbook
- `references/identity-resolution.md` — the dedup walkthrough
- `references/sync.md` — incremental-sync contract
- `references/extending.md` — adding a new source or domain
