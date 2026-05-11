---
name: omnigraph-personal-knowledge
description: 'Bootstrap and maintain a personal knowledge graph (second brain) on Omnigraph. Pulls notes, contacts, conversations, calendar, and meeting transcripts from Obsidian, Notion, Granola, Slack, Google Workspace (Drive/Gmail/Calendar), Apple Notes, LinkedIn (CSV export), and WhatsApp (chat export) into one governed graph the user controls. Handles first-time setup with a demo path, source-by-source connect path, idempotent imports with --since incremental sync, an identity-resolution wizard for cross-source person dedup, and an auto-run headline report after every load. The skill composes fetch + map code per source by reading the spec docs in references/sources/; no pre-written Python ships with the cookbook. Use this skill any time the user wants to set up, refresh, query, or extend their personal knowledge graph in Omnigraph.'
---

# omnigraph-personal-knowledge

The user-facing surface for the `personal-knowledge` cookbook in `omnigraph-cookbooks`. The cookbook ships the schema, queries, source specs, and seed. **No pre-written Python code ships with the cookbook** — the agent reads the per-source specs and composes fetch + map code inline each session.

> **First principle**: the user interacts with their graph through Claude. They never need to learn `.gq` syntax. When they ask a question, you compose a query against the schema; you don't push them at a query language.
>
> **Second principle**: when you import data, you compose the fetch + map code yourself, reading `references/sources/<source>.md` for what to fetch and how to map it. The spec is precise where it matters (our domain — slugs, mapping, idempotency) and semantic where the source API may drift (endpoints, field paths — link to live docs).

## When to invoke

- "Set up my personal knowledge graph" / "graph my second brain" / "import my Notion (or Obsidian, Slack, etc.) into Omnigraph"
- "Sync my personal-knowledge graph" / "pull in updates from <source>"
- "Show me what's in my graph" / "who do I talk to most" / similar exploratory questions about an existing PK graph
- Any time the user references the `personal-knowledge/` cookbook directly

If the user is on `omnigraph-cookbooks/personal-knowledge/` but their intent is editorial (changing `schema.pg`, adding a new source spec), route them to the cookbook's `AGENTS.md` instead — that's the editor's contract; this is the user's contract.

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

Goal: graph populated and headline report on screen in under 30 seconds. No source spec involved — just init + load + read.

```bash
REPO=/tmp/personal-knowledge/repo
omnigraph init   --schema ./schema.pg "$REPO"
omnigraph load   --data ./seed.jsonl --mode overwrite "$REPO"
omnigraph-server --bind 127.0.0.1:8080 "$REPO" >/tmp/pk-server.log 2>&1 &
sleep 1
```

Then **run the headline report** (see `references/headline-report.md`) and present its 5 numbers with one observation. Offer 3 follow-up queries the user can ask Claude to run next.

Demo data is fictional. When the user is ready to connect their own apps, route to Phase 2 against a fresh repo.

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

Honor the selection: only walk through setup for what they picked. Skipping any source is fully supported.

### Step 2.2 — per-source setup + composition

For each selected source, **one source at a time**:

