# Source: Granola

Spec for ingesting Granola meeting notes into the personal-knowledge graph. The agent reads this doc + `../loading-rules.md` + `../identity-resolution.md` and composes the fetch + map code per session.

## About

Granola is a meeting-notes app that records and transcribes meetings, producing structured notes with attendee lists, transcripts, and summaries. Two ingestion modes are supported:

- **API mode**: the user has a Granola API token; the agent calls Granola's API directly.
- **Local export mode**: the user has a Granola JSON export on disk.

Use Granola when the user has meeting transcripts they want anchored to Events + attendees in the graph.

## Authoritative reference

Granola's public API surface evolves; the agent should treat these as the source of truth:

- Granola docs landing — https://docs.granola.ai (or https://www.granola.ai/docs)
- Granola API reference — fetch from the docs landing
- `granola-to-graph` skill (the user's installed skill) — check installed skills for current endpoint shape if API mode

When the spec below doesn't match observed behavior, fetch the docs and adapt. The mapping intent is stable; the API surface may drift.

## Auth + setup ritual

**API mode**:

1. Ask the user if they have a Granola API token. If yes, capture it.
2. Optionally let them set `GRANOLA_API_BASE` (default `https://api.granola.so` or whatever the docs currently specify).
3. Validate by hitting the meetings/notes listing endpoint with `page_size=1`. 200 → valid; 401 → bad token; surface other errors.
4. Persist via `keyring` under service `omnigraph-pk`, key `granola-token`.

**Local export mode**:

1. Ask the user for the path to their Granola JSON export.
2. Validate that the file exists, parses as JSON, and contains a top-level array (under `notes`, `meetings`, `data`, or root).

## Fetch intent

The agent needs:

1. **Per-meeting record** with at minimum: a stable meeting id, title, transcript (or body), summary if present, attendee list, start/end times, created/updated timestamps, optional meeting URL.
2. **Pagination** in API mode — cursor or page-based depending on Granola's current shape. Iterate until exhausted.
3. **Time filtering** for `--since`: API mode passes a server-side `updated_after` (or equivalent) parameter; export mode filters client-side on `updated_at`.

Throttle politely (~0.5 sec between calls) in API mode.

## Field extraction intent

Per meeting record, what we want and where Granola typically carries it:

| What we want | Where to look |
|---|---|
| Meeting id | `id` / `meeting_id` / `note_id` (stable across re-runs) |
| Title | `title` / `name` |
| Transcript / body | `transcript` / `transcript_text` / `body` |
| Summary | `summary` / `summary_text` (optional, but valuable as `Artifact.brief` if present) |
| Attendees | `attendees` / `participants` — array of `{name, email}` or sometimes just names |
| Start time | `started_at` / `start_time` / `created_at` |
| End time | `ended_at` / `end_time` |
| Updated | `updated_at` / `modified_at` |
| URL | `url` (the meeting's permalink in Granola) |

For unknown fields, pass through under a `meta` bag — don't drop information.

## Mapping (raw → schema)

Per Granola meeting imported, emit:

```
ExternalID:
  slug:        ext-granola-<8-hex-of-sha256("granola/" + meeting_id)>
  source:      granola
  external_id: <meeting_id>
  createdAt:   <created_at>

Artifact (transcript):
  slug:        art-granola-<sanitized_meeting_id>
  name:        "Transcript: " + <title>
  kind:        transcript
  source:      granola
  source_ref:  <meeting_id>
  url:         <url>
  content:     <transcript>
  timestamp:   <started_at>
  createdAt:   <created_at>
  updatedAt:   <updated_at or started_at>

Event:
  slug:        event-granola-<sanitized_meeting_id>
  name:        <title>
  kind:        meeting
  brief:       <summary if present>
  date:        <started_at>
  end_date:    <ended_at>
  createdAt:   <created_at>
  updatedAt:   <updated_at>

Edge:
  RecordOf: <artifact.slug> -> <event.slug>

For each attendee:
  Person       (name, email if present, relation: "other")
  Optionally   ExternalID + IdentifiesPerson if a stable Granola user id is exposed
  Attended:    <person.slug> -> <event.slug>
  Mentions:    <artifact.slug> -> <person.slug>
```

## Slug derivation (stable, our convention)

| Slug | Algorithm |
|---|---|
| `ext-granola-<hash>` | first 8 hex of `sha256("granola/" + meeting_id)` |
| `art-granola-<id>` | sanitized meeting_id (replace non-alphanumeric with `-`) |
| `event-granola-<id>` | same sanitized meeting_id with `event-` prefix |
| `person-<email-slug>` (email known) | normalize email → kebab |
| `person-<name-slug>-<hash>` (no email) | name + 8-hex sha256 suffix |

Same meeting_id → same slugs. Re-runs are idempotent.

## Idempotency + `--since`

- No `--since` → re-pull every meeting; merge upserts by slug.
- `--since <iso>` → API mode uses `updated_after`; export mode filters client-side.
- Emit a `SyncRun` record at the end per `loading-rules.md`.

## Known semi-stable quirks

1. **Attendee shapes vary.** Sometimes `{name, email}`, sometimes a `displayName` field, sometimes just a string. Tolerate all; the agent should extract email when present (high-value for cross-source identity) and fall back to name.

2. **Transcripts may be empty or absent.** Some meetings have no transcript (cancelled, audio failed, etc.). Emit the Event + Artifact (with empty `content`) anyway — the metadata still matters.

3. **Summary structure varies.** Sometimes plain text, sometimes structured bullet points, sometimes nested by speaker. Treat as a string; let the user/agent post-process for richer extraction in v2.

4. **Meeting URL stability.** Some Granola URLs include slugs that change if the title is renamed. Use the `id` field as the canonical identifier, not the URL.

5. **API auth changes.** Granola has switched auth patterns in the past (header name, token format). If validation fails with the expected `Authorization: Bearer` pattern, check the docs link above for current auth.

## Sample I/O

### Sample raw meeting

```json
{
  "id": "mtg-abc123",
  "title": "Marcus 1:1 — advisor onboarding",
  "transcript": "MARCUS: Build smaller, but better. SARAH: ...",
  "summary": "Discussed advisor terms; Marcus emphasized onboarding simplification.",
  "attendees": [
    {"name": "Marcus LeBlanc", "email": "marcus@leblancadvisors.com"},
    {"name": "Sarah Chen", "email": "sarah@modernrelay.com"}
  ],
  "started_at": "2026-04-12T15:00:00Z",
  "ended_at": "2026-04-12T15:45:00Z",
  "created_at": "2026-04-12T15:00:00Z",
  "updated_at": "2026-04-12T16:00:00Z",
  "url": "https://granola.so/notes/mtg-abc123"
}
```

### Expected schema-shaped output

```json
{"type": "ExternalID", "data": {"slug": "ext-granola-f3a91b22", "source": "granola", "external_id": "mtg-abc123", "createdAt": "..."}}
{"type": "Artifact",   "data": {"slug": "art-granola-mtg-abc123", "name": "Transcript: Marcus 1:1 — advisor onboarding", "kind": "transcript", "source": "granola", "url": "...", "content": "MARCUS: Build smaller...", "timestamp": "2026-04-12T15:00:00Z", ...}}
{"type": "Event",      "data": {"slug": "event-granola-mtg-abc123", "name": "Marcus 1:1 — advisor onboarding", "kind": "meeting", "brief": "Discussed advisor terms...", "date": "2026-04-12T15:00:00Z", "end_date": "2026-04-12T15:45:00Z", ...}}
{"edge": "RecordOf", "from": "art-granola-mtg-abc123", "to": "event-granola-mtg-abc123"}
{"type": "Person", "data": {"slug": "person-marcus-leblanc", "name": "Marcus LeBlanc", "email": "marcus@leblancadvisors.com", "relation": "other", ...}}
{"edge": "Attended", "from": "person-marcus-leblanc", "to": "event-granola-mtg-abc123"}
{"edge": "Mentions", "from": "art-granola-mtg-abc123", "to": "person-marcus-leblanc"}
{"type": "Person", "data": {"slug": "person-sarah-chen", ...}}
{"edge": "Attended", "from": "person-sarah-chen", "to": "event-granola-mtg-abc123"}
{"edge": "Mentions", "from": "art-granola-mtg-abc123", "to": "person-sarah-chen"}
```

One meeting with 2 attendees → ~10 records.

## What the agent does NOT need to do

- Build a long-lived CLI script — composed inline per session.
- Speaker-diarize the transcript — Granola's already done it; we just store the text.
- Resolve attendee emails to existing graph Persons — that's the dedup wizard's job per `../identity-resolution.md`.
- Re-implement cross-source dispatch logic — `loading-rules.md` handles it.
