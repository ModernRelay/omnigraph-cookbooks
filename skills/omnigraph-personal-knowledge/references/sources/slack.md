# Source: Slack

Spec for ingesting a Slack workspace's accessible messages into the personal-knowledge graph. The agent reads this doc + `../loading-rules.md` + `../identity-resolution.md` and composes the fetch + map code per session.

## About

Slack exposes a Web API behind a Bot User OAuth Token. A bot can only see messages in channels (or DMs / MPIMs) it has been **explicitly invited to** — there is no "see everything" mode without enterprise admin scope.

Use Slack when the user wants their direct messages, group DMs, and invited-channel history in the graph.

## Authoritative reference

- Slack API home — https://api.slack.com/web
- `auth.test` (token validation) — https://api.slack.com/methods/auth.test
- `conversations.list` (enumerate channels) — https://api.slack.com/methods/conversations.list
- `conversations.history` (channel messages) — https://api.slack.com/methods/conversations.history
- `users.list` / `users.info` — https://api.slack.com/methods/users.list
- Rate limits — https://api.slack.com/apis/rate-limits
- OAuth scopes reference — https://api.slack.com/scopes

When the spec below doesn't match observed behavior, fall back to these.

## Auth + setup ritual

1. Open `https://api.slack.com/apps` in the user's browser.
2. Have the user create a new app (From Scratch), name it (e.g. `Omnigraph PK`), pick their workspace.
3. Under **OAuth & Permissions** → **Bot Token Scopes**, add the following (all are read-only):
   - `channels:history`, `groups:history`, `im:history`, `mpim:history`
   - `channels:read`, `groups:read`, `im:read`, `mpim:read`
   - `users:read`
4. **Install to workspace** (or **Reinstall** if scopes were changed). Allow.
5. Capture the **Bot User OAuth Token** (starts with `xoxb-`). User OAuth tokens (`xoxp-`) are the wrong kind; explain the difference if the user pastes the wrong one.
6. Validate with `auth.test`. 200 with `ok: true` → valid; the response carries the bot's `user_id`, `team`, and `team_id` — capture them.
7. Tell the user to invite the bot to channels they want imported: in each channel, `/invite @<bot_handle>`. The handle is the `user` field returned by `auth.test`, lowercase with underscores. Without invites, the bot sees zero messages — flag this clearly.
8. Persist via `keyring` under service `omnigraph-pk`, key `slack-bot-token`.

## Fetch intent

The agent needs:

1. **User cache** — call `users.list` once at the start (paginated) and cache `user_id → {name, real_name, profile}` for the run. Used for resolving message senders and mentioned users.
2. **Conversation enumeration** — `conversations.list` with `types=public_channel,private_channel,mpim,im` (paginated). Each result is a conversation the bot can see.
3. **Per-conversation message history** — `conversations.history` for each accessible channel, paginated. `oldest=<unix_ts>` parameter for `--since` filtering. The bot may get `not_in_channel` errors for channels it hasn't been invited to — log and skip, don't crash.

## Field extraction intent

