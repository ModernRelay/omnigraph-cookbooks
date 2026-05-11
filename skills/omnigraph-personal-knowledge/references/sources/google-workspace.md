# Source: Google Workspace (Drive, Gmail, Calendar)

Spec for ingesting Google Workspace data into the personal-knowledge graph. The agent reads this doc + `../loading-rules.md` + `../identity-resolution.md` and composes the fetch + map code per session.

## About

Google Workspace is an umbrella for three separate API surfaces the agent can ingest:

- **Drive** — file metadata + content (Docs, Sheets, PDFs, etc.)
- **Gmail** — messages with subjects, threading, addressing
- **Calendar** — events with attendees, locations, times

All three share one OAuth flow; scopes are per-API. The user picks which sub-products to import (`--drive`, `--gmail`, `--gcal` — any combination).

## Authoritative reference

- Google APIs explorer — https://developers.google.com/apis-explorer
- OAuth 2.0 for desktop apps — https://developers.google.com/identity/protocols/oauth2/native-app
- Drive API v3 — https://developers.google.com/drive/api/v3/reference
- Gmail API v1 — https://developers.google.com/gmail/api/reference/rest
- Calendar API v3 — https://developers.google.com/calendar/api/v3/reference
- Scopes reference — https://developers.google.com/identity/protocols/oauth2/scopes

When endpoints, response shapes, or scopes drift, fall back to these.

## Auth + setup ritual

1. Open `https://console.cloud.google.com/apis/credentials` in the user's browser.
2. Have the user create a project (any name), enable the APIs they want (Drive, Gmail, Calendar — only what corresponds to the sub-flows they picked), and create OAuth 2.0 credentials as **Desktop app type**.
3. Have them download the `client_secret.json` and tell us the path.
4. Required scopes (read-only):
   - Drive: `https://www.googleapis.com/auth/drive.readonly`
   - Gmail: `https://www.googleapis.com/auth/gmail.readonly`
   - Calendar: `https://www.googleapis.com/auth/calendar.readonly`
5. Run the OAuth installed-app flow with `client_secret.json` to obtain `credentials` (refresh + access tokens). Persist `credentials` to `~/.config/omnigraph-personal-knowledge/google-token.json`. Subsequent runs reuse this and refresh as needed.
6. Validate by hitting one trivial endpoint per requested sub-flow (e.g. `users.getProfile` for Gmail; `drive.about.get` for Drive; `calendarList.list` for Calendar).

## Fetch intent

Three sub-flows, each independent:

### Drive

- List files via the Drive API, paginated. Filter `trashed = false`. For `--since`, filter on `modifiedTime >= since`.
- Project fields: `id, name, mimeType, webViewLink, modifiedTime, createdTime, owners, parents, size`.
- Optionally download file content for text-MIME-types (Docs, plain text) via the export endpoint. Skip large binaries unless explicitly requested.

### Gmail

- List messages via `users.messages.list`, paginated. For `--since`, pass `q=after:<unix_ts>`.
- For each listed message id, fetch full message via `users.messages.get` with `format=full` to get the body parts.
- Throttle politely. Cap first runs with `--gmail-max <N>` — a 10-year inbox is otherwise a multi-hour fetch.

### Calendar

- List events via `events.list`, paginated, with `singleEvents=true` to expand recurrences, `orderBy=startTime`. For `--since`, pass `updatedMin`.
- Project fields: `id, summary, description, location, start, end, attendees, organizer, status, created, updated, htmlLink`.

## Field extraction intent

### Drive file

| What we want | Where to look |
|---|---|
| File id | `id` |
| Title | `name` |
| MIME type | `mimeType` (informs `Artifact.kind` mapping) |
| URL | `webViewLink` |
| Body (if text-extractable) | export with the appropriate `mimeType=text/plain` for Docs, otherwise empty |
| Owners | `owners[].emailAddress` (Person extraction) |
| Created / updated | `createdTime`, `modifiedTime` |

### Gmail message

| What we want | Where to look |
|---|---|
| Message id | `id` |
| Thread id | `threadId` |
| Subject | header `Subject` |
| From | header `From` (may include display name + `<email>`) |
| To, Cc | headers `To`, `Cc` (comma-separated) |
| Date | header `Date` or `internalDate` (epoch ms) |
| Body — plain text | walk `payload.parts` recursively, find `mimeType: text/plain`, base64url-decode `body.data` |
| Body — HTML | same as plain, looking for `text/html` |
| Labels | `labelIds` |
| Snippet | `snippet` |

