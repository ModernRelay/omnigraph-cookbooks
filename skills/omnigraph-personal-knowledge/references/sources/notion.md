# Source: Notion

Spec for ingesting a Notion workspace into the personal-knowledge graph. The agent reads this doc + `../loading-rules.md` + `../identity-resolution.md` and composes the fetch + map code per session.

## About

Notion exposes a REST API behind an integration token. One integration sees only the pages and databases its owner explicitly connects it to — but **child pages inherit** the parent connection. Connecting the integration to two top-level workspaces typically grants access to dozens of pages.

Use Notion when the user has notes, docs, project pages, or databases in Notion they want imported.

## Authoritative reference

Notion's API drifts; the agent should treat these links as the source of truth and fall back to them when the spec below doesn't match observed behavior:

- API reference index — https://developers.notion.com/reference/intro
- Versioning (`Notion-Version` header) — https://developers.notion.com/reference/versioning
- Search — https://developers.notion.com/reference/post-search
- Database query — https://developers.notion.com/reference/post-database-query
- Page object — https://developers.notion.com/reference/page
- Block children — https://developers.notion.com/reference/get-block-children
- Property value shapes — https://developers.notion.com/reference/property-value-object
- Block shapes — https://developers.notion.com/reference/block
- Rate limits — https://developers.notion.com/reference/request-limits

When in doubt about a specific field path or endpoint shape, fetch the relevant link and use what's current. The mapping intent below is stable; the API surface is what may drift.

## Auth + setup ritual

1. Open `https://www.notion.so/profile/integrations` in the user's browser.
2. Have the user create a new internal integration (any name, e.g. `Omnigraph PK`), scoped to their workspace.
3. Capture the integration token (starts with `ntn_` or `secret_`).
4. Validate the token with a single round-trip — Notion's "Retrieve a user" endpoint with the bot's identity works. 200 → valid; 401 → bad token; other → surface the body to the user.
5. Tell the user to add the integration to each page or database they want imported: in Notion, open the page → `···` (top right) → **Connections** → search the integration name → connect. Child pages inherit.
6. Persist the token via `keyring` under service `omnigraph-pk`, key `notion-token`.

## Fetch intent

The agent needs three kinds of data per import:

1. **Page enumeration** — every page (and optionally database) the integration can see.
   - Default mode: walk all accessible pages via the search endpoint, filtered to `object: "page"`.
   - Scoped mode (`--database-id <id>`): walk only one database via the database-query endpoint.
   - Sort results by `last_edited_time` descending so `--since` filtering can short-circuit.

2. **Page bodies** — the block tree under each page, fetched via the block-children endpoint, paginated.

3. **Time filtering for `--since`**:
   - Database-query supports a server-side `last_edited_time` filter — use it.
   - Search has no native time filter; sort descending and stop iterating once a page's `last_edited_time < since`.

Throttle to Notion's published rate limit. On 429, honor `Retry-After` and back off; don't crash the import on transient throttling.

## Field extraction intent

Notion exposes typed properties on pages. Each property has a `type` discriminator naming the variant; the value lives at `value[type]`. The shapes are documented in the property-value-object link above — fetch if the agent observes unexpected structure.

What we want from a page, and where Notion typically carries it:

| What we want | Where to look |
|---|---|
| Page title | the property whose `type == "title"` — concatenate `plain_text` from its rich-text segments |
| Free-text content of any property | rich-text segments → concat `plain_text` |
| Tag-like values | `multi_select` names (these become `Note.tags`) + `status` if present |
| People references | `people[]` entries — each has an id + name (these become Person + Mentions edges) |
| Relations to other pages | `relation[].id` — array of page IDs (LinkedNote edge candidates) |
| URL | the page's top-level `url` field |
| Timestamps | top-level `created_time` + `last_edited_time` |
| Body | block-children of the page, flattened to Markdown-style plaintext |

For unknown property types, the `type` discriminator names the variant. Read the linked docs and extract the most semantic field — usually mirroring one of the patterns above.

### Block bodies