1. Read `references/sources/<source>.md`. This is the source-specific spec the agent needs to compose precise fetch + map code.
2. Execute the **Auth + setup ritual** section of that doc — browser deep-links, token capture, validation round-trips, `keyring` persistence. The doc carries the per-source detail.
3. Compose the fetch code inline (using the doc's *Fetch intent* + *Field extraction intent* + linked authoritative-reference URLs if the API has drifted). Run it. Capture raw records in memory.
4. Compose the map code inline (using the doc's *Mapping* + *Slug derivation* sections). Convert raw records to schema-shaped node + edge records.
5. Apply `references/loading-rules.md` cross-cutting rules (dedupe-within-run, dangling-edge filtering, stable-ID enforcement, SyncRun emission).
6. Run `omnigraph init --schema ./schema.pg "$REPO"` if the repo doesn't exist yet, then `omnigraph load --mode merge --data <patch.jsonl> "$REPO"`.

While the fetch runs (Notion's a 50-page workspace can take 30s; Slack's a 200-message channel 20s), **narrate to the user**. Don't sit on a silent prompt — read `schema.pg` aloud, explain the node types they're about to see, surface progress as it streams.

### Step 2.3 — headline report

After all selected sources have loaded, **always** run the headline report (`references/headline-report.md`). It's the payoff moment.

### Step 2.4 — identity-resolution wizard

If the user connected more than one source, propose the dedup wizard (`references/identity-resolution.md`). Skip if only one source connected — there's nothing to merge.

### Step 2.5 — what-next

Offer 3-5 follow-up queries Claude can run on demand, picked per `references/headline-report.md`'s follow-up rules.

## Phase 3 — exploratory queries (existing graph)

When the user asks a natural-language question about their graph:

1. Read `schema.pg` (cached from previous loads in this conversation).
2. Compose a `.gq` query against the schema. Prefer adding a one-off query inline; if it's the kind of question they'll ask repeatedly, offer to save it as an alias in `omnigraph.yaml`.
3. For queries about a person, apply the SameAs-aware traversal per `references/identity-resolution.md` — resolve the closure, run the alias for each aliased slug, union.
4. Run it via `omnigraph read`.
5. Format the result for the user — never dump raw JSON unless they ask for it.
6. Suggest a follow-up.

## Phase 4 — sync (refresh existing graph)

The user invokes you with "sync my graph" or "pull in new stuff." Steps:

1. For each connected source: query `last_sync_for_source <source> succeeded` via the `last-sync` alias. Take the `completed_at` as the `--since` value.
2. For each source, re-read `references/sources/<source>.md`, re-compose fetch + map code with the `--since` filter applied (per the source's *Idempotency + `--since`* section).
3. Apply `references/loading-rules.md` cross-cutting rules.
4. Run `omnigraph load --mode merge` with the new patch.
5. Run a slim headline-delta report ("X new notes since last sync, Y new artifacts, Z new persons") instead of the full one. See `references/sync.md`.

If a source has never synced, treat as first-run for that source (no `--since`).

## Phase 5 — extending

**Adding a new source** the user mentions (Day One, Roam, Mem, etc.):

1. Read an existing similar source's spec doc as a structural template (`references/sources/obsidian.md` for file-walk sources, `notion.md` for API-token sources, `slack.md` for OAuth-app sources, `linkedin.md` for CSV-export sources, `whatsapp.md` for text-export sources).
2. Draft a new `references/sources/<new_source>.md` following the same shape: About, Authoritative reference, Auth + setup ritual, Fetch intent, Field extraction intent, Mapping (raw → schema), Slug derivation, Idempotency + `--since`, Known quirks, Sample I/O.
3. Compose fetch + map code per the new spec. Run end-to-end against the user's real data.
4. If the source's data needs new enum values (e.g., `Artifact.source: <new_source>`), schedule a schema overlay (see `references/extending.md`).

**Adding a domain overlay** (Health, Financing, Inspiration, Frames):

- See the cookbook's `EXTENDING.md`. Paste the relevant `.pg` snippet into `schema.pg` on a branch, run `omnigraph schema diff` + `omnigraph schema apply --branch <slug>`. Each overlay is self-contained.

## Conventions

- **Zero pre-written Python in the cookbook.** The agent composes fetch + map code per session, reading source specs.
- **Idempotent imports**: every emit + load combination is safe to re-run. Stable IDs guarantee `omnigraph load --mode merge` upserts cleanly.
- **Credentials in keyring**: paste once, ever. `keyring set omnigraph-pk <source>-token`.
- **No raw JSON dumps to the user.** Always present query results as structured prose, tables, or named lists.
- **No teaching `.gq`** unless the user asks. They interact through you.
- **Real seed only**: never invent fake personal data and load it into the user's actual graph. The bundled `seed.jsonl` is for demo mode only and uses a fictional persona ("Alex Rivera").
- **One-source-at-a-time setup**: even if the user picked 8 sources, walk through them one by one. Don't AskUserQuestion 8 tokens upfront.
- **When in doubt about a source's current API surface**, fetch the authoritative-reference URLs listed in that source's spec doc. The specs are stable on our domain (slugs, mapping); semantic where the source's API may drift.

## Common failure modes — handle gracefully

- **Bad credential**: validation round-trip fails. Re-prompt with the specific error. Don't proceed to fetch on a bad token.
- **Empty source**: fetch returns zero records. That's fine, not an error. Note it in the summary.
- **`omnigraph` CLI missing**: explain `brew install ModernRelay/tap/omnigraph` and stop.
- **Schema drift**: if the cookbook's `schema.pg` doesn't match what's loaded in the graph, run `omnigraph schema plan` and offer to apply on a branch.
- **Rate limit (Slack, Google, Notion)**: throttle and back off on 429s per each source's spec. Don't panic if a long run pauses for 30s.
- **Source API has drifted**: a source spec doc's example call doesn't match current behavior. Fetch the authoritative-reference URLs at the top of that spec doc, identify what changed, adapt the code.

## References

- `references/sources/<source>.md` — per-source spec (Notion, Obsidian, Granola, Slack, Google Workspace, Apple Notes, LinkedIn, WhatsApp). Read the relevant one before composing fetch + map code for that source.
- `references/loading-rules.md` — cross-cutting rules: dedupe-within-run, dangling-edge filtering, SyncRun emission, stable-ID enforcement
- `references/headline-report.md` — the 5-numbers playbook + follow-up rules
- `references/identity-resolution.md` — the dedup walkthrough + SameAs-aware traversal pattern
- `references/sync.md` — incremental-sync contract
- `references/extending.md` — adding a new source spec or domain overlay
