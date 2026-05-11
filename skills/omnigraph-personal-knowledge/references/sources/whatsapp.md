# Source: WhatsApp (chat export)

Spec for ingesting WhatsApp chat exports into the personal-knowledge graph. The agent reads this doc + `../loading-rules.md` + `../identity-resolution.md` and composes the fetch + map code per session.

## About

WhatsApp doesn't expose a personal-data API. The supported path is the in-app **"Export Chat"** feature, which produces a `.txt` file per conversation. The user does this manually per chat they want imported — there's no bulk export.

Use WhatsApp when the user has DMs or group chats they want anchored in the graph. Best-fit for a small number of important conversations rather than a full chat history.

## Authoritative reference

- WhatsApp help: export chat history — https://faq.whatsapp.com/1180414079177245/?cms_platform=android (Android) and https://faq.whatsapp.com/1180414079177245/?cms_platform=iphone (iOS)
- Chat export format is informally documented; line shape varies slightly between iOS, Android, and locale.

## Setup

No auth. The user does the work per chat:

1. Opens the chat in WhatsApp (iOS or Android)
2. Taps **chat info** → **Export Chat** → **Without Media** (we don't ingest media files for v1)
3. Sends the resulting `.txt` file somewhere accessible (AirDrop / email / cloud)
4. Tells the agent the path to a single `.txt` file or a directory of them

For multi-chat ingestion, the user exports each chat separately and drops them all in one folder. The agent walks the folder for `.txt` files.

## Fetch intent

The agent:

1. Reads the file (or each file in a folder) line by line
2. Identifies the first line in each chat as carrying the chat's earliest message — the rest follow
3. Parses each message line into `{timestamp, sender, text}`
4. Handles multi-line messages (continuation lines that don't match the header pattern belong to the previous message)
5. Detects whether the chat is a DM or group based on the number of unique senders (>2 → group)

## Field extraction intent

Two formats to support, picked by line prefix:

### iOS bracketed format

```
[DD/MM/YY, HH:MM:SS AM] Sender Name: message text
```

Regex anchor: `^\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\]\s+(?P<sender>[^:]+?):\s(?P<text>.*)$`

### Android dash format

```
DD/MM/YY, HH:MM - Sender Name: message text
```

Regex anchor: `^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\s+-\s+(?P<sender>[^:]+?):\s(?P<text>.*)$`

### System events (chat creation, member joins, encryption notices)

A line that matches the date+time prefix but has no `Sender: ` (the colon-text part) is a system event. Skip these or capture as metadata.

### Timestamp parsing

Common date formats:

- `DD/MM/YY` (most locales)
- `MM/DD/YY` (US locale)

Try several formats and take the first that parses. Coerce to ISO UTC.

### Multi-line messages

Any line that doesn't match the header regex belongs to the previous message — append to its `text` with a newline separator.

## Mapping (raw → schema)

Per WhatsApp message imported, emit:

```
ExternalID:
  slug:        ext-whatsapp-<8-hex-of-sha256("whatsapp/" + chat_id + "/" + timestamp)>
  source:      whatsapp
  external_id: <chat_id>/<timestamp>
  createdAt:   <timestamp>

Artifact:
  slug:        art-whatsapp-<chat_id>-<sanitized_timestamp>
  name:        <text truncated to 80 chars> or "(empty)"
  kind:        message
  source:      whatsapp
  source_ref:  <chat_id>/<timestamp>
  content:     <text>
  timestamp:   <timestamp>

Conversation (per chat, deduped per loading-rules.md):
  slug:        conv-whatsapp-<8-hex-of-sha256("whatsapp/" + chat_id)>
  external_id: <chat_id>
  kind:        dm | group
  source:      whatsapp
  name:        <chat_name from filename>

Edge:
  InConversation: <artifact.slug> -> <conversation.slug>

For each unique sender:
  Person                (name from sender field, relation: "other")
  ExternalID            (source: whatsapp, external_id: <sender_phone_or_name>)
  IdentifiesPerson:     <ext.slug> -> <person.slug>
  ArtifactFromPerson:   <artifact.slug> -> <person.slug>
  ConversationWith:     <conversation.slug> -> <person.slug>
```

### Chat id and chat name

WhatsApp doesn't carry a chat id in the export. Use the export filename as the chat name (e.g. `WhatsApp Chat with Jane Park.txt`) and derive `chat_id` as a hash of the filename. This means renaming the file produces a new chat id — accept this; the user shouldn't rename exports.

```
chat_id = sha256(filename)[:16]
chat_name = filename stem, stripped of "WhatsApp Chat with " / "WhatsApp Chat - " prefixes
```

## Slug derivation (stable, our convention)

| Slug | Algorithm |
|---|---|
| `ext-whatsapp-<hash>` | first 8 hex of `sha256("whatsapp/" + chat_id + "/" + timestamp)` |
| `art-whatsapp-<chat_id>-<ts>` | concatenated chat_id + sanitized timestamp |
| `conv-whatsapp-<hash>` | first 8 hex of `sha256("whatsapp/" + chat_id)` |
| `person-<name-slug>-<hash>` | sender name + 8-hex hash (WhatsApp exports rarely include phone numbers as identifiers) |

Same export file on a re-run → same slugs. Different filename (or rename) → new slugs.

## Idempotency + `--since`

- No `--since` → re-parse every line in every export file.
- `--since <iso>` → filter messages where `timestamp >= since`. Per-message; cheap.
- Emit a `SyncRun` per `loading-rules.md`.

## Known semi-stable quirks

1. **Format variation by locale + OS.** Date format, AM/PM, and the dash-vs-bracket separator all vary. The agent should attempt both regex patterns and several date formats and accept the first that succeeds per line.

2. **The "Without Media" requirement.** "Export Chat → With Media" generates a folder with text + image files. For v1, we only handle the `.txt`; tell the user to choose "Without Media".

3. **Multi-line messages.** A line of text that doesn't match the header regex is a continuation. The agent maintains a `current` message variable and appends until the next header line.

4. **System events.** "Messages and calls are end-to-end encrypted...", "You changed the group description.", join/leave notifications. These match the date prefix but have no sender. Skip or capture as `kind: system` Artifacts.

5. **No phone numbers in exports.** WhatsApp's export shows sender display names only. This makes cross-source identity resolution harder than Slack — the user may have to manually merge "Mom" (WhatsApp) with their mother's email-based Person.

6. **Forwarded messages.** Often prefixed with "(forwarded)" or similar in the text. No structured marker; preserve in `text`.

7. **Emoji.** Generally fine — UTF-8 in the export file. The agent should preserve them.

## Sample I/O

### Sample raw lines (iOS bracketed)

```
[15/03/26, 10:43:21 AM] Jane Park: Hey, are we still on for Friday?
[15/03/26, 10:45:08 AM] Alex Rivera: Yep — 11am at Blue Bottle?
[15/03/26, 10:45:23 AM] Jane Park: 👍
```

Filename: `WhatsApp Chat with Jane Park.txt` → chat_name `"Jane Park"`, chat_id `<sha256 of filename>[:16]`.

### Expected schema-shaped output (one message)

```json
{"type": "ExternalID", "data": {"slug": "ext-whatsapp-9c3a1b2d", "source": "whatsapp", "external_id": "abc123/2026-03-15T10:43:21Z", "createdAt": "2026-03-15T10:43:21Z"}}
{"type": "Artifact", "data": {"slug": "art-whatsapp-abc123-2026-03-15T10-43-21Z", "name": "Hey, are we still on for Friday?", "kind": "message", "source": "whatsapp", "content": "Hey, are we still on for Friday?", "timestamp": "2026-03-15T10:43:21Z"}}
{"type": "Conversation", "data": {"slug": "conv-whatsapp-7d8e1f2a", "external_id": "abc123", "kind": "dm", "source": "whatsapp", "name": "Jane Park"}}
{"edge": "InConversation", "from": "art-whatsapp-abc123-2026-03-15T10-43-21Z", "to": "conv-whatsapp-7d8e1f2a"}
{"type": "Person", "data": {"slug": "person-jane-park-a1b2c3d4", "name": "Jane Park", "relation": "other", ...}}
{"type": "ExternalID", "data": {"slug": "ext-whatsapp-b1c2d3e4", "source": "whatsapp", "external_id": "Jane Park", ...}}
{"edge": "IdentifiesPerson", "from": "ext-whatsapp-b1c2d3e4", "to": "person-jane-park-a1b2c3d4"}
{"edge": "ArtifactFromPerson", "from": "art-whatsapp-abc123-2026-03-15T10-43-21Z", "to": "person-jane-park-a1b2c3d4"}
{"edge": "ConversationWith", "from": "conv-whatsapp-7d8e1f2a", "to": "person-jane-park-a1b2c3d4"}
```

One message with one sender → ~8 records. Dedupe collapses Conversation + Person + ConversationWith to single instances when N messages share a sender/chat.

## What the agent does NOT need to do

- Decrypt WhatsApp's on-device storage — out of scope; the export is the supported path.
- Parse media files — v1 is text-only.
- Resolve sender phone numbers — WhatsApp exports don't carry them.
- Detect DM vs group reliably without seeing all senders — for very short export files (<10 messages, 2 senders), default to DM unless filename or content suggests otherwise.
