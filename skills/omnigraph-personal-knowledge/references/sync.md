# Sync — incremental refresh contract

The user invokes you with "sync my graph", "pull updates", "refresh personal-knowledge", etc. Steps:

## 1. Look up last sync per source

For each connected source (you know which ones from the keyring entries), run:

```
omnigraph read --alias last-sync --source <source>
```

If the result is empty (no prior `SyncRun`), treat that source as a first-import for the next step (omit `--since`).

If it returns a row, use `completed_at` as `--since` for the importer.

## 2. Run importers with --since

Source support for `--since`:

| Source | --since respected? | Notes |
|---|---|---|
| Obsidian | yes (mtime filter) | Cheap |
| Notion | yes (`last_edited_time`) | API-side filter |
| Granola | yes (`updated_after`) | API-side filter |
| Slack | yes (`oldest` ts) | Per-channel; cursor-paginated |
| Gmail | yes (`after:` query) | Server-side `q` |
| Drive | yes (`modifiedTime`) | Server-side |
| Calendar | yes (`updatedMin`) | Server-side |
| Apple Notes | client-side filter | Full re-dump, then filter |
| LinkedIn | n/a | User re-requests export periodically |
| WhatsApp | n/a | User re-exports periodically |

For LinkedIn and WhatsApp, ask the user if they have a fresh export to drop in; if not, skip.

## 3. Transform + load

Same as first-run:

```bash
python demo/transform.py /tmp/raw-*.jsonl --out /tmp/patch.jsonl
omnigraph load --data /tmp/patch.jsonl --mode merge "$REPO"
```

The transform emits a fresh `SyncRun` record with current timestamp, so the next sync's `--since` query will pick it up.

## 4. Slim delta report (instead of full headline)

After incremental load, present a delta-shaped summary:

```
Sync complete
─────────────
+ {N_NEW_NOTES} new notes ({source_breakdown})
+ {N_NEW_ARTIFACTS} new artifacts
+ {N_NEW_PERSONS} new persons (suggest dedup if any)
+ {N_NEW_CONVERSATIONS} new conversations
```

Plus the most surprising delta — a person/topic/artifact that newly cleared a threshold ("Marcus is suddenly your most-mentioned person this week", etc.).

If new persons appeared that look like cross-source duplicates of existing ones, offer to run a quick dedup wizard pass (just the new candidates, not a full re-scan).

## Failure handling

- **Source's last sync was failed**: run as a fresh sync (no `--since`); the failed `SyncRun` won't satisfy the `status: succeeded` filter on `last-sync`.
- **Token expired** (Google OAuth, Notion rotated): catch in validation step; re-run the credential capture from `source-setup.md`.
- **Partial run**: if 5 of 8 importers succeed and 3 fail, transform + load the 5 that worked, record `status: partial` in the SyncRun (the importer should signal this), and report which sources failed.

## Scheduling

If the user wants hands-free sync, they can chain this skill into the existing `schedule` skill. Suggest: "Want to run this nightly at 3am?" → if yes, hand off the schedule action with the sync command. Don't try to install cron from this skill — that's the schedule skill's job.