### Calendar event

| What we want | Where to look |
|---|---|
| Event id | `id` |
| Title | `summary` |
| Description | `description` |
| Start, end | `start.dateTime` (or `start.date` for all-day), same for `end` |
| Attendees | `attendees[].emailAddress`, `.displayName`, `.responseStatus` |
| Organizer | `organizer.emailAddress` |
| Status | `status` |
| URL | `htmlLink` |
| Created / updated | `created`, `updated` |

## Mapping (raw → schema)

### Drive → Artifact

```
ExternalID:
  slug:        ext-drive-<8-hex-of-sha256("drive/" + file_id)>
  source:      drive
  external_id: <file_id>
  createdAt:   <createdTime>

Artifact:
  slug:        art-drive-<sanitized_file_id>
  name:        <file.name>
  kind:        document
  source:      drive
  source_ref:  <file_id>
  url:         <webViewLink>
  content:     <body if text-extractable>
  timestamp:   <modifiedTime>
  createdAt:   <createdTime>
  updatedAt:   <modifiedTime>

For each owner with an email:
  Person       (name, email)
  ExternalID   (source: email, external_id: <owner email>)
  IdentifiesPerson: <ext.slug> -> <person.slug>
  ArtifactFromPerson: <artifact.slug> -> <person.slug>
```

### Gmail → Email (first-class type)

```
ExternalID:
  slug:        ext-email-<8-hex-of-sha256("email/" + message_id)>
  source:      email
  external_id: <message_id>

Email (first-class node):
  slug:        email-<8-hex-of-sha256(message_id)>
  message_id:  <message_id>
  thread_id:   <threadId>
  subject:     <subject>
  labels:      <labelIds>
  account:     <user's email address>
  from:        <from address>
  to:          <to addresses>
  cc:          <cc addresses>
  timestamp:   <internalDate as iso>
  content_text: <plain body>
  content_html: <html body>
  snippet:     <snippet>
  createdAt:   <internalDate>
  updatedAt:   <internalDate>

Conversation (one per thread, deduped per loading-rules.md):
  slug:        conv-email-<8-hex-of-sha256(thread_id)>
  external_id: <threadId>
  kind:        group
  source:      email
  name:        <subject of the thread>

Edge:
  EmailInConversation: <email.slug> -> <conversation.slug>

For each address in From / To / Cc:
  Person (name from header display, email)
  ExternalID (source: email, external_id: <address>)
  IdentifiesPerson
  EmailFromPerson:  <email.slug> -> <person.slug>  (for From)
  EmailToPerson:    <email.slug> -> <person.slug>  (for To, Cc)
```

### Calendar → Event

```
ExternalID:
  slug:        ext-calendar-<8-hex-of-sha256("calendar/" + event_id)>
  source:      calendar
  external_id: <event_id>

Event:
  slug:        event-gcalendar-<sanitized_event_id>
  name:        <summary>
  kind:        meeting
  brief:       <description>
  date:        <start.dateTime>
  end_date:    <end.dateTime>
  createdAt:   <created>
  updatedAt:   <updated>

For each attendee with an email:
  Person      (name = displayName or email, email)
  ExternalID  (source: email, external_id: <attendee email>)
  IdentifiesPerson
  Attended:   <person.slug> -> <event.slug>
```

## Slug derivation (stable, our convention)

| Slug | Algorithm |
|---|---|
| `ext-drive-<hash>` | first 8 hex of `sha256("drive/" + file_id)` |
| `ext-email-<hash>` | first 8 hex of `sha256("email/" + message_id)` |
| `ext-calendar-<hash>` | first 8 hex of `sha256("calendar/" + event_id)` |
| `email-<hash>` | first 8 hex of `sha256(message_id)` |
| `conv-email-<hash>` | first 8 hex of `sha256(thread_id)` |
| `art-drive-<id>` | sanitized file_id |
| `event-gcalendar-<id>` | sanitized event_id |
| `person-<email-slug>` | normalize email → kebab |

