#!/usr/bin/env python3
"""
Parse WhatsApp chat exports and emit raw JSONL — one record per message.

WhatsApp lets you export a chat as a .txt file (Chat → ⋯ → Export Chat → Without Media).
This script reads one or more such files (or a directory of them) and parses
the message log. Both iOS bracketed format and Android dash format are
supported.

iOS format:
    [9/12/24, 10:43:21 AM] Jane Doe: Hey, are we still on for Friday?

Android format:
    9/12/24, 10:43 AM - Jane Doe: Hey, are we still on for Friday?

Usage:
    python import_whatsapp.py --input ~/Downloads/whatsapp-jane.txt --workspace-name my-whatsapp
    python import_whatsapp.py --input ./whatsapp-exports/ --workspace-name my-whatsapp --out raw.jsonl

Exit codes: 0 on success, 1 on argument error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable


# iOS:    [DD/MM/YY, HH:MM:SS AM] Sender: message
# Android: DD/MM/YY, HH:MM - Sender: message
LINE_IOS = re.compile(
    r"^\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\]\s+(?P<sender>[^:]+?):\s(?P<text>.*)$"
)
LINE_ANDROID = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\s+-\s+(?P<sender>[^:]+?):\s(?P<text>.*)$"
)
SYSTEM_LINE_IOS = re.compile(r"^\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\]\s+(?P<text>.*)$")
SYSTEM_LINE_ANDROID = re.compile(r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\s+-\s+(?P<text>.*)$")


def parse_timestamp(date: str, time: str) -> str:
    for date_fmt in ("%d/%m/%y", "%m/%d/%y", "%d/%m/%Y", "%m/%d/%Y"):
        for time_fmt in ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"):
            try:
                d = dt.datetime.strptime(f"{date} {time}", f"{date_fmt} {time_fmt}")
                return d.replace(tzinfo=dt.timezone.utc).isoformat()
            except ValueError:
                continue
    return ""


def chat_id_for(file_path: Path) -> str:
    return hashlib.sha256(file_path.name.encode("utf-8")).hexdigest()[:16]


def parse_chat(file_path: Path, workspace: str) -> Iterable[dict]:
    chat_id = chat_id_for(file_path)
    chat_name = file_path.stem.replace("WhatsApp Chat with ", "").replace("WhatsApp Chat - ", "")
    senders: set[str] = set()

    current: dict | None = None
    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            m = LINE_IOS.match(line) or LINE_ANDROID.match(line)
            if m:
                if current:
                    yield current
                ts = parse_timestamp(m.group("date"), m.group("time"))
                sender = m.group("sender").strip()
                senders.add(sender)
                current = {
                    "_source": "whatsapp",
                    "_source_format": "whatsapp-message",
                    "id": f"whatsapp-msg-{chat_id}-{ts}-{hashlib.sha256(sender.encode()).hexdigest()[:6]}",
                    "workspace_name": workspace,
                    "chat_id": chat_id,
                    "chat_name": chat_name,
                    "sender": sender,
                    "text": m.group("text"),
                    "timestamp": ts,
                }
                continue
            m_sys = SYSTEM_LINE_IOS.match(line) or SYSTEM_LINE_ANDROID.match(line)
            if m_sys:
                if current:
                    yield current
                    current = None
                continue
            if current and line:
                current["text"] += "\n" + line
        if current:
            yield current

    # Mark whether this looks like a group based on number of unique senders
    # (best-effort: emitted record's is_group is set retroactively in main).


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to a .txt export file, or a directory of them.",
    )
    parser.add_argument("--workspace-name", required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--since", default=None, help="ISO datetime; only messages with timestamp >= since are emitted.")
    args = parser.parse_args()

    input_path: Path = args.input.expanduser().resolve()
    if not input_path.exists():
        sys.stderr.write(f"ERROR: input not found: {input_path}\n")
        return 1
    files: list[Path] = (
        [input_path] if input_path.is_file() else sorted(p for p in input_path.iterdir() if p.suffix.lower() == ".txt")
    )
    if not files:
        sys.stderr.write(f"ERROR: no .txt files under {input_path}\n")
        return 1

    out_stream = args.out.open("w", encoding="utf-8") if args.out else sys.stdout
    total = 0
    try:
        for fp in files:
            messages = list(parse_chat(fp, args.workspace_name))
            sender_set = {m["sender"] for m in messages}
            is_group = len(sender_set) > 2
            for m in messages:
                if args.since and (m.get("timestamp") or "") < args.since:
                    continue
                m["is_group"] = is_group
                out_stream.write(json.dumps(m, ensure_ascii=False, default=str))
                out_stream.write("\n")
                total += 1
    finally:
        if args.out:
            out_stream.close()

    sys.stderr.write(f"whatsapp: emitted {total} records from {len(files)} chat file(s)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
