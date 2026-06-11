# CLAUDE.md — gtm-brain

Read the repo root `CLAUDE.md` first. This file covers what's specific to this cookbook.

## Invariants (do not break these)

1. **Evidence is append-only.** Never `update` a `Signal` or `Enrichment`. New facts = new nodes.
2. **`Account.status` is a projection.** Only the `add-verdict` mutation writes it, in the same atomic write as the verdict. Never hand-edit status, and never add another mutation that sets it.
3. **Enrichment writes are atomic pairs.** `add-enrichment` writes the evidence record *and* the Account's current-best properties together. Don't split them.
4. **Attribution is on the write path.** Every `Touch` carries `variant`; every `Verdict` gets its `Weighed` edges (via `link-weighed`) and `VerdictOn` edge at creation. These cannot be backfilled.

## Slug conventions

| Type | Pattern | Example |
|---|---|---|
| Account | company domain | `northwind-robotics.com` |
| Person | `<given>-<family>-<account>` | `maya-chen-northwind-robotics.com` |
| Signal | `<source>:<source_ref>` | `linkedin-jobs:nw-revops-7781` |
| Enrichment | `<source>:<account>:<date>` | `clearbit:northwind-robotics.com:2026-06-01` |
| Verdict | `v:<account>:<date>` | `v:northwind-robotics.com:2026-06-05` |
| Touch | `t:<account>:<date>` | `t:northwind-robotics.com:2026-06-05` |

Signal slugs are derived from the vendor's stable event id — re-ingesting the same event is idempotent by construction (defuses the 504-blind-retry duplicate trap on remote graphs).

## String fields that are secretly foreign keys

`source`, `variant`, `icp_version`, `discovered_via` are slug-disciplined strings — controlled vocabulary, lowercase-hyphenated, no free text. They are deferred node reifications. Promotion triggers:

| String | Promote to node when… |
|---|---|
| `source` | sources need trust weights or per-vendor config |
| `variant` | variants need metadata (prompt ref, hypothesis) or systematic A/B management |
| `icp_version` | a second ICP exists |
| `discovered_via` | same trigger as `source` |

Other deferred slices: `Technology` + `Uses` edges (add when displacement plays start), `Identifier` nodes (multi-channel identity), an `Outcome` event node (if per-touch outcome *history* ever matters — today the terminal state on `Touch` suffices).

## Gotchas specific to this schema

- `@range` syntax is `@range(prop, min..max)` — e.g. `score: I32 @range(score, 0..100)`. The skill docs' `@range(min, max)` form does not parse.
- `WorksAt.since/until` are `Date`: integer **days-since-epoch** in JSONL (`load`/`ingest`), ISO string in `mutate --params`. The seed omits them to dodge the trap; don't reintroduce it casually.
- Embeddings are `Vector(3072)` (ingest client, `gemini-embedding-2-preview`). `rank-prospects` passes a *string* to `nearest()`, which the **query-time** client auto-embeds — its model must be configured to 3072 dims or similarity is garbage. For offline dev: `OMNIGRAPH_EMBEDDINGS_MOCK=1` / `NANOGRAPH_EMBEDDINGS_MOCK=1`.
- `load --mode merge` does not recompute embeddings — after editing `profile_summary`/`summary` in bulk, run `omnigraph embed --reembed_all`.
- A verdict may legitimately weigh zero signals (a pure `fit` verdict at prospecting time) — that's why `Weighed` links are a separate mutation, not part of `add-verdict`.

## Workflow

```bash
cd gtm-brain
omnigraph lint --schema ./schema.pg --query ./queries/queries.gq    # after any edit
omnigraph lint --schema ./schema.pg --query ./queries/mutations.gq
```

Schema changes: `omnigraph schema plan` before `apply`, always. Data changes through aliases (preferred) or `ingest` onto a branch for bulk. Keep README/CLAUDE in sync with `schema.pg`.
