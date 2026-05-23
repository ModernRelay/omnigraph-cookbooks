#!/usr/bin/env python3
"""
Parallel → Omnigraph funding ingest.

Reads a Parallel CLI enrichment CSV (produced by `parallel-cli enrich run ...
--target out.csv`) and writes funding Signals + Measurements + Decisions
into the revops graph via `omnigraph change`.

This is the canonical Modal-style pipeline:
  Parallel enrich → structured rows → omnigraph mutations → graph state.

No Snowflake in the middle. The graph is the source of truth, the audit trail,
and the lookup endpoint.

Usage:
    parallel-cli enrich run \
        --data '[{"company":"Cognition","domain":"cognition.ai"}, ...]' \
        --intent "find latest funding round and total funding" \
        --processor core \
        --target /tmp/parallel-out.csv

    python ingest/parallel_funding_ingest.py /tmp/parallel-out.csv \
        --slug-map cognition.ai=acc-cognition,cursor.com=acc-cursor,decagon.ai=acc-decagon \
        --actor act-agent-classifier \
        --policy pol-prompt-classifier-v2 \
        --source src-parallel-task
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path


# ── parsing helpers ─────────────────────────────────────────────────────────

# Strip "$2,300,000,000", "$2.3 billion", "$2.3B", or "$285M" -> USD.
_BILLION = re.compile(r"([\d.]+)\s*(?:billion|bn|b)\b", re.I)
_MILLION = re.compile(r"([\d.]+)\s*(?:million|mn|m)\b", re.I)
_MONEY_TOKEN = re.compile(
    r"\$?\s*[\d,.]+(?:\.\d+)?\s*(?:billion|million|bn|mn|b|m)\b|\$[\d,.]+(?:\.\d+)?",
    re.I,
)


def parse_usd(value: str) -> float | None:
    if not value or value.strip().lower() in ("undisclosed", "unknown", "n/a", ""):
        return None
    s = value.strip().replace("$", "").replace(",", "").replace(" ", "")
    if m := _BILLION.search(s):
        return float(m.group(1)) * 1_000_000_000
    if m := _MILLION.search(s):
        return float(m.group(1)) * 1_000_000
    try:
        return float(s)
    except ValueError:
        return None


_DATE_FORMATS = ["%Y-%m-%d", "%b %d, %Y", "%B %Y", "%b %Y", "%Y"]


def parse_date(value: str) -> dt.date | None:
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class FundingFact:
    """Parsed first row of the `funding_rounds` field — the most recent round."""

    stage: str | None              # "Series D"
    amount_usd: float | None       # 2_300_000_000
    valuation_usd: float | None    # 29_300_000_000 (post-money)
    occurred_on: dt.date | None    # 2025-11-13
    raw: str                       # original Parallel text


def parse_latest_round(funding_rounds: str) -> FundingFact | None:
    """
    Parallel returns funding_rounds as a Python-list-as-string. Take the first
    element (most recent) and extract structured fields heuristically. This is
    intentionally lenient — real-world Parallel output is high-quality but
    not strictly normalized; we want graceful degradation, not strictness.
    """
    if not funding_rounds:
        return None
    try:
        rounds = json.loads(funding_rounds.replace("'", '"'))
    except json.JSONDecodeError:
        # Fall back to splitting the literal Python list
        rounds = [r.strip(" []'") for r in funding_rounds.strip("[]").split("', '")]
    if not rounds:
        return None
    first = rounds[0]

    stage_match = re.search(r"(Series\s+[A-Z]+|Seed|Pre-Seed|Early\s+rounds)", first, re.I)
    stage = stage_match.group(1) if stage_match else None

    valuation = None
    val_match = (
        re.search(r"(\$?\s*[\d.,]+(?:\.\d+)?\s*(?:billion|million|bn|mn|b|m)\b)\s+(?:post-money\s+)?valuation", first, re.I)
        or re.search(r"valuation[^\d$]{0,40}(\$?\s*[\d.,]+(?:\.\d+)?\s*(?:billion|million|bn|mn|b|m)\b)", first, re.I)
    )
    if val_match:
        valuation = parse_usd(val_match.group(1))

    # Pull monetary tokens. The first token is conventionally the round size.
    amount = None
    amounts = _MONEY_TOKEN.findall(first)
    if amounts:
        amount = parse_usd(amounts[0])
        if amount == valuation and len(amounts) > 1:
            amount = parse_usd(amounts[1])

    occurred = None
    for d in re.findall(r"\d{4}-\d{2}-\d{2}|[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|[A-Z][a-z]+\s+\d{4}", first):
        if parsed := parse_date(d):
            occurred = parsed
            break

    return FundingFact(stage=stage, amount_usd=amount, valuation_usd=valuation,
                       occurred_on=occurred, raw=first)


# ── omnigraph change helpers ────────────────────────────────────────────────

def change(alias: str, *args: str, dry_run: bool = False) -> None:
    cmd = ["omnigraph", "change", "--alias", alias, *args]
    if dry_run:
        print("[dry-run]", " ".join(cmd))
        return
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAIL {alias}: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    line = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
    print(f"OK   {alias} {' '.join(args)[:80]}  → {line[:60]}")


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def short_id() -> str:
    return uuid.uuid4().hex[:8]


def row_value(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return value.strip()
    return ""


# ── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Ingest Parallel funding enrichment into Omnigraph.")
    p.add_argument("csv_file", help="Parallel enrich CSV output")
    p.add_argument("--slug-map", required=True,
                   help="domain=slug,domain=slug,... mapping rows to Account slugs")
    p.add_argument("--actor", default="act-agent-classifier",
                   help="Actor slug that ran the enrichment")
    p.add_argument("--policy", default="pol-prompt-classifier-v2",
                   help="Policy slug (prompt version) used")
    p.add_argument("--source", default="src-parallel-task",
                   help="Source slug for provenance")
    p.add_argument("--dry-run", action="store_true",
                   help="Print mutations without executing")
    args = p.parse_args()

    slug_map = dict(pair.split("=", 1) for pair in args.slug_map.split(","))
    now = now_iso()
    today = dt.date.today().isoformat()
    batch = short_id()

    with open(args.csv_file) as f:
        for row in csv.DictReader(f):
            domain = row_value(row, "domain", "company_domain", "website")
            account_slug = slug_map.get(domain)
            if not account_slug:
                print(f"skip: no slug mapped for {domain}", file=sys.stderr)
                continue

            company = row_value(row, "company", "company_name", "name") or domain
            fact = parse_latest_round(row_value(row, "funding_rounds", "latest_funding_round", "latest_round"))
            total_funding = parse_usd(row_value(row, "total_funding_usd", "total_funding", "funding_total"))
            tag = short_id()

            # 1. Funding Signal for the latest round
            if fact:
                sig_slug = f"sig-{account_slug.removeprefix('acc-')}-funding-{tag}"
                signal_name = f"{company}: {fact.stage or 'funding round'}"
                captured = fact.occurred_on.isoformat() + "T00:00:00Z" if fact.occurred_on else now
                brief = fact.raw[:240]
                change("add-signal", "--params",
                       json.dumps({"slug": sig_slug, "name": signal_name, "kind": "funding",
                                   "strength": "strong", "capturedAt": captured,
                                   "brief": brief, "createdAt": now}),
                       dry_run=args.dry_run)
                change("link-signal-on-account", "--params",
                       json.dumps({"signal": sig_slug, "account": account_slug}),
                       dry_run=args.dry_run)
                change("link-signal-source", "--params",
                       json.dumps({"signal": sig_slug, "source": args.source}),
                       dry_run=args.dry_run)
            else:
                sig_slug = None

            # 2. Measurement: total funding to date
            if total_funding is not None:
                meas_slug = f"meas-{account_slug.removeprefix('acc-')}-funding-{tag}"
                change("add-measurement", "--params",
                       json.dumps({"slug": meas_slug, "metricKey": "funding_raised_usd",
                                   "value": total_funding, "observedAt": now, "createdAt": now}),
                       dry_run=args.dry_run)
                change("link-measures-account", "--params",
                       json.dumps({"measurement": meas_slug, "account": account_slug}),
                       dry_run=args.dry_run)
                change("link-measures-source", "--params",
                       json.dumps({"measurement": meas_slug, "source": args.source}),
                       dry_run=args.dry_run)
            else:
                meas_slug = None

            # 3. Decision recording the enrichment run
            dec_slug = f"dec-enrich-{account_slug.removeprefix('acc-')}-{tag}"
            rationale = (f"Parallel-enriched funding facts. "
                         f"Latest: {fact.raw[:140] if fact else 'unknown'}")
            change("add-decision", "--params",
                   json.dumps({"slug": dec_slug, "intent": "enrich_funding",
                               "domain": "sales", "status": "approved",
                               "assertion": "fact", "rationale": rationale,
                               "decidedAt": now, "createdAt": now}),
                   dry_run=args.dry_run)
            change("link-made-by", "--params",
                   json.dumps({"decision": dec_slug, "actor": args.actor}),
                   dry_run=args.dry_run)
            change("link-decision-targets-account", "--params",
                   json.dumps({"decision": dec_slug, "account": account_slug}),
                   dry_run=args.dry_run)
            change("link-screened-by", "--params",
                   json.dumps({"decision": dec_slug, "policy": args.policy, "outcome": "passed"}),
                   dry_run=args.dry_run)
            if sig_slug:
                change("link-informed-by", "--params",
                       json.dumps({"decision": dec_slug, "signal": sig_slug,
                                   "influence": "primary"}),
                       dry_run=args.dry_run)
            if meas_slug:
                change("link-measures-decision", "--params",
                       json.dumps({"measurement": meas_slug, "decision": dec_slug}),
                       dry_run=args.dry_run)

            print(f"-- ingested {company} ({account_slug}) --")

    print(f"\nbatch {batch} ingested at {now}")


if __name__ == "__main__":
    main()
