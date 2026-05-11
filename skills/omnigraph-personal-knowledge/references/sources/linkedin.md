# Source: LinkedIn (CSV data export)

Spec for ingesting a LinkedIn data export into the personal-knowledge graph. The agent reads this doc + `../loading-rules.md` + `../identity-resolution.md` and composes the fetch + map code per session.

## About

LinkedIn doesn't expose a personal-data API. The supported path is LinkedIn's official **"Get a copy of your data"** export — a ZIP of CSV files emailed to the user, containing connections, messages, profile, positions, posts, reactions, and more.

This means **no auth, no scraping, no API rate limits** — the user has already authenticated by being logged into LinkedIn, and the export is theirs by right. The agent just walks the unzipped directory.

Use LinkedIn when the user wants their connections, DMs, work history, and posts in the graph.

## Authoritative reference

- LinkedIn data export request page — https://www.linkedin.com/mypreferences/d/download-my-data
- LinkedIn help: download your data — https://www.linkedin.com/help/linkedin/answer/a1339364

The CSV column names and structure occasionally change. When the agent encounters unfamiliar columns, it should adapt — column names are usually self-describing.

## Setup

No auth. The user does the work once:

1. Goes to the export request page (link above)
2. Picks at minimum: Connections, Messages, Profile, Positions, Shares
3. Submits the request — LinkedIn emails them when it's ready (sometimes minutes, sometimes 24h)
4. Downloads the ZIP, unzips somewhere
5. Tells the agent the path to the unzipped directory

The agent validates: directory exists, contains at least one recognized CSV (`Connections.csv`, `messages.csv`, `Profile.csv`, etc.).

## Fetch intent

The agent walks the export directory looking for known CSV file names. For each recognized file, it iterates rows and emits records. **Order-independent** — each file is its own contributor.

Recognized files (case-insensitive matching helps; LinkedIn occasionally varies the casing):

| File | Contains | Record kind |
|---|---|---|
| `Connections.csv` | One row per connection | connection |
| `messages.csv` | One row per direct-message turn | message |
| `Profile.csv` | One row — the user's own profile | profile |
| `Positions.csv` | One row per work position (current + past) | position |
| `Education.csv` | One row per school | education |
| `Shares.csv` | One row per post / share | post |
| `Reactions.csv` | One row per reaction the user gave | reaction (v1.1 — skip for v1) |

`messages.csv` is often labeled `messages.csv` lowercase; older exports used `Messages.csv`. Try both.

LinkedIn occasionally includes a "Notes:" preamble before the header row in some files. Skip lines until the first row that looks like column headers.

## Field extraction intent

### Connection row

| What we want | Common column name |
|---|---|
| First name | `First Name` |
| Last name | `Last Name` |
| Email | `Email Address` (often blank — LinkedIn only includes if the connection chose to share) |
| Profile URL | `URL` |
| Company | `Company` |
| Position | `Position` |
| Connected on | `Connected On` (date) |

### Message row

| What we want | Common column name |
|---|---|
| Conversation id | `CONVERSATION ID` |
| Conversation title | `CONVERSATION TITLE` |
| From | `FROM` (display name) |
| Sender profile URL | `SENDER PROFILE URL` |
| To | `TO` |
| Date | `DATE` |
| Subject | `SUBJECT` |
| Content | `CONTENT` |
| Folder | `FOLDER` |

### Profile row

| What we want | Common column name |
|---|---|
| First / Last name | `First Name`, `Last Name` |
| Headline | `Headline` |
| Summary | `Summary` |
| Industry | `Industry` |
| Geo location | `Geo Location` |

### Position row

| What we want | Common column name |
|---|---|
| Company | `Company Name` |
| Title | `Title` |
| Description | `Description` |
| Location | `Location` |
| Started on | `Started On` |
| Finished on | `Finished On` (blank = current) |

### Share / Post row

