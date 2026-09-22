# CLAUDE.md — pharma-intel

Scoped guidance for the `pharma-intel/` starter. Repo-wide conventions live in `../CLAUDE.md`.

## What This Is

An Omnigraph schema + seed modeling competitive pharma intelligence from a sponsor's perspective. Uses the SPIKE framework for the intelligence layer, plus two additional layers: **external pipeline** (Compound, Mechanism, Trial, Company, Deal, RegulatoryAction) and **internal context** (Program, Assumption, Decision, OpenQuestion). Schema, seed data, and queries only — no application code.

The reference seed is **Viking Therapeutics** (NASDAQ: VKTX), a public GLP-1/GIP dual-agonist sponsor in obesity. All seed data is sourced from SEC filings, investor presentations, clinicaltrials.gov, and press releases — no MNPI.

## Key Files

- `schema.pg` — Executable Omnigraph schema. Source of truth.
- `README.md` — Reference seed description, schema essentials, quick start.
- `seed.md` / `seed.jsonl` — Seed dataset (human-readable / loadable).
- `queries/*.gq` — Read and mutation queries.
- `omnigraph-config.example.yaml` — Example operator config (aliases). Merge its `aliases:` into your per-user `~/.omnigraph/config.yaml`; this cookbook ships no `omnigraph.yaml`.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).

## Setup

The rules — `import` before the first `apply`, `load` addressing, `/healthz`, how aliases and
stored queries behave — are in `../CLAUDE.md`. This is that sequence with pharma-intel's names filled in:

```bash
cd pharma-intel
omnigraph cluster import --config .
omnigraph cluster plan   --config .
omnigraph cluster apply  --config . --as <you>     # creates graphs/pharma.omni
omnigraph load --data seed.jsonl --mode overwrite graphs/pharma.omni
omnigraph-server --cluster . --bind 127.0.0.1:8080 --unauthenticated &
curl -s http://127.0.0.1:8080/healthz
```

Graph id `pharma`. Stored queries and their parameters: `omnigraph queries list --cluster . --graph pharma`.
Alias args bind by name to `$params`: `omnigraph alias assumption-contradictions asmp-oral-displaces-injectable` is `omnigraph query assumption_contradicting_signals --graph pharma --params '{"slug":"asmp-oral-displaces-injectable"}'`.

## Writing

Aliases are read-only; mutations run as `omnigraph mutate <name> --params '<json>'` with every
non-optional property supplied. Signatures live in `queries/mutations.gq`. Working example:

```bash
omnigraph mutate add_signal --graph pharma --params '{"slug":"sig-orforglipron-approval","name":"FDA approves orforglipron","brief":"First oral small-molecule GLP-1 approved for obesity.","stagingTimestamp":"2026-09-14T00:00:00Z","createdAt":"2026-09-14T00:00:00Z","updatedAt":"2026-09-14T00:00:00Z"}'
omnigraph mutate link_about_compound --graph pharma --params '{"signal":"sig-orforglipron-approval","compound":"comp-vk2735-sc"}'
```

With `defaults.server` / `default_graph` from the operator config, `--graph` can be omitted.

## Domain Model

**External Pipeline:** `Compound`, `Mechanism`, `Trial`, `Company`, `Deal`, `RegulatoryAction`
**SPIKE Intelligence:** `Signal`, `Pattern`, `Insight`
**Provenance:** `SourceEntity`, `InformationArtifact`
**Internal Context:** `Program`, `Assumption`, `Decision`, `OpenQuestion`

**Core analytical loop:** Signals form or contradict Patterns (industry-intel style). But signals also edge to internal `Assumption`s and `OpenQuestion`s, which turns the graph into a live view of *which internal beliefs the latest external evidence supports or threatens*. `Decision`s bind programs, assumptions, and open questions into a single queryable object — so "what's on fire before the 2026-07 interim readout?" becomes a graph traversal, not a spreadsheet.

**Design choices to preserve:**

- Three layers, one graph — do not split into separate graphs
- `Assumption`, `Decision`, `OpenQuestion` are **nodes**, not properties on a program — they have their own evidence chains
- Flat enums everywhere: `phase`, `modality`, `route`, `domain`, `kind`, `level`, `status`
- Edge naming: `VerbTargetType` for pipeline/analytical edges (`FormsPattern`, `DevelopedByCompany`), `SignalIntentInternal` for bridge edges (`SupportsAssumption`, `ContradictsAssumption`, `InformsQuestion`)
- Seed data must be real and publicly sourced — every signal traces to an `InformationArtifact` with a live URL

## The Demo "Wow" Queries

These are the queries the seed is shaped to light up — preserve them when iterating:

| Alias | Input | Expected outcome |
|-------|-------|------------------|
| `assumption-contradictions` | `asmp-oral-displaces-injectable` | 2 signals (Pfizer + Structure) contradicting a strategic assumption from a different silo |
| `decision-questions` | `dec-vanquish-interim-readout` | The open question that needs to be answered before the committee meeting |
| `decision-assumptions` | `dec-oral-phase3-start` | Two assumptions — one currently contradicted, one supported |
| `pattern-contradictions` | `pat-oral-glp1-thesis` | The same Pfizer + Structure signals surfaced from the pattern angle |
| `signal-informs-questions` | `sig-pfizer-danuglipron-discontinued` | A Viking clinical-team open question informed by a Pfizer event |
| `program-landscape-signals` | `prog-vk2735-sc` | 5 signals across every compound targeting the program's mechanism, time-sorted — "what's happening in my space" |
| `mechanism-signals-via-compound` | `mech-gip-glp1-dual` | Same fan-out from the mechanism angle (transits Mechanism → Compound → Signal) |

If a schema or seed change breaks any of these, the three-layer model is not delivering — fix the seed rather than compromising the schema.

## Agent Workflow

Use this starter as a decision-intelligence loop, not just a lookup table:

1. Start from a decision, program, assumption, or fresh external signal.
2. Expand internal context with aliases like `decision-assumptions`, `decision-questions`, `program-competitors`, and `program-landscape-signals`.
3. Build the evidence matrix with `assumption-supports` and `assumption-contradictions`.
4. Trace signal impact with `signal-supports-assumptions`, `signal-contradicts-assumptions`, and `signal-informs-questions`.
5. If using web research, map each new public signal to existing graph objects before proposing data changes: `AboutCompound`, `RelevantCompany`, `FormsPattern` / `ContradictsPattern`, `SupportsAssumption` / `ContradictsAssumption`, and `InformsQuestion`.
6. Report the decision impact: what changed, which assumptions moved, which questions remain open, and which graph update should be made.

## When Editing

- Consult [Omnigraph schema principles](https://github.com/ModernRelay/omnigraph) for design guidance
- Use `@rename_from(...)` on property/type renames for migration support
- Keep README.md in sync with schema.pg
- Prefer semantic edge names over generic ones (`ContradictsAssumption` not `RelatedTo`)
- Required vs optional is deliberate — don't add `?` without reason
- No embeddings in v1 — the narrative surfaces are graph-structured, not vector-search-driven