Blocks have a `type` discriminator. For body extraction, concatenate `rich_text[].plain_text` from each block, formatted by type — headings get `#`/`##`/`###` prefixes, list items get `-` or `1.`, to-dos get `- [x]`/`- [ ]`, quotes get `>`, code blocks get fenced backticks. Unknown block types: drop or fall back to the rich-text concat.

### Mentions inside rich-text

A rich-text segment with `type == "mention"` carries a sub-typed mention object. Handle:

- `user` mentions → emit Person + ExternalID + IdentifiesPerson + Mentions edge (from the page's Artifact to the Person)
- `page` mentions → emit a LinkedNote edge candidate from this page's Note to the target page's Note (subject to dangling-edge filtering — see `loading-rules.md`)
- `database` mentions → ignore for v1

## Mapping (raw → schema)

Per Notion page imported, emit:

```
ExternalID:
  slug:        ext-notion-<8-hex-of-sha256("notion/" + page_id)>
  source:      notion
  external_id: <page_id>
  createdAt:   page.created_time

Artifact:
  slug:        art-notion-<page_id_no_dashes>
  name:        <title or "(untitled)">
  kind:        document
  source:      notion
  source_ref:  <page_id>
  url:         page.url
  content:     <concatenated block body>
  timestamp:   page.last_edited_time
  createdAt:   page.created_time
  updatedAt:   page.last_edited_time

Note:
  slug:        note-notion-<page_id_no_dashes>
  name:        <title>
  kind:        idea
  content:     <body>
  tags:        <multi_select names + status, deduped>
  createdAt:   page.created_time
  updatedAt:   page.last_edited_time

Edge:
  NoteFromArtifact: <note.slug> -> <artifact.slug>

For each unique user mention or people-property entry:
  Person       (name, relation: "other", timestamps)
  ExternalID   (source: notion, external_id: <notion_user_id>)
  IdentifiesPerson: <external_id.slug> -> <person.slug>
  Mentions:         <artifact.slug>  -> <person.slug>

For each page-mention in rich-text:
  LinkedNote candidate: <note.slug> -> <target_note.slug>
  → filtered at load time per loading-rules.md (drop if target_note slug isn't in the same patch)
```

## Slug derivation (stable, our convention)

| Slug | Algorithm |
|---|---|
| `ext-notion-<hash>` | first 8 hex chars of `sha256("notion/" + page_id)` |
| `art-notion-<id>` | strip hyphens from page UUID |
| `note-notion-<id>` | same as art slug but `note-` prefix |
| `person-<email-slug>` (if email known) | normalize email → kebab |
| `person-<name-slug>-<hash>` (no email) | name + 8-hex sha256 suffix |

Same page_id on a re-run → same slugs → `omnigraph load --mode merge` upserts cleanly.

## Idempotency + `--since`

- No `--since` → re-import every page; merge upserts by slug.
- `--since <iso>` → use the prior successful `SyncRun.completed_at` from `omnigraph read --alias last-sync notion succeeded`. Use database-query's `last_edited_time` filter when scoped; for full-search, sort descending + stop at threshold.
- Emit a `SyncRun` record at the end of the run per `loading-rules.md`.

## Known semi-stable quirks

These have surprised us consistently — call them out for the user, handle them in code:

1. **Child-page inheritance.** Connecting the integration to one parent page grants access to all descendants. Two parent-page connections often fan out to 50+ pages. Tell the user up front; offer a `--max-pages` cap on first runs so a 1,000-page workspace doesn't run for 20 minutes.

2. **Empty titles.** A page with no title returns an empty rich-text array. Use `"(untitled)"` as the `name`; don't error.

3. **People-properties without an `id`.** Skip — we can't make a stable Person slug without a source-native identifier.

4. **Archived pages.** Notion's search returns archived pages by default. Skip on `page.archived == true` unless the user opts in.

5. **Databases mixed in search results.** A "page" filter in search still occasionally returns database objects. Either request only `object: "page"` and skip unexpected types, or emit databases as Artifacts of `kind: "document"` and stop there (no Note derived).

6. **429 rate-limit responses.** Catch, read `Retry-After`, sleep, retry once. Don't crash the import on a single throttle event.

7. **Bot identity vs. workspace.** The bot has its own `user_id` distinct from the workspace name. The bot itself shouldn't be emitted as a Person — it's the import agent, not a human in the user's life.

## Sample I/O

### Sample raw page

```json
{
  "id": "248408d8-60ed-8040-9aaa-edf010320a05",
  "created_time": "2026-04-30T10:00:00.000Z",
  "last_edited_time": "2026-05-08T14:38:00.000Z",
  "url": "https://www.notion.so/It-all-starts-with-a-database-248408d860ed80409aaaedf010320a05",
  "archived": false,
  "parent": {"type": "workspace", "workspace": true},
  "properties": {
    "Name": {"type": "title", "title": [{"plain_text": "It all starts with a database"}]},
    "Tags": {"type": "multi_select", "multi_select": [{"name": "data"}, {"name": "infra"}]},
    "Owner": {"type": "people", "people": [{"id": "abc-123", "name": "Jane Park"}]}
  }
}
```

Body blocks fetched separately:

```json
[
  {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Why typed graphs win"}]}},
  {"type": "paragraph", "paragraph": {"rich_text": [
    {"type": "text", "plain_text": "Long conversation with "},
    {"type": "mention", "mention": {"type": "user", "user": {"id": "abc-123", "name": "Jane Park"}}, "plain_text": "@Jane"},
    {"type": "text", "plain_text": " about this last week."}
  ]}}
]
```

### Expected schema-shaped output (8 records)

```json
{"type": "ExternalID", "data": {"slug": "ext-notion-a1b2c3d4", "source": "notion", "external_id": "248408d8-60ed-8040-9aaa-edf010320a05", "createdAt": "2026-04-30T10:00:00.000Z"}}
{"type": "Artifact",   "data": {"slug": "art-notion-248408d860ed80409aaaedf010320a05", "name": "It all starts with a database", "kind": "document", "source": "notion", "source_ref": "248408d8-60ed-8040-9aaa-edf010320a05", "url": "...", "content": "# Why typed graphs win\n\nLong conversation with @Jane about this last week.", "timestamp": "2026-05-08T14:38:00.000Z", "createdAt": "2026-04-30T10:00:00.000Z", "updatedAt": "2026-05-08T14:38:00.000Z"}}
{"type": "Note",       "data": {"slug": "note-notion-248408d860ed80409aaaedf010320a05", "name": "It all starts with a database", "kind": "idea", "tags": ["data", "infra"], "content": "...", "createdAt": "...", "updatedAt": "..."}}
{"edge": "NoteFromArtifact", "from": "note-notion-248408d860ed80409aaaedf010320a05", "to": "art-notion-248408d860ed80409aaaedf010320a05"}
{"type": "Person",     "data": {"slug": "person-jane-park-a1b2c3d4", "name": "Jane Park", "relation": "other", "createdAt": "...", "updatedAt": "..."}}
{"type": "ExternalID", "data": {"slug": "ext-notion-abc12345", "source": "notion", "external_id": "abc-123", "createdAt": "..."}}
{"edge": "IdentifiesPerson", "from": "ext-notion-abc12345", "to": "person-jane-park-a1b2c3d4"}
{"edge": "Mentions",         "from": "art-notion-248408d860ed80409aaaedf010320a05", "to": "person-jane-park-a1b2c3d4"}
```

One Notion page → 8 schema-shaped records. A typical 200-page workspace produces ~1,500-2,500 records.

## What the agent does NOT need to do

- Build a long-lived CLI script — this is composed inline per session.
- Persist intermediate JSONL to disk unless useful for debugging. Streaming straight into `omnigraph load --mode merge --data -` is fine.
- Re-implement cross-source dispatch logic — that's `loading-rules.md`'s job.
- Reverse-engineer the API. If the spec above doesn't match observed behavior, fetch the relevant docs link and adapt.
