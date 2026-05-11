#!/usr/bin/env python3
"""
Dump Apple Notes via AppleScript and emit raw JSONL.

Mac-only. Uses `osascript` to walk every accessible note across all accounts
and folders. Apple Notes encrypts the body of locked notes — those come back
with a placeholder body and a `is_locked: true` flag.

Usage:
    python import_apple_notes.py --workspace-name my-notes
    python import_apple_notes.py --workspace-name my-notes --account "iCloud" --out raw.jsonl

Exit codes: 0 on success, 1 on argument / platform error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path


# Field separator chosen to be exotic enough that note bodies won't contain it.
FS = "\x1e"  # ASCII record separator
RS = "\x1f"  # ASCII unit separator (between notes)


APPLESCRIPT = r"""
on isoFromDate(d)
    set yr to year of d as integer
    set mo to (month of d as integer)
    set da to day of d as integer
    set h to hours of d
    set m to minutes of d
    set s to seconds of d
    return (yr as text) & "-" & text -2 thru -1 of ("0" & (mo as text)) & "-" & text -2 thru -1 of ("0" & (da as text)) & "T" & text -2 thru -1 of ("0" & (h as text)) & ":" & text -2 thru -1 of ("0" & (m as text)) & ":" & text -2 thru -1 of ("0" & (s as text))
end isoFromDate

set FS to (ASCII character 30)
set RS to (ASCII character 31)

set output to ""
tell application "Notes"
    repeat with acc in accounts
        set accName to (name of acc)
        repeat with n in (notes of acc)
            try
                set nId to (id of n)
                set nName to (name of n)
                set nBody to (body of n)
                set nFolder to (name of (container of n))
                set nCreated to (creation date of n)
                set nMod to (modification date of n)
                set nLocked to (password protected of n)
                set output to output & accName & FS & nFolder & FS & nId & FS & nName & FS & my isoFromDate(nCreated) & FS & my isoFromDate(nMod) & FS & nLocked & FS & nBody & RS
            end try
        end repeat
    end repeat
end tell
return output
"""


def run_applescript() -> str:
    proc = subprocess.run(
        ["osascript", "-e", APPLESCRIPT],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"osascript failed: {proc.stderr.strip()}")
    return proc.stdout


def html_to_text(html: str) -> str:
    """Notes returns body as HTML. Strip tags to plaintext."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def parse_notes(raw: str, account_filter: str | None, workspace_name: str) -> list[dict]:
    records: list[dict] = []
    for chunk in raw.split(RS):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(FS)
        if len(parts) < 8:
            continue
        acc, folder, note_id, title, created, updated, locked, body_html = parts[:8]
        if account_filter and acc.strip().lower() != account_filter.strip().lower():
            continue
        is_locked = locked.strip().lower() in {"true", "yes"}
        body = html_to_text(body_html) if not is_locked else "(locked note — body unavailable)"
        records.append(
            {
                "_source": "apple-notes",
                "_source_format": "apple-notes-note",
                "id": f"note-apple-{note_id.split('/')[-1]}",
                "workspace_name": workspace_name,
                "note_id": note_id,
                "account": acc,
                "folder": folder,
                "title": title,
                "body": body,
                "is_locked": is_locked,
                "created_at": created if "T" in created else created,
                "updated_at": updated if "T" in updated else updated,
            }
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace-name", required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--account", default=None, help="Limit to a specific account name (e.g. 'iCloud')")
    parser.add_argument(
        "--since",
        default=None,
        help="ISO datetime; client-side filter on modification_date.",
    )
    args = parser.parse_args()

    if sys.platform != "darwin":
        sys.stderr.write("ERROR: Apple Notes is Mac-only (osascript unavailable on this platform)\n")
        return 1

    try:
        raw = run_applescript()
    except RuntimeError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 1

    records = parse_notes(raw, args.account, args.workspace_name)
    if args.since:
        records = [r for r in records if (r.get("updated_at") or "") >= args.since]

    out_stream = args.out.open("w", encoding="utf-8") if args.out else sys.stdout
    try:
        for r in records:
            out_stream.write(json.dumps(r, ensure_ascii=False, default=str))
            out_stream.write("\n")
    finally:
        if args.out:
            out_stream.close()

    sys.stderr.write(f"apple-notes: emitted {len(records)} records\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
