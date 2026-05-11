#!/usr/bin/env python3
"""
Walk a Notion workspace via the Notion API and emit one rich JSONL record per page.

This is the *raw extraction* layer. Every fact we can pull out of a page —
title, body (block plaintext), full property dict, mentions of people and other
pages, page-to-page relations, timestamps — comes along in a single record.
Schema mapping happens in a later step against whatever ontology the cookbook adopts.

Setup (one-time):
    1. Go to https://www.notion.so/my-integrations and create an internal integration
    2. Copy the integration token (starts with `ntn_` or `secret_`)
    3. In any Notion page or database you want imported, click ··· → Connections → add the integration

Usage:
    NOTION_TOKEN=ntn_xxx python import_notion.py --workspace-name my-notion
    NOTION_TOKEN=ntn_xxx python import_notion.py --workspace-name my-notion --database-id <id> --out raw.jsonl

Exit codes: 0 on success, 1 on argument / auth / network error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

try:
    from notion_client import Client
    from notion_client.errors import APIResponseError
except ImportError:
    sys.stderr.write(
        "ERROR: notion-client not installed.\n"
        "  pip install -r requirements.txt   # or: pip install notion-client\n"
    )
    sys.exit(1)


PAGE_SIZE = 100
THROTTLE_SECONDS = 0.34  # Notion API limit is 3 req/sec; stay well under.


def workspace_slug(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "workspace"


def page_id_compact(page_id: str) -> str:
    return page_id.replace("-", "")


def make_note_id(workspace_name: str, page_id: str) -> str:
    return f"note-notion-{workspace_slug(workspace_name)}-{page_id_compact(page_id)}"


def make_person_id(user_id: str) -> str:
    return f"person-notion-{page_id_compact(user_id)}"


def derive_title(properties: dict[str, Any]) -> str:
    """Notion stores the page title as the property whose type is 'title'."""
    for _, prop in properties.items():
        if prop.get("type") == "title":
            return _rich_text_plain(prop.get("title", []))
    return ""


def _rich_text_plain(rich: list[dict[str, Any]] | None) -> str:
    if not rich:
        return ""
    return "".join(part.get("plain_text", "") for part in rich)


def _extract_mentions_and_relations(rich: list[dict[str, Any]] | None, mentions: list[dict[str, Any]], relations: list[dict[str, Any]]) -> None:
    if not rich:
        return
    for part in rich:
        m = part.get("mention")
        if not m:
            continue
        mtype = m.get("type")
        if mtype == "user":
            user = m.get("user") or {}
            mentions.append(
                {
                    "kind": "user",
                    "user_id": user.get("id"),
                    "name": user.get("name"),
                    "person_id": make_person_id(user["id"]) if user.get("id") else None,
                }
            )
        elif mtype == "page":
            page = m.get("page") or {}
            relations.append({"kind": "page_mention", "page_id": page.get("id")})
        elif mtype == "database":
            db = m.get("database") or {}
            relations.append({"kind": "database_mention", "database_id": db.get("id")})


def block_to_text(block: dict[str, Any], mentions: list[dict[str, Any]], relations: list[dict[str, Any]]) -> str:
    """Extract plaintext from a single block. Mutates `mentions` and `relations`."""
    btype = block.get("type")
    payload = block.get(btype) if btype else None
    if not payload:
        return ""
    rich = payload.get("rich_text") or payload.get("text") or []
    _extract_mentions_and_relations(rich, mentions, relations)
    text = _rich_text_plain(rich)

    # Special-case: child page references (which appear as block type 'child_page')
    if btype == "child_page":
        relations.append({"kind": "child_page", "title": payload.get("title")})

    if btype == "heading_1":
        return f"# {text}"
    if btype == "heading_2":
        return f"## {text}"
    if btype == "heading_3":
        return f"### {text}"
    if btype == "bulleted_list_item":
        return f"- {text}"
    if btype == "numbered_list_item":
        return f"1. {text}"
    if btype == "to_do":
        checked = "x" if payload.get("checked") else " "
        return f"- [{checked}] {text}"
    if btype == "quote":
        return f"> {text}"
    if btype == "code":
        return f"```{payload.get('language','')}\n{text}\n```"
    return text


def fetch_all_blocks(client: Client, page_id: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        time.sleep(THROTTLE_SECONDS)
        kwargs: dict[str, Any] = {"block_id": page_id, "page_size": PAGE_SIZE}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.blocks.children.list(**kwargs)
        blocks.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return blocks


def normalize_property(prop: dict[str, Any]) -> Any:
    """Reduce a Notion property to a plain JSON-friendly value."""
    ptype = prop.get("type")
    if ptype == "title":
        return _rich_text_plain(prop.get("title", []))
    if ptype == "rich_text":
        return _rich_text_plain(prop.get("rich_text", []))
    if ptype == "number":
        return prop.get("number")
    if ptype == "select":
        return (prop.get("select") or {}).get("name")
    if ptype == "multi_select":
        return [opt.get("name") for opt in prop.get("multi_select", [])]
    if ptype == "status":
        return (prop.get("status") or {}).get("name")
    if ptype == "date":
        return prop.get("date")
    if ptype == "people":
        return [
            {"id": p.get("id"), "name": p.get("name"), "person_id": make_person_id(p["id"]) if p.get("id") else None}
            for p in prop.get("people", [])
        ]
    if ptype == "checkbox":
        return prop.get("checkbox")
    if ptype == "url":
        return prop.get("url")
    if ptype == "email":
        return prop.get("email")
    if ptype == "phone_number":
        return prop.get("phone_number")
    if ptype == "relation":
        return [r.get("id") for r in prop.get("relation", [])]
    if ptype == "files":
        return [f.get("name") for f in prop.get("files", [])]
    if ptype == "created_time":
        return prop.get("created_time")
    if ptype == "last_edited_time":
        return prop.get("last_edited_time")
    if ptype == "created_by":
        return (prop.get("created_by") or {}).get("id")
    if ptype == "last_edited_by":
        return (prop.get("last_edited_by") or {}).get("id")
    if ptype == "formula":
        return prop.get("formula")
    if ptype == "rollup":
        return prop.get("rollup")
    return prop  # unknown type — keep raw


def normalize_properties(properties: dict[str, Any]) -> dict[str, Any]:
    return {name: normalize_property(prop) for name, prop in (properties or {}).items()}


def parent_ref(parent: dict[str, Any]) -> dict[str, Any]:
    out = {"type": parent.get("type")}
    for k in ("page_id", "database_id", "workspace", "block_id"):
        if k in parent:
            out[k] = parent[k]
    return out


def iter_pages(client: Client, database_id: str | None, since_iso: str | None) -> Iterable[dict[str, Any]]:
    if database_id:
        yield from _iter_database_pages(client, database_id, since_iso)
        return
    yield from _iter_search_pages(client, since_iso)


def _iter_database_pages(client: Client, database_id: str, since_iso: str | None) -> Iterable[dict[str, Any]]:
    cursor: str | None = None
    while True:
        time.sleep(THROTTLE_SECONDS)
        kwargs: dict[str, Any] = {"database_id": database_id, "page_size": PAGE_SIZE}
        if since_iso:
            kwargs["filter"] = {
                "timestamp": "last_edited_time",
                "last_edited_time": {"on_or_after": since_iso},
            }
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.databases.query(**kwargs)
        for page in resp.get("results", []):
            yield page
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")


def _iter_search_pages(client: Client, since_iso: str | None) -> Iterable[dict[str, Any]]:
    """Search has no native time filter; fetch all and filter client-side."""
    cursor: str | None = None
    while True:
        time.sleep(THROTTLE_SECONDS)
        kwargs: dict[str, Any] = {
            "filter": {"value": "page", "property": "object"},
            "page_size": PAGE_SIZE,
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
        }
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.search(**kwargs)
        for page in resp.get("results", []):
            if since_iso and (page.get("last_edited_time") or "") < since_iso:
                # Sorted descending — once we drop below the threshold, we're done.
                return
            yield page
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")


def build_record(client: Client, page: dict[str, Any], workspace_name: str) -> dict[str, Any]:
    page_id: str = page["id"]
    properties = page.get("properties", {})
    mentions: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []

    blocks = fetch_all_blocks(client, page_id)
    body_lines: list[str] = []
    for blk in blocks:
        text = block_to_text(blk, mentions, relations)
        if text:
            body_lines.append(text)
    body = "\n\n".join(body_lines)

    return {
        "_source": "notion",
        "_source_format": "notion-page",
        "id": make_note_id(workspace_name, page_id),
        "workspace_name": workspace_name,
        "page_id": page_id,
        "url": page.get("url"),
        "public_url": page.get("public_url"),
        "title": derive_title(properties),
        "body": body,
        "properties": normalize_properties(properties),
        "mentions": mentions,
        "relations": relations,
        "parent": parent_ref(page.get("parent", {})),
        "created_at": page.get("created_time"),
        "updated_at": page.get("last_edited_time"),
        "created_by": (page.get("created_by") or {}).get("id"),
        "last_edited_by": (page.get("last_edited_by") or {}).get("id"),
        "archived": page.get("archived", False),
        "block_count": len(blocks),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace-name", required=True, help="Logical name for this Notion workspace")
    parser.add_argument(
        "--database-id",
        default=None,
        help="Optional: only import pages in this database. If omitted, search all pages the integration can see.",
    )
    parser.add_argument("--out", type=Path, default=None, help="Output JSONL file (default: stdout)")
    parser.add_argument(
        "--token-env",
        default="NOTION_TOKEN",
        help="Environment variable holding the Notion integration token (default: NOTION_TOKEN)",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Only include pages with last_edited_time >= this ISO datetime. Cuts re-import size dramatically.",
    )
    args = parser.parse_args()

    token = os.environ.get(args.token_env)
    if not token:
        sys.stderr.write(
            f"ERROR: ${args.token_env} not set. Create an internal integration at "
            f"https://www.notion.so/my-integrations and export the token.\n"
        )
        return 1

    client = Client(auth=token)
    out_stream = args.out.open("w", encoding="utf-8") if args.out else sys.stdout
    count = 0
    errors = 0
    try:
        for page in iter_pages(client, args.database_id, args.since):
            try:
                record = build_record(client, page, args.workspace_name)
            except APIResponseError as exc:
                errors += 1
                sys.stderr.write(f"WARN: Notion API error on page {page.get('id')}: {exc}\n")
                continue
            except Exception as exc:
                errors += 1
                sys.stderr.write(f"WARN: failed to process page {page.get('id')}: {exc}\n")
                continue
            out_stream.write(json.dumps(record, ensure_ascii=False, default=str))
            out_stream.write("\n")
            count += 1
    finally:
        if args.out:
            out_stream.close()

    sys.stderr.write(f"notion: emitted {count} records ({errors} errors)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
