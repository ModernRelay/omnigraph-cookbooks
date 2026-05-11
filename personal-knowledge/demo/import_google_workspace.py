#!/usr/bin/env python3
"""
Pull Google Workspace data (Drive files, Gmail messages, Calendar events) and
emit raw JSONL.

OAuth flow: the first run opens a browser and writes credentials to
`~/.config/omnigraph-personal-knowledge/google-token.json`. Subsequent runs
re-use those credentials.

Setup:
    1. Create a project at https://console.cloud.google.com
    2. Enable Drive, Gmail, Calendar APIs
    3. Create OAuth 2.0 credentials (Desktop app), download client_secret.json
    4. Point GOOGLE_CLIENT_SECRETS at that file (default: ./google_client_secrets.json)

Usage:
    python import_google_workspace.py --workspace-name my-google --gmail --drive --gcal
    python import_google_workspace.py --workspace-name my-google --gmail --since 2026-04-01T00:00:00Z

Exit codes: 0 on success, 1 on auth/network error.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    sys.stderr.write(
        "ERROR: Google API libs not installed.\n"
        "  pip install -r requirements.txt\n"
    )
    sys.exit(1)


SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

CONFIG_DIR = Path.home() / ".config" / "omnigraph-personal-knowledge"
TOKEN_PATH = CONFIG_DIR / "google-token.json"
DEFAULT_CLIENT_SECRETS = Path("./google_client_secrets.json")


def get_credentials(client_secrets: Path) -> Credentials:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    creds: Credentials | None = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not client_secrets.exists():
                sys.stderr.write(f"ERROR: client secrets file not found: {client_secrets}\n")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


# ─── Drive ────────────────────────────────────────────────────────────────────


def iter_drive_files(creds: Credentials, since: str | None) -> Iterable[dict[str, Any]]:
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    q = "trashed = false"
    if since:
        q += f" and modifiedTime >= '{since}'"
    page_token: str | None = None
    while True:
        resp = service.files().list(
            q=q,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType, webViewLink, modifiedTime, createdTime, owners, parents, size)",
            pageToken=page_token,
        ).execute()
        for f in resp.get("files", []):
            yield f
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def build_drive_record(f: dict[str, Any], workspace_name: str) -> dict[str, Any]:
    return {
        "_source": "gdrive",
        "_source_format": "drive-file",
        "id": f"gdrive-file-{f['id']}",
        "workspace_name": workspace_name,
        "file_id": f["id"],
        "title": f.get("name"),
        "mime_type": f.get("mimeType"),
        "url": f.get("webViewLink"),
        "size": f.get("size"),
        "owners": [o.get("emailAddress") for o in f.get("owners") or []],
        "parents": f.get("parents") or [],
        "created_at": f.get("createdTime"),
        "updated_at": f.get("modifiedTime"),
    }


# ─── Gmail ────────────────────────────────────────────────────────────────────


def iter_gmail_messages(creds: Credentials, since: str | None, max_results: int | None) -> Iterable[dict[str, Any]]:
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    q_parts: list[str] = []
    if since:
        d = dt.datetime.fromisoformat(since.replace("Z", "+00:00"))
        q_parts.append(f"after:{int(d.timestamp())}")
    q = " ".join(q_parts) or None

    page_token: str | None = None
    fetched = 0
    while True:
        kwargs: dict[str, Any] = {"userId": "me", "maxResults": 100}
        if q:
            kwargs["q"] = q
        if page_token:
            kwargs["pageToken"] = page_token
        resp = service.users().messages().list(**kwargs).execute()
        for stub in resp.get("messages") or []:
            full = service.users().messages().get(userId="me", id=stub["id"], format="full").execute()
            yield full
            fetched += 1
            if max_results and fetched >= max_results:
                return
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def _header(headers: list[dict[str, str]], name: str) -> str | None:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


def _decode_part(part: dict[str, Any]) -> tuple[str, str]:
    text, html = "", ""
    body = part.get("body") or {}
    data = body.get("data")
    if data:
        decoded = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        if part.get("mimeType") == "text/plain":
            text = decoded
        elif part.get("mimeType") == "text/html":
            html = decoded
    for sub in part.get("parts") or []:
        t, h = _decode_part(sub)
        text = text or t
        html = html or h
    return text, html


def build_gmail_record(msg: dict[str, Any], workspace_name: str, account: str) -> dict[str, Any]:
    payload = msg.get("payload") or {}
    headers = payload.get("headers") or []
    subject = _header(headers, "Subject")
    from_addr = _header(headers, "From") or ""
    to_addrs = [a.strip() for a in (_header(headers, "To") or "").split(",") if a.strip()]
    cc_addrs = [a.strip() for a in (_header(headers, "Cc") or "").split(",") if a.strip()]
    date_hdr = _header(headers, "Date")
    text, html = _decode_part(payload)
    return {
        "_source": "gmail",
        "_source_format": "gmail-message",
        "id": f"gmail-msg-{msg['id']}",
        "workspace_name": workspace_name,
        "account": account,
        "message_id": msg["id"],
        "thread_id": msg.get("threadId"),
        "subject": subject,
        "from": from_addr,
        "to": to_addrs,
        "cc": cc_addrs,
        "labels": msg.get("labelIds") or [],
        "snippet": msg.get("snippet"),
        "content_text": text,
        "content_html": html,
        "timestamp": dt.datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=dt.timezone.utc).isoformat(),
        "history_id": msg.get("historyId"),
    }


# ─── Calendar ─────────────────────────────────────────────────────────────────


def iter_calendar_events(creds: Credentials, since: str | None) -> Iterable[dict[str, Any]]:
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    page_token: str | None = None
    while True:
        kwargs: dict[str, Any] = {
            "calendarId": "primary",
            "maxResults": 250,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if since:
            kwargs["updatedMin"] = since
        if page_token:
            kwargs["pageToken"] = page_token
        resp = service.events().list(**kwargs).execute()
        for e in resp.get("items") or []:
            yield e
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def build_calendar_record(e: dict[str, Any], workspace_name: str) -> dict[str, Any]:
    return {
        "_source": "gcalendar",
        "_source_format": "gcal-event",
        "id": f"gcal-event-{e['id']}",
        "workspace_name": workspace_name,
        "event_id": e["id"],
        "title": e.get("summary"),
        "description": e.get("description"),
        "location": e.get("location"),
        "start_at": (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date"),
        "end_at": (e.get("end") or {}).get("dateTime") or (e.get("end") or {}).get("date"),
        "attendees": [
            {"email": a.get("email"), "displayName": a.get("displayName"), "responseStatus": a.get("responseStatus")}
            for a in (e.get("attendees") or [])
        ],
        "organizer": (e.get("organizer") or {}).get("email"),
        "status": e.get("status"),
        "created_at": e.get("created"),
        "updated_at": e.get("updated"),
        "url": e.get("htmlLink"),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace-name", required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--since", default=None)
    parser.add_argument("--drive", action="store_true", help="Import Drive files")
    parser.add_argument("--gmail", action="store_true", help="Import Gmail messages")
    parser.add_argument("--gcal", action="store_true", help="Import Calendar events")
    parser.add_argument("--gmail-max", type=int, default=None, help="Cap on Gmail messages per run")
    parser.add_argument("--gmail-account", default="me", help="Account label for Email records")
    parser.add_argument(
        "--client-secrets",
        type=Path,
        default=Path(os.environ.get("GOOGLE_CLIENT_SECRETS", str(DEFAULT_CLIENT_SECRETS))),
    )
    args = parser.parse_args()

    if not (args.drive or args.gmail or args.gcal):
        sys.stderr.write("ERROR: pick at least one of --drive --gmail --gcal\n")
        return 1

    creds = get_credentials(args.client_secrets)
    out_stream = args.out.open("w", encoding="utf-8") if args.out else sys.stdout
    counts: dict[str, int] = {"drive": 0, "gmail": 0, "gcal": 0}

    try:
        if args.drive:
            for f in iter_drive_files(creds, args.since):
                out_stream.write(json.dumps(build_drive_record(f, args.workspace_name), ensure_ascii=False, default=str))
                out_stream.write("\n")
                counts["drive"] += 1
        if args.gmail:
            for m in iter_gmail_messages(creds, args.since, args.gmail_max):
                out_stream.write(
                    json.dumps(build_gmail_record(m, args.workspace_name, args.gmail_account), ensure_ascii=False, default=str)
                )
                out_stream.write("\n")
                counts["gmail"] += 1
        if args.gcal:
            for e in iter_calendar_events(creds, args.since):
                out_stream.write(json.dumps(build_calendar_record(e, args.workspace_name), ensure_ascii=False, default=str))
                out_stream.write("\n")
                counts["gcal"] += 1
    except HttpError as exc:
        sys.stderr.write(f"ERROR: Google API: {exc}\n")
        return 1
    finally:
        if args.out:
            out_stream.close()

    sys.stderr.write(
        f"google: emitted drive={counts['drive']} gmail={counts['gmail']} gcal={counts['gcal']}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
