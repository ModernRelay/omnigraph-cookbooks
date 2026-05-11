#!/usr/bin/env python3
"""
Walk an Obsidian vault and emit one rich JSONL record per markdown file.

This is the *raw extraction* layer. Every fact we can pull out of a note —
frontmatter, tags, wiki-links, external links, headings, timestamps — comes
along in a single record. Schema mapping happens in a later step against
whatever ontology the cookbook adopts.

Usage:
    python import_obsidian.py --vault ~/MyVault --workspace-name my-vault
    python import_obsidian.py --vault ./test-vault --workspace-name test --out raw.jsonl

Exit codes: 0 on success, 1 on argument or filesystem error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    import frontmatter  # python-frontmatter
except ImportError:
    sys.stderr.write(
        "ERROR: python-frontmatter not installed.\n"
        "  pip install -r requirements.txt   # or: pip install python-frontmatter\n"
    )
    sys.exit(1)


SKIP_DIRS = {".obsidian", ".trash", ".git", ".github", "node_modules"}

WIKI_LINK_RE = re.compile(r"\[\[([^\]\[\|\n]+?)(?:\|([^\]\[\n]+))?\]\]")
EXTERNAL_LINK_RE = re.compile(r"(?<!!)\[([^\]\n]+)\]\((https?://[^\)\s]+)\)")
INLINE_TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z][\w/\-]*)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def slugify_path(workspace: str, relative_path: str) -> str:
    """Stable, human-readable slug from workspace + relative path. Collision-safe via short hash suffix."""
    stem = relative_path
    if stem.lower().endswith(".md"):
        stem = stem[:-3]
    cleaned = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    h = hashlib.sha256(f"{workspace}/{relative_path}".encode("utf-8")).hexdigest()[:8]
    ws = re.sub(r"[^a-z0-9]+", "-", workspace.lower()).strip("-") or "vault"
    return f"note-obs-{ws}-{cleaned}-{h}" if cleaned else f"note-obs-{ws}-{h}"


def file_birthtime(path: Path) -> str | None:
    """Best-effort file creation timestamp (Mac st_birthtime, otherwise None)."""
    try:
        st = path.stat()
        bt = getattr(st, "st_birthtime", None)
        if bt:
            return dt.datetime.fromtimestamp(bt, tz=dt.timezone.utc).isoformat()
    except OSError:
        return None
    return None


def file_mtime(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).isoformat()


def normalize_frontmatter_dates(meta: dict[str, Any]) -> tuple[str | None, str | None]:
    """Look for common created/updated keys in frontmatter."""
    created_keys = ("created", "created_at", "createdAt", "date")
    updated_keys = ("updated", "updated_at", "updatedAt", "modified", "last_modified")
    created = None
    updated = None
    for k in created_keys:
        if k in meta and meta[k]:
            created = _coerce_iso(meta[k])
            break
    for k in updated_keys:
        if k in meta and meta[k]:
            updated = _coerce_iso(meta[k])
            break
    return created, updated


def _coerce_iso(value: Any) -> str | None:
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.isoformat()
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=dt.timezone.utc).isoformat()
    if isinstance(value, str):
        return value
    return None


def extract_tags(meta: dict[str, Any], body: str) -> list[str]:
    raw: list[str] = []
    fm_tags = meta.get("tags") or meta.get("tag")
    if isinstance(fm_tags, str):
        raw.extend(t.strip() for t in re.split(r"[,\s]+", fm_tags) if t.strip())
    elif isinstance(fm_tags, list):
        raw.extend(str(t).strip() for t in fm_tags if str(t).strip())
    raw.extend(m.group(1) for m in INLINE_TAG_RE.finditer(body))
    seen = set()
    out: list[str] = []
    for tag in raw:
        normalized = tag.lstrip("#").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def extract_wiki_links(body: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen = set()
    for m in WIKI_LINK_RE.finditer(body):
        target = m.group(1).strip()
        alias = (m.group(2) or "").strip()
        key = (target, alias)
        if key in seen:
            continue
        seen.add(key)
        link: dict[str, str] = {"target": target}
        if alias:
            link["alias"] = alias
        out.append(link)
    return out


def extract_external_links(body: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen = set()
    for m in EXTERNAL_LINK_RE.finditer(body):
        text = m.group(1).strip()
        url = m.group(2).strip()
        if url in seen:
            continue
        seen.add(url)
        out.append({"text": text, "url": url})
    return out


def extract_headings(body: str) -> list[dict[str, Any]]:
    return [{"level": len(m.group(1)), "text": m.group(2).strip()} for m in HEADING_RE.finditer(body)]


def derive_title(meta: dict[str, Any], body: str, fallback: str) -> str:
    title = meta.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line:
            break
    return fallback


def iter_markdown_files(vault: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in files:
            if name.lower().endswith(".md"):
                yield Path(root) / name


def build_record(vault: Path, path: Path, workspace_name: str) -> dict[str, Any]:
    rel = path.relative_to(vault).as_posix()
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    post = frontmatter.loads(raw_text)
    meta = dict(post.metadata or {})
    body = post.content or ""
    fm_created, fm_updated = normalize_frontmatter_dates(meta)
    return {
        "_source": "obsidian",
        "_source_format": "obsidian-markdown",
        "id": slugify_path(workspace_name, rel),
        "workspace_name": workspace_name,
        "relative_path": rel,
        "file_name": path.stem,
        "title": derive_title(meta, body, path.stem),
        "body": body,
        "frontmatter": meta,
        "tags": extract_tags(meta, body),
        "wiki_links": extract_wiki_links(body),
        "external_links": extract_external_links(body),
        "headings": extract_headings(body),
        "created_at": fm_created or file_birthtime(path) or file_mtime(path),
        "updated_at": fm_updated or file_mtime(path),
        "size_bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--vault", required=True, type=Path, help="Path to the Obsidian vault root")
    parser.add_argument(
        "--workspace-name", required=True, help="Logical name for this vault (e.g. 'my-vault')"
    )
    parser.add_argument("--out", type=Path, default=None, help="Output JSONL file (default: stdout)")
    parser.add_argument(
        "--since",
        default=None,
        help="Only include files with mtime >= this ISO datetime (e.g. 2026-05-01T00:00:00Z). Skipped files reduce import size on re-runs.",
    )
    args = parser.parse_args()

    vault: Path = args.vault.expanduser().resolve()
    if not vault.exists() or not vault.is_dir():
        sys.stderr.write(f"ERROR: vault path does not exist or is not a directory: {vault}\n")
        return 1

    since_ts: float | None = None
    if args.since:
        try:
            since_ts = dt.datetime.fromisoformat(args.since.replace("Z", "+00:00")).timestamp()
        except ValueError:
            sys.stderr.write(f"ERROR: --since not a valid ISO datetime: {args.since}\n")
            return 1

    out_stream = args.out.open("w", encoding="utf-8") if args.out else sys.stdout
    count = 0
    skipped = 0
    errors = 0
    try:
        for md_path in iter_markdown_files(vault):
            if since_ts is not None and md_path.stat().st_mtime < since_ts:
                skipped += 1
                continue
            try:
                record = build_record(vault, md_path, args.workspace_name)
            except Exception as exc:
                errors += 1
                sys.stderr.write(f"WARN: failed to parse {md_path}: {exc}\n")
                continue
            out_stream.write(json.dumps(record, ensure_ascii=False, default=str))
            out_stream.write("\n")
            count += 1
    finally:
        if args.out:
            out_stream.close()

    sys.stderr.write(f"obsidian: emitted {count} records ({skipped} skipped via --since, {errors} parse errors)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
