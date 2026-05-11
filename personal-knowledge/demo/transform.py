#!/usr/bin/env python3
"""
Transform raw JSONL from any importer into schema-shaped JSONL ready for
`omnigraph load --mode merge`. Reads raw records from one or more files (or
stdin), dispatches per `_source`, emits typed nodes + edges.

Output format (one record per line):
    {"type": "TypeName", "data": {...}}            for nodes
    {"edge": "EdgeName", "from": "src-slug", "to": "tgt-slug", "data": {...}}  for edges

Plus a single SyncRun record at the end summarizing the run.

Usage:
    python transform.py raw-obsidian.jsonl raw-notion.jsonl > patch.jsonl
    cat raw-*.jsonl | python transform.py - > patch.jsonl
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable


# ─── Slug helpers ─────────────────────────────────────────────────────────────

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str, max_len: int = 64) -> str:
    return _SLUG_RE.sub("-", value.lower()).strip("-")[:max_len] or "x"


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def person_slug(name: str | None, email: str | None = None) -> str:
    if email:
        return f"person-{_slugify(email)}"
    if name:
        return f"person-{_slugify(name)}-{_short_hash(name)}"
    return f"person-anon-{uuid.uuid4().hex[:8]}"


def org_slug(name: str) -> str:
    return f"org-{_slugify(name)}-{_short_hash(name)}"


def place_slug(name: str) -> str:
    return f"place-{_slugify(name)}-{_short_hash(name)}"


def event_slug(source: str, external_id: str) -> str:
    return f"event-{_slugify(source)}-{_slugify(external_id)}-{_short_hash(external_id)}"


def artifact_slug(source: str, external_id: str) -> str:
    return f"art-{_slugify(source)}-{_slugify(external_id)}-{_short_hash(external_id)}"


def note_slug(source: str, external_id: str) -> str:
    return f"note-{_slugify(source)}-{_slugify(external_id)}-{_short_hash(external_id)}"


def conversation_slug(source: str, external_id: str) -> str:
    return f"conv-{_slugify(source)}-{_slugify(external_id)}-{_short_hash(external_id)}"


def email_slug(message_id: str) -> str:
    return f"email-{_short_hash(message_id)}"


def external_id_slug(source: str, external_id: str) -> str:
    return f"ext-{_slugify(source)}-{_short_hash(f'{source}/{external_id}')}"


# ─── Time helpers ─────────────────────────────────────────────────────────────


def _now() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).isoformat()


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.isoformat()
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=dt.timezone.utc).isoformat()
    return str(value)


# ─── Emission helpers ─────────────────────────────────────────────────────────


def node(type_name: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"type": type_name, "data": data}


def edge(name: str, from_slug: str, to_slug: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"edge": name, "from": from_slug, "to": to_slug}
    if data:
        out["data"] = data
    return out


def external_id_record(source: str, external_id: str, created_at: str | None = None) -> dict[str, Any]:
    return node(
        "ExternalID",
        {
            "slug": external_id_slug(source, external_id),
            "source": source,
            "external_id": external_id,
            "createdAt": created_at or _now(),
        },
    )


def person_record(name: str | None, email: str | None = None, brief: str | None = None) -> dict[str, Any]:
    now = _now()
    return node(
        "Person",
        {
            "slug": person_slug(name, email),
            "name": name or email or "(unknown)",
            "email": email,
            "relation": "other",
            "brief": brief,
            "createdAt": now,
            "updatedAt": now,
        },
    )


# ─── Per-source transforms ────────────────────────────────────────────────────


def transform_obsidian(raw: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Each Obsidian markdown file → 1 Artifact + 1 Note + 1 ExternalID."""
    rel = raw.get("relative_path", "")
    title = raw.get("title") or raw.get("file_name") or rel
    body = raw.get("body") or ""
    created = _iso(raw.get("created_at")) or _now()
    updated = _iso(raw.get("updated_at")) or created

    art_slug = artifact_slug("obsidian", rel)
    nt_slug = note_slug("obsidian", rel)

    yield external_id_record("obsidian", rel, created)
    yield node(
        "Artifact",
        {
            "slug": art_slug,
            "name": title,
            "kind": "document",
            "source": "obsidian",
            "source_ref": rel,
            "content": body,
            "timestamp": updated,
            "createdAt": created,
            "updatedAt": updated,
        },
    )
    yield node(
        "Note",
        {
            "slug": nt_slug,
            "name": title,
            "kind": _obsidian_note_kind(raw),
            "content": body,
            "tags": raw.get("tags") or [],
            "createdAt": created,
            "updatedAt": updated,
        },
    )
    yield edge("NoteFromArtifact", nt_slug, art_slug)

    # Wiki-links targeting other obsidian notes → LinkedNote (best-effort)
    for link in raw.get("wiki_links") or []:
        target = link.get("target") if isinstance(link, dict) else None
        if not target:
            continue
        tgt_rel = target if target.lower().endswith(".md") else f"{target}.md"
        tgt_slug = note_slug("obsidian", tgt_rel)
        yield edge("LinkedNote", nt_slug, tgt_slug)


