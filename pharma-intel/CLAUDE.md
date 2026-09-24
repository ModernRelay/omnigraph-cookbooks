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

## Answering and writing (agents)

- **Answer from the graph, not the files.** Use the aliases / stored queries against the running server; never assemble an answer by reading `seed.jsonl` or `seed.md` — they are load inputs, not the live state.
- **Alias args bind by name to the query's `$params`** (`args: [slug]` fills `$slug`): `omnigraph alias assumption-contradictions asmp-oral-displaces-injectable` is `omnigraph query assumption_contradicting_signals --graph pharma --params '{"slug":"asmp-oral-displaces-injectable"}'`.
- **Mutations are not aliasable on 0.10** (`'add_x' is a mutation — use omnigraph mutate add_x`). Run them with `omnigraph mutate <name> --params '<json>'`, every non-optional property supplied; signatures live in `queries/mutations.gq`. Working example:

  ```bash
  omnigraph mutate add_signal --graph pharma --params '{"slug":"sig-orforglipron-approval","name":"FDA approves orforglipron","brief":"First oral small-molecule GLP-1 approved for obesity.","stagingTimestamp":"2026-09-14T00:00:00Z","createdAt":"2026-09-14T00:00:00Z","updatedAt":"2026-09-14T00:00:00Z"}'
  omnigraph mutate link_about_compound --graph pharma --params '{"signal":"sig-orforglipron-approval","compound":"comp-vk2735-sc"}'
  ```

  With `defaults.server` / `default_graph` from the operator config, `--graph` can be omitted.
- **Full-text `search()` is case-sensitive** (the `search_*` queries behind the `search-signals` alias): the term must match the stored casing — `Medicare` matches, `medicare` returns 0 rows with no error.

## Setup, in order (verified against 0.10)

`cluster import` comes **before** the first `apply` — without it `apply` exits 1
with `state_missing __cluster/state.json: apply requires an existing state.json`.

```bash
cd pharma-intel
omnigraph cluster import --config .                # once: bootstraps __cluster/state.json
omnigraph cluster apply  --config . --as <you>     # creates graphs/pharma.omni, applies schema + stored queries
omnigraph load --data seed.jsonl --mode overwrite graphs/pharma.omni
omnigraph-server --cluster . --unauthenticated &   # 127.0.0.1:8080 — refuses to start without this flag or auth
curl -s http://127.0.0.1:8080/healthz              # {"status":"ok",…}; the path is /healthz, /health is 404
```

### `load` addressing

`--data` is the **seed file**; the **graph** is the positional URI. Both are
required, as is `--mode` (`overwrite` | `append` | `merge`).

| Target | Command |
|---|---|
| Local storage, no server | `omnigraph load --data seed.jsonl --mode overwrite graphs/pharma.omni` |
| A running server | `omnigraph load --data seed.jsonl --mode overwrite --server http://127.0.0.1:8080 --graph pharma --yes` |

One address per command. The engine's own refusals:

- `--graph` next to a positional URI or `--store` → *"--graph selects a graph
  within a server or cluster scope; a positional URI / --store is already a
  single graph"*. `--graph` pairs with `--server`, nothing else.
- `--cluster` on `load` → *"`load` is a data command; --cluster addresses a
  cluster-scoped command and does not apply."*
- `omnigraph load seed.jsonl …` — the positional slot is the **graph**, never the data file.
- `overwrite` through a server prompts, so non-interactive callers add `--yes`.

### Find the query instead of guessing it

- **`omnigraph queries list --cluster . --graph pharma`** prints every stored
  query and mutation *with its parameter names*, offline, no server needed. Read
  the signature before writing `--params`: `query patterns_by_kind($kind:
  String)` takes `{"kind":…}`, not `{"slug":…}`.
- `omnigraph query <name>` resolves a **stored query by name** and needs a
  server — passing query text there fails with *"by-name invocation needs a
  server (the stored-query catalog is server-owned)"*. Ad-hoc GQL goes through
  `-e`, in the same dialect as the `.gq` files:

  ```bash
  omnigraph query -e 'query q($slug: String) { match { $s: Signal { slug: $slug } } return { $s.slug, $s.name } }' \
    --params '{"slug":"sig-pfizer-danuglipron-discontinued"}' --store file://$PWD/graphs/pharma.omni
  ```

  Filters bind **inside the node's braces** (`$s: Signal { slug: $slug }`) — there
  is no `where`, no `filter { … }`, no `Signal[slug=="…"]`. The parameter list is
  required even when empty (`query q()`), and `limit N` / `order { … }` sit
  inside the outer braces after `return`, never trailing the string.

- `omnigraph alias <name> [args]` carries its own server and graph — adding
  `--graph`/`--server` errors with *"remove global scope flag(s)"*. **An alias
  name is not a query name:** `queries list` prints `get_signal` and
  `search_signals`, whose aliases are `signal` and `search-signals` — hyphenated,
  and often dropping a `get_` prefix. They are the keys under `aliases:` in
  `omnigraph-config.example.yaml`; there is no `--list`.

## Schema Language (`.pg`)

- `node` defines entity types; `edge` defines typed relationships (`edge Name: Source -> Target`)
- `@key` marks external identity (always `slug` here)
- `@index`, `@unique`, `@card(min..max)`, `@range(lo..hi)`
- `?` = optional, `[Type]` = list, `enum(...)` = inline closed set
- Comments use `//` not `#`

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

## Validation

```bash
omnigraph lint --schema schema.pg --query queries/signals.gq
```

The `lint` command validates both queries and schema against each other — use it after any schema or query edit.

## When Editing

- Consult [Omnigraph schema principles](https://github.com/ModernRelay/omnigraph) for design guidance
- Use `@rename_from(...)` on property/type renames for migration support
- Keep README.md in sync with schema.pg
- Prefer semantic edge names over generic ones (`ContradictsAssumption` not `RelatedTo`)
- Required vs optional is deliberate — don't add `?` without reason
- No embeddings in v1 — the narrative surfaces are graph-structured, not vector-search-driven

## Cluster control plane (two-file model)

`cluster.yaml` is the deployment: graph `pharma`, `schema.pg`, and every
stored query, converged with `omnigraph cluster import|plan|apply --config .`
(apply creates `graphs/pharma.omni`; schema edits show migration previews
in plan; graph deletion is approval-gated). Per-operator ergonomics (aliases,
CLI defaults, identity) live in your per-user `~/.omnigraph/config.yaml`, NOT
in this cookbook — merge the aliases from `omnigraph-config.example.yaml` into
it. Aliases invoke stored queries (`omnigraph alias <name> [args]`), so they
need a running server. Serve with `omnigraph-server --cluster .` (a cluster
server never reads operator config). Data still flows through
`omnigraph load/mutate` against `graphs/pharma.omni`. Never commit
`__cluster/` or `graphs/` (gitignored — local state).
