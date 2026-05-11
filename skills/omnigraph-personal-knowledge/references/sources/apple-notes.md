# Source: Apple Notes

Spec for ingesting Apple Notes into the personal-knowledge graph. The agent reads this doc + `../loading-rules.md` + `../identity-resolution.md` and composes the fetch + map code per session.

## About

Apple Notes is a macOS / iOS notes app. The local data lives in an encrypted SQLite store; **the supported scriptable path is AppleScript**, invoked via `osascript`. **Mac-only.** Notes with passcodes are encrypted on disk; their bodies are unavailable.

Use Apple Notes when the user has notes in Apple's app — typically a mix of short captures, shopping lists, and journal entries — and wants them in the graph.

## Authoritative reference

- AppleScript: Apple Notes scripting reference — Notes.app dictionary (open Notes.app, then Script Editor → Open Dictionary → Notes)
- macOS osascript man page — `man osascript`
- Notes feature docs — https://support.apple.com/guide/notes/

No public Apple API for Notes. The AppleScript interface is the only stable scriptable path.

## Setup

No auth. On first run, macOS prompts the user to grant `osascript` (or whatever process invokes it) access to Notes:

1. The agent runs `osascript -e '<small probe>'` (e.g. listing account names).
2. macOS shows a permission dialog. The user clicks **OK**.
3. Subsequent runs reuse the granted permission. If they revoke it, the next run prompts again.

If the agent isn't running on macOS, error early with a clear message; this source is unavailable on Linux/Windows.

## Fetch intent

The agent composes an AppleScript that:

1. Iterates over `accounts of application "Notes"` (e.g. iCloud, On My Mac, possibly others)
2. For each account, iterates `notes of <account>`
3. For each note, captures: account name, folder name (`name of container of n`), note id, name (title), body (HTML), creation date, modification date, password-protected boolean
4. Emits one record per note using a custom field separator (ASCII record-separator `\x1e` between fields, unit-separator `\x1f` between records) so the body's HTML can include any character without breaking parsing
5. Returns the full string

The agent reads stdout, splits on the unit separator, then on the field separator, and yields one parsed record per note.

For `--since`, filter client-side on `modification_date`.

For `--account <name>`, filter inside the AppleScript by matching `name of acc`.

## Field extraction intent

| What we want | Where to look |
|---|---|
| Account | iterate `accounts of application "Notes"`; capture `name of acc` |
| Folder | `name of container of n` |
| Note id | `id of n` (a long URI-like string, stable across renames) |
| Title | `name of n` |
| Body | `body of n` (HTML; render to plaintext by stripping tags) |
| Created | `creation date of n` (AppleScript date — format to ISO) |
| Modified | `modification date of n` |
| Locked | `password protected of n` (boolean) |

