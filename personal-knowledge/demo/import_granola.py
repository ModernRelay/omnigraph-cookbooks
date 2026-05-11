#!/usr/bin/env python3
"""
Pull Granola meeting notes (transcripts, summaries, attendees) and emit raw JSONL.

Two input paths supported:

  1. **API mode** — set GRANOLA_TOKEN and the importer hits the Granola API
     (default base: https://api.granola.so). One record per meeting.
  2. **Local export mode** — `--input path/to/granola-export.json` reads a
     JSON file you've exported from the Granola app.

Setup:
    Either: export GRANOLA_TOKEN=...  (and optionally GRANOLA_API_BASE)
    Or:     download a Granola export JSON to disk

Usage:
    GRANOLA_TOKEN=... python import_granola.py --workspace-name my-granola
    python import_granola.py --workspace-name my-granola --input ./granola.json --out raw.jsonl

The exact Granola API surface evolves; verify the endpoint against your
Granola docs or the `granola-to-graph` skill. The importer treats the API
response defensively — unknown fields pass through unchanged in `meta`.

Exit codes: 0 on success, 1 on argument / auth / network error.
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
    import urllib.request as urlreq
    import urllib.error
except ImportError:  # pragma: no cover
    sys.stderr.write("ERROR: stdlib urllib missing\n")
    sys.exit(1)


PAGE_SIZE = 100
THROTTLE_SECONDS = 0.5


def workspace_slug(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"


def make_meeting_id(meeting_id: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_-]+", "", meeting_id) or meeting_id


def fetch_api(base: str, token: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = base.rstrip("/") + path
    if params:
        from urllib.parse import urlencode

        url = url + "?" + urlencode(params)
    req = urlreq.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urlreq.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def iter_api_meetings(base: str, token: str, since: str | None) -> Iterable[dict[str, Any]]:
    cursor: str | None = None
    while True:
        time.sleep(THROTTLE_SECONDS)
        params: dict[str, Any] = {"page_size": PAGE_SIZE}
        if cursor:
            params["cursor"] = cursor
        if since:
            params["updated_after"] = since
        resp = fetch_api(base, token, "/v1/notes", params)
        for item in resp.get("data") or resp.get("results") or []:
            yield item
        cursor = resp.get("next_cursor") or resp.get("cursor")
        if not cursor:
            break


def iter_local_meetings(input_path: Path, since: str | None) -> Iterable[dict[str, Any]]:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    items = data.get("notes") or data.get("meetings") or data.get("data") or data
    if not isinstance(items, list):
        sys.stderr.write("ERROR: expected a list of meetings in the export JSON\n")
        return
    for item in items:
        if since:
            updated = item.get("updated_at") or item.get("modified_at") or ""
            if updated < since:
                continue
        yield item


def build_record(item: dict[str, Any], workspace_name: str) -> dict[str, Any]:
    meeting_id = item.get("id") or item.get("meeting_id") or item.get("note_id") or ""
    title = item.get("title") or item.get("name") or "(untitled meeting)"
    transcript = item.get("transcript") or item.get("transcript_text") or item.get("body") or ""
    summary = item.get("summary") or item.get("summary_text")
    attendees_raw = item.get("attendees") or item.get("participants") or []
    attendees: list[dict[str, Any]] = []
    for a in attendees_raw:
        if isinstance(a, str):
            attendees.append({"name": a})
        elif isinstance(a, dict):
            attendees.append({"name": a.get("name") or a.get("displayName"), "email": a.get("email")})
    return {
        "_source": "granola",
        "_source_format": "granola-meeting",
        "id": f"meeting-granola-{make_meeting_id(meeting_id)}",
        "workspace_name": workspace_name,
        "meeting_id": meeting_id,
        "title": title,
        "transcript": transcript,
        "summary": summary,
        "attendees": attendees,
        "started_at": item.get("started_at") or item.get("start_time") or item.get("created_at"),
        "ended_at": item.get("ended_at") or item.get("end_time"),
        "created_at": item.get("created_at") or item.get("started_at"),
        "updated_at": item.get("updated_at") or item.get("modified_at"),
        "url": item.get("url"),
        "meta": {k: v for k, v in item.items() if k not in {"id", "title", "transcript", "summary", "attendees"}},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace-name", required=True)
    parser.add_argument("--input", type=Path, default=None, help="Local Granola export JSON file")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--token-env", default="GRANOLA_TOKEN")
    parser.add_argument("--api-base", default=os.environ.get("GRANOLA_API_BASE", "https://api.granola.so"))
    parser.add_argument("--since", default=None)
    args = parser.parse_args()

    out_stream = args.out.open("w", encoding="utf-8") if args.out else sys.stdout
    count, errors = 0, 0
    try:
        if args.input:
            iterator = iter_local_meetings(args.input, args.since)
        else:
            token = os.environ.get(args.token_env)
            if not token:
                sys.stderr.write(
                    f"ERROR: ${args.token_env} not set and no --input file given. "
                    "Either export your Granola token or pass --input.\n"
                )
                return 1
            iterator = iter_api_meetings(args.api_base, token, args.since)
        for item in iterator:
            try:
                record = build_record(item, args.workspace_name)
            except Exception as exc:
                errors += 1
                sys.stderr.write(f"WARN: skipping meeting: {exc}\n")
                continue
            out_stream.write(json.dumps(record, ensure_ascii=False, default=str))
            out_stream.write("\n")
            count += 1
    except urllib.error.HTTPError as exc:
        sys.stderr.write(f"ERROR: Granola API returned {exc.code}: {exc.reason}\n")
        return 1
    except urllib.error.URLError as exc:
        sys.stderr.write(f"ERROR: Granola API unreachable: {exc.reason}\n")
        return 1
    finally:
        if args.out:
            out_stream.close()

    sys.stderr.write(f"granola: emitted {count} records ({errors} errors)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
