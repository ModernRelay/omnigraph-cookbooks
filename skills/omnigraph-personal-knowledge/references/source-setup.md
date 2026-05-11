# Source setup — per-source recipes

Each recipe assumes you've already asked the user which sources to connect (Phase 2.1 in `SKILL.md`). For each picked source, walk through its recipe one source at a time. Validate before importing. Persist tokens via `keyring`.

Tokens are stored under the service name `omnigraph-pk` with a per-source key (e.g. `notion-token`, `slack-bot-token`). Use `keyring set omnigraph-pk <key>` and `keyring get omnigraph-pk <key>` from Python:

```python
import keyring
keyring.set_password("omnigraph-pk", "notion-token", token)
token = keyring.get_password("omnigraph-pk", "notion-token")
```

---

## Obsidian (no auth)

1. Ask: "Where's your Obsidian vault on disk? (just the path to the folder)"
2. Validate: `Path(value).exists() and Path(value).is_dir()`. Fail fast on missing/invalid.
3. Ask for a workspace label (e.g. `personal-vault`). Keep it short, kebab-case.
4. Run: `python demo/import_obsidian.py --vault $VAULT --workspace-name $WORKSPACE --out /tmp/raw-obsidian.jsonl`
5. Confirm: "Found N markdown files. Importing..."

No token. No keyring entry needed.

---

## Notion (integration token)

1. Open browser: `open https://www.notion.so/my-integrations` (run via Bash).
2. Tell user: "Create an internal integration named 'Omnigraph PK'. Once created, click 'Show' next to the Internal Integration Token and copy it."
3. AskUserQuestion: "Paste your Notion integration token here (starts with `ntn_` or `secret_`)."
4. Validate: round-trip with `notion-client` — list users or search; if it 401s, the token is wrong; if 403s on a specific page, the integration hasn't been added to that page.
5. Once validated, **also tell them**: "Now go to each Notion page or database you want imported, click `···` → `Connections` → add 'Omnigraph PK'."
6. Persist: `keyring set omnigraph-pk notion-token <value>`.
7. Run: `NOTION_TOKEN=$(keyring get omnigraph-pk notion-token) python demo/import_notion.py --workspace-name $WORKSPACE --out /tmp/raw-notion.jsonl`

If the user has a specific database to scope to, accept `--database-id`.

---

## Granola (API token or local export)

Granola's public API surface evolves; check the user's `granola-to-graph` skill if installed for the current endpoint shape.

**API mode** (preferred when available):

1. Ask: "Do you have a Granola API token, or would you rather drop a local export JSON?"
2. If token: validate by hitting `/v1/notes?page_size=1`. If it 200s, persist with `keyring set omnigraph-pk granola-token`.
3. Run: `GRANOLA_TOKEN=... python demo/import_granola.py --workspace-name $WORKSPACE --out /tmp/raw-granola.jsonl`

**Export mode**:

1. Ask: "Drop the path to your Granola export JSON file."
2. Validate: file exists, parses as JSON, has `notes`/`meetings`/`data` array.
3. Run: `python demo/import_granola.py --workspace-name $WORKSPACE --input $PATH --out /tmp/raw-granola.jsonl`

---

## Slack (bot token)

1. Open browser: `open https://api.slack.com/apps`. Tell the user: "Create a new app, name it 'Omnigraph PK', From scratch, pick your workspace."
2. Tell them which scopes to add (OAuth & Permissions → Bot Token Scopes):
   - `channels:history`, `groups:history`, `im:history`, `mpim:history`
   - `channels:read`, `groups:read`, `im:read`, `mpim:read`
   - `users:read`
3. After installing to workspace, copy the Bot Token (`xoxb-...`).
4. AskUserQuestion: "Paste the Bot Token (`xoxb-...`)."
5. Validate: `WebClient(token).auth_test()`. On success, show the team name + bot user.
6. **Important warning**: the bot only sees channels it's been invited to. Tell them: "After this connects, invite `@Omnigraph PK` to any channel you want imported with `/invite @omnigraph-pk`."
7. Persist: `keyring set omnigraph-pk slack-bot-token`.
8. Run: `SLACK_BOT_TOKEN=... python demo/import_slack.py --workspace-name $WORKSPACE --out /tmp/raw-slack.jsonl`

If first run takes a long time, suggest `--channels C123,C456` to limit scope on first sync.

---

## Google Workspace (OAuth)

This is the heaviest setup. Sub-options: Drive, Gmail, Calendar — ask which they want.

1. Tell user: "Google needs a one-time OAuth consent. I'll open Google Cloud Console — create a project (any name), enable Drive/Gmail/Calendar APIs as needed, then create OAuth 2.0 Desktop credentials."
2. Open browser: `open https://console.cloud.google.com/apis/credentials`.
3. AskUserQuestion: "Drop the path to the downloaded `client_secret.json`."
4. Validate: file exists, parses as JSON, has `installed.client_id`.
5. Run the importer with the chosen sub-flags. The first run will pop a browser tab for OAuth; subsequent runs reuse `~/.config/omnigraph-personal-knowledge/google-token.json`:

```bash
python demo/import_google_workspace.py \
  --workspace-name $WORKSPACE \
  --client-secrets $PATH \
  --gmail --drive --gcal \
  --gmail-account "$USER_EMAIL" \
  --out /tmp/raw-google.jsonl
```

For Gmail, **always cap the first run** with `--gmail-max 500` so a 10-year inbox doesn't import in one go. Tell the user: "I'll fetch your most recent 500 emails first. Once we confirm the shape looks right, we can backfill more with another run."

---

## Apple Notes (Mac only)

1. Check platform: `sys.platform == "darwin"`. If not Mac, skip and tell the user.
2. AppleScript needs Notes.app accessibility permission on first run. macOS will prompt automatically — tell the user: "macOS may pop a permission dialog. Click 'OK' for `osascript` to access Notes."
3. Run: `python demo/import_apple_notes.py --workspace-name $WORKSPACE --out /tmp/raw-apple.jsonl`
4. Note: locked notes return placeholder bodies. Tell the user.

---

## LinkedIn (CSV export)

1. Tell user: "LinkedIn doesn't have a personal API. Instead, request an export of your data."
2. Open browser: `open https://www.linkedin.com/mypreferences/d/download-my-data`. Tell them to pick "Connections, Messages, Profile, Positions" at minimum.
3. After they get the email + downloads + unzips, ask: "Drop the path to the unzipped folder."
4. Validate: directory exists, contains at least one of `Connections.csv`, `messages.csv`, `Profile.csv`.
5. Run: `python demo/import_linkedin.py --export-dir $PATH --workspace-name $WORKSPACE --out /tmp/raw-linkedin.jsonl`

---

## WhatsApp (chat export)

1. Tell user: "WhatsApp's only export path is per-chat. Open a chat → ⋯ → Export Chat → Without Media. AirDrop/email it to your Mac."
2. Ask: "Drop the path to a single `.txt` export — or to a folder of them."
3. Validate: path exists, is `.txt` or contains at least one `.txt`.
4. Run: `python demo/import_whatsapp.py --input $PATH --workspace-name $WORKSPACE --out /tmp/raw-whatsapp.jsonl`

For multi-chat ingestion, point at the directory.