Locked notes return a body placeholder (Apple's word, not a real body). The agent should emit the note with `is_locked: true` in `meta` and an explanatory `content` string ("(locked note — body unavailable)") rather than skip — the user wants to know the note exists.

### HTML → plaintext rendering

Apple Notes stores bodies as HTML. The agent should:

- Replace `<br>` and `</p>` with newlines
- Strip remaining tags
- Unescape HTML entities (`&nbsp;` → space, `&amp;` → `&`, etc.)
- Collapse multi-blank-line runs

The output goes into `Note.content` and `Artifact.content`.

## Mapping (raw → schema)

Per Apple Note imported, emit:

```
ExternalID:
  slug:        ext-apple-notes-<8-hex-of-sha256("apple-notes/" + note_id)>
  source:      apple-notes
  external_id: <note_id>
  createdAt:   <created_at>

Artifact:
  slug:        art-apple-notes-<sanitized_note_id_tail>
  name:        <title>
  kind:        document
  source:      apple-notes
  source_ref:  <note_id>
  content:     <plaintext body>
  timestamp:   <updated_at>
  createdAt:   <created_at>
  updatedAt:   <updated_at>

Note:
  slug:        note-apple-notes-<sanitized_note_id_tail>
  name:        <title>
  kind:        idea
  content:     <plaintext body>
  createdAt:   <created_at>
  updatedAt:   <updated_at>

Edge:
  NoteFromArtifact: <note.slug> -> <artifact.slug>
```

Apple Notes doesn't expose structured mentions or links, so no Person extraction by default. The agent could optionally regex `@mention` patterns from the body, but for v1 keep it simple — Notes is a freeform jot tool.

## Slug derivation (stable, our convention)

| Slug | Algorithm |
|---|---|
| `ext-apple-notes-<hash>` | first 8 hex of `sha256("apple-notes/" + note_id)` |
| `art-apple-notes-<id>` | use the tail segment of the note_id (after the last `/`), sanitized |
| `note-apple-notes-<id>` | same as art slug but `note-` prefix |

Same note_id on a re-run → same slugs.

## Idempotency + `--since`

- No `--since` → re-dump every accessible note. Cheap (AppleScript walks the local store; no network).
- `--since <iso>` → filter client-side on `modification_date >= since`.
- Emit a `SyncRun` per `loading-rules.md`.

## Known semi-stable quirks

1. **Permission prompt on first run.** macOS shows an "osascript wants to control Notes" dialog. The user must click OK. If they decline, the AppleScript returns an empty result silently. Detect zero records on the first run and prompt the user to check their Security & Privacy settings.

2. **Locked notes are opaque.** Notes protected with a password have encrypted bodies. AppleScript returns an empty / placeholder body. Mark them and move on.

3. **HTML body, not Markdown.** Notes stores rich text as HTML, not Markdown. The plaintext rendering above is sufficient for v1; full HTML-to-Markdown conversion is a v1.1 enhancement if needed.

4. **Field separator choice.** The default `osascript` output is a string. We use `\x1e` and `\x1f` as field/record separators because they're vanishingly unlikely to appear in note bodies. If they ever do, the parser will produce malformed records — defensive: handle parse errors per-record, skip + log.

5. **Account scoping.** Some users have multiple Apple ID accounts attached (work + personal). Default: import all. Allow `--account "iCloud"` to scope to one.

6. **Notes folders.** Folders are flat strings (no nested hierarchy via AppleScript). Capture as `folder` field in `meta`; we don't model them as graph nodes for v1.

7. **iOS-only notes.** Notes created on iOS sync to the Mac via iCloud. If iCloud sync is paused or the user is offline, recent iOS notes won't appear. Tell the user to ensure Notes is signed in and synced.

## Sample I/O

### Sample raw record (one note, after AppleScript parsing)

```
account:    iCloud
folder:     Notes
note_id:    x-coredata://[...]/ICNote/p3251
title:      Spanish conjunctions
created:    2026-03-15T12:00:00Z
updated:    2026-04-30T08:00:00Z
locked:     false
body_html:  <div><h2>Para vs por</h2><p>Para = destination. Por = cause.</p></div>
```

### Expected schema-shaped output

```json
{"type": "ExternalID", "data": {"slug": "ext-apple-notes-c5e1f0a3", "source": "apple-notes", "external_id": "x-coredata://[...]/ICNote/p3251", "createdAt": "2026-03-15T12:00:00Z"}}
{"type": "Artifact",   "data": {"slug": "art-apple-notes-p3251", "name": "Spanish conjunctions", "kind": "document", "source": "apple-notes", "content": "## Para vs por\n\nPara = destination. Por = cause.", "timestamp": "2026-04-30T08:00:00Z", ...}}
{"type": "Note",       "data": {"slug": "note-apple-notes-p3251", "name": "Spanish conjunctions", "kind": "idea", "content": "...", "createdAt": "2026-03-15T12:00:00Z", "updatedAt": "2026-04-30T08:00:00Z"}}
{"edge": "NoteFromArtifact", "from": "note-apple-notes-p3251", "to": "art-apple-notes-p3251"}
```

One note → 4 records. A typical 200-note Apple Notes account produces ~800 records.

## What the agent does NOT need to do

- Read the local SQLite database directly — the AppleScript path is the supported one, and direct SQLite access breaks on macOS updates and risks corruption.
- Decrypt locked notes — impossible without the user's passcode, and explicitly out of scope.
- Convert HTML to Markdown beyond the plaintext rendering above. Bare text is enough for `Note.content`.
- Capture image attachments embedded in note bodies — v1 keeps it text-only.