Same Google id → same slugs → re-runs upsert cleanly.

## Idempotency + `--since`

- All three sub-flows accept `--since`. Drive uses `modifiedTime >= since`; Gmail uses `q=after:<unix_ts>`; Calendar uses `updatedMin`.
- Emit one `SyncRun` per sub-flow imported (so the user gets per-product sync visibility), or one combined SyncRun with `source: google-workspace` — pick consistently per `loading-rules.md`.
- Drive + Gmail thread participants → Person nodes use `email` as the discriminator. Same email across Drive owner + Gmail sender → same Person slug → graph naturally unifies.

## Known semi-stable quirks

1. **OAuth setup is heaviest of the 8 sources.** Walk users through it carefully. Cite Google Cloud Console UI changes if they drift.

2. **Token storage location matters.** `~/.config/omnigraph-personal-knowledge/google-token.json` is the convention. The agent must `chmod 600` after writing (refresh tokens are credentials).

3. **Gmail volume.** A 10-year inbox is 50k-100k messages. **Always cap first runs** with `--gmail-max 500` — explain the cap to the user up front. Subsequent runs use `--since` to incrementalize.

4. **All-day events.** Calendar events without time use `start.date` / `end.date` (date strings, not datetime). The agent must coerce to start-of-day UTC for `Event.date`.

5. **Recurring events.** With `singleEvents=true`, recurrences are expanded to individual events. Without it, you get the master event only — useful for some queries, useless for "what happened on a date" lookups. Default to expanded.

6. **From-header parsing.** Gmail's `From` header often looks like `"Jane Park" <jane@kettle.so>`. Parse to extract the bare email — that's the stable identifier — and use the display name for `Person.name`.

7. **Attendees without `email`.** Calendar can include attendees that are external resources (e.g. a meeting room calendar). Filter to attendees with `email` populated; skip rooms.

8. **MIME-type-aware Drive content extraction.** Native Docs/Sheets need `export` not `get`. PDFs, images, binaries — skip content extraction for v1 (the metadata is enough).

## Sample I/O

### Gmail sample

```json
{
  "id": "18c3a0f...",
  "threadId": "18c3a0f...",
  "labelIds": ["INBOX", "IMPORTANT"],
  "internalDate": "1747500000000",
  "payload": {
    "headers": [
      {"name": "Subject", "value": "Advisor agreement — final draft"},
      {"name": "From", "value": "\"Marcus LeBlanc\" <marcus@leblancadvisors.com>"},
      {"name": "To", "value": "alex@arivera.dev"},
      {"name": "Date", "value": "Thu, 10 Apr 2026 14:00:00 -0700"}
    ],
    "parts": [
      {"mimeType": "text/plain", "body": {"data": "<base64url>"}}
    ]
  },
  "snippet": "Alex, attached is the final draft..."
}
```

### Expected output (5 records, edges elided)

```json
{"type": "ExternalID", "data": {"slug": "ext-email-9a3b1c2d", "source": "email", "external_id": "18c3a0f...", ...}}
{"type": "Email", "data": {"slug": "email-9a3b1c2d", "subject": "Advisor agreement — final draft", "from": "marcus@leblancadvisors.com", "to": ["alex@arivera.dev"], "timestamp": "2026-04-10T21:00:00Z", ...}}
{"type": "Conversation", "data": {"slug": "conv-email-9a3b1c2d", "external_id": "18c3a0f...", "kind": "group", "source": "email", "name": "Advisor agreement — final draft"}}
{"type": "Person", "data": {"slug": "person-marcus-leblanc", "name": "Marcus LeBlanc", "email": "marcus@leblancadvisors.com", "relation": "other", ...}}
{"type": "Person", "data": {"slug": "person-alex-rivera", "name": "Alex", "email": "alex@arivera.dev", "relation": "other", ...}}
```

Plus 4 edges (EmailFromPerson, EmailToPerson, EmailInConversation, IdentifiesPerson × 2).

## What the agent does NOT need to do

- Build a long-lived CLI script — composed inline per session.
- Download every Drive file's content — `mimeType` informs whether body extraction is worth it.
- Ingest attachments from Gmail unless explicitly asked.
- Resolve cross-account identity (a single user with two Google accounts) — that's the dedup wizard's job.