| What we want | Where to look |
|---|---|
| Channel id | `channel.id` |
| Channel name | `channel.name` (for channels); for DMs/MPIMs, use `is_im`/`is_mpim` flags and resolve via `user_cache` |
| DM/group/channel type | `channel.is_im`, `channel.is_mpim`, default to channel otherwise |
| Message timestamp | `message.ts` (Slack's "ts" is Unix-seconds-with-fractional, also serves as message id within a channel) |
| Thread root | `message.thread_ts` (if set, this message is in a thread; the root has `ts == thread_ts`) |
| Sender user_id | `message.user` (or `message.bot_id` for bot messages) |
| Sender name | `user_cache[user_id].profile.real_name` or `.name` |
| Text body | `message.text` |
| Subtype | `message.subtype` (e.g. `channel_join`, `message_changed`) — skip system events or mark them distinctly |
| Reactions, files | `message.reactions`, `message.files` — capture if useful but not required for v1 |
| Permalink | `message.permalink` (sometimes only available via `chat.getPermalink`) |

User mentions inside text show up as `<@U12345678>` — the agent can resolve them via `user_cache` to emit Person + Mentions edges.

## Mapping (raw → schema)

Per Slack message imported, emit:

```
ExternalID:
  slug:        ext-slack-<8-hex-of-sha256("slack/" + channel_id + "/" + ts)>
  source:      slack
  external_id: <channel_id> + "/" + <ts>
  createdAt:   <timestamp>

Artifact:
  slug:        art-slack-<channel_id>-<sanitized_ts>
  name:        truncated text (first 80 chars) or "(empty message)"
  kind:        message
  source:      slack
  source_ref:  <channel_id>/<ts>
  content:     <full text>
  timestamp:   <iso datetime from ts>
  createdAt:   <timestamp>
  updatedAt:   <timestamp>

Conversation (per channel, deduped per loading-rules.md):
  slug:         conv-slack-<channel_id>-<hash>
  external_id:  <channel_id>
  kind:         dm | group | channel
  source:       slack
  name:         <channel.name or null for DMs>
  createdAt:    <earliest message timestamp>
  updatedAt:    <latest message timestamp>

Edge:
  InConversation: <artifact.slug> -> <conversation.slug>

For each unique sender / mentioned user:
  Person          (name from cache, relation: "other")
  ExternalID      (source: slack, external_id: <user_id>)
  IdentifiesPerson:    <external_id.slug> -> <person.slug>
  ArtifactFromPerson:  <artifact.slug>    -> <sender.slug>
  ConversationWith:    <conversation.slug> -> <sender.slug>
  Mentions:            <artifact.slug>    -> <mentioned_person.slug>  (for @-mentions only)
```

## Slug derivation (stable, our convention)

| Slug | Algorithm |
|---|---|
| `ext-slack-<hash>` | first 8 hex of `sha256("slack/" + channel_id + "/" + ts)` for messages; `sha256("slack/" + user_id)` for users |
| `art-slack-<channel_id>-<ts>` | concatenated channel + sanitized ts |
| `conv-slack-<channel_id>-<hash>` | channel id + 8-hex sha256 suffix |
| `person-<name-slug>-<hash>` | sender's real_name slugified + 8-hex hash (Slack rarely exposes email) |

Same channel + ts → same Artifact slug. Re-runs upsert cleanly.

## Idempotency + `--since`

- No `--since` → re-pull every accessible channel's full history. Expensive for large workspaces — warn the user, consider `--channels C123,C456` to scope.
- `--since <iso>` → pass `oldest=<unix_ts>` to `conversations.history`. Server-side filter.
- Emit `SyncRun` per `loading-rules.md`.

## Known semi-stable quirks

1. **`not_in_channel` errors are not real failures.** They mean the bot hasn't been invited to that channel. Log to stderr, skip, continue with the next channel. Don't crash the run.

2. **Rate limits are tier-based.** `conversations.history` is Tier 3 (~50 calls/min). Throttle to ~1.1 sec between calls per channel; on 429, honor `Retry-After` and back off.

3. **Slack's `ts` is the message ID.** Two messages in the same channel with the same `ts` is impossible; we use `<channel_id>/<ts>` as the stable identifier.

4. **Bot users vs human users.** `message.user` is set for human messages; `message.bot_id` for app/integration messages. For v1, the agent can emit Persons for human senders only and skip bot messages (`subtype: bot_message`) — they're rarely interesting and pollute the Person table.

5. **DMs return one human + the bot.** A 1:1 DM between the bot and a user surfaces as a conversation; the human is the only other participant. Mark `is_dm: true` on the Conversation.

6. **`channel_join` subtype messages.** Slack auto-emits "X has joined the channel" — these add noise. Skip or mark as `Artifact.kind: message, subtype: channel_join` so they can be filtered downstream.

7. **Mentions inside text use raw user IDs.** `<@U12345678>` not `@username`. Resolve via `user_cache`.

8. **Token kind matters.** A `xoxp-` (User OAuth) token validates with `auth.test` but lacks the bot-scoped permissions needed for `conversations.history`. If the user pastes a `xoxp-`, redirect them to the **Bot User OAuth Token** in the same OAuth page.

## Sample I/O

### Sample raw message (after channel + user_cache fetched)

```json
{
  "type": "message",
  "user": "U0AJXB128BH",
  "text": "morning CRM check — May 11, 2026",
  "ts": "1778485246.831879",
  "team": "T08EBKR02RK"
}
```

Channel: `{id: "C0B3CKCDT32", name: "crm-reminders", is_im: false, is_mpim: false}`
User from cache: `{id: "U0AJXB128BH", real_name: "Jorge Campo"}`

### Expected schema-shaped output

```json
{"type": "ExternalID", "data": {"slug": "ext-slack-7c9e1a2b", "source": "slack", "external_id": "C0B3CKCDT32/1778485246.831879", ...}}
{"type": "Artifact",   "data": {"slug": "art-slack-c0b3ckcdt32-1778485246-831879", "name": "morning CRM check — May 11, 2026", "kind": "message", "source": "slack", "content": "morning CRM check — May 11, 2026", "timestamp": "2026-05-11T07:40:46.831Z", ...}}
{"type": "Conversation", "data": {"slug": "conv-slack-c0b3ckcdt32-07989f93", "external_id": "C0B3CKCDT32", "kind": "channel", "source": "slack", "name": "crm-reminders", ...}}
{"edge": "InConversation", "from": "art-slack-c0b3ckcdt32-1778485246-831879", "to": "conv-slack-c0b3ckcdt32-07989f93"}
{"type": "Person",     "data": {"slug": "person-jorge-campo-a1b2c3d4", "name": "Jorge Campo", "relation": "other", ...}}
{"type": "ExternalID", "data": {"slug": "ext-slack-9e1f2a3b", "source": "slack", "external_id": "U0AJXB128BH", ...}}
{"edge": "IdentifiesPerson",   "from": "ext-slack-9e1f2a3b", "to": "person-jorge-campo-a1b2c3d4"}
{"edge": "ArtifactFromPerson", "from": "art-slack-c0b3ckcdt32-1778485246-831879", "to": "person-jorge-campo-a1b2c3d4"}
{"edge": "ConversationWith",   "from": "conv-slack-c0b3ckcdt32-07989f93", "to": "person-jorge-campo-a1b2c3d4"}
```

One message with one sender → 8 records. After dedupe-within-run, multiple messages from the same channel/sender collapse the Conversation + Person + edges to single instances.

## What the agent does NOT need to do

- Build a long-lived CLI script — composed inline per session.
- Fetch reaction emoji metadata or file attachments unless explicitly asked.
- Resolve every cross-workspace shared channel — for v1, treat each shared channel as belonging to the workspace where the bot was installed.
- Re-implement dedup-within-run — `loading-rules.md` handles collapsing repeated Conversation/Person emissions to single slugs.
