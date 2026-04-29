"""
Parallel Task API → Omnigraph demo
----------------------------------

Takes a list of account slugs + domains, fires a Parallel Task run per account
with a fixed output schema, then writes the resulting Claims (with full Basis
provenance) into the Omnigraph graph as a single JSONL patch.

Every Claim carries:
  - confidence (from Parallel's FieldBasis)
  - reasoning + source URLs (from FieldBasis)
  - a ResearchRun pointer with promptVersion + schemaVersion

Run:
    export PARALLEL_API_KEY=...
    python enrich.py --accounts acct-cognition acct-factory acct-pika

Emits:
    ./out/claims-<run-id>.jsonl

Load into Omnigraph:
    cd ..
    omnigraph load --data ./demo/out/claims-<run-id>.jsonl --mode merge \\
        /tmp/gtm-for-infra/repo
    # or against shared storage:
    #   set -a && source ./.env.omni && set +a
    #   omnigraph load --data ./demo/out/claims-<run-id>.jsonl --mode merge \\
    #       s3://omnigraph-local/repos/gtm-for-infra
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from parallel import Parallel


PROMPT_VERSION = "v5"
SCHEMA_VERSION = "v2"
PROCESSOR = "core"


# Output schema — what Parallel returns per account. Flat on purpose; each
# top-level field becomes one Claim. Parallel's FieldBasis carries confidence +
# citations per field automatically, so no need to ask for them here.
OUTPUT_SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "headcount": {
                "type": "string",
                "description": "Current employee headcount from LinkedIn or careers page",
            },
            "latest_funding_stage": {
                "type": "string",
                "description": "Most recent announced funding stage (e.g. series-b)",
            },
            "latest_lead_investor": {
                "type": "string",
                "description": "Name of the lead investor on the most recent round",
            },
            "last_funding_amount_usd": {
                "type": "string",
                "description": "Amount raised in the most recent round in USD (numeric string, no commas)",
            },
            "primary_workload_kind": {
                "type": "string",
                "description": "One of: training, inference, sandbox, batch, eval, data-pipeline",
            },
            "estimated_annual_revenue_usd": {
                "type": "string",
                "description": "Best-available bottoms-up estimate of current annual revenue in USD",
            },
        },
        "required": ["headcount", "latest_funding_stage"],
    },
}


INPUT_SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "account_slug": {"type": "string"},
            "account_name": {"type": "string"},
            "domain": {"type": "string"},
        },
        "required": ["account_slug", "account_name", "domain"],
    },
}


# Account roster the demo will enrich. In a real pipeline this would come from
# your CRM / a Monitor API webhook. Keep short for a fast demo loop.
DEMO_ACCOUNTS = {
    "acct-cognition": ("Cognition (Devin)", "cognition.ai"),
    "acct-factory": ("Factory", "factory.ai"),
    "acct-pika": ("Pika Labs", "pika.art"),
    "acct-krea": ("Krea", "krea.ai"),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_task_spec() -> dict[str, Any]:
    return {
        "input_schema": INPUT_SCHEMA,
        "output_schema": OUTPUT_SCHEMA,
    }


def run_enrichment(
    client: Parallel, account_slug: str, account_name: str, domain: str
) -> dict[str, Any]:
    run = client.task_run.create(
        input={
            "account_slug": account_slug,
            "account_name": account_name,
            "domain": domain,
        },
        task_spec=build_task_spec(),
        processor=PROCESSOR,
        metadata={"prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION},
    )
    result = client.task_run.result(run.run_id, api_timeout=3600)
    return {
        "run_id": run.run_id,
        "output": result.output.content if result.output else {},
        "basis": result.output.basis if result.output else [],
    }


def emit_research_run(run_slug: str, task_id: str, ran_at: str) -> dict[str, Any]:
    return {
        "type": "ResearchRun",
        "data": {
            "id": run_slug,
            "slug": run_slug,
            "taskId": task_id,
            "processor": PROCESSOR,
            "promptVersion": PROMPT_VERSION,
            "schemaVersion": SCHEMA_VERSION,
            "ranAt": ran_at,
            "createdAt": ran_at,
        },
    }


def emit_source(source_slug: str, url: str, title: str | None) -> dict[str, Any]:
    return {
        "type": "Source",
        "data": {
            "id": source_slug,
            "slug": source_slug,
            "url": url,
            "title": title,
            "createdAt": now_iso(),
        },
    }


def emit_claim(
    claim_slug: str,
    predicate: str,
    value: str,
    confidence: str,
    reasoning: str | None,
    asserted_at: str,
) -> dict[str, Any]:
    return {
        "type": "Claim",
        "data": {
            "id": claim_slug,
            "slug": claim_slug,
            "predicate": predicate,
            "value": value,
            "confidence": confidence,
            "reasoning": reasoning,
            "assertedAt": asserted_at,
            "createdAt": asserted_at,
        },
    }


def edge(edge_type: str, src: str, dst: str) -> dict[str, Any]:
    return {"edge": edge_type, "from": src, "to": dst, "data": {}}


def stable_source_slug(url: str) -> str:
    # Deterministic short slug from URL so we don't re-create the same Source
    # twice within one run.
    digest = uuid.uuid5(uuid.NAMESPACE_URL, url).hex[:12]
    return f"src-{digest}"


def _as_dict(obj: Any) -> dict[str, Any]:
    # Parallel SDK returns pydantic models; normalize to plain dicts.
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return dict(obj)


def patches_for_account(
    account_slug: str,
    run_slug: str,
    output: dict[str, Any],
    basis: list[Any],
    asserted_at: str,
) -> Iterable[dict[str, Any]]:
    # One Claim per top-level output field. Cite every FieldBasis citation
    # URL as a Source node, grounded via GroundedInSource.
    basis_by_field: dict[str, dict[str, Any]] = {}
    for b in (basis or []):
        bd = _as_dict(b)
        if bd.get("field"):
            basis_by_field[bd["field"]] = bd

    output = _as_dict(output)
    for field, value in output.items():
        if value in (None, ""):
            continue

        field_basis = basis_by_field.get(field, {})
        confidence = (field_basis.get("confidence") or "medium").lower()
        reasoning = field_basis.get("reasoning")
        citations = field_basis.get("citations") or []

        claim_slug = f"claim-{account_slug.removeprefix('acct-')}-{field}-{PROMPT_VERSION}"

        yield emit_claim(
            claim_slug,
            predicate=field,
            value=str(value),
            confidence=confidence,
            reasoning=reasoning,
            asserted_at=asserted_at,
        )
        yield edge("AssertedClaim", run_slug, claim_slug)
        yield edge("AboutAccount", claim_slug, account_slug)

        for cite in citations:
            cd = _as_dict(cite)
            url = cd.get("url")
            if not url:
                continue
            source_slug = stable_source_slug(url)
            yield emit_source(source_slug, url, cd.get("title"))
            yield edge("GroundedInSource", claim_slug, source_slug)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--accounts",
        nargs="+",
        default=list(DEMO_ACCOUNTS.keys()),
        help="Account slugs to enrich (default: demo roster)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent / "out",
        help="Output directory for the JSONL patch",
    )
    args = parser.parse_args()

    api_key = os.environ.get("PARALLEL_API_KEY")
    if not api_key:
        print("PARALLEL_API_KEY is not set", file=sys.stderr)
        return 1

    client = Parallel(api_key=api_key)
    args.out.mkdir(parents=True, exist_ok=True)

    run_slug = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    ran_at = now_iso()

    patch: list[dict[str, Any]] = []

    # We create one ResearchRun node per batch — conceptually this is the
    # "one prompt version ran across these accounts" anchor.
    first_task_id: str | None = None

    for slug in args.accounts:
        if slug not in DEMO_ACCOUNTS:
            print(f"Skipping unknown account {slug}", file=sys.stderr)
            continue
        name, domain = DEMO_ACCOUNTS[slug]
        print(f"Enriching {slug} ({domain}) ...", file=sys.stderr)
        try:
            res = run_enrichment(client, slug, name, domain)
        except Exception as exc:
            print(f"  failed: {exc}", file=sys.stderr)
            continue

        first_task_id = first_task_id or res["run_id"]
        patch.extend(
            patches_for_account(
                slug, run_slug, res["output"], res["basis"], ran_at
            )
        )

    if first_task_id is None:
        print("No successful runs", file=sys.stderr)
        return 2

    # Prepend the ResearchRun node so Claim.AssertedClaim edges resolve.
    patch.insert(0, emit_research_run(run_slug, first_task_id, ran_at))

    out_file = args.out / f"claims-{run_slug}.jsonl"
    with out_file.open("w") as f:
        for row in patch:
            f.write(json.dumps(row) + "\n")

    print(f"Wrote {len(patch)} rows → {out_file}")
    print()
    print("Load with:")
    print(
        f"  omnigraph load --data {out_file.relative_to(Path.cwd())} "
        f"--mode merge /tmp/gtm-for-infra/repo"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
