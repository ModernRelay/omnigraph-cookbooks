#!/usr/bin/env python3
"""
Walk a LinkedIn data export directory and emit raw JSONL.

LinkedIn's official "Get a copy of your data" download (linkedin.com/mypreferences/d/download-my-data)
delivers a ZIP of CSVs. Unzip somewhere, point this script at the directory, and it walks every
recognized CSV file kind. No API, no token, no scraping — fully user-controlled.

Recognized files (all optional; missing files are skipped):

    Connections.csv         → one record per connection (kind=connection)
    messages.csv            → one record per direct-message line (kind=message)
    Profile.csv             → one record for the user's own profile (kind=profile)
    Positions.csv           → one record per past or current job (kind=position)
    Education.csv           → one record per school (kind=education)
    Shares.csv              → one record per post you shared (kind=post)
    Reactions.csv           → one record per reaction (kind=reaction)

Usage:
    python import_linkedin.py --export-dir ~/Downloads/Basic_LinkedInDataExport_2026-05-08 --workspace-name my-linkedin
    python import_linkedin.py --export-dir ./linkedin-export --workspace-name my-linkedin --out raw.jsonl

Exit codes: 0 on success, 1 on argument / read error.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Iterable


def _norm_key(s: str) -> str:
    return s.strip().lower().replace(" ", "_").replace("-", "_")


def read_csv(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        # LinkedIn exports sometimes have a "Notes:" preamble. Skip until we find a header row.
        rows = list(csv.reader(f))
    if not rows:
        return
    header_idx = 0
    for i, row in enumerate(rows[:5]):
        if any(cell and cell[0].isalpha() for cell in row) and len(row) > 1:
            header_idx = i
            break
    headers = [_norm_key(c) for c in rows[header_idx]]
    for row in rows[header_idx + 1 :]:
        if not any(cell.strip() for cell in row):
            continue
        yield {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}


def find_file(export_dir: Path, candidates: list[str]) -> Path | None:
    for name in candidates:
        p = export_dir / name
        if p.exists():
            return p
    # case-insensitive fallback
    by_lower = {p.name.lower(): p for p in export_dir.iterdir() if p.is_file()}
    for name in candidates:
        p = by_lower.get(name.lower())
        if p:
            return p
    return None


def emit_connections(path: Path | None, workspace: str) -> Iterable[dict[str, Any]]:
    if not path:
        return
    for row in read_csv(path):
        yield {
            "_source": "linkedin",
            "_source_format": "linkedin-connection",
            "_kind": "connection",
            "id": f"linkedin-conn-{row.get('email_address') or row.get('first_name','')+'-'+row.get('last_name','')}",
            "workspace_name": workspace,
            "first_name": row.get("first_name"),
            "last_name": row.get("last_name"),
            "url": row.get("url"),
            "email": row.get("email_address"),
            "company": row.get("company"),
            "position": row.get("position"),
            "connected_on": row.get("connected_on"),
            "timestamp": row.get("connected_on"),
        }


def emit_messages(path: Path | None, workspace: str) -> Iterable[dict[str, Any]]:
    if not path:
        return
    for row in read_csv(path):
        yield {
            "_source": "linkedin",
            "_source_format": "linkedin-message",
            "_kind": "message",
            "id": f"linkedin-msg-{row.get('conversation_id','')}-{row.get('date','')}",
            "workspace_name": workspace,
            "conversation_id": row.get("conversation_id"),
            "conversation_title": row.get("conversation_title"),
            "from": row.get("from"),
            "sender_profile_url": row.get("sender_profile_url"),
            "to": row.get("to"),
            "recipient_profile_urls": row.get("recipient_profile_urls"),
            "date": row.get("date"),
            "subject": row.get("subject"),
            "content": row.get("content"),
            "folder": row.get("folder"),
            "timestamp": row.get("date"),
        }


def emit_profile(path: Path | None, workspace: str) -> Iterable[dict[str, Any]]:
    if not path:
        return
    rows = list(read_csv(path))
    if not rows:
        return
    p = rows[0]
    yield {
        "_source": "linkedin",
        "_source_format": "linkedin-profile",
        "_kind": "profile",
        "id": f"linkedin-profile-{p.get('first_name','')}-{p.get('last_name','')}",
        "workspace_name": workspace,
        "first_name": p.get("first_name"),
        "last_name": p.get("last_name"),
        "headline": p.get("headline"),
        "summary": p.get("summary"),
        "industry": p.get("industry"),
        "geo_location": p.get("geo_location"),
    }


def emit_positions(path: Path | None, workspace: str) -> Iterable[dict[str, Any]]:
    if not path:
        return
    for row in read_csv(path):
        yield {
            "_source": "linkedin",
            "_source_format": "linkedin-position",
            "_kind": "position",
            "id": f"linkedin-pos-{row.get('company_name','')}-{row.get('started_on','')}",
            "workspace_name": workspace,
            "company": row.get("company_name"),
            "title": row.get("title"),
            "description": row.get("description"),
            "location": row.get("location"),
            "started_on": row.get("started_on") or row.get("started"),
            "finished_on": row.get("finished_on") or row.get("finished"),
        }


def emit_shares(path: Path | None, workspace: str) -> Iterable[dict[str, Any]]:
    if not path:
        return
    for row in read_csv(path):
        yield {
            "_source": "linkedin",
            "_source_format": "linkedin-share",
            "_kind": "post",
            "id": f"linkedin-share-{row.get('share_link') or row.get('date','')}",
            "workspace_name": workspace,
            "post_id": row.get("share_link") or row.get("id"),
            "url": row.get("share_link"),
            "date": row.get("date"),
            "content": row.get("share_commentary") or row.get("content"),
            "media_url": row.get("media_url"),
            "visibility": row.get("visibility"),
            "timestamp": row.get("date"),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export-dir", required=True, type=Path, help="Path to the unzipped LinkedIn data export folder")
    parser.add_argument("--workspace-name", required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--since",
        default=None,
        help="ISO datetime; coarse filter on date / connected_on fields where present.",
    )
    args = parser.parse_args()

    export_dir: Path = args.export_dir.expanduser().resolve()
    if not export_dir.exists() or not export_dir.is_dir():
        sys.stderr.write(f"ERROR: export-dir not found or not a directory: {export_dir}\n")
        return 1

    files = {
        "connections": find_file(export_dir, ["Connections.csv"]),
        "messages": find_file(export_dir, ["messages.csv", "Messages.csv"]),
        "profile": find_file(export_dir, ["Profile.csv"]),
        "positions": find_file(export_dir, ["Positions.csv"]),
        "shares": find_file(export_dir, ["Shares.csv"]),
    }

    out_stream = args.out.open("w", encoding="utf-8") if args.out else sys.stdout
    counts: dict[str, int] = {}
    emitters = [
        ("connection", emit_connections(files["connections"], args.workspace_name)),
        ("message", emit_messages(files["messages"], args.workspace_name)),
        ("profile", emit_profile(files["profile"], args.workspace_name)),
        ("position", emit_positions(files["positions"], args.workspace_name)),
        ("post", emit_shares(files["shares"], args.workspace_name)),
    ]
    try:
        for kind, gen in emitters:
            for r in gen:
                if args.since and (r.get("timestamp") or "") < args.since:
                    continue
                out_stream.write(json.dumps(r, ensure_ascii=False, default=str))
                out_stream.write("\n")
                counts[kind] = counts.get(kind, 0) + 1
    finally:
        if args.out:
            out_stream.close()

    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    sys.stderr.write(f"linkedin: emitted {sum(counts.values())} records ({summary})\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