def _obsidian_note_kind(raw: dict[str, Any]) -> str:
    fname = (raw.get("file_name") or "").lower()
    fm = raw.get("frontmatter") or {}
    if "type" in fm and fm["type"] in ("idea", "reflection", "insight", "quote", "dream", "journal", "principle"):
        return fm["type"]
    if fname.startswith("daily") or re.match(r"\d{4}-\d{2}-\d{2}", fname):
        return "journal"
    return "idea"


def transform_notion(raw: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Each Notion page → 1 Artifact + 1 Note + 1 ExternalID, plus Persons for mentions/people-properties."""
    page_id = raw.get("page_id") or ""
    title = raw.get("title") or "(untitled)"
    body = raw.get("body") or ""
    url = raw.get("url")
    created = _iso(raw.get("created_at")) or _now()
    updated = _iso(raw.get("updated_at")) or created

    art_slug = artifact_slug("notion", page_id)
    nt_slug = note_slug("notion", page_id)

    yield external_id_record("notion", page_id, created)
    yield node(
        "Artifact",
        {
            "slug": art_slug,
            "name": title,
            "kind": "document",
            "source": "notion",
            "source_ref": page_id,
            "url": url,
            "content": body,
            "timestamp": updated,
            "createdAt": created,
            "updatedAt": updated,
        },
    )
    yield node(
        "Note",
        {
            "slug": nt_slug,
            "name": title,
            "kind": "idea",
            "content": body,
            "tags": _notion_tags(raw.get("properties") or {}),
            "createdAt": created,
            "updatedAt": updated,
        },
    )
    yield edge("NoteFromArtifact", nt_slug, art_slug)

    # People mentioned inline
    seen_persons: set[str] = set()
    for mention in raw.get("mentions") or []:
        if mention.get("kind") != "user":
            continue
        name = mention.get("name")
        user_id = mention.get("user_id")
        if not user_id or user_id in seen_persons:
            continue
        seen_persons.add(user_id)
        p_slug = person_slug(name, None)
        yield person_record(name)
        yield external_id_record("notion", user_id, created)
        yield edge("IdentifiesPerson", external_id_slug("notion", user_id), p_slug)
        yield edge("Mentions", art_slug, p_slug)

    # People-properties (assignees, owners, etc.)
    for prop_value in (raw.get("properties") or {}).values():
        if not isinstance(prop_value, list):
            continue
        for p in prop_value:
            if not isinstance(p, dict) or "person_id" not in p:
                continue
            user_id = p.get("id")
            name = p.get("name")
            if not user_id or user_id in seen_persons:
                continue
            seen_persons.add(user_id)
            p_slug = person_slug(name, None)
            yield person_record(name)
            yield external_id_record("notion", user_id, created)
            yield edge("IdentifiesPerson", external_id_slug("notion", user_id), p_slug)
            yield edge("Mentions", art_slug, p_slug)


def _notion_tags(properties: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for value in properties.values():
        if isinstance(value, list) and value and all(isinstance(x, str) for x in value):
            tags.extend(value)
    return list(dict.fromkeys(tags))


def transform_granola(raw: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Each Granola meeting → 1 Artifact (transcript) + 1 Event + Persons for attendees."""
    meeting_id = raw.get("meeting_id") or raw.get("id") or ""
    title = raw.get("title") or "(untitled meeting)"
    transcript = raw.get("transcript") or raw.get("body") or ""
    started_at = _iso(raw.get("started_at") or raw.get("created_at")) or _now()
    ended_at = _iso(raw.get("ended_at"))
    created = _iso(raw.get("created_at")) or started_at

    art_slug = artifact_slug("granola", meeting_id)
    evt_slug = event_slug("granola", meeting_id)

    yield external_id_record("granola", meeting_id, created)
    yield node(
        "Artifact",
        {
            "slug": art_slug,
            "name": f"Transcript: {title}",
            "kind": "transcript",
            "source": "granola",
            "source_ref": meeting_id,
            "content": transcript,
            "timestamp": started_at,
            "createdAt": created,
            "updatedAt": created,
        },
    )
    yield node(
        "Event",
        {
            "slug": evt_slug,
            "name": title,
            "kind": "meeting",
            "date": started_at,
            "end_date": ended_at,
            "createdAt": created,
            "updatedAt": created,
        },
    )
    yield edge("RecordOf", art_slug, evt_slug)

    for attendee in raw.get("attendees") or []:
        if isinstance(attendee, dict):
            email = attendee.get("email")
            name = attendee.get("name") or email
        else:
            name, email = str(attendee), None
        if not name and not email:
            continue
        p_slug = person_slug(name, email)
        yield person_record(name, email)
        yield edge("Attended", p_slug, evt_slug)
        yield edge("Mentions", art_slug, p_slug)


def transform_slack(raw: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Each Slack message → 1 Artifact + 1 ExternalID + Conversation membership."""
    channel_id = raw.get("channel_id") or ""
    ts = raw.get("ts") or ""
    msg_id = f"{channel_id}/{ts}"
    text = raw.get("text") or ""
    user_id = raw.get("user_id")
    user_name = raw.get("user_name")
    timestamp = _iso(raw.get("timestamp")) or _now()
    is_dm = bool(raw.get("is_dm"))

    art_slug = artifact_slug("slack", msg_id)
    conv_slug = conversation_slug("slack", channel_id)

    yield external_id_record("slack", msg_id, timestamp)
    yield node(
        "Artifact",
        {
            "slug": art_slug,
            "name": (text[:80] + "…") if len(text) > 80 else text or "(empty message)",
            "kind": "message",
            "source": "slack",
            "source_ref": msg_id,
            "content": text,
            "timestamp": timestamp,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    )
    yield node(
        "Conversation",
        {
            "slug": conv_slug,
            "external_id": channel_id,
            "kind": "dm" if is_dm else "channel",
            "source": "slack",
            "name": raw.get("channel_name"),
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    )
    yield edge("InConversation", art_slug, conv_slug)

    if user_id:
        p_slug = person_slug(user_name, None)
        yield person_record(user_name)
        yield external_id_record("slack", user_id, timestamp)
        yield edge("IdentifiesPerson", external_id_slug("slack", user_id), p_slug)
        yield edge("ArtifactFromPerson", art_slug, p_slug)
        yield edge("ConversationWith", conv_slug, p_slug)


def transform_gmail(raw: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Each Gmail thread message → 1 Email + 1 ExternalID + Conversation per thread."""
    msg_id = raw.get("message_id") or ""
    thread_id = raw.get("thread_id") or ""
    em_slug = email_slug(msg_id)
    conv_slug = conversation_slug("email", thread_id)
    timestamp = _iso(raw.get("timestamp")) or _now()

    yield external_id_record("email", msg_id, timestamp)
    yield node(
        "Email",
        {
            "slug": em_slug,
            "message_id": msg_id,
            "thread_id": thread_id,
            "subject": raw.get("subject"),
            "labels": raw.get("labels") or [],
            "account": raw.get("account") or "",
            "from": raw.get("from") or "",
            "to": raw.get("to") or [],
            "cc": raw.get("cc") or [],
            "timestamp": timestamp,
            "content_text": raw.get("content_text"),
            "content_html": raw.get("content_html"),
            "snippet": raw.get("snippet"),
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    )
    yield node(
        "Conversation",
        {
            "slug": conv_slug,
            "external_id": thread_id,
            "kind": "group",
            "source": "email",
            "name": raw.get("subject"),
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    )
    yield edge("EmailInConversation", em_slug, conv_slug)

    for addr in [raw.get("from")] + (raw.get("to") or []):
        if not addr:
            continue
        addr = addr.strip()
        p_slug = person_slug(addr, addr)
        yield person_record(addr, addr)
        yield external_id_record("email", addr, timestamp)
        yield edge("IdentifiesPerson", external_id_slug("email", addr), p_slug)
        if addr == raw.get("from"):
            yield edge("EmailFromPerson", em_slug, p_slug)
        else:
            yield edge("EmailToPerson", em_slug, p_slug)


def transform_gdrive(raw: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Each Drive file → 1 Artifact + 1 ExternalID."""
    file_id = raw.get("file_id") or ""
    title = raw.get("title") or "(untitled)"
    timestamp = _iso(raw.get("updated_at") or raw.get("created_at")) or _now()
    art_slug = artifact_slug("drive", file_id)

    yield external_id_record("drive", file_id, timestamp)
    yield node(
        "Artifact",
        {
            "slug": art_slug,
            "name": title,
            "kind": "document",
            "source": "drive",
            "source_ref": file_id,
            "url": raw.get("url"),
            "content": raw.get("body"),
            "timestamp": timestamp,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    )


def transform_gcalendar(raw: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Each Calendar event → 1 Event + 1 ExternalID + attendees as Persons."""
    evt_id = raw.get("event_id") or ""
    title = raw.get("title") or "(untitled event)"
    start = _iso(raw.get("start_at")) or _now()
    end = _iso(raw.get("end_at"))
    created = _iso(raw.get("created_at")) or start
    evt_slug = event_slug("gcalendar", evt_id)

    yield external_id_record("calendar", evt_id, created)
    yield node(
        "Event",
        {
            "slug": evt_slug,
            "name": title,
            "kind": "meeting",
            "brief": raw.get("description"),
            "date": start,
            "end_date": end,
            "createdAt": created,
            "updatedAt": created,
        },
    )

    for attendee in raw.get("attendees") or []:
        email = attendee.get("email") if isinstance(attendee, dict) else None
        if not email:
            continue
        name = attendee.get("displayName") or email
        p_slug = person_slug(name, email)
        yield person_record(name, email)
        yield external_id_record("email", email, created)
        yield edge("IdentifiesPerson", external_id_slug("email", email), p_slug)
        yield edge("Attended", p_slug, evt_slug)


def transform_apple_notes(raw: dict[str, Any]) -> Iterable[dict[str, Any]]:
    note_id = raw.get("note_id") or ""
    title = raw.get("title") or "(untitled note)"
    body = raw.get("body") or ""
    created = _iso(raw.get("created_at")) or _now()
    updated = _iso(raw.get("updated_at")) or created
    art_slug = artifact_slug("apple-notes", note_id)
    nt_slug = note_slug("apple-notes", note_id)

    yield external_id_record("apple-notes", note_id, created)
    yield node(
        "Artifact",
        {
            "slug": art_slug,
            "name": title,
            "kind": "document",
            "source": "apple-notes",
            "source_ref": note_id,
            "content": body,
            "timestamp": updated,
            "createdAt": created,
            "updatedAt": updated,
        },
    )
    yield node(
        "Note",
        {
            "slug": nt_slug,
            "name": title,
            "kind": "idea",
            "content": body,
            "createdAt": created,
            "updatedAt": updated,
        },
    )
    yield edge("NoteFromArtifact", nt_slug, art_slug)


def transform_linkedin(raw: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """LinkedIn data export rows. _kind tells us which CSV they came from."""
    kind = raw.get("_kind")
    timestamp = _iso(raw.get("timestamp") or raw.get("connected_on")) or _now()

    if kind == "connection":
        name = " ".join(filter(None, [raw.get("first_name"), raw.get("last_name")])) or raw.get("email")
        email = raw.get("email")
        p_slug = person_slug(name, email)
        ext_id = email or name or uuid.uuid4().hex
        yield person_record(name, email, brief=raw.get("position"))
        yield external_id_record("linkedin", ext_id, timestamp)
        yield edge("IdentifiesPerson", external_id_slug("linkedin", ext_id), p_slug)
        if raw.get("company"):
            o_slug = org_slug(raw["company"])
            now = _now()
            yield node(
                "Organization",
                {"slug": o_slug, "name": raw["company"], "kind": "company", "createdAt": now, "updatedAt": now},
            )
            yield edge(
                "BelongsTo",
                p_slug,
                o_slug,
                {"role": raw.get("position"), "since": _iso(raw.get("connected_on")), "source": "linkedin", "current": True},
            )
        return

    if kind == "message":
        msg_id = raw.get("conversation_id", "") + "/" + (raw.get("date") or "")
        art_slug = artifact_slug("linkedin", msg_id)
        conv_slug = conversation_slug("linkedin", raw.get("conversation_id") or "unknown")
        yield external_id_record("linkedin", msg_id, timestamp)
        yield node(
            "Artifact",
            {
                "slug": art_slug,
                "name": (raw.get("content") or "")[:80] or "(empty)",
                "kind": "message",
                "source": "linkedin",
                "source_ref": msg_id,
                "content": raw.get("content"),
                "timestamp": timestamp,
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
        )
        yield node(
            "Conversation",
            {
                "slug": conv_slug,
                "external_id": raw.get("conversation_id") or "",
                "kind": "dm",
                "source": "linkedin",
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
        )
        yield edge("InConversation", art_slug, conv_slug)
        if raw.get("from"):
            p_slug = person_slug(raw["from"], None)
            yield person_record(raw["from"])
            yield edge("ArtifactFromPerson", art_slug, p_slug)
        return

    if kind == "post":
        post_id = raw.get("post_id") or raw.get("url") or uuid.uuid4().hex
        art_slug = artifact_slug("linkedin", post_id)
        yield external_id_record("linkedin", post_id, timestamp)
        yield node(
            "Artifact",
            {
                "slug": art_slug,
                "name": (raw.get("content") or "")[:80] or "(empty)",
                "kind": "post",
                "source": "linkedin",
                "source_ref": post_id,
                "url": raw.get("url"),
                "content": raw.get("content"),
                "timestamp": timestamp,
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
        )


def transform_whatsapp(raw: dict[str, Any]) -> Iterable[dict[str, Any]]:
    chat_id = raw.get("chat_id") or ""
    msg_id = raw.get("message_id") or f"{chat_id}/{raw.get('timestamp')}"
    text = raw.get("text") or ""
    sender = raw.get("sender")
    timestamp = _iso(raw.get("timestamp")) or _now()
    is_group = bool(raw.get("is_group"))

    art_slug = artifact_slug("whatsapp", msg_id)
    conv_slug = conversation_slug("whatsapp", chat_id)

    yield external_id_record("whatsapp", msg_id, timestamp)
    yield node(
        "Artifact",
        {
            "slug": art_slug,
            "name": (text[:80] + "…") if len(text) > 80 else text or "(empty)",
            "kind": "message",
            "source": "whatsapp",
            "source_ref": msg_id,
            "content": text,
            "timestamp": timestamp,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    )
    yield node(
        "Conversation",
        {
            "slug": conv_slug,
            "external_id": chat_id,
            "kind": "group" if is_group else "dm",
            "source": "whatsapp",
            "name": raw.get("chat_name"),
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    )
    yield edge("InConversation", art_slug, conv_slug)

    if sender:
        p_slug = person_slug(sender, None)
        yield person_record(sender)
        yield external_id_record("whatsapp", sender, timestamp)
        yield edge("IdentifiesPerson", external_id_slug("whatsapp", sender), p_slug)
        yield edge("ArtifactFromPerson", art_slug, p_slug)
        yield edge("ConversationWith", conv_slug, p_slug)


# ─── Dispatch ─────────────────────────────────────────────────────────────────

DISPATCH = {
    "obsidian": transform_obsidian,
    "notion": transform_notion,
    "granola": transform_granola,
    "slack": transform_slack,
    "gmail": transform_gmail,
    "gdrive": transform_gdrive,
    "gcalendar": transform_gcalendar,
    "apple-notes": transform_apple_notes,
    "linkedin": transform_linkedin,
    "whatsapp": transform_whatsapp,
}


def transform_record(raw: dict[str, Any]) -> Iterable[dict[str, Any]]:
    src = raw.get("_source")
    fn = DISPATCH.get(src)
    if not fn:
        sys.stderr.write(f"WARN: unknown source '{src}' in record {raw.get('id')}\n")
        return
    yield from fn(raw)


def sync_run_record(source_counts: dict[str, int], started_at: str) -> dict[str, Any]:
    completed = _now()
    sources = sorted(source_counts.keys())
    total = sum(source_counts.values())
    slug_basis = f"{','.join(sources)}/{started_at}"
    src_label = sources[0] if len(sources) == 1 else "manual"
    return node(
        "SyncRun",
        {
            "slug": f"sync-{_slugify(src_label)}-{_short_hash(slug_basis)}",
            "source": src_label,
            "started_at": started_at,
            "completed_at": completed,
            "status": "succeeded",
            "records_imported": total,
            "createdAt": completed,
            "updatedAt": completed,
        },
    )


def _read_raw_records(inputs: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for src_path in inputs:
        stream: Iterable[str]
        if src_path == "-":
            stream = sys.stdin
        else:
            stream = Path(src_path).open("r", encoding="utf-8")
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                sys.stderr.write(f"WARN: invalid JSON in {src_path}: {exc}\n")
                continue
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="*", default=["-"], help="Raw JSONL files (use '-' for stdin)")
    parser.add_argument("--out", type=Path, default=None, help="Output JSONL file (default: stdout)")
    args = parser.parse_args()

    started_at = _now()
    out_stream = args.out.open("w", encoding="utf-8") if args.out else sys.stdout
    source_counts: dict[str, int] = {}

    raw_records = _read_raw_records(args.inputs)
    for raw in raw_records:
        src = raw.get("_source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    # Pre-pass: collect all valid Note slugs being emitted, so we can drop
    # LinkedNote edges whose target doesn't resolve.
    valid_note_slugs: set[str] = set()
    for raw in raw_records:
        for emitted in transform_record(raw):
            if emitted.get("type") == "Note":
                valid_note_slugs.add(emitted["data"]["slug"])

    # Main pass with deduplication:
    # - Nodes deduped by (type, slug); on collision, keep the record with the
    #   most-recent updatedAt (or first if neither has it).
    # - Edges deduped by (edge_name, from, to, frozenset(data items)). Edges
    #   with the same triple but different payload (e.g. DerivedFromArtifact
    #   with different `activity` values) stay distinct.
    nodes_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    edges_seen: set[tuple[str, str, str, tuple]] = set()
    edges_in_order: list[dict[str, Any]] = []
    dropped_dangling: int = 0

    for raw in raw_records:
        for emitted in transform_record(raw):
            if "type" in emitted:
                key = (emitted["type"], emitted["data"].get("slug", ""))
                existing = nodes_by_key.get(key)
                if existing is None:
                    nodes_by_key[key] = emitted
                else:
                    new_ts = emitted["data"].get("updatedAt") or emitted["data"].get("timestamp") or ""
                    old_ts = existing["data"].get("updatedAt") or existing["data"].get("timestamp") or ""
                    if str(new_ts) > str(old_ts):
                        nodes_by_key[key] = emitted
            elif "edge" in emitted:
                if emitted["edge"] == "LinkedNote" and emitted.get("to") not in valid_note_slugs:
                    dropped_dangling += 1
                    continue
                data = emitted.get("data") or {}
                data_key = tuple(sorted((k, json.dumps(v, default=str, sort_keys=True)) for k, v in data.items()))
                triple = (emitted["edge"], emitted["from"], emitted["to"], data_key)
                if triple in edges_seen:
                    continue
                edges_seen.add(triple)
                edges_in_order.append(emitted)

    try:
        for node_rec in nodes_by_key.values():
            out_stream.write(json.dumps(node_rec, ensure_ascii=False, default=str))
            out_stream.write("\n")
        for edge_rec in edges_in_order:
            out_stream.write(json.dumps(edge_rec, ensure_ascii=False, default=str))
            out_stream.write("\n")
        # Trailing SyncRun summary record
        out_stream.write(json.dumps(sync_run_record(source_counts, started_at), ensure_ascii=False, default=str))
        out_stream.write("\n")
    finally:
        if args.out:
            out_stream.close()

    sys.stderr.write(
        f"transform: {sum(source_counts.values())} raw records → "
        f"{len(nodes_by_key)} nodes + {len(edges_in_order)} edges "
        f"(dropped {dropped_dangling} dangling LinkedNote edges; deduped collisions in single run)\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
