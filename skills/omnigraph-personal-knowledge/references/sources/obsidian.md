# Source: Obsidian

Spec for ingesting an Obsidian vault into the personal-knowledge graph. The agent reads this doc + `../loading-rules.md` + `../identity-resolution.md` and composes the fetch + map code per session.

## About

Obsidian is a Markdown-file-on-disk app. A "vault" is a directory of `.md` files, often with YAML frontmatter, inline `#tags`, and `[[wiki-links]]` between notes. No API, no auth — the agent walks the filesystem directly.

Use Obsidian when the user has a Markdown vault and wants its content in the graph.

## Authoritative reference

Obsidian's link/tag/frontmatter conventions are stable but documented across the user-facing help, not a strict spec. Useful references:

- Obsidian help: linking notes — https://help.obsidian.md/Linking+notes+and+files/Internal+links
- Obsidian help: tags — https://help.obsidian.md/Editing+and+formatting/Tags
- Obsidian help: properties (frontmatter) — https://help.obsidian.md/Editing+and+formatting/Properties
- Markdown frontmatter convention — YAML between leading `---` lines

When the spec below doesn't match observed vault behavior (e.g. a plugin introduced a new link syntax), fall back to these references.

## Setup

No auth. The agent needs only the absolute path to the vault root, supplied by the user. Validate that:

- Path exists and is a directory
- Contains at least one `.md` file (warn the user if zero)
- Is readable

Skip these subdirectories during the walk (Obsidian-internal or VCS noise):

```
.obsidian   .trash   .git   .github   node_modules
```

Plus any directory starting with `.` — these are dotfiles by convention.

## Fetch intent

The agent needs:

1. **A recursive walk** of all `.md` files under the vault root (skipping the directories above).
2. **For each file**, its frontmatter (if present), body, and filesystem timestamps (`mtime` for `updated`, `birthtime` for `created` on macOS).
3. **Time filtering** for `--since`: skip files whose `mtime < since`. Cheap because the agent doesn't need to read content to decide.

The walk is sequential; vaults are small enough that streaming the filesystem is fine.

## Field extraction intent

A typical Obsidian markdown file has:

| What we want | Where to look |
|---|---|
| Title | Frontmatter `title:` → first H1 in body → filename (in that order of preference) |
| Body | Everything after frontmatter (or the whole file if no frontmatter) |
| Tags | Frontmatter `tags:` (string or array) ∪ inline `#tag` matches in body |
| Wiki-links | `[[Target]]` and `[[Target\|Alias]]` patterns — parse with a regex |
| External links | Markdown `[text](http(s)://...)` patterns |
| Created/updated | Frontmatter `created`/`updated` keys (or aliases) → fallback to filesystem times |
| Headings | `^#{1,6}\s+text` matches — useful for body structure but optional in output |

For frontmatter parsing the agent should follow YAML conventions; common keys for dates include `created`, `created_at`, `createdAt`, `date`; for updated: `updated`, `updated_at`, `updatedAt`, `modified`, `last_modified`. Coerce date-only values to start-of-day UTC.

### Note kind heuristic

Map to `Note.kind` enum as follows:

- Frontmatter `type:` field present and matches an enum value (`idea`, `reflection`, `insight`, `quote`, `dream`, `journal`, `principle`) → use it
- Filename starts with `daily` or matches `YYYY-MM-DD` → `journal`
- Otherwise → `idea` (the safe default)

## Mapping (raw → schema)

Per markdown file imported, emit:

```
ExternalID:
  slug:        ext-obsidian-<8-hex-of-sha256("obsidian/" + relative_path)>
  source:      obsidian
  external_id: <relative_path>             # vault-relative, posix-separator
  createdAt:   <created_at>

Artifact:
  slug:        art-obsidian-<slug(relative_path)>-<hash>
  name:        <title>
  kind:        document
  source:      obsidian
  source_ref:  <relative_path>
  content:     <raw markdown body>
  timestamp:   <updated_at>
  createdAt:   <created_at>
  updatedAt:   <updated_at>

Note:
  slug:        note-obsidian-<slug(relative_path)>-<hash>
  name:        <title>
  kind:        <kind heuristic>
  content:     <body>
  tags:        <union of frontmatter tags + inline #tags, deduped>
  createdAt:   <created_at>
  updatedAt:   <updated_at>

Edge:
  NoteFromArtifact: <note.slug> -> <artifact.slug>

For each wiki-link [[Target]] in body:
  LinkedNote candidate: <note.slug> -> note-obsidian-<slug(target+".md")>-<hash>
  → filtered at load time per loading-rules.md
```