| What we want | Common column name |
|---|---|
| Date | `Date` |
| Content | `Share Commentary` or `Content` |
| Media URL | `Media URL` |
| Share link | `Share Link` (the post's URL) |
| Visibility | `Visibility` |

## Mapping (raw → schema)

### Connection → Person + BelongsTo

```
Person:
  slug:     person-<email-slug> if email else person-<name-slug>-<hash>
  name:     "<First> <Last>"
  email:    <email or null>
  relation: "professional"   # safe default for LinkedIn connections
  brief:    <Position>

ExternalID:
  slug:        ext-linkedin-<8-hex-of-sha256("linkedin/" + email_or_name)>
  source:      linkedin
  external_id: <email or name>

Edge:
  IdentifiesPerson: <ext.slug> -> <person.slug>

If Company present:
  Organization (slug: org-<company-slug>-<hash>, name, kind: company)
  BelongsTo: <person.slug> -> <organization.slug>
    with role: <Position>, since: <Connected On>, source: "linkedin", current: true
```

### Message → Artifact + Conversation

```
ExternalID:
  slug:        ext-linkedin-<8-hex-of-sha256("linkedin/" + conv_id + "/" + date)>
  source:      linkedin
  external_id: <conversation_id>/<date>

Artifact:
  slug:        art-linkedin-<sanitized_conv_id>-<date_sanitized>
  name:        <content truncated to 80 chars>
  kind:        message
  source:      linkedin
  content:     <content>
  timestamp:   <date>

Conversation:
  slug:         conv-linkedin-<8-hex-of-sha256("linkedin/" + conversation_id)>
  external_id:  <conversation_id>
  kind:         dm
  source:       linkedin
  name:         <Conversation Title or null>

Edge:
  InConversation: <artifact.slug> -> <conversation.slug>

If From / sender_profile_url resolvable:
  Person (name from From)
  ArtifactFromPerson: <artifact.slug> -> <person.slug>
```

### Profile → (informational; usually doesn't emit graph records unless mapping to a self-Person)

For v1, skip — the user's own profile doesn't need to be in their personal graph as a separate entity (they ARE the graph).

### Position → BelongsTo (for the user's self-Person)

If the agent has emitted a self-Person elsewhere (e.g. from connections matching the user's email), Position rows become BelongsTo edges to Organizations.

For v1, easiest to skip Positions unless explicitly requested.

### Share / Post → Artifact

```
ExternalID:
  slug:        ext-linkedin-<hash of share_link or date>
  source:      linkedin
  external_id: <share_link>

Artifact:
  slug:        art-linkedin-<sanitized_share_link_tail>
  name:        <content truncated to 80 chars>
  kind:        post
  source:      linkedin
  url:         <share_link>
  content:     <content>
  timestamp:   <date>
```

## Slug derivation (stable, our convention)

| Slug | Algorithm |
|---|---|
| `ext-linkedin-<hash>` | first 8 hex of `sha256("linkedin/" + identifier)` where identifier is email, conv_id+date, or share_link |
| `art-linkedin-<id>` | sanitized identifier (message id, share_link tail) |
| `conv-linkedin-<hash>` | first 8 hex of `sha256("linkedin/" + conversation_id)` |
| `person-<email-slug>` (email known) | normalize email → kebab |
| `person-<name-slug>-<hash>` (no email) | name + 8-hex sha256 suffix |
| `org-<company-slug>-<hash>` | normalize company name → kebab + 8-hex sha256 suffix |

## Idempotency + `--since`

- No `--since` → walk every row in every recognized CSV. Cheap.
- `--since <iso>` → filter rows where the date field is `>= since`. Per-row; no I/O cost beyond CSV scan.
- Emit a `SyncRun` at the end per `loading-rules.md`.

## Known semi-stable quirks

1. **Export cadence is manual.** Users have to re-request a new export each time they want fresh data. There's no incremental endpoint. Tell the user; for "live" sync they should request a new export quarterly.

2. **Connection email is rarely populated.** LinkedIn only includes a connection's email if the connection explicitly chose to share it. Plan for `email = null` on most rows; use name-based slug fallback.

3. **Message format varies by export age.** Older exports may use different column names. The agent should be tolerant — match common aliases (`From`, `from`, `FROM`).

4. **Preamble lines.** Some CSVs start with `"Notes: ..."` lines before the header. Skip until you find a row whose first cell starts with a letter and the row has >1 cell.

5. **Encoded characters.** LinkedIn CSVs use UTF-8 but occasionally include odd encodings for emoji or accented characters. Use `errors="replace"` when reading.

6. **Self-connections.** The user's own profile appears in some files. Filter by matching the user's email (from `Profile.csv`) and exclude from connections.

7. **No timestamps on positions.** Positions sometimes have `Started On` as a month-year string (`Jan 2020`) or even just a year. Parse leniently; coerce to ISO with start-of-month fallback.

## Sample I/O

### Sample raw rows (one each from Connections + messages)

`Connections.csv`:
```csv
First Name,Last Name,Email Address,URL,Company,Position,Connected On
Jane,Park,jane@kettle.so,https://www.linkedin.com/in/janepark,Kettle,Product Manager,2025-08-12
```

`messages.csv`:
```csv
CONVERSATION ID,CONVERSATION TITLE,FROM,SENDER PROFILE URL,TO,DATE,SUBJECT,CONTENT,FOLDER
conv-abc-123,,Jane Park,https://www.linkedin.com/in/janepark,Alex Rivera,2026-04-15T14:00:00Z,,"Hey Alex, quick question about onboarding...",INBOX
```

### Expected schema-shaped output (selected records)

```json
{"type": "Person", "data": {"slug": "person-jane-park-a1b2c3d4", "name": "Jane Park", "email": "jane@kettle.so", "relation": "professional", "brief": "Product Manager", ...}}
{"type": "ExternalID", "data": {"slug": "ext-linkedin-9e3f1a2b", "source": "linkedin", "external_id": "jane@kettle.so", ...}}
{"edge": "IdentifiesPerson", "from": "ext-linkedin-9e3f1a2b", "to": "person-jane-park-a1b2c3d4"}
{"type": "Organization", "data": {"slug": "org-kettle-c4e5f6a1", "name": "Kettle", "kind": "company", ...}}
{"edge": "BelongsTo", "from": "person-jane-park-a1b2c3d4", "to": "org-kettle-c4e5f6a1", "data": {"role": "Product Manager", "since": "2025-08-12", "source": "linkedin", "current": true}}
{"type": "Artifact", "data": {"slug": "art-linkedin-conv-abc-123-2026-04-15", "name": "Hey Alex, quick question about onboarding...", "kind": "message", "source": "linkedin", "content": "...", "timestamp": "2026-04-15T14:00:00Z"}}
{"type": "Conversation", "data": {"slug": "conv-linkedin-7f8a9b1c", "external_id": "conv-abc-123", "kind": "dm", "source": "linkedin", "name": null}}
{"edge": "InConversation", "from": "art-linkedin-conv-abc-123-2026-04-15", "to": "conv-linkedin-7f8a9b1c"}
{"edge": "ArtifactFromPerson", "from": "art-linkedin-conv-abc-123-2026-04-15", "to": "person-jane-park-a1b2c3d4"}
```

## What the agent does NOT need to do

- Authenticate to LinkedIn — the export is already authenticated.
- Scrape LinkedIn — explicitly out of scope; the official export is the right path.
- Resolve cross-source identity (Jane on LinkedIn = Jane on Slack) — that's the dedup wizard's job per `../identity-resolution.md`.
- Re-implement dedup-within-run — `loading-rules.md` handles collapsing repeated Person/Organization emissions.
