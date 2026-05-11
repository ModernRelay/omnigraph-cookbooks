#!/usr/bin/env python3
"""
Pull Slack messages from accessible channels (DMs, MPIMs, public, private with bot in)
and emit raw JSONL — one record per message.

Setup:
    1. Create a Slack app at https://api.slack.com/apps
    2. Add scopes: channels:history, groups:history, im:history, mpim:history,
                   channels:read, groups:read, im:read, mpim:read, users:read
    3. Install to workspace, copy the bot token (xoxb-...)
    4. Invite the bot to any channels you want imported

Usage:
    SLACK_BOT_TOKEN=xoxb-... python import_slack.py --workspace-name my-slack
    SLACK_BOT_TOKEN=xoxb-... python import_slack.py --workspace-name my-slack --since 2026-04-01T00:00:00Z --out raw.jsonl

Exit codes: 0 on success, 1 on argument / auth / rate-limit error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    sys.stderr.write("ERROR: slack-sdk not installed.\n  pip install -r requirements.txt\n")
    sys.exit(1)


PAGE_SIZE = 200
THROTTLE_SECONDS = 1.1  # tier-3 endpoint limit


def iso_to_ts(iso: str) -> float:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def slack_ts_to_iso(slack_ts: str) -> str:
    secs = float(slack_ts)
    return dt.datetime.fromtimestamp(secs, tz=dt.timezone.utc).isoformat()


def list_user_cache(client: WebClient) -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    cursor: str | None = None
    while True:
        time.sleep(THROTTLE_SECONDS)
        kwargs: dict[str, Any] = {"limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.users_list(**kwargs)
        for u in resp.get("members") or []:
            cache[u["id"]] = u
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    return cache


def list_conversations(client: WebClient) -> Iterable[dict[str, Any]]:
    cursor: str | None = None
    while True:
        time.sleep(THROTTLE_SECONDS)
        kwargs: dict[str, Any] = {
            "limit": PAGE_SIZE,
            "types": "public_channel,private_channel,mpim,im",
        }
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_list(**kwargs)
        for c in resp.get("channels") or []:
            yield c
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break


def iter_channel_messages(client: WebClient, channel_id: str, oldest: str | None) -> Iterable[dict[str, Any]]:
    cursor: str | None = None
    while True:
        time.sleep(THROTTLE_SECONDS)
        kwargs: dict[str, Any] = {"channel": channel_id, "limit": PAGE_SIZE}
        if cursor:
            kwargs["cursor"] = cursor
        if oldest:
            kwargs["oldest"] = oldest
        try:
            resp = client.conversations_history(**kwargs)
        except SlackApiError as exc:
            if exc.response.get("error") == "ratelimited":
                retry = int(exc.response.headers.get("Retry-After", "30"))
                sys.stderr.write(f"slack: rate-limited, sleeping {retry}s\n")
                time.sleep(retry)
                continue
            raise
        for m in resp.get("messages") or []:
            yield m
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break


def build_record(
    message: dict[str, Any],
    channel: dict[str, Any],
    workspace_name: str,
    user_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    user_id = message.get("user") or message.get("bot_id") or ""
    user = user_cache.get(user_id, {})
    user_name = (user.get("profile") or {}).get("real_name") or user.get("name") or user_id
    is_dm = bool(channel.get("is_im"))
    is_mpim = bool(channel.get("is_mpim"))
    channel_name = channel.get("name") or (channel.get("user") and user_cache.get(channel["user"], {}).get("name"))
    return {
        "_source": "slack",
        "_source_format": "slack-message",
        "id": f"slack-msg-{channel['id']}-{message.get('ts')}",
        "workspace_name": workspace_name,
        "channel_id": channel["id"],
        "channel_name": channel_name,
        "is_dm": is_dm or is_mpim,
        "is_group": is_mpim,
        "ts": message.get("ts"),
        "thread_ts": message.get("thread_ts"),
        "user_id": user_id,
        "user_name": user_name,
        "text": message.get("text") or "",
        "subtype": message.get("subtype"),
        "reactions": message.get("reactions") or [],
        "files": [{"name": f.get("name"), "url": f.get("url_private")} for f in (message.get("files") or [])],
        "timestamp": slack_ts_to_iso(message["ts"]) if message.get("ts") else None,
        "permalink": message.get("permalink"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace-name", required=True)
    parser.add_argument("--token-env", default="SLACK_BOT_TOKEN")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--since",
        default=None,
        help="ISO datetime; only messages with ts >= since are emitted (translated to Slack 'oldest').",
    )
    parser.add_argument(
        "--channels",
        default=None,
        help="Comma-separated channel IDs to limit to. Default: all channels the bot can see.",
    )
    args = parser.parse_args()

    token = os.environ.get(args.token_env)
    if not token:
        sys.stderr.write(f"ERROR: ${args.token_env} not set\n")
        return 1

    oldest = None
    if args.since:
        try:
            oldest = f"{iso_to_ts(args.since):.6f}"
        except ValueError:
            sys.stderr.write(f"ERROR: --since not a valid ISO datetime: {args.since}\n")
            return 1

    only_channels = set(c.strip() for c in (args.channels or "").split(",") if c.strip()) or None

    client = WebClient(token=token)
    out_stream = args.out.open("w", encoding="utf-8") if args.out else sys.stdout
    count = 0
    errors = 0
    try:
        sys.stderr.write("slack: caching users...\n")
        users = list_user_cache(client)
        sys.stderr.write(f"slack: {len(users)} users cached\n")

        for channel in list_conversations(client):
            if only_channels and channel["id"] not in only_channels:
                continue
            try:
                for msg in iter_channel_messages(client, channel["id"], oldest):
                    record = build_record(msg, channel, args.workspace_name, users)
                    out_stream.write(json.dumps(record, ensure_ascii=False, default=str))
                    out_stream.write("\n")
                    count += 1
            except SlackApiError as exc:
                errors += 1
                sys.stderr.write(
                    f"WARN: skipping channel {channel.get('name') or channel['id']}: "
                    f"{exc.response.get('error')}\n"
                )
                continue
    finally:
        if args.out:
            out_stream.close()

    sys.stderr.write(f"slack: emitted {count} records ({errors} channel errors)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