Wiki-link targets often omit the `.md` extension — normalize by appending `.md` before slugifying. They can also reference subfolder paths (`[[people/ragnor]]`).

## Slug derivation (stable, our convention)

| Slug | Algorithm |
|---|---|
| `ext-obsidian-<hash>` | first 8 hex of `sha256("obsidian/" + relative_path)` |
| `art-obsidian-<path-slug>-<hash>` | kebab-cased relative path (no `.md`) + 8-hex `sha256(workspace/relative_path)` suffix for uniqueness |
| `note-obsidian-<path-slug>-<hash>` | same as art slug but `note-` prefix |

Same vault path on a re-run → same slugs → `omnigraph load --mode merge` upserts cleanly. Renaming or moving a file changes its slug; treat renames as new notes (or implement a rename detector in v2).

## Idempotency + `--since`

- No `--since` → re-walk every file; merge upserts by slug.
- `--since <iso>` → skip files where `mtime < since`. Per-file filter, no I/O for skipped files beyond stat.
- Emit a `SyncRun` record at the end of the run per `loading-rules.md`.

## Known semi-stable quirks

1. **Daily-note convention.** Files named `YYYY-MM-DD.md` or `daily-YYYY-MM-DD.md` are journals by convention. The kind heuristic catches this; the agent should preserve it.

2. **Frontmatter dialects vary.** Some users write `tags: [a, b]` (YAML inline list); some `tags:\n  - a\n  - b` (block list); some write a single string `tags: a b c` (space-separated). Tolerate all three.

3. **Inline tags inside code blocks.** A `#tag` inside a fenced code block isn't actually a tag — it's literal text. For v1, accept the false positives (rare; tagging in code is unusual). For stricter parsing, strip fenced code blocks before extracting inline tags.

4. **Wiki-link target ambiguity.** `[[Notes]]` could refer to `Notes.md` at the vault root or `subfolder/Notes.md`. Obsidian itself uses a shortest-unique-match algorithm. For v1, normalize to `Target.md` at root; if dangling-edge filtering drops it, the agent can re-attempt with subfolder scan in v2.

5. **Embeds vs links.** `![[Target]]` is an embed; `[[Target]]` is a link. For v1, treat both the same — they reference another note.

6. **Vault-relative aliasing in `[[Target|Alias]]`.** Capture the alias text but don't use it for the target slug — the target is the part before the pipe.

## Sample I/O

### Sample raw record (one markdown file)

```yaml
---
title: PK vision
tags: [pk, agents, context]
created: 2026-05-07
type: insight
---

# PK vision

Agents writing into governed context is the next phase. See [[note-omnigraph]] and the [manifesto](https://modernrelay.com/manifesto).

#pk #agents
```

### Expected schema-shaped output

```json
{"type": "ExternalID", "data": {"slug": "ext-obsidian-7de1eaba", "source": "obsidian", "external_id": "pk-vision.md", "createdAt": "2026-05-07T00:00:00.000Z"}}
{"type": "Artifact",   "data": {"slug": "art-obsidian-pk-vision-a277de95", "name": "PK vision", "kind": "document", "source": "obsidian", "source_ref": "pk-vision.md", "content": "# PK vision\n\nAgents writing into governed context...", "timestamp": "2026-05-07T00:00:00.000Z", "createdAt": "2026-05-07T00:00:00.000Z", "updatedAt": "2026-05-07T00:00:00.000Z"}}
{"type": "Note",       "data": {"slug": "note-obsidian-pk-vision-a277de95", "name": "PK vision", "kind": "insight", "tags": ["pk", "agents", "context"], "content": "...", "createdAt": "...", "updatedAt": "..."}}
{"edge": "NoteFromArtifact", "from": "note-obsidian-pk-vision-a277de95", "to": "art-obsidian-pk-vision-a277de95"}
{"edge": "LinkedNote",       "from": "note-obsidian-pk-vision-a277de95", "to": "note-obsidian-note-omnigraph-md-6bad1eb3"}
```

(The LinkedNote edge survives or gets dropped at load time depending on whether `note-obsidian-note-omnigraph-md-6bad1eb3` exists in the same patch — see `loading-rules.md`.)

One markdown file → ~5 records (more if multiple wiki-links). A 200-file vault produces ~1,000 records.

## What the agent does NOT need to do

- Build a long-lived CLI script — composed inline per session.
- Read files outside the vault root — Obsidian is strictly the vault tree.
- Re-implement cross-source dispatch logic — `loading-rules.md` handles dedup and dangling-edge filtering.
- Parse Markdown beyond what's needed for the extraction intent above. Don't render to HTML; just keep the body string.
