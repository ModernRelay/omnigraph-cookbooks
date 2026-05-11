# Loading rules — cross-source concerns

Rules the agent applies when stitching per-source records into a final patch ready for `omnigraph load --mode merge`. Apply uniformly regardless of which sources contributed.

The per-source spec docs (`sources/*.md`) tell the agent *what* records to emit. This doc tells the agent *how to combine them* before loading.

## Rule 1 — Dedupe nodes within a single run

A single import session may emit the same node multiple times. Examples:

- Slack: 50 messages from the same channel emit 50 Conversation records with the same slug
- Notion: 30 pages mentioning the same user emit 30 Person records with the same slug
- Calendar: 10 events with the same attendee emit 10 Person records with the same slug

Collapse these. Group emitted nodes by `(type, slug)`. When a collision is found:

- Keep one record per `(type, slug)` pair
- Among colliding records, prefer the one with the most-recent `updatedAt` (or `timestamp` if `updatedAt` is absent)
- Discard the others

Why: the underlying graph store enforces slug uniqueness, but `omnigraph load --mode merge` interprets each emitted record as an upsert — multiple records with the same slug means multiple round-trip upserts, wasting work and risking stale-data wins.

Implementation hint: a single `dict[(type, slug), record]` accumulator solves this in linear time over the emitted record stream.

## Rule 2 — Dedupe edges within a single run

The same edge can be emitted N times when N artifacts share endpoints. Examples:

- ConversationWith from `conv-slack-abc` to `person-jorge` emitted 50 times (once per message Jorge sent in that channel)
- IdentifiesPerson from `ext-notion-xyz` to `person-jane` emitted 30 times (once per page mentioning Jane)
- ArtifactFromPerson for each message from the same sender — distinct artifacts, but the edge pattern repeats

Group emitted edges by `(edge_name, from, to, frozenset(data items))`. The `data` part matters: two `DerivedFromArtifact` edges between the same nodes with different `activity` values are legitimately different and shouldn't be collapsed. But identical-payload edges should.

Keep the first emission; discard repeats.

## Rule 3 — Drop dangling `LinkedNote` edges

`LinkedNote` is emitted speculatively for every wiki-link, page-mention, or `@-link` the source contains. The target Note may not exist in this run (the user has a wiki-link to a note they never created, or the integration doesn't have access to the linked page).

Filter pass:

- Collect every Note slug that the patch emits, including from this and prior runs
- For each `LinkedNote` edge candidate, check whether the `to` slug is in that set
- Drop edges whose target is absent

This prevents `omnigraph load` from failing on `edge LinkedNote row N: dst not found in Note` errors, which abort the whole load atomically.

Implementation hint: two passes over the emitted records — first to collect Note slugs, second to filter LinkedNote edges. The agent can also query the live graph for existing Note slugs if it wants to preserve LinkedNote edges that point to previously-loaded Notes from other sessions.

## Rule 4 — Stable IDs everywhere

Every node slug must be **deterministic from source-native identifiers**. Same source + same input on a re-run produces the same slug. This makes `omnigraph load --mode merge` idempotent: re-running an import upserts existing records rather than creating duplicates.

The per-source docs (`sources/*.md`) define each slug pattern. Verify before emitting:

- No `uuid.uuid4()` or random suffixes
- Hashes are derived from source-native identifiers (page_id, file path, message ts, etc.) — not from timestamps of the current run
- Email-based slugs normalize the email first (lowercase, trim, strip dots/plus-tags in local part if you want collision behavior)

If a record genuinely doesn't have a stable identifier (rare), prefer skipping it over emitting an unstable slug. Random slugs poison the graph — each re-run creates a new duplicate Person/Artifact.

## Rule 5 — Required fields on every node

Every node emitted needs these fields populated:

- `slug` — required, the @key
- `createdAt` — ISO datetime
- `updatedAt` — ISO datetime, ≥ `createdAt`

Per-node-type required fields per `../../personal-knowledge/schema.pg`. If the source doesn't provide a timestamp, fall back to the run's start time — `updatedAt` shouldn't be more recent than now, but it shouldn't be empty either.

## Rule 6 — Emit a `SyncRun` per import

Every import session ends with a `SyncRun` record:

```
SyncRun:
  slug:        sync-<source>-<8-hex-of-sha256(source + started_at)>
  source:      <source>     # one of the Artifact.source enum values, or "manual" if mixed
  started_at:  <run start ISO>
  completed_at: <run end ISO>
  status:      succeeded | partial | failed
  records_imported: <count>
  error:       <error summary if status != succeeded>
  createdAt:   <run end ISO>
  updatedAt:   <run end ISO>
```

For `--since` lookups on subsequent runs, the skill queries `omnigraph read --alias last-sync <source> succeeded` and uses `completed_at` as the `since` value.

If the import imported from multiple sources in one run (rare — typically the skill runs one source at a time), emit one `SyncRun` per source.

## Rule 7 — Streaming vs batched loading

For graphs <100k records (typical personal-knowledge scale), batch the entire patch into one JSONL file and call `omnigraph load --mode merge --data patch.jsonl <repo>` once.

For larger imports (rare), the agent can stream into `omnigraph load --mode merge --data - <repo>` via stdin. Either way: a single `omnigraph load` invocation per source's patch is the convention.

Don't fragment one source's records across multiple load calls — atomicity is per-load, and partial failures are harder to reason about across multiple invocations.

## Rule 8 — Error handling per record

If parsing a single source record fails (malformed CSV row, unparseable Notion block, etc.):

- Log to stderr with the source identifier and the parse-error type
- Continue with the next record
- Don't abort the whole import on a single bad record

If the load itself fails (constraint violation, schema mismatch, network), surface the error to the user with the offending record's slug. Common case: a slug pattern produced a value that violates a schema constraint — fix and re-run.

## Rule 9 — Don't emit records for the user themselves as a Person

The user is the implicit subject of their personal knowledge graph; we don't model them as a Person node (they ARE the graph).

When emitting Person records from message senders, calendar attendees, etc., the agent should:

- Recognize the user's own email / handle (collected at setup time per source)
- Skip emitting a Person for that identity
- Still emit edges that would have pointed at the user (e.g. `EmailToPerson` for emails to a colleague) — only the user's own self-Person is suppressed

If the agent can't tell which identity is the user's, default to emitting all senders as Persons and let the dedup wizard sort it out.

## Quick-reference checklist

Before calling `omnigraph load --mode merge`, the agent's patch must satisfy:

- [ ] Every node has a stable slug, `createdAt`, `updatedAt`
- [ ] No duplicate `(type, slug)` pairs — collapsed to single emissions
- [ ] No duplicate `(edge, from, to, data)` quadruples — collapsed
- [ ] No `LinkedNote` edges pointing at slugs absent from the patch (and from the live graph, if checked)
- [ ] A single `SyncRun` per source at the end
- [ ] No Person record for the user themselves

If any check fails, fix in the in-memory accumulator before serializing to JSONL.
