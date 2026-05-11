# personal-knowledge — raw importers (CLI)

The CLI surface for the cookbook's importers. The `omnigraph-personal-knowledge` skill orchestrates this whole pipeline; this README documents the underlying commands for environments without an agentskills.io-compatible runtime, or for direct invocation in scripts.

Each importer reads from one source and emits rich JSONL: every field the source provides, one record per line. Re-running with the same input produces records with the same `id`, so downstream `omnigraph load --mode merge` upserts cleanly.

After running an importer (or several), pipe the raw output through `transform.py` to produce schema-shaped JSONL ready for `omnigraph load`.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Pipeline shape

```
importer (per source)        transform.py                  omnigraph load
──────────────────────  →    ─────────────────────────  →  ──────────────
raw JSONL with all the      schema-shaped JSONL ready      upserts via
fields the source provides  for omnigraph load --merge     stable slugs
```

## Per-source CLI reference

### Obsidian
```bash
python import_obsidian.py \
  --vault ~/MyVault \
  --workspace-name my-vault \
  [--since 2026-04-01T00:00:00Z] \
  --out raw-obsidian.jsonl
```
Walks `*.md` files. No auth. `--since` filters by file mtime.

### Notion
```bash
NOTION_TOKEN=ntn_xxx python import_notion.py \
  --workspace-name my-notion \
  [--database-id <id>] \
  [--since 2026-04-01T00:00:00Z] \
  --out raw-notion.jsonl
```
Create an integration at `notion.so/my-integrations`. Add it to pages/databases via Connections.

### Granola
```bash
# API mode:
GRANOLA_TOKEN=xxx python import_granola.py \
  --workspace-name my-granola \
  [--since 2026-04-01T00:00:00Z] \
  --out raw-granola.jsonl

# Local export mode:
python import_granola.py \
  --workspace-name my-granola \
  --input ./granola-export.json \
  --out raw-granola.jsonl
```

### Slack
```bash
SLACK_BOT_TOKEN=xoxb-xxx python import_slack.py \
  --workspace-name my-slack \
  [--channels C111,C222] \
  [--since 2026-04-01T00:00:00Z] \
  --out raw-slack.jsonl
```
Create a Slack app at `api.slack.com/apps`, add scopes (`*:history`, `*:read`, `users:read`), install to workspace, copy the bot token. Invite the bot to any channels you want imported.

### Google Workspace
```bash
GOOGLE_CLIENT_SECRETS=./client_secret.json python import_google_workspace.py \
  --workspace-name my-google \
  --gmail --drive --gcal \
  --gmail-account "you@example.com" \
  [--gmail-max 500] \
  [--since 2026-04-01T00:00:00Z] \
  --out raw-google.jsonl
```
First run pops a browser for OAuth consent. Token cached at `~/.config/omnigraph-personal-knowledge/google-token.json`.

### Apple Notes (Mac only)
```bash
python import_apple_notes.py \
  --workspace-name my-apple-notes \
  [--account "iCloud"] \
  [--since 2026-04-01T00:00:00Z] \
  --out raw-apple.jsonl
```
Uses `osascript`. Locked notes return placeholder bodies.

### LinkedIn (CSV export)
```bash
python import_linkedin.py \
  --export-dir ~/Downloads/Basic_LinkedInDataExport_2026-05-08 \
  --workspace-name my-linkedin \
  --out raw-linkedin.jsonl
```
Request export from `linkedin.com/mypreferences/d/download-my-data`. Unzip, point at the directory.

### WhatsApp (chat export)
```bash
python import_whatsapp.py \
  --input ~/Downloads/whatsapp-jane.txt \
  --workspace-name my-whatsapp \
  --out raw-whatsapp.jsonl
```
Or point at a directory of `.txt` exports. Both iOS (bracketed) and Android (dash) formats are recognized.

## Transform raw → schema-shaped

```bash
python transform.py raw-*.jsonl --out patch.jsonl
# or via stdin:
cat raw-*.jsonl | python transform.py - --out patch.jsonl
```

Output: one record per line, either `{"type": "TypeName", "data": {...}}` (node) or `{"edge": "EdgeName", "from": "src-slug", "to": "tgt-slug"}` (edge). Plus a trailing `SyncRun` summary record.

## Load into Omnigraph

```bash
cd ..  # back to personal-knowledge/

REPO=s3://omnigraph-local/repos/personal-knowledge
omnigraph init --schema ./schema.pg "$REPO"   # first time only
omnigraph load --data /tmp/patch.jsonl --mode merge "$REPO"
```

## Idempotency

Every importer produces stable `id` values. Re-running and re-loading is safe — `--mode merge` upserts. Stable IDs come from source-native identifiers (Notion `page_id`, Slack `channel/ts`, file relative paths, etc.) hashed where needed.

## What this does NOT do

- **No write-back** — these are read-only.
- **No webhooks** — pull-only. For real-time, set up a separate sync process.
- **No embeddings** — Chunk records have an `embedding: Vector(3072) @embed("text") @index` field but the embed pipeline is separate (`omnigraph embed` CLI, post-load).
