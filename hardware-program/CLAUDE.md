# CLAUDE.md — hardware-program

Scoped guidance for the `hardware-program/` cookbook. Repo-wide conventions
live in `../CLAUDE.md`. For general OmniGraph operations use the **omnigraph**
skill; this file covers only what is specific to this cookbook.

## What This Is

Requirements, architecture, design values, verification and program state of a
hardware program as one typed graph. Budget closure, verification status,
staleness, change impact and review readiness are derived by stored queries on
every read, never stored. Schema, seed, queries, policies and an agent skill;
no application code. The seed is a fictional smallsat program, "Petrel"; all
names and numbers are invented.

## Key Files

- `schema.pg` — 15 node types, 27 edge types.
- `queries/program.gq` — 38 stored reads.
- `queries/mutations.gq` — 21 stored writes; updates re-check their state.
- `seed.jsonl` / `seed.md` — reference seed. Keep them in sync; `seed.md`
  lists what each read must return on the fresh seed.
- `policies/graph.policy.yaml` — reader, writer, admin and `act-agent` roles.
- `skill/SKILL.md` — guidance for an agent working on a program graph.

## Rules

- Graph id `program`. Stored queries and parameters:
  `omnigraph queries list --cluster . --graph program`.
- Do not add stored status fields for anything a query derives: no
  "verified", "over budget", "stale" or "ready for review" flags. Extend the
  query instead.
- A budget is a requirement with `quantity`, `comparator` and `limit_value`,
  allocated to a block; `budget_rollup` sums parameters of that quantity on
  the blocks strictly beneath it. Non-additive values (frequency, temperature)
  sit on the block their requirement is allocated to, so no roll-up adds them.
- Every requirement write stamps `updated_at = now()`; `stale_verification`
  depends on it. Field edits use `expected` as a compare-and-swap.
- `record_test_run` writes the run and the test case's status in one commit.
  Keep them together.
- `act-agent` writes only on unprotected branches and cannot merge or delete a
  branch. The shared checker asserts this; do not widen the agent rules.
- Keep the seed vendor-neutral and fictional. Standards are cited by public
  identifier with descriptive clause names, never invented clause numbers.
- After a schema, query or seed change, re-run the reads against a fresh seed
  and update `seed.md`, then run `../scripts/check-cookbooks.py`.
